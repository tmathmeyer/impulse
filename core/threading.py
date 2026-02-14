from __future__ import annotations

import abc
import multiprocessing
import queue
import signal
import traceback
import typing

from impulse.core import job_printer
from impulse.core import exceptions


class Messages(object):
  """Shared message constants for threading."""
  EMPTY_RESPONSE='Internal: Empty Response'
  TIMEOUT='Job Waiter Timed Out'


T=typing.TypeVar('T', covariant=True)


class GraphNode(typing.Generic[T]):
  """Base class for a node in the dependency graph."""
  def __init__(self,
               dependencies:set['GraphNode[T]'],
               has_internal_access:bool):
    self.dependencies=dependencies
    self.remaining_dependencies=set(dependencies)
    self._has_internal_access=has_internal_access
    self.__in_thread__=False

  def check_thread(self) -> None:
    """Asserts that the code is running within a worker thread."""
    assert self.__in_thread__

  def __call__(self, debug:bool=False) -> T|'UpdateGraphResponseData[T]':
    self.__in_thread__=True
    if self._has_internal_access:
      access=UpdateGraphResponseData[T]()
      self.run_job(debug, access)
      return access
    else:
      return self.run_job(debug)

  @abc.abstractmethod
  def run_job(self, debug:bool,
              internal_access:'UpdateGraphResponseData[T]'|None=None) -> T:
    """Executes the actual work of the job."""
    pass

  @abc.abstractmethod
  def __eq__(self, other:object) -> bool:
    pass

  @abc.abstractmethod
  def __hash__(self) -> int:
    pass

  @abc.abstractmethod
  def get_name(self) -> str:
    """Returns the name of the job."""
    pass

  @abc.abstractmethod
  def data(self) -> T:
    """Returns the data associated with the job."""
    pass


class UpdateGraphResponseData(typing.Generic[T]):
  """Data returned by a job to update the dependency graph."""
  def __init__(self) -> None:
    self.added_graph:set[GraphNode[T]]=set()
    self.rerun_more_deps:list[GraphNode[T]]=[]

  def InjectMoreGraph(self, graph:set[GraphNode[T]]) -> None:
    """Adds more nodes to the build graph."""
    self.added_graph|= graph

  def RerunWithDependency(self, nodes:list[GraphNode[T]]) -> None:
    """
    Specifies that the current job should be rerun after these nodes
    completed.
    """
    self.added_graph|= set(nodes)
    self.rerun_more_deps=nodes


class NullNode(GraphNode[None]):
  """A placeholder node representing no action or an empty state."""
  def __init__(self) -> None:
    super().__init__(set(), False)

  def run_job(self, *args:object, **kwargs:object) -> None:
    raise NotImplementedError()

  def __eq__(self, other:object) -> bool:
    return isinstance(other, NullNode)

  def __hash__(self) -> int:
    raise NotImplementedError()

  def get_name(self) -> str:
    raise NotImplementedError()

  def data(self) -> None:
    raise NotImplementedError()


class JobResponse(typing.Generic[T]):
  """Response sent from a worker thread to the main pool."""
  class LEVEL(object):
    FATAL='__L_FATAL__'
    WARNING='__L_WARNING__'
    YELLOW='__L_YELLOW__'
    GREEN='__L_GREEN__'

  def __init__(self, level:str,
                     job_id:int,
                     job:GraphNode[T]|None,
                     message:str='',
                     result:UpdateGraphResponseData[T]|T|\
                            typing.Callable|None=None
                     ):
    self._level=level
    self._msg=message
    self._result=result
    self._job=job
    self._id=job_id

  def level(self) -> str:
    """Returns the severity level of the response."""
    return self._level

  def message(self) -> str:
    """Returns the message associated with the response."""
    return self._msg

  def result(self) -> UpdateGraphResponseData[T]|T|\
                       typing.Callable|None:
    """Returns the result produced by the job."""
    return self._result

  def job(self) -> GraphNode[T]:
    """Returns the job that generated this response."""
    assert self._job is not None
    return self._job

  def id(self) -> int:
    """Returns the ID of the worker thread."""
    return self._id


def handle_pdb(sig:int, frame:object) -> None:
  """Signal handler to enter PDB debugger."""
  import pdb
  pdb.Pdb().set_trace(frame)


