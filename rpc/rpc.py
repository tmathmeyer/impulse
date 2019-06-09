
import inspect
import multiprocessing as mp
import os
import sys
import traceback
import uuid


OKBLUE = '\033[91m'
OKGREEN = '\033[92m'
OKPOO = '\033[95m'
ENDC = '\033[0m'
debug = False


def QueueRead(q):
  if debug:
    print('{}{}: reading from: {}{}'.format(
      OKPOO, os.getpid(), str(id(q))[-2:], ENDC))
  x = q.get()
  if debug:
    print('{}{}: read({}):  ({}) - {}{}'.format(
      OKBLUE, os.getpid(), str(id(q))[-2:], inspect.stack()[1][2], x, ENDC))
  return x


def QueueWrite(q, v):
  if debug:
    print('{}{}: write({}): ({}) - {}{}'.format(
      OKGREEN, os.getpid(), str(id(q))[-2:], inspect.stack()[1][2], v, ENDC))
  q.put(v)


def QueueAwaitResponse(iQueue, oQueue, rpc):
  QueueWrite(oQueue, rpc)
  while True:
    value = QueueRead(iQueue)
    if value.get_uuid() == rpc.get_uuid():
      if type(value) is Throw:
        value.PrintExceptionBacktrace()
        return []
      if type(value) is Value:
        return value.value
      if type(value) is RCWrapper:
        value.set_queues(iQueue, oQueue)
      return value
    iQueue.put(value)


class PyRPC(object):
  def __init__(self):
    self.__uuid = str(uuid.uuid4())

  def __repr__(self):
    return '{}::{}'.format(self.__class__.__name__, self.__uuid.split('-')[1])

  def get_uuid(self):
    return self.__uuid

  def set_uuid(self, uuid):
    self.__uuid = uuid
    return self


class Delete(PyRPC):
  def __init__(self):
    super().__init__()


class Value(PyRPC):
  def __init__(self, value):
    super().__init__()
    self.value = value


class GetAttr(PyRPC):
  def __init__(self, attr):
    super().__init__()
    self.attr = attr

  def __repr__(self):
    return '{} (attr: {})'.format(super().__repr__(), self.attr)


class SetAttr(PyRPC):
  def __init__(self, attr, val):
    super().__init__()
    self.attr = attr
    self.val = val


class Throw(PyRPC):
  def __init__(self, exc):
    super().__init__()
    self.exc = exc
    self.backtrace = [(x.filename, x.lineno) for x in
                      traceback.extract_tb(sys.exc_info()[2])]

  def PrintExceptionBacktrace(self):
    print(self.exc)
    for ind, bt in enumerate(self.backtrace):
      print('{}{}::{}'.format('  ' * ind, bt[0], bt[1]))


class RPCall(PyRPC):
  def __init__(self, args, kwargs):
    super().__init__()
    self.args = args
    self.kwargs = kwargs


class RCWrapper(PyRPC):
  def __init__(self):
    super().__init__()
    self._inQueue = None
    self._outQueue = None

  def set_queues(self, inQueue, outQueue):
    self._inQueue = inQueue
    self._outQueue = outQueue

  def __call__(self, *args, **kwargs):
    rpc = RPCall(args, kwargs).set_uuid(self.get_uuid())
    return QueueAwaitResponse(self._inQueue, self._outQueue, rpc)


class CallCache(object):
  def __init__(self):
    self.cache = {}

  def CreateCallback(self, fn, uuid):
    cb = RCWrapper().set_uuid(uuid)
    self.cache[cb.get_uuid()] = fn
    return cb

  def GetCallback(self, uid):
    return self.cache[uid]

  def PopCallback(self, uid):
    fn = self.GetCallback(uid)
    del self.cache[uid]
    return fn


def WrapRemoteInstance(clazz, args, kwargs, inQueue, outQueue):
  callCache = CallCache()
  instance = clazz(*args, **kwargs)
  while True:
    job = QueueRead(inQueue)
    if type(job) is Delete:
      return job

    try:
      if type(job) is GetAttr:
        value = getattr(instance, job.attr)
        response = Value(value)
        if callable(value):
          response = callCache.CreateCallback(value, job.get_uuid())
        QueueWrite(outQueue, response.set_uuid(job.get_uuid()))

      elif type(job) is SetAttr:
        if type(job.val) is RCWrapper:
          job.val.set_queues(inQueue, outQueue)
        setattr(instance, job.attr, job.val)

      elif type(job) is RPCall:
        fn = callCache.GetCallback(job.get_uuid())
        value = fn(*job.args, **job.kwargs)
        QueueWrite(outQueue, Value(value).set_uuid(job.get_uuid()))


    except Exception as e:
      if debug:
        traceback.print(exc)
      QueueWrite(outQueue, Throw(e).set_uuid(job.get_uuid()))
      return e


class RPC(object):
  __Initialized = False
  def __init__(self, clazz, *args, **kwargs):
    self._inQueue = mp.Queue()
    self._outQueue = mp.Queue()
    self._process = mp.Process(
      target=WrapRemoteInstance,
      args=(clazz, args, kwargs, self._outQueue, self._inQueue))
    self._process.start()
    self.__Initialized = True

  def __getattr__(self, attr):
    if self._process.is_alive():
      return QueueAwaitResponse(self._inQueue, self._outQueue, GetAttr(attr))

  def __setattr__(self, attr, val):
    if not self.__Initialized:
      return super().__setattr__(attr, val)
    QueueWrite(self._outQueue, SetAttr(attr, val))

  def __del__(self):
    if self._process.is_alive():
      QueueWrite(self._outQueue, Delete())
      self._process.join()


def RPCClass(decorated):
  def Decorator(*args, **kwargs):
    return RPC(decorated, *args, **kwargs)
  return Decorator