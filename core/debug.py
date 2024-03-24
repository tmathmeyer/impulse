

__DEBUG = {'generic': False}

def DebugMsg(message:str):
  if IsDebug():
    print(message)

def EnableDebug(key='generic'):
  global __DEBUG
  __DEBUG[key] = True


def DisableDebug(key='generic'):
  global __DEBUG
  __DEBUG[key] = False


def IsDebug(key='generic') -> bool:
  global __DEBUG
  return __DEBUG.get(key, False)