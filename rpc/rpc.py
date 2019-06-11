
import multiprocessing as mp
import os
import sys
import traceback
import uuid

from multiprocessing import managers as MM
backup_ap = MM.AutoProxy
def redef(token, serializer, manager=None, authkey=None, exposed=None,
          incref=True, manager_owned=True):
  return backup_ap(token, serializer, manager, authkey, exposed, incref)
MM.AutoProxy = redef




DEBUG = False
BLUE = '\033[91m'
GREEN = '\033[92m'
GREY = '\033[95m'
ENDC = '\033[0m'

class RPCMessage(object):
  def __init__(self, response:'NamedQueue'):
    self._response_queue = response
    self.token = str(uuid.uuid4())

  def SendResponse(self, inQueue:'NamedQueue', clazz, *args, **kwargs):
    write_out = clazz(inQueue, *args, **kwargs)
    write_out.token = self.token
    self._response_queue.Write(write_out)
    return write_out

  def __repr__(self):
    return '{}::{}({})'.format(self.__class__.__name__,
      self.token.split('-')[1], {
        k:v for k,v in self.__dict__.items()
        if not (k.startswith('_') or k == 'token')
      })


class NamedQueue(object):
  def __init__(self, manager:mp.Manager, name:str):
    self._queue = manager.Queue()
    self._name = name
    self._waiting = {}

  def SubQueue(self):
    return NamedQueue(mp.Manager(), '{}::{}'.format(self._name, '1'))

  def Read(self) -> RPCMessage:
    if DEBUG:
      print('{} :: reading from: {}'.format(
        os.environ.get('_NAME', '_'), self._name))
    x = self._queue.get()
    if DEBUG:
      print('{} :: got value "{}" from {}'.format(
        os.environ.get('_NAME', '_'), x, self._name))
    return x

  def ReadUntil(self, token) -> RPCMessage:
    if DEBUG:
      print('{} :: reading from: {}'.format(
        os.environ.get('_NAME', '_'), self._name))
    while True:
      x = self._queue.get()
      if DEBUG:
        print('{} :: got value "{}" from {}'.format(
          os.environ.get('_NAME', '_'), x, self._name))
      if x.token == token:
        return x
      elif x.token in self._waiting:
        self._waiting[x.token].Write(x)
      else:
        self._queue.put(x)

  def Write(self, value:RPCMessage):
    if DEBUG:
      print('{} :: writing "{}" to {}'.format(
        os.environ.get('_NAME', '_'), value, self._name))
    self._queue.put(value)


class RPCSetAttr(RPCMessage):
  def __init__(self, response:NamedQueue, attr:str, val):
    super().__init__(response)
    self.attr = attr
    self.val = val

    
class RPCSetitem(RPCMessage):
  def __init__(self, response:NamedQueue, key:str, val):
    super().__init__(response)
    self.key = key
    self.val = val

    
class RPCCall(RPCMessage):
  def __init__(self, response:NamedQueue, args, kwargs):
    super().__init__(response)
    self.args = args
    self.kwargs = kwargs

    
class RPCGetAttr(RPCMessage):
  def __init__(self, response:NamedQueue, attr:str):
    super().__init__(response)
    self.attr = attr

    
class RPCDelattr(RPCMessage):
  def __init__(self, response:NamedQueue, attr:str):
    super().__init__(response)
    self.attr = attr

    
class RPCGetitem(RPCMessage):
  def __init__(self, response:NamedQueue, key:str):
    super().__init__(response)
    self.key = key

    
class RPCDelitem(RPCMessage):
  def __init__(self, response:NamedQueue, key:str):
    super().__init__(response)
    self.key = key

    
class RPCRepr(RPCMessage):
  def __init__(self, response:NamedQueue):
    super().__init__(response)

    
class RPCDir(RPCMessage):
  def __init__(self, response:NamedQueue):
    super().__init__(response)

    
class RPCHash(RPCMessage):
  def __init__(self, response:NamedQueue):
    super().__init__(response)

    
class RPCDel(RPCMessage):
  def __init__(self, response:NamedQueue):
    super().__init__(response)


class RPCValue(RPCMessage):
  def __init__(self, response:NamedQueue, value):
    super().__init__(response)
    self.value = value


class RPCException(RPCMessage):
  def __init__(self, response:NamedQueue, exc:Exception):
    print(exc)
    super().__init__(response)
    self.exc = exc
    self.backtrace = [(x.filename, x.lineno) for x in
                      traceback.extract_tb(sys.exc_info()[2])]

  def Print(self):
    print(self.exc)
    for ind, bt in enumerate(self.backtrace):
      print('{}{}::{}'.format('  ' * ind, bt[0], bt[1]))


