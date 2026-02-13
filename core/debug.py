
import typing

__DEBUG:dict[str, bool] = {'generic': False}


def DebugMsg(message:str) -> None:
  """Prints a debug message if debugging is enabled."""
  if IsDebug():
    print(message)


def EnableDebug(key:str='generic') -> None:
  """Enables debugging for the specified key."""
  global __DEBUG
  __DEBUG[key] = True


def DisableDebug(key:str='generic') -> None:
  """Disables debugging for the specified key."""
  global __DEBUG
  __DEBUG[key] = False


def IsDebug(key:str='generic') -> bool:
  """Returns True if debugging is enabled for the specified key."""
  global __DEBUG
  return __DEBUG.get(key, False)
