
import sys
from impulse.core import debug

class JobPrinter(object):
  def __init__(self, jobcount, pool_count):
    self._jobs = ['IDLE' for _ in range(pool_count)]
    self._jobs_print_length = 0
    self._completed_jobs = 0
    self._total_jobs = jobcount
    self._pool_count = pool_count
    self._print()

  def add_job_count(self, new_count):
    self._total_jobs += new_count

  def write_task_msg(self, mid, msg):
    self._jobs[mid] = msg
    if not debug.IsDebug():
      self._print()
    else:
      print(msg)

  def remove_task_msg(self, mid):
    self._completed_jobs += 1
    self._jobs[mid] = 'IDLE'
    if not debug.IsDebug():
      self._print()

  def _print(self):
    countline = '[{} / {}]'.format(self._completed_jobs, self._total_jobs)
    if not debug.IsDebug():
      for _ in range(self._jobs_print_length):
        print('\033[G\033[2K\033[F', end='')

    if debug.IsDebug():
      for msg in self._jobs:
        if 'IDLE' != msg:
          print(msg)
    else:
      for msg in [countline] + self._jobs:
        print(msg)

    self._jobs_print_length = len(self._jobs) + 1
    sys.stdout.flush()

  def finished(self, err=None):
    if err:
      self._jobs = [err]
    else:
      self._jobs = ['Done']
    self._print()
    print('')