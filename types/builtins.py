from __future__ import annotations
import abc
import inspect
import glob
import typing

from impulse.core import errors
from impulse.core import exceptions
from impulse.core import debug
from impulse.types import references
from impulse.types import parsed_target
from impulse.types import paths


def StackScour(filename:str) ->inspect.FrameInfo|None:
  for frame in inspect.stack():
    if frame.filename.endswith(filename):
      return frame
  return None


class EnvironmentLoader(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def LoadFile(self, file:references.File) ->None:
    '''Loads a file into the environment'''


class BuiltinMethod(object):
  def __init__(self):
    self._loader:EnvironmentLoader|None = None

  def Attach(self, loader:EnvironmentLoader) ->None:
    self._loader = loader

  def _GetBuildFileFromStack(self) ->references.File:
    # Walks the stack to find the BUILD file where the builtin method was called
    build_file = 'Fake'
    build_file_index = 1
    while not build_file.endswith('BUILD'):
      build_file = inspect.stack()[build_file_index].filename
      build_file_index += 1
    return references.File(paths.AbsolutePath(build_file))


class DeprecationWarning(BuiltinMethod):
  def __init__(self, method:str):
    super().__init__()
    self._method = method

  def __call__(self, *_, **__) ->None:
    callsite = inspect.stack()[1]
    msg = f'[{callsite.filename}:{callsite.lineno}]: The {self._method} method is deprecated'
    debug.DebugMsg(msg)


class LoadFile(BuiltinMethod):
  def __call__(self, *files:list[str]) ->None:
    if self._loader is None:
      raise errors.FatalError('BuiltinMethod not attached to loader')
    for loading in files:
      try:
        loadfile = references.File(paths.QualifiedPath(loading).AbsPath())
        self._loader.LoadFile(loadfile)
      except exceptions.FileNotFoundException:
        callframe = StackScour('BUILD')
        if callframe is None:
          raise errors.FatalError('No BUILD file found in stack trace')
        raise errors.FileNotFoundError(loading,
                                       callframe.filename,
                                       callframe.positions) from None


class Pattern(BuiltinMethod):
  def __call__(self, pattern:str) ->list[references.File]:
    build_file:references.File = self._GetBuildFileFromStack()
    filename = references.Filename(pattern)
    pattern_file:references.File = build_file.Directory().GetFile(filename)
    regex = pattern_file.Absolute().Value()
    try:
      files = []
      for file in glob.glob(regex):
        absolute_path = paths.AbsolutePath(file)
        files.append(absolute_path.QualPath().RelativeLocation())
      return files
    except Exception:
      return []


class Platform(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive):
    super().__init__()
    self._archive = archive

  def __call__(self, **kwargs):
    assert 'name' in kwargs
    name = kwargs['name']
    reference_name = references.Target.Parse(
      f':{name}', self._GetBuildFileFromStack().Directory())
    return self._archive.AddPlatformTarget(parsed_target.PlatformTarget(
      reference_name, **kwargs))


class BuildRule(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive, cmdline:dict):
    super().__init__()
    self._archive = archive
    self._cmdline = cmdline

  def __call__(self, fn):
    # Store the type of buildrule
    buildrule_name = fn.__name__

    debug.DebugMsg(f'Registering build rule: {buildrule_name}')

    # all params to a build rule must be keyword!
    def replacement(DBBG=False, *args, **kwargs):
      # 'name' is a required argument!
      if 'name' not in kwargs:
        callframe = StackScour('BUILD')
        msg = '`name` attribute is required for all targets'
        raise errors.InvalidSyntax(msg, buildrule_name, callframe)
      name = kwargs['name']

      # add any extra tags a user sers
      extra_tags = kwargs.get('tags', [])

      # This is the buildfile that the rule is called from
      build_file = self._GetBuildFileFromStack()

      target = references.Target.Parse(f':{name}', build_file.Directory())
      try:
        return self._archive.AddBuildTarget(
          parsed_target.BuildTarget(
            target, fn, kwargs, self._cmdline, extra_tags))
      except exceptions.TargetCannotBeMapped as tcbm:
        callframe = StackScour('BUILD')
        if callframe is None:
          raise errors.FatalError('Could not find BUILD file on stack')
        raise errors.InvalidDependency(targetname=tcbm.target,
                                       targetfile=tcbm.location,
                                       sourcefile=callframe.filename,
                                       sourcerange=callframe.positions) from None
    return replacement


class BuildMacro(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive):
    super().__init__()
    self._archive = archive

  def _GetMacroFile(self):
    return 'fooey'

  def __call__(self, fn):
    def Replacement(name, **kwargs):
      return fn(self, name, **kwargs)
    return Replacement

  def ImitateRule(self, rulefile:str, rulename:str, args:dict,
                  kwargs:dict|None = None, tags:list|None = None):
    args.update({'tags':tags or [], 'buildfile':self._GetMacroFile()})
    args.update(kwargs or {})
    load_file = references.File(paths.QualifiedPath(rulefile).AbsPath())
    self._archive.GetBuildTargetFromFile(load_file, rulename)(**args)
