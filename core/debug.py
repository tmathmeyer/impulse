

__DEBUG = False

def EnableDebug():
  global __DEBUG
  __DEBUG = True


def DisableDebug():
  global __DEBUG
  __DEBUG = False


def IsDebug() -> bool:
  global __DEBUG
  return __DEBUG