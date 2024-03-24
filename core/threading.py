import abc
import multiprocessing
import queue
import signal
import traceback
from typing import Set, Dict, TypeVar, Generic

from impulse.core import job_printer


class Messages(object):
  EMPTY_RESPONSE = 'Internal: Empty Response'
  TIMEOUT = 'Job Waiter Timed Out'


class UpdateGraphResponseData(object):
  def __init__(self):
    self.added_graph = set()
    self.rerun_more_deps = None

  def InjectMoreGraph(self, graph):
    self.added_graph |= graph

  def RerunWithDependency(self, nodes):
    self.added_graph |= (nodes)
    self.rerun_more_deps = nodes

T = TypeVar('T')
class GraphNode(Generic[T]):
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
      access = UpdateGraphResponseData()
      self.run_job(debug, access)
      return access
    else:
      return self.run_job(debug)

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

  @abc.abstractmethod
  def data(self) -> T:
    pass


class NullNode(GraphNode):
  def __init__(self):
    super().__init__(set(), False)
  def run_job(*args, **kwargs):
    raise NotImplementedError()
  def __eq__(self, other):
    return type(other) == NullNode
  def __hash__(*args, **kwargs):
    raise NotImplementedError()
  def get_name(*args, **kwargs):
    raise NotImplementedError()
  def data(self):
    raise NotImplementedError()


class JobResponse(object):
  class LEVEL(object):
    FATAL = '__L_FATAL__'
    WARNING = '__L_WARNING__'
    YELLOW = '__L_YELLOW__'
    GREEN = '__L_GREEN__'

  def __init__(self, level:str,
                     job_id:int,
                     job:GraphNode,
                     message:str='',
                     result=None):
    self._level = level
    self._msg = message
    self._result = result
    self._job = job
    self._id = job_id

  def level(self) -> str:
    return self._level

  def message(self) -> str:
    return self._msg

  def result(self):
    return self._result

  def job(self) -> GraphNode:
    return self._job

  def id(self) -> int:
    return self._id


def handle_pdb(sig, frame):
  import pdb
  pdb.Pdb().set_trace(frame)


class ThreadWatchdog(multiprocessing.Process):
  POISON = NullNode()
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
    self.name = f'Watchdog#{self._id}'

    if self._debug:
      signal.signal(signal.SIGUSR1, handle_pdb)

  def _Fail(self, exc:Exception):
    self._job_response_queue.put(JobResponse(
        JobResponse.LEVEL.FATAL, self._id, NullNode(),
        message=str(exc)))
    if not self._debug:
      return
    traceback.print_exc()

  def run(self):
    while True:
      job = ThreadWatchdog.POISON
      try:
        job = self._job_input_queue.get(timeout=5)
      except:
        self._job_response_queue.put(JobResponse(
          JobResponse.LEVEL.WARNING, self._id, None,
          message=Messages.TIMEOUT))
        continue

      if job == ThreadWatchdog.POISON:
        self._job_input_queue.task_done()
        self._job_input_queue.join()
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
  def __init__(self, poolcount:int, debug:bool = False):
    super().__init__()
    self._debug = debug
    self._job_response_queue:queue.Queue[JobResponse] = multiprocessing.Queue()
    self._job_input_queue:queue.Queue[GraphNode] = multiprocessing.JoinableQueue()
    self._pool_count:int = poolcount
    self._printer = job_printer.JobPrinter(0, poolcount)
    self._input = None
    self._error_message = None
    self._watchdogs = []

  @abc.abstractmethod
  def OnStart(self):
    pass

  @abc.abstractmethod
  def IsFinished(self):
    pass

  @abc.abstractmethod
  def _on_reply(self, response):
    pass

  @abc.abstractmethod
  def _message_pump(self):
    pass

  def Start(self, data, threaded=True):
    self._input = data
    self._create_watchdogs()
    if threaded:
      self.start()
    else:
      self.run()

  def run(self):
    self.OnStart()
    self._run_loop()

  def _create_watchdogs(self):
    for i in range(self._pool_count):
      watchdog = ThreadWatchdog(
        watchdog_id = i,
        debug_mode = self._debug,
        job_input_queue = self._job_input_queue,
        job_response_queue = self._job_response_queue)
      watchdog.start()
      self._watchdogs.append(watchdog)

  def _kill_watchdogs(self):
    for _ in range(self._pool_count):
      self._job_input_queue.put(ThreadWatchdog.POISON)
    self._job_input_queue.join()
    for dog in self._watchdogs:
      dog.kill()

  def _run_loop(self):
    while True:
      if self.IsFinished():
        self._kill_watchdogs()
        self._printer.finished()
        return

      if not self._message_pump():
        continue

      response = self._job_response_queue.get()
      if not response:
        self._kill_watchdogs()
        self._printer.finished(err=Messages.EMPTY_RESPONSE)
        return

      if response.level() == JobResponse.LEVEL.FATAL:
        self._kill_watchdogs()
        self._printer.finished(err=response.message())
        return

      if not self._on_reply(response):
        self._kill_watchdogs()
        self._printer.finished(err=self._error_message)
        return


