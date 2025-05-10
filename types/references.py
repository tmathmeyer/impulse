
import os
import typing

from impulse.core import exceptions
from impulse.types import paths


class Filename(object):
  def __init__(self, name:str):
    self._name = name

  def Name(self) -> str:
    return self._name

  def __hash__(self) -> int:
    return hash(self._name)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Filename):
      return False
    return self._name == other._name


class Directory(object):
  def __init__(self, path:paths.AbsolutePath):
    self._path = path

  def Absolute(self) -> paths.AbsolutePath:
    return self._path

  def Relative(self) -> paths.QualifiedPath:
    return self._path.QualPath()

  def GetFile(self, file:Filename) -> 'File':
    return File(paths.AbsolutePath(os.path.join(self._path.Value(), file.Name())))

  def __hash__(self) -> int:
    return hash(self._path)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Directory):
      return False
    return self._path == other._path


class File(object):
  def __init__(self, path:paths.AbsolutePath):
    self._path = path

  def Absolute(self) -> paths.AbsolutePath:
    return self._path

  def Relative(self) -> paths.QualifiedPath:
    return self._path.QualPath()

  def Directory(self) -> Directory:
    return Directory(paths.AbsolutePath(os.path.dirname(self._path.Value())))

  def Filename(self) -> Filename:
    return Filename(os.path.basename(self._path.Value()))

  def __hash__(self) -> int:
    return hash(self._path)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, File):
      return False
    return self._path == other._path


class TargetName(object):
  def __init__(self, name:str):
    self._name = name

  def Name(self) -> str:
    return self._name

  def __hash__(self) -> int:
    return hash(self._name)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, TargetName):
      return False
    return self._name == other._name


class Package(object):
  def __init__(self, name:Filename, path:paths.QualifiedPath):
    self._name = name
    self._path = path

  def __hash__(self) -> int:
    return hash(self._name)

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Package):
      return False
    return self._name == other._name and self._path == other._path

  def GetRelativePath(self) -> str:
    return os.path.join(self._path.Value()[2:], self._name.Name())


class Target(object):
  def __init__(self, name:TargetName, directory:Directory):
    self._target_name = name
    self._target_dir = directory
    assert type(directory) == Directory

  def __repr__(self) -> str:
    return str(self)

  def __str__(self) -> str:
    return f'{self._target_dir.Relative().Value()}:{self._target_name.Name()}'

  def __hash__(self) -> int:
    return hash(repr(self))

  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, Target):
      return False
    return repr(self) == repr(other)

  def GetBuildFile(self) -> File:
    return self._target_dir.GetFile(Filename('BUILD'))

  def GetPackage(self) -> Package:
    return Package(Filename(self._target_name.Name() + '.zip'),
                   self._target_dir.Relative())

  def GetName(self) -> TargetName:
    return self._target_name

  def GetDirectory(self) -> Directory:
    return self._target_dir

  @staticmethod
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
                    Directory(paths.QualifiedPath(path).AbsPath()))
    if not directory:
      raise exceptions.InvalidPathException(
        'Unable to determine local path', content)
    if path:
      raise exceptions.InvalidPathException(
        'Path component must be fully qualified', path)
    return Target(TargetName(name), directory)