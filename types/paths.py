

from __future__ import annotations
import abc
import os
import typing

from impulse.core import exceptions
from impulse.core import environment


class Path(metaclass=abc.ABCMeta):
  """Base class for all path representations in impulse."""
  @abc.abstractmethod
  def Value(self) -> str:
    """Returns the path as a string."""

  @abc.abstractmethod
  def SplitFile(self) -> tuple[Path, str]:
    """Splits the path into a directory path and a filename."""

  @abc.abstractmethod
  def AbsPath(self) -> AbsolutePath:
    """Converts this path to an absolute filesystem path."""

  @abc.abstractmethod
  def QualPath(self) -> QualifiedPath:
    """Converts this path to a repository-qualified path (starting with //)."""


class AbsolutePath(Path):
  """Represents an absolute path on the filesystem."""
  _rawpath: str
  _qualpath: QualifiedPath

  def __init__(self, path: str):
    self._rawpath = path

  def Value(self) -> str:
    """Returns the absolute path string."""
    return self._rawpath

  def SplitFile(self) -> tuple[AbsolutePath, str]:
    """Splits the absolute path into a directory AbsolutePath and a filename."""
    dir_path, file_name = os.path.split(self._rawpath)
    return AbsolutePath(dir_path), file_name

  def AbsPath(self) -> AbsolutePath:
    """Returns itself as it is already an absolute path."""
    return self

  def QualPath(self) -> QualifiedPath:
    """
    Converts this absolute path to a repository-qualified path.
    Requires that the path be within the impulse root.
    """
    if getattr(self, '_qualpath', None) is None:
      root = environment.Root()
      if not self._rawpath.startswith(root):
        raise exceptions.InvalidPathException(
          self._rawpath, f'Path is not within impulse root ({root})')
      self._qualpath = QualifiedPath('//' + self._rawpath[len(root):].lstrip('/'))
    return self._qualpath

  def __hash__(self) -> int:
    return hash(self._rawpath)

  def __eq__(self, other: typing.Any) -> bool:
    if not isinstance(other, AbsolutePath):
      return False
    return self._rawpath == other._rawpath


class QualifiedPath(Path):
  """Represents a repository-qualified path (starting with //)."""
  def __init__(self, path: str):
    if not path.startswith('//'):
      raise exceptions.InvalidPathException(
        path, 'Path is not repository-relative (missing //)')
    self._value = path

  def Value(self) -> str:
    """Returns the qualified path string (e.g., //foo/bar)."""
    return self._value

  def SplitFile(self) -> tuple[QualifiedPath, str]:
    """Splits the qualified path into a directory QualifiedPath and a filename."""
    dir_path, file_name = os.path.split(self._value)
    return QualifiedPath(dir_path), file_name

  def QualPath(self) -> QualifiedPath:
    """Returns itself as it is already a qualified path."""
    return self

  def AbsPath(self) -> AbsolutePath:
    """Converts this qualified path to an absolute filesystem path."""
    return AbsolutePath(os.path.join(environment.Root(), self._value[2:]))

  def __hash__(self) -> int:
    return hash(self._value)

  def __eq__(self, other: typing.Any) -> bool:
    if not isinstance(other, QualifiedPath):
      return False
    return self._value == other._value

  def RelativeLocation(self) -> str:
    """Returns the path relative to the impulse root (without //)."""
    return self._value[2:]