class DependentPool(ThreadPool):
  def __init__(self, poolcount:int, debug:bool=False):
    super().__init__(poolcount, debug)
    self._pending_add = set()
    self._in_flight = set()
    self._completed = set()

  def OnStart(self):
    self._printer.add_job_count(len(self._input))
    self._cycle_graph()
    self._add_nodes()

  def _add_nodes(self):
    for node in self._pending_add:
      self._job_input_queue.put(node)
    self._in_flight |= self._pending_add
    self._pending_add = set()

  def _cycle_graph(self, remove_node:GraphNode=None):
    newgraph:Set[GraphNode] = set()
    for node in self._input:
      if remove_node:
        node.remaining_dependencies.discard(remove_node)
      if node.remaining_dependencies:
        newgraph.add(node)
      else:
        self._pending_add.add(node)
    self._input = newgraph

  def _force_cycle_graph(self):
    for job in self._input:
      if not len(job.remaining_dependencies):
        return True
      for depends in job.remaining_dependencies:
        if depends in self._completed:
          job.remaining_dependencies.discard(depends)
          return True
    return False

  def _handle_good_status(self, status:JobResponse):
    self._in_flight.remove(status.job())
    self._completed.add(status.job())
    response = status.result()
    discard_node = True
    if response:
      if isinstance(response, UpdateGraphResponseData):
        discard_node = not self._update_graph(status.job(), response)
    if discard_node:
      self._cycle_graph(status.job())
    else:
      self._cycle_graph()

  def _update_graph(self,
                    node_from:GraphNode,
                    results:UpdateGraphResponseData) -> bool:
    results.added_graph -= self._completed
    self._input |= results.added_graph
    self._printer.add_job_count(len(results.added_graph))

    if results.rerun_more_deps:
      needs_rerun = False
      for new_addition in results.rerun_more_deps:
        if new_addition not in self._completed:
          node_from.remaining_dependencies.add(new_addition)
          node_from.dependencies.add(new_addition)
          needs_rerun = True
      if needs_rerun:
        self._completed.remove(node_from)
        node_from.data().execution_count += 1
        self._input.add(node_from)
      return needs_rerun
    return False

  def IsFinished(self):
    return ((not self._input) and
            (not self._pending_add) and
            (not self._in_flight))

  def _message_pump(self):
    self._add_nodes()
    return True

  def _on_reply(self, response):
    if response.level() == JobResponse.LEVEL.WARNING:
      if response.message() == Messages.TIMEOUT:
        if self._force_cycle_graph():
          self._cycle_graph()
          self._add_nodes()
          return True
      self._printer.write_task_msg(response.id(), response.message())
      return True

    if response.level() == JobResponse.LEVEL.GREEN:
      self._printer.remove_task_msg(response.id())
      self._handle_good_status(response)

    if response.level() == JobResponse.LEVEL.YELLOW:
      self._printer.write_task_msg(response.id(), response.message())

    return True


class StreamingPool(ThreadPool):
  def __init__(self, poolcount:int, debug:bool=False):
    super().__init__(poolcount, debug)
    self._finished = False
    self._replies = []
    self._sent_jobs = 0

  def OnStart(self):
    for _ in range(self._pool_count):
      try:
        self._sent_jobs += 1
        self._job_input_queue.put(next(self._input))
      except StopIteration:
        self._sent_jobs -= 1
        self._finished = True

  def IsFinished(self):
    return self._finished and (len(self._replies) == self._sent_jobs)

  def _on_reply(self, response):
    if response.level() == JobResponse.LEVEL.WARNING:
      self._printer.write_task_msg(response.id(), response.message())
      return True
    if response.level() == JobResponse.LEVEL.YELLOW:
      self._printer.write_task_msg(response.id(), response.message())
      return True
    if response.level() == JobResponse.LEVEL.GREEN:
      self._printer.remove_task_msg(response.id())
      self._replies.append(response.result())
      return True
    return False

  def _message_pump(self):
    try:
      self._sent_jobs += 1
      self._job_input_queue.put(next(self._input))
      return True
    except StopIteration:
      self._finished = True
      self._sent_jobs -= 1
      return True

  def Replies(self):
    return self._replies