class ThreadWatchdog(multiprocessing.Process, typing.Generic[T]):
  """Worker process that monitors and executes jobs from a queue."""
  POISON=NullNode()
  __slots__=['_id', '_debug', '_job_input_queue', '_job_response_queue']

  def __init__(self,
               watchdog_id:int,
               debug_mode:bool,
               job_input_queue:multiprocessing.JoinableQueue,
               job_response_queue:multiprocessing.Queue):
    multiprocessing.Process.__init__(self)
    self._id=watchdog_id
    self._debug=debug_mode
    self._job_input_queue=job_input_queue
    self._job_response_queue=job_response_queue
    self.name=f'Watchdog#{self._id}'

    if self._debug:
      signal.signal(signal.SIGUSR1, handle_pdb)

  def _Fail(self, exc:Exception) -> None:
    """Handles job failure by sending a fatal response."""
    resp=JobResponse(JobResponse.LEVEL.FATAL, self._id,
                       typing.cast(GraphNode[T], NullNode()), message=str(exc))
    self._job_response_queue.put(resp)
    if not self._debug:
      return
    traceback.print_exc()

  def run(self) -> None:
    """Main execution loop for the worker thread."""
    while True:
      job=ThreadWatchdog.POISON
      try:
        job=self._job_input_queue.get(timeout=5)
      except Exception:
        resp=JobResponse(JobResponse.LEVEL.WARNING, self._id, None,
                           message=Messages.TIMEOUT)
        self._job_response_queue.put(resp)
        continue

      if job == ThreadWatchdog.POISON:
        self._job_input_queue.task_done()
        self._job_input_queue.join()
        return

      resp=JobResponse(JobResponse.LEVEL.YELLOW, self._id,
                         typing.cast(GraphNode[T], job), message=str(job))
      self._job_response_queue.put(resp)

      try:
        job_result=job()
      except Exception as e:
        self._job_input_queue.task_done()
        self._Fail(e)
        continue

      resp=JobResponse(JobResponse.LEVEL.GREEN, self._id,
                         typing.cast(GraphNode[T], job), result=job_result)
      self._job_response_queue.put(resp)
      self._job_input_queue.task_done()


class ThreadPool(multiprocessing.Process, typing.Generic[T]):
  """Base class for managing a pool of worker processes."""
  def __init__(self, poolcount:int, debug:bool=False):
    super().__init__()
    self._debug=debug
    self._job_response_queue:queue.Queue[JobResponse[T]]=(
      multiprocessing.Queue())
    self._job_input_queue:queue.Queue[GraphNode[T]]=(
      multiprocessing.JoinableQueue())
    self._pool_count:int=poolcount
    self._printer=job_printer.JobPrinter(0, poolcount)
    self._input:object=None
    self._error_message:str|None=None
    self._watchdogs:list[ThreadWatchdog[T]]=[]

  @abc.abstractmethod
  def OnStart(self) -> None:
    """Hook called before the main execution loop starts."""
    pass

  @abc.abstractmethod
  def IsFinished(self) -> bool:
    """Returns True if all jobs in the pool are complete."""
    pass

  @abc.abstractmethod
  def _on_reply(self, response:JobResponse[T]) -> bool:
    """Handles a response from a worker thread."""
    pass

  @abc.abstractmethod
  def _message_pump(self) -> bool:
    """Pumps messages from the input source."""
    pass

  def Start(self, data:object, threaded:bool=True) -> None:
    """Initializes and starts the thread pool."""
    self._input=data
    self._create_watchdogs()
    if threaded:
      self.start()
    else:
      self.run()

  def run(self) -> None:
    """Main execution loop for the thread pool manager."""
    self.OnStart()
    self._run_loop()

  def _create_watchdogs(self) -> None:
    """Spawns worker processes."""
    for i in range(self._pool_count):
      watchdog=ThreadWatchdog[T](
        watchdog_id=i,
        debug_mode=self._debug,
        job_input_queue=self._job_input_queue,
        job_response_queue=self._job_response_queue)
      watchdog.start()
      self._watchdogs.append(watchdog)

  def _kill_watchdogs(self) -> None:
    """Shuts down all worker processes."""
    for _ in range(self._pool_count):
      poison=typing.cast(GraphNode[T], ThreadWatchdog.POISON)
      self._job_input_queue.put(poison)
    self._job_input_queue.join()
    for dog in self._watchdogs:
      dog.kill()

  def _run_loop(self) -> None:
    """Internal loop that handles message passing."""
    while True:
      if self.IsFinished():
        self._kill_watchdogs()
        self._printer.finished()
        return

      if not self._message_pump():
        continue

      response=self._job_response_queue.get()
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


