from __future__ import annotations

import abc
import os
import typing

from impulse.core import environment


class Path(metaclass=abc.ABCMeta):
  """Base class for all path types in the impulse system."""
  @abc.abstractmethod
  def Value(self) -> str:
    """Returns the string representation of the path."""

  @abc.abstractmethod
  def Relative(self) -> 'RelativePath':
    """Returns the path as a RelativePath."""

  @abc.abstractmethod
  def Absolute(self) -> 'AbsolutePath':
    """Returns the path as an AbsolutePath."""

  @abc.abstractmethod
  def QualPath(self) -> 'QualifiedPath':
    """Returns the path as a QualifiedPath."""

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.Value()})'

  def __str__(self) -> str:
    return self.Value()


class AbsolutePath(Path):
  """Represents an absolute path on the filesystem."""
  def __init__(self, path:str):
    self._rawpath=path

  def Value(self) -> str:
    return self._rawpath

  def Relative(self) -> 'RelativePath':
    root=environment.Root()
    if self._rawpath.startswith(root):
      return RelativePath('.' + self._rawpath[len(root):])
    raise ValueError(f'Path {self._rawpath} is not within root {root}')

  def Absolute(self) -> 'AbsolutePath':
    return self

  def QualPath(self) -> 'QualifiedPath':
    root=environment.Root()
    if not self._rawpath.startswith(root):
      raise ValueError(f'Path {self._rawpath} is not within root {root}')
    return QualifiedPath('//' + self._rawpath[len(root)+1:])

  def __eq__(self, other:object) -> bool:
    if isinstance(other, AbsolutePath):
      return self._rawpath == other._rawpath
    return False

  def __hash__(self) -> int:
    return hash(self._rawpath)


class QualifiedPath(Path):
  """Represents a path qualified by the repository root (//foo/bar)."""
  def __init__(self, path:str):
    self._rawpath=path

  def Value(self) -> str:
    return self._rawpath

  def Relative(self) -> 'RelativePath':
    return RelativePath('.' + self._rawpath[1:])

  def Absolute(self) -> 'AbsolutePath':
    root=environment.Root()
    return AbsolutePath(os.path.join(root, self._rawpath[2:]))

  def QualPath(self) -> 'QualifiedPath':
    return self

  def AbsPath(self) -> str:
    """Returns the absolute path as a string."""
    return self.Absolute().Value()

  def RelativeLocation(self) -> str:
    """Returns the path relative to the root (without //)."""
    return self._rawpath[2:]

  def DirName(self) -> 'QualifiedPath':
    """Returns the qualified path to the parent directory."""
    return QualifiedPath(os.path.dirname(self._rawpath))

  def __eq__(self, other:object) -> bool:
    if isinstance(other, QualifiedPath):
      return self._rawpath == other._rawpath
    return False

  def __hash__(self) -> int:
    return hash(self._rawpath)


class RelativePath(Path):
  """Represents a path relative to some directory."""
  def __init__(self, path:str):
    self._value=path

  def Value(self) -> str:
    return self._value

  def Relative(self) -> 'RelativePath':
    return self

  def Absolute(self) -> 'AbsolutePath':
    return AbsolutePath(os.path.abspath(self._value))

  def QualPath(self) -> 'QualifiedPath':
    return self.Absolute().QualPath()

  def __eq__(self, other:object) -> bool:
    if isinstance(other, RelativePath):
      return self._value == other._value
    return False

  def __hash__(self) -> int:
    return hash(self._value)
