
import os
import typing

from impulse.core import exceptions
from impulse.types import typecheck
from impulse.types import paths


class Filename(object):
  @typecheck.Assert
  def __init__(self, name:str):
    self._name = name

  @typecheck.Assert
  def Name(self) -> str:
    return self._name

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._name)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Filename):
      return False
    return self._name == other._name


class Directory(object):
  @typecheck.Assert
  def __init__(self, path:paths.AbsolutePath):
    self._path = path

  @typecheck.Assert
  def Absolute(self) -> paths.AbsolutePath:
    return self._path

  @typecheck.Assert
  def Relative(self) -> paths.QualifiedPath:
    return self._path.QualifiedPath()

  def File(self, file:Filename) -> 'File':
    return File(paths.AbsolutePath(os.path.join(self._path.Value(), file.Name())))

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._path)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Directory):
      return False
    return self._path == other._path


class File(object):
  @typecheck.Assert
  def __init__(self, path:paths.AbsolutePath):
    self._path = path

  @typecheck.Assert
  def Absolute(self) -> paths.AbsolutePath:
    return self._path

  @typecheck.Assert
  def Relative(self) -> paths.QualifiedPath:
    return self._path.QualifiedPath()

  @typecheck.Assert
  def Directory(self) -> Directory:
    return Directory(paths.AbsolutePath(os.path.dirname(self._path.Value())))

  @typecheck.Assert
  def Filename(self) -> Filename:
    return Filename(os.path.basename(self._path.Value()))

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._path)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, File):
      return False
    return self._path == other._path


class TargetName(object):
  @typecheck.Assert
  def __init__(self, name:str):
    self._name = name

  @typecheck.Assert
  def Name(self) -> str:
    return self._name

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._name)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, TargetName):
      return False
    return self._name == other._name


class Package(object):
  @typecheck.Assert
  def __init__(self, name:Filename, path:paths.QualifiedPath):
    self._name = name
    self._path = path

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(self._name)

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Package):
      return False
    return self._name == other._name and self._path == other._path

  @typecheck.Assert
  def GetRelativePath(self) -> str:
    return os.path.join(self._path.Value()[2:], self._name.Name())


class Target(object):
  @typecheck.Assert
  def __init__(self, name:TargetName, directory:Directory):
    self._target_name = name
    self._target_dir = directory
    assert type(directory) == Directory

  @typecheck.Assert
  def __repr__(self) -> str:
    return str(self)

  @typecheck.Assert
  def __str__(self) -> str:
    return f'{self._target_dir.Relative().Value()}:{self._target_name.Name()}'

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(repr(self))

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Target):
      return False
    return repr(self) == repr(other)

  @typecheck.Assert
  def GetBuildFile(self) -> File:
    return self._target_dir.File(Filename('BUILD'))

  @typecheck.Assert
  def GetPackage(self) -> Package:
    return Package(Filename(self._target_name.Name() + '.zip'),
                   self._target_dir.Relative())

  @typecheck.Assert
  def GetName(self) -> TargetName:
    return self._target_name

  @typecheck.Assert
  def GetDirectory(self) -> Directory:
    return self._target_dir

  @staticmethod
  @typecheck.Assert
  def Parse(content:str, directory:Directory|None = None) -> typing.Any:
    split = content.split(':')
    if len(split) != 2:
      raise exceptions.InvalidPathException(
        'Target must either a local path (:target) '
        'or qualified path (//path/to/build:target)',
        content)
    path, name = split
    if path.startswith('//'):
      return Target(TargetName(name),
                    Directory(paths.QualifiedPath(path).AbsolutePath()))
    if not directory:
      raise exceptions.InvalidPathException(
        'Unable to determine local path', content)
    if path:
      raise exceptions.InvalidPathException(
        'Path component must be fully qualified', path)
    return Target(TargetName(name), directory)