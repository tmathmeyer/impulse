from __future__ import annotations

import os
import typing

from impulse.types import paths


class Filename(object):
  """Represents a filename component of a path."""
  def __init__(self, name:str):
    self._name=name

  def Name(self) -> str:
    return self._name

  def __str__(self) -> str:
    return self._name

  def __eq__(self, other:object) -> bool:
    if isinstance(other, Filename):
      return self._name == other._name
    return False

  def __hash__(self) -> int:
    return hash(self._name)


class Directory(object):
  """Represents a directory in the impulse repository."""
  def __init__(self, path:paths.QualifiedPath):
    self._path=path

  def GetFile(self, file:Filename) -> 'File':
    """Returns a File object in this directory."""
    path=os.path.join(self._path.Value(), file.Name())
    return File(paths.QualifiedPath(path))

  def QualPath(self) -> paths.QualifiedPath:
    return self._path

  def Relative(self) -> paths.RelativePath:
    return self._path.Relative()

  def Absolute(self) -> paths.AbsolutePath:
    return self._path.Absolute()

  def __str__(self) -> str:
    return self._path.Value()

  def __eq__(self, other:object) -> bool:
    if isinstance(other, Directory):
      return self._path == other._path
    return False

  def __hash__(self) -> int:
    return hash(self._path)


class File(object):
  """Represents a file in the impulse repository."""
  def __init__(self, path:paths.Path):
    self._path=path

  def Absolute(self) -> paths.AbsolutePath:
    return self._path.Absolute()

  def QualPath(self) -> paths.QualifiedPath:
    return self._path.QualPath()

  def Directory(self) -> Directory:
    """Returns the directory containing this file."""
    return Directory(self.QualPath().DirName())

  def __str__(self) -> str:
    return str(self._path)

  def __eq__(self, other:object) -> bool:
    if isinstance(other, File):
      return self._path == other._path
    return False

  def __hash__(self) -> int:
    return hash(self._path)


class Package(object):
  """Represents a package (a directory containing a BUILD file)."""
  def __init__(self, name:str):
    self._name=name

  def GetRelativePath(self) -> str:
    """Returns path of package zip file relative to output root."""
    return self._name[2:] + '.zip'

  def __str__(self) -> str:
    return self._name

  def __eq__(self, other:object) -> bool:
    if isinstance(other, Package):
      return self._name == other._name
    return False

  def __hash__(self) -> int:
    return hash(self._name)


class Target(object):
  """Represents a build target (e.g., //foo:bar)."""
  def __init__(self, directory:Directory, name:Filename):
    self._target_name=name
    self._target_dir=directory

  @staticmethod
  def Parse(content:str, directory:Directory | None=None) -> 'Target':
    """Parses a target string into a Target object."""
    if ':' not in content:
      raise ValueError(f'Invalid target: {content}')
    split=content.split(':')
    path_str, name_str=split
    if path_str == '' and directory is not None:
      path=directory.QualPath()
    else:
      path=paths.QualifiedPath(path_str)
    return Target(Directory(path), Filename(name_str))

  def GetPackage(self) -> Package:
    """Returns the package containing this target."""
    return Package(str(self._target_dir))

  def GetName(self) -> Filename:
    """Returns the name component of the target."""
    return self._target_name

  def GetDirectory(self) -> Directory:
    """Returns the directory component of the target."""
    return self._target_dir

  def GetBuildFile(self) -> File:
    """Returns the File object for the package's BUILD file."""
    return self._target_dir.GetFile(Filename('BUILD'))

  def __str__(self) -> str:
    return f'{self._target_dir}:{self._target_name}'

  def __eq__(self, other:object) -> bool:
    if isinstance(other, Target):
      return (self._target_name == other._target_name and
              self._target_dir == other._target_dir)
    return False

  def __hash__(self) -> int:
    return hash(str(self))
