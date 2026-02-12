from __future__ import annotations
import os
import typing

from impulse.core import exceptions
from impulse.types import paths


class Filename(object):
  """Represents a single filename without any path components."""
  def __init__(self, name:str):
    self._name = name

  def Name(self) ->str:
    """Returns the string representation of the filename."""
    return self._name

  def __hash__(self) ->int:
    return hash(self._name)

  def __eq__(self, other:typing.Any) ->bool:
    if not isinstance(other, Filename):
      return False
    return self._name == other._name


class Directory(object):
  """Represents a directory in the filesystem."""
  def __init__(self, path:paths.AbsolutePath):
    self._path = path

  def Absolute(self) ->paths.AbsolutePath:
    """Returns the absolute path of the directory."""
    return self._path

  def Relative(self) ->paths.QualifiedPath:
    """Returns the repository-relative path of the directory."""
    return self._path.QualPath()

  def GetFile(self, file:Filename) ->File:
    """Returns a File object for a file within this directory."""
    return File(paths.AbsolutePath(os.path.join(self._path.Value(), file.Name())))

  def __hash__(self) ->int:
    return hash(self._path)

  def __eq__(self, other:typing.Any) ->bool:
    if not isinstance(other, Directory):
      return False
    return self._path == other._path


class File(object):
  """Represents a file in the filesystem."""
  def __init__(self, path:paths.AbsolutePath):
    self._path = path

  def Absolute(self) ->paths.AbsolutePath:
    """Returns the absolute path of the file."""
    return self._path

  def Relative(self) ->paths.QualifiedPath:
    """Returns the repository-relative path of the file."""
    return self._path.QualPath()

  def Directory(self) ->Directory:
    """Returns the Directory object containing this file."""
    return Directory(paths.AbsolutePath(os.path.dirname(self._path.Value())))

  def Filename(self) ->Filename:
    """Returns the Filename object for this file."""
    return Filename(os.path.basename(self._path.Value()))

  def __hash__(self) ->int:
    return hash(self._path)

  def __eq__(self, other:typing.Any) ->bool:
    if not isinstance(other, File):
      return False
    return self._path == other._path


class TargetName(object):
  """Represents the name of a build target."""
  def __init__(self, name:str):
    self._name = name

  def Name(self) ->str:
    """Returns the string representation of the target name."""
    return self._name

  def __hash__(self) ->int:
    return hash(self._name)

  def __eq__(self, other:typing.Any) ->bool:
    if not isinstance(other, TargetName):
      return False
    return self._name == other._name


class Package(object):
  """Represents a build package (usually a zip file)."""
  def __init__(self, name:Filename, path:paths.QualifiedPath):
    self._name = name
    self._path = path

  def __hash__(self) ->int:
    return hash(self._name)

  def __eq__(self, other:typing.Any) ->bool:
    if not isinstance(other, Package):
      return False
    return self._name == other._name and self._path == other._path

  def GetRelativePath(self) ->str:
    """Returns the repository-relative path to the package file."""
    return os.path.join(self._path.Value()[2:], self._name.Name())


class Target(object):
  """Represents a fully qualified build target (directory + name)."""
  def __init__(self, name:TargetName, directory:Directory):
    self._target_name = name
    self._target_dir = directory
    assert isinstance(directory, Directory)

  def __repr__(self) ->str:
    return str(self)

  def __str__(self) ->str:
    return f'{self._target_dir.Relative().Value()}:{self._target_name.Name()}'

  def __hash__(self) ->int:
    return hash(repr(self))

  def __eq__(self, other:typing.Any) ->bool:
    if not isinstance(other, Target):
      return False
    return repr(self) == repr(other)

  def GetBuildFile(self) ->File:
    """Returns the File object for the BUILD file defining this target."""
    return self._target_dir.GetFile(Filename('BUILD'))

  def GetPackage(self) ->Package:
    """Returns the Package object that this target will produce."""
    return Package(Filename(self._target_name.Name() + '.zip'),
                   self._target_dir.Relative())

  def GetName(self) ->TargetName:
    """Returns the TargetName object for this target."""
    return self._target_name

  def GetDirectory(self) ->Directory:
    """Returns the Directory object where this target is defined."""
    return self._target_dir

  @staticmethod
  def Parse(content:str, directory:Directory|None = None) ->Target:
    split = content.split(':')
    if len(split) != 2:
      raise exceptions.InvalidPathException(
        'Target must either a local path (:target) '
        'or qualified path (//path/to/build:target)',
        content)
    path, name = split
    if path.startswith('//'):
      return Target(TargetName(name),
                    Directory(paths.QualifiedPath(path).AbsPath()))
    if not directory:
      raise exceptions.InvalidPathException(
        'Unable to determine local path', content)
    if path:
      raise exceptions.InvalidPathException(
        'Path component must be fully qualified', path)
    return Target(TargetName(name), directory)
