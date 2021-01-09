

__DEBUG = {'generic': False}

def EnableDebug(key='generic'):
  global __DEBUG
  __DEBUG[key] = True


def DisableDebug(key='generic'):
  global __DEBUG
  __DEBUG[key] = False


def IsDebug(key='generic') -> bool:
  global __DEBUG
  return __DEBUG.get(key, False)