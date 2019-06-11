
import queue
import uuid
import threading

from impulse.rpc import rpc

@rpc.RPC
class BuilderPool(object):
  def __init__(self, threadcount):
    self.builders = [RunThread() for _ in range(threadcount)]
    self.backlog = queue.Queue()
    self.exportqueue = queue.Queue()

  def expire(self, build):
    self._message_loop()
    pass

  def ingest(self, build):
    self.backlog.put(build)
    self._message_loop()

  def running_build_ids(self):
    self._message_loop()
    return [b.GetTask().get_id() for b in self.builders
            if b.status == RunThread.RUNNING]

  def updates(self):
    self._message_loop()
    exports = []
    while not self.exportqueue.empty():
      exports.append(self.exportqueue.get())
    return exports

  def _message_loop(self):
    open_builders = queue.Queue()
    for builder in self.builders:
      if builder.status == RunThread.FINISHED:
        self.exportqueue.put(builder.GetTask())
        builder.status = RunThread.READY
      if builder.status == RunThread.READY:
        open_builders.put(builder)

    while not open_builders.empty() and not self.backlog.empty():
      open_builders.get().SetTask(self.backlog.get())


class RunThread(object):
  READY = str(uuid.uuid4())
  FINISHED = str(uuid.uuid4())
  RUNNING = str(uuid.uuid4())

  def __init__(self):
    self.status = RunThread.READY
    self.job = None
    self.thread = None

  def _run(self):
    self.job.Run()
    self.status = RunThread.FINISHED

  def SetTask(self, job):
    assert self.status == RunThread.READY
    self.status = RunThread.RUNNING
    self.job = job
    self.thread = threading.Thread(target=self._run)
    self.thread.start()

  def GetTask(self):
    return self.job