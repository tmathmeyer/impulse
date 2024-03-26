

import abc
import os
import typing

from impulse.core import exceptions
from impulse.core import environment
from impulse.types import typecheck


class Path(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def Value(self) -> str:
    '''Gets the path value as a string'''

  @abc.abstractmethod
  def SplitFile(self) -> ('Path', str):
    '''Splits the path into a directory path and a filename'''

  @abc.abstractmethod
  def AbsolutePath(self) -> 'Path':
    '''Converts this path type to an absolute filesystem path'''

  @abc.abstractmethod
  def QualifiedPath(self) -> 'Path':
    '''Converts this path type to an repository-local path'''


class AbsolutePath(Path):
  @typecheck.Assert
  def __init__(self, path:str):
    self._value = path

  @typecheck.Assert
  def Value(self) -> str:
    return self._value

  @typecheck.Assert
  def SplitFile(self) -> tuple[Path, str]:
    dir, file = os.path.split(self._value)
    return AbsolutePath(dir), file

  @typecheck.Assert
  def AbsolutePath(self) -> Path:
    return self

  @typecheck.Assert
  def QualifiedPath(self) -> Path:
    root = environment.Root()
    if not self._value.startswith(root):
      raise exceptions.InvalidPathException(
        self._value, f'Path is not within impulse root ({root})')
    return QualifiedPath('/' + self._value[len(root):])

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._value)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, AbsolutePath):
      return False
    return self._value == other._value


class QualifiedPath(Path):
  @typecheck.Assert
  def __init__(self, path:str):
    if not path.startswith('//'):
      raise exceptions.InvalidPathException(
        path, 'Path is not repository-relative (missing //)')
    self._value = path

  @typecheck.Assert
  def Value(self) -> str:
    return self._value

  @typecheck.Assert
  def SplitFile(self) -> tuple[Path, str]:
    dir, file = os.path.split(self._value)
    return QualifiedPath(dir), file

  @typecheck.Assert
  def QualifiedPath(self) -> Path:
    return self

  @typecheck.Assert
  def AbsolutePath(self) -> AbsolutePath:
    return AbsolutePath(os.path.join(environment.Root(), self._value[2:]))

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._value)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, QualifiedPath):
      return False
    return self._value == other._value

  def RelativeLocation(self) -> str:
    return self._value[2:]