class RPCEval(RPCMessage):
  def __init__(self, response:NamedQueue, attr, args, kwargs):
    super().__init__(response)
    self.args = args
    self.kwargs = kwargs
    self.attr = attr


class RPCBoundMethod(RPCMessage):
  def __init__(self, response:NamedQueue, attr:str, writeback:NamedQueue):
    super().__init__(response)
    self._writeback = writeback
    self._attr = attr
    self._await_response = False

  def __call__(self, *args, **kwargs):
    E = self.SendResponse(self._writeback, RPCEval, self._attr, args, kwargs)
    if self._await_response:
      return AwaitResult(self._writeback, self.token)


def SendValue(V, I, Q:NamedQueue, M:RPCMessage):
  if callable(V) and getattr(V, '__self__', None) is I:
    M.SendResponse(Q, RPCBoundMethod, V.__name__, M._response_queue)
  else:
    M.SendResponse(Q, RPCValue, V)


def HandleMessage(M:RPCMessage, Q:NamedQueue, I) -> bool:
  try:
    if type(M) is RPCGetAttr:
      SendValue(getattr(I, M.attr), I, Q, M)
    elif type(M) is RPCEval:
      V = getattr(I, M.attr)(*M.args, **M.kwargs)
      SendValue(V, I, Q, M)
    elif type(M) is RPCDel:
      M.SendResponse(Q, RPCDel)
      return False
    elif type(M) is RPCValue:
      print("UNHANDLED ==> {}::{}".format(M, M.value))
    else:
      print("UNHANDLED==>{}".format(M))
    return True
  except Exception as e:
    print(e)
    M.SendResponse(Q, RPCException, e)
    return True


def BindMethod(clazz, I, O):
  clazz._I = I
  clazz._O = O
  return Binder


def Binder(self, method):
  return RPCBoundMethod(self._I, method.__name__, self._O)


def WrapRemoteInstance(clazz, args, kwargs, read_queue:NamedQueue):
  clazz.Bind = BindMethod(clazz, read_queue, read_queue)
  instance = clazz(*args, **kwargs)
  while True:
    incoming = read_queue.Read()
    if not HandleMessage(incoming, read_queue, instance):
      return


def AwaitResult(q, token):
  result = q.ReadUntil(token)
  assert result.token == token
  if type(result) == RPCValue:
    return result.value
  if type(result) == RPCException:
    result.Print()
    return None
  if type(result) == RPCBoundMethod:
    result._await_response = True
  return result


def RPC(clazz):
  class RPCReplacement(object):
    __Initialized = False # Needed for __setattr__

    def __init__(self, *args, **kwargs):
      self.__manager = mp.Manager()
      self.__incoming_queue = NamedQueue(self.__manager, 'MAILBOX(main)')
      self.__outgoing_queue = NamedQueue(
        self.__manager, 'MAILBOX({}({}))'.format(clazz.__name__, args[0]))
      self.__reprocessed_queue = NamedQueue(self.__manager, 'JUNKMAIL')
      self.__process = mp.Process(
        target=WrapRemoteInstance,
        args=(clazz, args, kwargs, self.__outgoing_queue))
      self.__process.start()
      self.__Initialized = True

    def __AwaitResponse(self, clazz, *args):
      instance = clazz(self.__incoming_queue, *args)
      self.__outgoing_queue.Write(instance)
      return AwaitResult(self.__incoming_queue, instance.token)

    def __setattr__(self, attr, val):
      if not self.__Initialized:
        return super().__setattr__(attr, val)
      return self.__AwaitResponse(RPCSetAttr, attr, val)

    def __setitem__(self, key, val):
      return self.__AwaitResponse(RPCSetitem, key, val)

    def __call__(self, *args, **kwargs):
      return self.__AwaitResponse(RPCCall, args, kwargs)

    def __getattr__(self, attr):
      return self.__AwaitResponse(RPCGetAttr, attr)

    def __getitem__(self, key):
      return self.__AwaitResponse(RPCGetitem, key)

    def __delitem__(self, key):
      return self.__AwaitResponse(RPCDelitem, key)

    def __del__(self):
      return self.__AwaitResponse(RPCDel)

    #def __repr__(self):
    #  return self.__AwaitResponse(RPCRepr)

    def __dir__(self):
      return self.__AwaitResponse(RPCDir)

    def __hash__(self):
      return self.__AwaitResponse(RPCHash)

    def __delattr__(self, attr):
      self.__AwaitResponse(RPCDelattr, attr)
      self.__process.join()

  return RPCReplacement


