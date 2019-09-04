import abc
import multiprocessing
import traceback
from typing import Set, Dict

from impulse import status_out

class Messages(object):
  EMPTY_RESPONSE = 'Internal: Empty Response'
  TIMEOUT = 'Job Waiter Timed Out'


class InternalAccess(object):
  def __init__(self):
    self.added_graph:Set['GraphNode'] = set()
    self.who_needs_me_needs_also = None

  def InjectMoreGraph(self, graph):
    self.added_graph |= graph

  def MoveDependencyTo(self, rule, node=None):
    if node:
      self.added_graph.add(node)
    self.who_needs_me_needs_also = rule


class GraphNode(object):
  def __init__(self,
               dependencies:Set['GraphNode'],
               has_internal_access:bool):
    # A set(DependentJob)
    self.dependencies = dependencies
    self.remaining_dependencies = set(dependencies)
    self._has_internal_access = has_internal_access
    self.__in_thread__ = False

  def check_thread(self):
    assert self.__in_thread__

  def __call__(self, debug=False):
    self.__in_thread__ = True
    if self._has_internal_access:
      access = InternalAccess()
      self.run_job(debug, access)
      return access
    else:
      self.run_job(debug)
      return None

  @abc.abstractmethod
  def run_job(self, debug, internal_access=None):
    pass

  @abc.abstractmethod
  def __eq__(self, other):
    pass

  @abc.abstractmethod
  def __hash__(self):
    pass

  @abc.abstractmethod
  def get_name(self):
    pass


class JobResponse(object):
  class LEVEL(object):
    FATAL = '__L_FATAL__'
    WARNING = '__L_WARNING__'
    YELLOW = '__L_YELLOW__'
    GREEN = '__L_GREEN__'

  def __init__(self, level:LEVEL,
                     job_id:int,
                     job:GraphNode,
                     message:str=None,
                     result=None):
    self._level = level
    self._msg = message
    self._result = result
    self._job = job
    self._id = job_id

  def level(self) -> 'JobResponse.LEVEL':
    return self._level

  def message(self) -> str:
    return self._msg

  def result(self):
    return self._result

  def job(self) -> GraphNode:
    return self._job

  def id(self) -> int:
    return self._id


class UpdateGraphResponseData(object):
  def __init__(self):
    self.added_graph = set()
    self.who_needs_me_needs_also = None

  def InjectMoreGraph(self, graph):
    self.added_graph |= graph

  def MoveDependencyTo(self, rule, node=None):
    if node:
      self.added_graph.add(node)
    self.who_needs_me_needs_also = rule


class ThreadWatchdog(multiprocessing.Process):
  POISON = '__TW_POISON__'
  __slots__ = ['_id', '_debug', '_job_input_queue', '_job_response_queue']

  def __init__(self,
               watchdog_id:int,
               debug_mode:bool,
               job_input_queue:multiprocessing.JoinableQueue,
               job_response_queue:multiprocessing.Queue):
    multiprocessing.Process.__init__(self)
    self._id = watchdog_id
    self._debug = debug_mode
    self._job_input_queue = job_input_queue
    self._job_response_queue = job_response_queue

  def _Fail(self, exc:Exception):
    self._job_response_queue.put(JobResponse(
        JobResponse.LEVEL.FATAL, self._id, None,
        message=str(exc)))
    if not self._debug:
      return
    traceback.print_exc()

  def run(self):
    while True:
      job = ThreadWatchdog.POISON
      try:
        job = self._job_input_queue.get(timeout=30)
      except:
        self._job_response_queue.put(JobResponse(
          JobResponse.LEVEL.WARNING, self._id, None,
          message=Messages.TIMEOUT))
        continue

      if job == ThreadWatchdog.POISON:
        self._job_input_queue.task_done()
        return

      self._job_response_queue.put(JobResponse(
        JobResponse.LEVEL.YELLOW, self._id, job, message=str(job)))

      try:
        job_result = job()
      except Exception as e:
        self._job_input_queue.task_done()
        self._Fail(e)
        continue

      self._job_response_queue.put(JobResponse(
        JobResponse.LEVEL.GREEN, self._id, job,
        result=job_result))
      self._job_input_queue.task_done()


