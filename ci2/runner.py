
from impulse.ci2 import runnertype
from impulse.ci2 import run_integration_impl
from impulse.host import libhost
from impulse.rpc import rpc

import multiprocessing

@rpc.RPC
class Runner(object):
  def __init__(self, deltaQ, jobQ):
    self._deltaQ = deltaQ
    self._jobQ = jobQ

  def Start(self):
    self.task_runner.PostTask('ReadFromQueue')

  def ReadFromQueue(self):
    job = self._jobQ.get()
    if job is None:
      return
    self.SetStatus(job, 'pending')
    try:
      for stdline in run_integration_impl.RunIntegrationTest(job):
        self._deltaQ.put(('append', job.get_id(), 'stdout', stdline))
      self.SetStatus(job, 'success')
    except str as exit_msg:
      self._deltaQ.put(('append', job.get_id(), 'stdout', exit_msg))
      self.SetStatus(job, 'failure')
    except Exception as e:
      self._deltaQ.put(('append', job.get_id(), 'stdout', str(e)))
      self.SetStatus(job, 'failure')
    self.task_runner.PostTask('ReadFromQueue')

  def SetStatus(self, job, status):
    self._deltaQ.put(('setattr', job.get_id(), 'status', status))
    job_source_module = getattr(
      __import__(f'impulse.ci2.{job.job_source}').ci2, job.job_source)
    hostname = libhost.GetHostname()
    url = f'https://{hostname}/api/{job._resource_name}/{job.get_id()}'
    job_source_module.UpdatePRStatus(
      job.writeback_url, status, url, 'build status', 'impulse/ci')


class JobHost(runnertype.RunnerType):
  def __init__(self):
    self._deltaQ = multiprocessing.Queue()
    self._jobQ = multiprocessing.Queue()
    self._runner = Runner(self._deltaQ, self._jobQ)
    self._runner.Start()

  def EnqueueJob(self, instance):
    self._deltaQ.put(('init', instance.get_id(), instance))
    self._jobQ.put(instance)

  def QueryJobDeltas(self):
    deltas = []
    while not self._deltaQ.empty():
      deltas.append(self._deltaQ.get())
    return deltas

  def __del__(self):
    self._jobQ.put(None)