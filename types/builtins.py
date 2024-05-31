
import abc
import inspect
import glob

from impulse.core import debug
from impulse.loaders import buildmacro
from impulse.types import references
from impulse.types import parsed_target
from impulse.types import paths
from impulse.types import typecheck


class EnvironmentLoader(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def LoadFile(self, file:references.File):
    '''Loads a file into the environment'''


class BuiltinMethod(object):
  def __init__(self):
    self._loader:EnvironmentLoader = None

  @typecheck.Assert
  def Attach(self, loader:EnvironmentError) -> None:
    self._loader = loader

  @typecheck.Assert
  def _GetBuildFileFromStack(self) -> references.File:
    # Walks the stack to find the BUILD file where the builtin method was called
    build_file = 'Fake'
    build_file_index = 1
    while not build_file.endswith('BUILD'):
      build_file = inspect.stack()[build_file_index].filename
      build_file_index += 1
    return references.File(paths.AbsolutePath(build_file))


class DeprecationWarning(BuiltinMethod):
  @typecheck.Assert
  def __init__(self, method:str):
    super().__init__()
    self._method = method

  @typecheck.Assert
  def __call__(self, *_, **__) -> None:
    callsite = inspect.stack()[1]
    debug.DebugMsg(f'[{callsite.filename}:{callsite.lineno}]: '
                   f'The {self._method} method is deprecated')


class LoadFile(BuiltinMethod):
  @typecheck.Assert
  def __call__(self, *files:list[str]) -> None:
    for loading in files:
      loadfile = references.File(paths.QualifiedPath(loading).AbsolutePath())
      self._loader.LoadFile(loadfile)


class Pattern(BuiltinMethod):
  @typecheck.Assert
  def __call__(self, pattern:str):
    build_file:references.File = self._GetBuildFileFromStack()
    pattern:references.File = build_file.Directory().File(references.Filename(pattern))
    regex = pattern.Absolute().Value()
    try:
      files = []
      for file in glob.glob(regex):
        files.append(references.File(file).Absolute().QualifiedPath().RelativeLocation())
      return files
    except:
      return []


class Platform(BuiltinMethod):
  @typecheck.Assert
  def __init__(self, archive:parsed_target.TargetArchive):
    self._archive = archive

  @typecheck.Assert
  def __call__(self, **kwargs):
    assert 'name' in kwargs
    name = kwargs['name']
    reference_name = references.Target.Parse(
      f':{name}', self._GetBuildFileFromStack().Directory())
    return self._archive.AddPlatformTarget(parsed_target.PlatformTarget(
      reference_name, **kwargs))


class BuildRule(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive, cmdline:dict):
    self._archive = archive
    self._cmdline = cmdline

  def __call__(self, fn):
    # Store the type of buildrule
    buildrule_name = fn.__name__

    debug.DebugMsg(f'Registering build rule: {buildrule_name}')

    # all params to a build rule must be keyword!
    def replacement(DBBG=False, **kwargs):
      # 'name' is a required argument!
      assert 'name' in kwargs
      name = kwargs['name']

      # add any extra tags a user sers
      extra_tags = kwargs.get('tags', [])

      # This is the buildfile that the rule is called from
      build_file = self._GetBuildFileFromStack()

      target = references.Target.Parse(f':{name}', build_file.Directory())
      return self._archive.AddBuildTarget(
        parsed_target.BuildTarget(
          target, fn, kwargs, self._cmdline, extra_tags))

    return replacement


class BuildMacro(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive):
    self._archive = archive

  def _GetMacroFile(self):
    return 'fooey'

  def __call__(self, fn):
    def Replacement(name, **kwargs):
      return fn(self, name, **kwargs)
    return Replacement

  def ImitateRule(self, rulefile:str, rulename:str, args:dict,
                  kwargs:dict=None, tags:list=None):
    args.update({'tags': tags or [], 'buildfile': self._GetMacroFile()})
    args.update(kwargs or {})
    load_file = references.File(paths.QualifiedPath(rulefile).AbsolutePath())
    self._archive.GetBuildTargetFromFile(load_file, rulename)(**args)


