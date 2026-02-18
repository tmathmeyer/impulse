
import multiprocessing as mp
import queue
import signal

from impulse.core import job_printer
from impulse.pkg import packaging
from impulse.types import graph_node


def handle_pdb(sig, frame):
  import pdb
  pdb.Pdb().set_trace(frame)


class UpdateGraphResponseData(object):
  def __init__(self):
    self.added_graph = set()
    self.rerun_more_deps = []

  def InjectMoreGraph(self, graph):
    self.added_graph |= graph

  def RerunWithDependency(self, nodes):
    self.added_graph |= (nodes)
    self.rerun_more_deps = nodes


JobSpec = graph_node.GraphNode[packaging.ExportablePackage]


class JobStop(graph_node.GraphNode[None]):
  def __init__(self):
    super().__init__(set(), False)
  def run_job(*args, **kwargs):
    raise NotImplementedError()
  def __eq__(self, other):
    return type(other) == JobStop
  def __hash__(*args, **kwargs):
    raise NotImplementedError()
  def get_name(*args, **kwargs):
    raise NotImplementedError()
  def data(self) -> None:
    raise NotImplementedError()


class TypePipe[T]:
  """Typed Wrapper on multiprcessing.Connection - does not support bytes."""
  __slots__ = ('_pipe',)

  @staticmethod
  def Pipe() -> (TypePipe[T], TypePipe[T]):
    a, b = mp.Pipe()
    return (TypePipe(a), TypePipe(b))

  def __init__(self, pipe:mp.Connection):
    self._pipe = pipe

  def send(self, object:T) -> None:
    return self._pipe.send(object)

  def recv(self) -> T:
    return self._pipe.recv()

  def close(self) -> None:
    self._pipe.close()

  def poll(self, timeout:int|None = -1) -> bool:
    if timeout != -1:
      return self._pipe.poll(timeout)
    return self._pipe.poll()


class TypeQueue[T]:
  def __init__(self, joinable:bool = False):
    self._joinable = joinable
    self._queue = mp.JoinableQueue() if joinable else mp.Queue()

  def get(self, block:bool=True, timeout:int|None = -1) -> T:
    if timeout != -1:
      return self._queue.get(block, timeout)
    return self._queue.get(block)

  def put(self, object:T) -> None:
    return self._queue.put(object)

  def task_done(self) -> None:
    if self._joinable:
      return self._queue.task_done()

  def join(self) -> None:
    if self._joinable:
      return self._queue.join()


class JobStatus():
  WORKING_SIGNAL = 1
  WAITING_SIGNAL = 2
  SUCCESS_SIGNAL = 3
  FAILURE_SIGNAL = 4

  def __init__(self, signal:int, task_runner_id:int):
    self._signal = signal
    self._task_runner_id = task_runner_id

  def IsWorking(self):
    return self._signal == JobStatus.WORKING_SIGNAL

  def IsWaiting(self):
    return self._signal == JobStatus.WAITING_SIGNAL

  def IsSuccess(self):
    return self._signal == JobStatus.SUCCESS_SIGNAL

  def IsFailed(self):
    return self._signal == JobStatus.FAILURE_SIGNAL

  def ThreadID(self) -> int:
    return self._task_runner_id

  def GetMessage(self) -> str:
    if self.IsWorking():
      return str(self._job)
    if self.IsWaiting():
      return f'Waiting... {self._timeout}s'
    if self.IsSuccess():
      raise ValueError('!!!')
    if self.IsFailed():
      return str(self._exception)

  def GetJob(self) -> JobSpec:
    if self.IsWorking() or self.IsSuccess():
      return self._job
    raise ValueError('!!!')

  def GetResult(self) -> packaging.ExportablePackage:
    if self.IsSuccess():
      return self._result
    raise ValueError('!!!')

  def GetException(self) -> Exception:
    if self.IsFailed():
      return self._exception
    raise ValueError('!!!')

  @staticmethod
  def Waiting(task_runner_id:int, timeout:int) -> JobStatus:
    waiting = JobStatus(JobStatus.WAITING_SIGNAL, task_runner_id)
    waiting._timeout = timeout
    return waiting

  @staticmethod
  def Working(task_runner_id:int, job:JobSpec) -> JobStatus:
    working = JobStatus(JobStatus.WORKING_SIGNAL, task_runner_id)
    working._job = job
    return working

  @staticmethod
  def Failed(task_runner_id:int, exception:Exception) -> JobStatus:
    failed = JobStatus(JobStatus.FAILURE_SIGNAL, task_runner_id)
    failed._exception = exception
    return failed

  @staticmethod
  def Success(task_runner_id: int, job:JobSpec, result:packaging.ExportablePackage) -> JobStatus:
    success = JobStatus(JobStatus.SUCCESS_SIGNAL, task_runner_id)
    success._job = job
    success._result = result
    return success


class PoolStatus():
  SUCCESS = 0
  FAILURE = 1
  def __init__(self, signal:int, failed:JobStatus|None):
    self._signal = signal
    self._failed = failed

  def GetErrorReport(self) -> JobStatus|None:
    return self._failed

  @staticmethod
  def Success() -> PoolStatus:
    return PoolStatus(PoolStatus.SUCCESS, None)

  @staticmethod
  def Error(failed:JobStatus|None) -> PoolStatus:
    return PoolStatus(PoolStatus.FAILURE, failed)


