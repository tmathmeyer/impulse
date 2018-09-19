import abc
import multiprocessing
import os
import random
import sys
import time


from impulse import status_out


TASK_POISON = None


class GraphCompleteException(Exception):
  pass


class CommandError(Exception):
  def __init__(self, msg):
    super().__init__(msg)
    self.msg = msg


class DependentJob(metaclass=abc.ABCMeta):
  def __init__(self, dependencies):
    # A set(DependentJob)
    self.dependencies = dependencies

  def is_satisfied(self, completed):
    return completed.issuperset(self.dependencies)

  def __call__(self, debug=False):
    self.run_job(debug)

  @abc.abstractmethod
  def run_job(self, debug):
    pass

  @abc.abstractmethod
  def __eq__(self, other):
    pass

  @abc.abstractmethod
  def __hash__(self):
    pass


class TaskStatus(object):
  def __init__(self, task_id, job, finished):
    self.id = task_id
    self.job = job
    self.finished = finished

  def __repr__(self):
    return 'id: %s  --  %s' % (self.id, self.job)


class TaskRunner(multiprocessing.Process):
  def __init__(self, id_num, job_input, signal_output):
    multiprocessing.Process.__init__(self)
    self.id = id_num
    self.job_input = job_input
    self.signal_output = signal_output

  def run(self):
    while True:
      job = self.job_input.get()
      if job is TASK_POISON:
        self.job_input.task_done()
        return

      self.signal_output.put(TaskStatus(self.id, job, False))
      try:
        job()
      except CommandError as e:
        self.signal_output.put(e.msg)
      self.signal_output.put(TaskStatus(self.id, job, True))
      self.job_input.task_done()
    return


class DependentPool(multiprocessing.Process):
  def __init__(self, poolcount):
    multiprocessing.Process.__init__(self)
    self.threadstatus_queue = multiprocessing.Queue()
    self.job_input_queue = multiprocessing.JoinableQueue()
    self.pool_count = poolcount
    status_out.setup_status(poolcount)


  def run(self):
    for i in range(self.pool_count):
      TaskRunner(i, self.job_input_queue, self.threadstatus_queue).start()

    while True:
      status = self.threadstatus_queue.get()
      if isinstance(status, str): # Error condition
        for _ in range(self.pool_count):
          self.job_input_queue.put(TASK_POISON)
        self.job_input_queue.join()
        status_out.cleanup_status()
        print('FAILED: ' + status)
        return

      if not status.finished:
        status_out.report_thread(status.id, status.job)
      else:
        status_out.reset_thread(status.id)
        self.completed.add(status.job)
        if not self.check_add_nodes():
          for _ in range(self.pool_count):
            self.job_input_queue.put(TASK_POISON)
          self.job_input_queue.join()
          status_out.cleanup_status()
          return

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