class DependentPool(ThreadPool[T]):
  """Thread pool that handles jobs with inter-dependencies."""
  def __init__(self, poolcount:int, debug:bool=False):
    super().__init__(poolcount, debug)
    self._pending_add:set[GraphNode[T]]=set()
    self._in_flight:set[GraphNode[T]]=set()
    self._completed:set[GraphNode[T]]=set()

  def OnStart(self) -> None:
    self._printer.add_job_count(len(self._input)) # type:ignore
    self._cycle_graph()
    self._add_nodes()

  def _add_nodes(self) -> None:
    """Pushes available nodes from pending to the worker queue."""
    for node in self._pending_add:
      self._job_input_queue.put(node)
    self._in_flight|= self._pending_add
    self._pending_add=set()

  def _cycle_graph(self, remove_node:GraphNode[T]|None=None) -> None:
    """Updates the graph by removing completed dependencies."""
    newgraph:set[GraphNode[T]]=set()
    for node in self._input: # type:ignore
      if remove_node:
        node.remaining_dependencies.discard(remove_node)
      if node.remaining_dependencies:
        newgraph.add(node)
      else:
        self._pending_add.add(node)
    self._input=newgraph

  def _force_cycle_graph(self) -> bool:
    """Forces dependency resolution for stalled jobs."""
    for job in self._input: # type:ignore
      if not len(job.remaining_dependencies):
        return True
      for depends in job.remaining_dependencies:
        if depends in self._completed:
          job.remaining_dependencies.discard(depends)
          return True
    return False

  def _handle_good_status(self, status:JobResponse[T]) -> None:
    """Handles a successful job completion."""
    self._in_flight.remove(status.job())
    self._completed.add(status.job())
    response=status.result()
    discard_node=True
    if response:
      if isinstance(response, UpdateGraphResponseData):
        discard_node=not self._update_graph(status.job(), response)
    if discard_node:
      self._cycle_graph(status.job())
    else:
      self._cycle_graph()

  def _update_graph(self,
                    node_from:GraphNode[T],
                    results:UpdateGraphResponseData[T]) -> bool:
    """Injects new nodes into the graph based on job results."""
    results.added_graph -= self._completed
    self._input|= results.added_graph # type:ignore
    self._printer.add_job_count(len(results.added_graph))

    if results.rerun_more_deps:
      needs_rerun=False
      for new_addition in results.rerun_more_deps:
        if new_addition not in self._completed:
          node_from.remaining_dependencies.add(new_addition)
          node_from.dependencies.add(new_addition)
          needs_rerun=True
      if needs_rerun:
        self._completed.remove(node_from)
        node_data=node_from.data()
        if hasattr(node_data, 'execution_count'):
          node_data.execution_count += 1 # type:ignore
        self._input.add(node_from) # type:ignore
      return needs_rerun
    return False

  def IsFinished(self) -> bool:
    return ((not self._input) and
            (not self._pending_add) and
            (not self._in_flight))

  def _message_pump(self) -> bool:
    self._add_nodes()
    return True

  def _on_reply(self, response:JobResponse[T]) -> bool:
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


class StreamingPool(ThreadPool[T]):
  """Thread pool that processes jobs from an iterator."""
  def __init__(self, poolcount:int, debug:bool=False):
    super().__init__(poolcount, debug)
    self._finished=False
    self._replies:list[T]=[]
    self._sent_jobs=0

  def OnStart(self) -> None:
    for _ in range(self._pool_count):
      try:
        self._sent_jobs += 1
        self._job_input_queue.put(next(self._input)) # type:ignore
      except StopIteration:
        self._sent_jobs -= 1
        self._finished=True

  def IsFinished(self) -> bool:
    return self._finished and (len(self._replies) == self._sent_jobs)

  def _on_reply(self, response:JobResponse[T]) -> bool:
    if response.level() == JobResponse.LEVEL.WARNING:
      self._printer.write_task_msg(response.id(), response.message())
      return True
    if response.level() == JobResponse.LEVEL.YELLOW:
      self._printer.write_task_msg(response.id(), response.message())
      return True
    if response.level() == JobResponse.LEVEL.GREEN:
      self._printer.remove_task_msg(response.id())
      self._replies.append(typing.cast(T, response.result()))
      return True
    return False

  def _message_pump(self) -> bool:
    try:
      self._sent_jobs += 1
      self._job_input_queue.put(next(self._input)) # type:ignore
      return True
    except StopIteration:
      self._finished=True
      self._sent_jobs -= 1
      return True

  def Replies(self) -> list[T]:
    """Returns the collected results from all jobs."""
    return self._replies