class TaskRunner(mp.Process):
  # This is delcared once so that it has the same `id`
  STOP_JOB = JobStop()

  def __init__(self, task_runner_id:int, debug:bool, inqueue:TypeQueue[JobSpec|JobStop], outqueue:TypeQueue[JobStatus]):
    super().__init__()
    self._task_runner_id = task_runner_id
    self._debug = debug
    self._job_input_queue = inqueue
    self._job_output_queue = outqueue
    if self._debug:
      signal.signal(signal.SIGUSR1, handle_pdb)

  def run(self):
    job_wait_timeout = 1
    while True:
      job = TaskRunner.STOP_JOB
      try:
        job = self._job_input_queue.get(timeout=job_wait_timeout)
      except queue.Empty:
        job_wait_timeout *= 2
        self._job_output_queue.put(JobStatus.Waiting(
          self._task_runner_id, job_wait_timeout))
        continue

      if job == TaskRunner.STOP_JOB:
        self._job_input_queue.task_done()
        self._job_input_queue.join()
        return

      job_wait_timeout = 1
      self._job_output_queue.put(JobStatus.Working(
        self._task_runner_id, job))

      try:
        job_result = job()
      except Exception as e:
        self._job_input_queue.task_done()
        self._job_output_queue.put(JobStatus.Failed(
          self._task_runner_id, e))
        continue

      self._job_output_queue.put(JobStatus.Success(
        self._task_runner_id, job, job_result))
      self._job_input_queue.task_done()


class PoolFiltration(mp.Process):
  """The filter system keeps the pool free of childrens... detritus."""
  def __init__(self, reporter:TypePipe[PoolStatus], threads:int, debug:bool):
    super().__init__()
    self._job_input_queue = TypeQueue[JobSpec|JobStop](joinable=True)
    self._job_output_queue = TypeQueue[JobStatus]()
    self._reporter = reporter
    self._printer = job_printer.JobPrinter(0, threads)
    self._task_runners = self._MakeTasks(threads, debug)

  def SetTargets(self, targets:set[parsed_target.StagedBuildTarget]) -> None:
    self._input = targets
    self._printer.add_job_count(len(self._input))

  def _OnProcStart(self) -> None:
    self._pending_add:Set[JobSpec] = set()
    self._in_flight:Set[JobSpec] = set()
    self._completed:Set[JobSpec] = set()

    self._CycleGraph()
    self._AddNodes()

  def _CycleGraph(self, remove_node:JobSpec|None = None):
    new_inputs:set[JobSpec] = set()
    for node in self._input:
      if remove_node:
        node.remaining_dependencies.discard(remove_node)
      if node.remaining_dependencies:
        new_inputs.add(node)
      else:
        self._pending_add.add(node)
    self._input = new_inputs

  def _AddNodes(self):
    for node in self._pending_add:
      self._job_input_queue.put(node)
    self._in_flight |= self._pending_add
    self._pending_add = set()

  def _IsFinished(self) -> bool:
    return not (self._input or self._pending_add or self._in_flight)

  def _SendStopJobs(self) -> None:
    for _ in self._task_runners:
      self._job_input_queue.put(TaskRunner.STOP_JOB)
    self._job_input_queue.join()
    for task_runner in self._task_runners:
      task_runner.kill()

  def _ShouldForceCycleGraphOnWait(self) -> bool:
    for job in self._input:
      if not len(job.remaining_dependencies):
        return True
      for depends in job.remaining_dependencies:
        if depends in self._completed:
          job.remaining_dependencies.discard(depends)
          return True
    return False

  def _UpdateGraph(self, job:JobSpec, result:UpdateGraphResponseData) -> bool:
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

  def _MakeTasks(self, threads:int, debug:bool) -> [TaskRunner]:
    task_runners = []
    for runner_id in range(threads):
      task_runner = TaskRunner(
        task_runner_id = runner_id,
        debug = debug,
        inqueue = self._job_input_queue,
        outqueue = self._job_output_queue)
      task_runner.start()
      task_runners.append(task_runner)
    return task_runners

  def run(self) -> None:
    self._OnProcStart()
    while True:
      if self._IsFinished():
        self._SendStopJobs()
        self._printer.finished()
        self._reporter.send(PoolStatus.Success())
        return

      self._AddNodes()
      status:JobStatus = self._job_output_queue.get()

      if not status:
        self._SendStopJobs()
        self._printer.finished(err = 'Unexpected empty queue message')
        self._reporter.send(PoolStatus.Error(None))
        return

      if status.IsFailed():
        self._SendStopJobs()
        self._printer.finished()
        self._reporter.send(PoolStatus.Error(status))
        return

      if status.IsWaiting():
        self._printer.write_task_msg(status.ThreadID(), status.GetMessage())
        if self._ShouldForceCycleGraphOnWait():
          self._CycleGraph()
          self._AddNodes()
        continue

      if status.IsWorking():
        self._printer.write_task_msg(status.ThreadID(), status.GetMessage())
        continue

      if status.IsSuccess():
        self._printer.remove_task_msg(status.ThreadID())
        self._in_flight.remove(status.GetJob())
        self._completed.add(status.GetJob())
        result = status.GetResult() # TODO: add typing!
        discard_node = True
        if isinstance(result, UpdateGraphResponseData):
          discard_node = not self._UpdateGraph(status.GetJob(), result)
        if discard_node:
          self._CycleGraph(status.GetJob())
        else:
          self._CycleGraph()
        continue

      raise ValueError('!!!')


class Lifeguard():
  """The lifeguard watches the pool to make sure the children don't drown."""

  __slots__ = ('_threads', '_debug', '_filter', '_receiver')
  def __init__(self, threads:int, debug:bool):
    self._threads = threads
    self._debug = debug
    self._receiver, reporter = TypePipe[PoolStatus].Pipe()
    self._filter = PoolFiltration(reporter, threads, debug)

  def OpenPool(self, targets:set[parsed_target.StagedBuildTarget]):
    self._filter.SetTargets(targets)
    self._filter.start()

  def ClosePool(self) -> PoolStatus:
    status:PoolStatus = self._receiver.recv()
    self._filter.join()
    return status
