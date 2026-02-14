from __future__ import annotations

import abc
import glob
import inspect
import os
import typing

from impulse.core import debug
from impulse.core import errors
from impulse.core import exceptions
from impulse.types import parsed_target
from impulse.types import references
from impulse.types import paths


def StackScour(filename:str) -> inspect.FrameInfo|None:
  """Walks the stack to find the first frame matching filename."""
  for frame in inspect.stack():
    if frame.filename.endswith(filename):
      return frame
  return None


class EnvironmentLoader(metaclass=abc.ABCMeta):
  """Interface for loading build files into an environment."""
  @abc.abstractmethod
  def LoadFile(self, file:references.File) -> None:
    """Loads the given build file."""


class BuiltinMethod(object):
  """Base class for build system builtin methods (e.g., load, pattern)."""
  def __init__(self) -> None:
    self._loader:EnvironmentLoader|None=None

  def Attach(self, loader:EnvironmentLoader) -> None:
    """Attaches this method to an environment loader."""
    self._loader=loader

  def _GetBuildFileFromStack(self) -> references.File:
    """Walks the stack to find the BUILD file where the method was called."""
    callframe=StackScour('BUILD')
    if callframe is None:
      raise errors.FatalError('No BUILD file found in stack trace')
    build_file=callframe.filename
    return references.File(paths.AbsolutePath(build_file))


class DeprecationWarning(BuiltinMethod):
  """Builtin that raises a warning when called."""
  def __init__(self, name:str):
    super().__init__()
    self._name=name

  def __call__(self, *args:object, **kwargs:object) -> None:
    print(f'WARNING: {self._name} is deprecated and will be removed.')


class LoadFile(BuiltinMethod):
  """Implementation of the load() builtin."""
  def __call__(self, *files:str) -> None:
    if self._loader is None:
      raise errors.FatalError('BuiltinMethod not attached to loader')
    for loading in files:
      try:
        loadfile=references.File(paths.QualifiedPath(loading))
        self._loader.LoadFile(loadfile)
      except exceptions.FileNotFoundException:
        callframe=StackScour('BUILD')
        if callframe is None:
          raise errors.FatalError('No BUILD file found in stack trace')
        raise errors.FileNotFoundError(loading,
                                       callframe.filename,
                                       callframe.positions) from None


class Pattern(BuiltinMethod):
  """Implementation of the pattern() builtin for globbing files."""
  def __call__(self, pattern_str:str) -> list[str]:
    build_file=self._GetBuildFileFromStack()
    pattern_file=build_file.Directory().GetFile(
        references.Filename(pattern_str))
    res=[]
    for filename in glob.glob(pattern_file.Absolute().Value()):
      res.append(os.path.basename(filename))
    return res


class BuildRule(BuiltinMethod):
  """Decorator for defining build rules."""
  def __init__(self, archive:parsed_target.TargetArchive,
               cmdline:dict[str, object]):
    super().__init__()
    self._archive=archive
    self._cmdline=cmdline

  def __call__(self, fn:typing.Callable) -> typing.Callable:
    buildrule_name=fn.__name__
    debug.DebugMsg(f'Registering build rule: {buildrule_name}')

    def replacement(DBBG:bool=False, *args:object,
                    **kwargs:object) -> parsed_target.BuildTarget:
      if 'name' not in kwargs:
        callframe=StackScour('BUILD')
        msg='`name` attribute is required for all targets'
        raise errors.InvalidSyntax(msg, buildrule_name, callframe)
      name=str(kwargs['name'])
      extra_tags=typing.cast(list[str], kwargs.get('tags', []))
      build_file=self._GetBuildFileFromStack()
      target=references.Target.Parse(f':{name}', build_file.Directory())
      try:
        return self._archive.AddBuildTarget(
          parsed_target.BuildTarget(
            target, fn, kwargs, self._cmdline, extra_tags))
      except exceptions.TargetCannotBeMapped as tcbm:
        callframe=StackScour('BUILD')
        if callframe is None:
          raise errors.FatalError('Could not find BUILD file on stack')
        raise errors.InvalidDependency(targetname=tcbm.target,
                                       targetfile=tcbm.location,
                                       sourcefile=callframe.filename,
                                       sourcerange=callframe.positions) \
              from None
    return replacement


class BuildMacro(BuiltinMethod):
  """Decorator for defining build macros."""
  def __init__(self, archive:parsed_target.TargetArchive):
    super().__init__()
    self._archive=archive

  def _GetMacroFile(self) -> str:
    return 'fooey'

  def __call__(self, fn:typing.Callable) -> typing.Callable:
    def Replacement(name:str, **kwargs:object) -> object:
      return fn(self, name, **kwargs)
    return Replacement

  def ImitateRule(self, rulefile:str, rulename:str, args:dict[str, object],
                  kwargs:dict[str, object]|None=None,
                  tags:list[str]|None=None) -> None:
    """Allows a macro to imitate a build rule call."""
    args.update({'tags': tags or [], 'buildfile': self._GetMacroFile()})
    args.update(kwargs or {})
    load_file=references.File(paths.QualifiedPath(rulefile))
    self._archive.GetBuildTargetFromFile(load_file, rulename)(**args)


class Platform(BuiltinMethod):
  """Implementation of the platform() builtin."""
  def __init__(self, archive:parsed_target.TargetArchive):
    super().__init__()
    self._archive=archive

  def __call__(self, name:str, **kwargs:object) -> \
      parsed_target.PlatformTarget:
    build_file=self._GetBuildFileFromStack()
    target=references.Target.Parse(f':{name}', build_file.Directory())
    return self._archive.AddPlatformTarget(
      parsed_target.PlatformTarget(target, **kwargs))
