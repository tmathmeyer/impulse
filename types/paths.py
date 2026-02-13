

import abc
import os
import typing

from impulse.core import exceptions
from impulse.core import environment


class Path(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def Value(self) -> str:
    '''Gets the path value as a string'''

  @abc.abstractmethod
  def SplitFile(self) -> tuple['Path', str]:
    '''Splits the path into a directory path and a filename'''

  @abc.abstractmethod
  def AbsPath(self) -> 'AbsolutePath':
    '''Converts this path type to an absolute filesystem path'''

  @abc.abstractmethod
  def QualPath(self) -> 'QualifiedPath':
    '''Converts this path type to an repository-local path'''


class AbsolutePath(Path):
  _rawpath:str
  _qualpath:'QualifiedPath'

  def __init__(self, path:str):
    self._rawpath = path

  def Value(self) -> str:
    return self._rawpath

  def SplitFile(self) -> tuple[Path, str]:
    dir, file = os.path.split(self._rawpath)
    return AbsolutePath(dir), file

  def AbsPath(self) -> 'AbsolutePath':
    return self

  def QualPath(self) -> 'QualifiedPath':
    if getattr(self, '_qualpath', None) is None:
      root = environment.Root()
      if not self._rawpath.startswith(root):
        raise exceptions.InvalidPathException(
          self._rawpath, f'Path is not within impulse root ({root})')
      rel = self._rawpath[len(root):]
      if not rel.startswith('/'):
        rel = '/' + rel
      self._qualpath = QualifiedPath('/' + rel)
    return self._qualpath

  def __hash__(self) -> int:
    return hash(self._rawpath)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, AbsolutePath):
      return False
    return self._rawpath == other._rawpath


class QualifiedPath(Path):
  def __init__(self, path:str):
    if not path.startswith('//'):
      raise exceptions.InvalidPathException(
        path, 'Path is not repository-relative (missing //)')
    self._value = path

  def Value(self) -> str:
    return self._value

  def SplitFile(self) -> tuple[Path, str]:
    dir, file = os.path.split(self._value)
    return QualifiedPath(dir), file

  def QualPath(self) -> 'QualifiedPath':
    return self

  def AbsPath(self) -> 'AbsolutePath':
    return AbsolutePath(os.path.join(environment.Root(), self._value[2:]))

  def __hash__(self) -> int:
    return hash(self._value)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, QualifiedPath):
      return False
    return self._value == other._value

  def RelativeLocation(self) -> str:
    return self._value[2:]