class ThreadPool(multiprocessing.Process):
  # Availible field slots.
  __slots__ = ['_debug', '_job_response_queue', '_job_input_queue',
               '_pool_count', '_printer', '_input_graph', '_graph',
               '_pending_add', '_in_flight', '_completed']

  def __init__(self,
               poolcount:int,  # the number of child threads to run
               debug:bool = False):  # run in debug mode
    multiprocessing.Process.__init__(self)

    self._debug:bool = debug
    self._job_response_queue = multiprocessing.Queue()
    self._job_input_queue = multiprocessing.JoinableQueue()
    self._pool_count:int = poolcount
    self._printer = status_out.JobPrinter(0, poolcount)

    self._graph:Set[GraphNode] = set()
    self._pending_add:Set[GraphNode] = set()
    self._in_flight:Set[GraphNode] = set()
    self._completed:Set[GraphNode] = set()

  def run(self):
    self._create_watchdogs()
    self._do_graph_loop()

  def Start(self, graph):
    self._printer.add_job_count(len(graph))
    self._graph = graph
    self._update_graph_status()
    self.start()

  def _create_watchdogs(self):
    for i in range(self._pool_count):
      watchdog = ThreadWatchdog(
        watchdog_id = i,
        debug_mode = self._debug,
        job_input_queue = self._job_input_queue,
        job_response_queue = self._job_response_queue)
      watchdog.start()

  def _add_nodes(self):
    for node in self._pending_add:
      self._job_input_queue.put(node)
    self._in_flight |= self._pending_add
    self._pending_add = set()

  def _is_finished(self):
    return ((not self._graph) and
            (not self._pending_add) and
            (not self._in_flight))

  def _finish_err(self, msg:str):
    for _ in range(self._pool_count):
      self._job_input_queue.put(ThreadWatchdog.POISON)
    self._printer.finished(err=msg)
    self._job_input_queue.join()
    return None

  def _handle_good_status(self, status:JobResponse):
    self._in_flight.remove(status.job())
    self._completed.add(status.job())
    response = status.result()
    if response:
      if isinstance(response, UpdateGraphResponseData):
        self._update_graph(status.job(), response)

    newgraph:Set[GraphNode] = set()
    for node in self._graph:
      node.remaining_dependencies.discard(status.job())
      if not node.remaining_dependencies:
        self._pending_add.add(node)
      else:
        newgraph.add(node)
    self._graph = newgraph

  def _update_graph_status(self):
    newgraph:Set[GraphNode] = set()
    for node in self._graph:
      if not node.remaining_dependencies:
        self._pending_add.add(node)
      else:
        newgraph.add(node)
    self._graph = newgraph

  def _update_graph(self,
                    node_from:GraphNode,
                    results:UpdateGraphResponseData):
    results.added_graph -= self._completed
    self._graph |= results.added_graph
    self._printer.add_job_count(len(results.added_graph))

    if results.who_needs_me_needs_also:
      for maybe_parent in self.graph:
        if node_from in maybe_parent.remaining_dependencies:
          for newly_added in results.added_graph:
            if newly_added.get_name() == str(results.who_needs_me_needs_also):
              maybe_parent.remaining_dependencies.add(newly_added)

  def _do_graph_loop(self):
    while True:
      if self._is_finished():
        for _ in range(self._pool_count):
          self._job_input_queue.put(ThreadWatchdog.POISON)
        self._job_input_queue.join()
        self._printer.finished()
        return

      self._add_nodes()
      job_response:JobResponse = self._job_response_queue.get()

      if not job_response:
        return self._finish_err(Messages.EMPTY_RESPONSE)

      if job_response.level() == JobResponse.LEVEL.FATAL:
        return self._finish_err(job_response.message())

      if job_response.level() == JobResponse.LEVEL.WARNING:
        self._printer.write_task_msg(job_response.id(), job_response.message())
        continue

      if job_response.level() == JobResponse.LEVEL.GREEN:
        self._printer.remove_task_msg(job_response.id())
        self._handle_good_status(job_response)

      if job_response.level() == JobResponse.LEVEL.YELLOW:
        self._printer.write_task_msg(job_response.id(), job_response.message())
        continue
