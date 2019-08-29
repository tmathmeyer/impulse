import abc
import multiprocessing
import traceback

from impulse import status_out


TASK_POISON = None


class GraphCompleteException(Exception):
  pass


class CommandError(Exception):
  def __init__(self, msg):
    super().__init__(msg)
    self.msg = msg
    self.__in_thread__ = False


class InternalAccess(object):
  def __init__(self):
    self.added_graph = set()
    self.who_needs_me_needs_also = None

  def InjectMoreGraph(self, graph):
    self.added_graph |= graph

  def MoveDependencyTo(self, rule, node=None):
    if node:
      self.added_graph.add(node)
    self.who_needs_me_needs_also = rule


class DependentJob(metaclass=abc.ABCMeta):
  def __init__(self, dependencies, has_internal_access):
    # A set(DependentJob)
    self.dependencies = dependencies
    self._has_internal_access = has_internal_access

  def is_satisfied(self, completed):
    return completed.issuperset(self.dependencies)

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


class TaskStatus(object):
  def __init__(self, task_id, job, result, finished, finishedGreen=False):
    self.id = task_id
    self.job = job
    self.job_result = result
    self.finished = finished
    self.finishedGreen = finishedGreen

  def __repr__(self):
    return 'id: {}  --  {}'.format(self.id, self.job)


class TaskRunner(multiprocessing.Process):
  def __init__(self, id_num, debug, job_input, signal_output):
    multiprocessing.Process.__init__(self)
    self.debug = debug
    self.id = id_num
    self.job_input = job_input
    self.signal_output = signal_output

  def run(self):
    while True:
      job = self.job_input.get()
      if job is TASK_POISON:
        self.job_input.task_done()
        return

      self.signal_output.put(TaskStatus(self.id, job, None, False))
      excepted = False
      job_result = None
      try:
        job_result = job()
      except CommandError as e:
        self._handle_exception(e)
        excepted = True
      except Exception as e:
        self._handle_exception(e)
        excepted = True

      self.signal_output.put(TaskStatus(
        self.id, job, job_result, True, not excepted))
      self.job_input.task_done()
    return

  def _handle_exception(self, exc):
    if not self.debug:
      self.signal_output.put(str(exc))
      return
    traceback.print_exc()
    print(exc)


class DependentPool(multiprocessing.Process):
  def __init__(self, debug, poolcount, jobcount):
    multiprocessing.Process.__init__(self)
    self.debug = debug
    self.threadstatus_queue = multiprocessing.Queue()
    self.job_input_queue = multiprocessing.JoinableQueue()
    self.pool_count = poolcount
    self.printer = status_out.JobPrinter(jobcount, poolcount)

  def run(self):
    for i in range(self.pool_count):
      TaskRunner(i, self.debug, self.job_input_queue, self.threadstatus_queue).start()

    while True:
      status = self.threadstatus_queue.get()
      if isinstance(status, str): # Error condition
        for _ in range(self.pool_count):
          self.job_input_queue.put(TASK_POISON)
        self.job_input_queue.join()
        self.printer.finished(err=status)
        return

      if not status.finished:
        self.printer.write_task_msg(status.id, status.job)
      else:
        self.printer.remove_task_msg(status.id)
        if status.finishedGreen:
          try:
            self.handle_good_status(status)
          except Exception as e:
            print(f'WHY IS THIS RAISED == {type(e)}({e})\n')
            self.completed.add(status.job)
        if not self.check_add_nodes() or not status.finishedGreen:
          for _ in range(self.pool_count):
            self.job_input_queue.put(TASK_POISON)
          self.job_input_queue.join()
          self.printer.finished()
          return

  def handle_good_status(self, status):
    is_completed = True
    if status.job_result:
      results = status.job_result
    else:
      results = InternalAccess()

    results.added_graph -= self.completed
    self.graph |= results.added_graph
    self.printer.add_job_count(len(results.added_graph))

    if results.who_needs_me_needs_also:
      for maybe_parent in self.graph:
        if status.job in maybe_parent.dependencies:
          for newly_added in results.added_graph:
            if newly_added.get_name() == str(results.who_needs_me_needs_also):
              maybe_parent.dependencies.add(newly_added)
          

    if is_completed:
      self.completed.add(status.job)


  def check_add_nodes(self):
    if not self.graph:
      return False

    to_remove = set()
    for node in self.graph:
      if node.is_satisfied(self.completed):
        self.job_input_queue.put(node)
        to_remove.add(node)

    self.graph = self.graph.difference(to_remove)
    return True

  def input_job_graph(self, graph):
    self.graph = graph
    self.completed = set()

    self.check_add_nodes()

    return self
