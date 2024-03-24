
import os
import typing

from impulse.types import typecheck
from impulse.types import paths


class Filename(object):
  @typecheck.Assert
  def __init__(self, name:str):
    self._name = name

  @typecheck.Assert
  def Name(self) -> str:
    return self._path

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
    return self._path

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


class Target(object):
  @typecheck.Assert
  def __init__(self, name:TargetName, directory:Directory):
    self._target_name = name
    self._target_dir = directory

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
    return self._directory.File(Filename('BUILD'))

  @typecheck.Assert
  def GetPackage(self) -> Package:
    return Package(Filename(self._target_name.Value() + '.zip'),
                   self._target_dir.Relative())
