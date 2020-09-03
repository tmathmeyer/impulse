
import time
import typing

from impulse.hal import api
from impulse.rpc import rpc


class LogManager(object):
  def __init__(self):
    pass

  def Log(self, value):
    raise NotImplementedError('Log not implemented')

  def GetNew(self, count=1):
    raise NotImplementedError('GetNew not implemented')

  def GetOld(self, count=1):
    raise NotImplementedError('GetOld not implemented')

  def GetAll(self):
    raise NotImplementedError('GetAll not implemented')


@rpc.RPC
class MemoryLogManager(object):
  def __init__(self, max_size=1000):
    super().__init__()
    self._memory = []
    self._maxSize = max_size

  def Log(self, value):
    self._memory.append(LogEntry(value))
    if len(self._memory) > self._maxSize:
      self._memory = self._memory[1:]

  def GetNew(self, count=1):
    return self._memory[0-min(count, len(self._memory)):]

  def GetOld(self, count=1):
    return self._memory[:min(count, len(self._memory))]

  def GetAll(self):
    return self._memory[::-1]

class LogEntry(api.Resource('logs', False)):
  def __init__(self, content):
    super().__init__()
    self.content = content
    self.time = time.strftime('%X %x %Z')

  def get_core_json(self):
    return { }

  def type(self):
    return self.__class__


class LogHost(api.ProvidesResources(LogEntry)):
  def __init__(self, manager):
    super().__init__(explorer=True)
    self._manager = manager

  @api.METHODS.get('/')
  def allLogs(self) -> [LogEntry]:
    return self._manager.GetAll()

  @api.METHODS.get('/recent/<count>')
  def selectLatest(self, count:int) -> [LogEntry]:
    return self._manager.GetNew(int(count))

  @classmethod
  def AttachMemoryLogManager(cls, app):
    log_manager = MemoryLogManager()
    app.RegisterResourceProvider(cls(log_manager))
    return log_manager