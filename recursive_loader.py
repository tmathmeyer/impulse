from __future__ import annotations

import inspect
import os
import sys
import types
import typing

from impulse import impulse_paths

from impulse.core import errors
from impulse.core import exceptions
from impulse.types import builtins
from impulse.types import references
from impulse.types import parsed_target
from impulse.types import paths


class LazyEnvironmentLoader(builtins.EnvironmentLoader):
  """Loads the environment for a build file."""
  def __init__(self, stub_map:dict[str, list[str]],
               builtin_methods:dict[str, builtins.BuiltinMethod]):
    self._loaded_files:set[references.File]=set()
    self._environment=builtin_methods
    for builtin in self._environment.values():
      builtin.Attach(self)
    for file, names in stub_map.items():
      for name in names:
        self._environment[name]=StubLoader(self, name, file)
    self._environment['__builtins__']=dict(__builtins__) # type:ignore
    self._environment['__builtins__']['__import__']=self.ImportInjector

  def IsStubOrUndefined(self, key:str) -> bool:
    """Checks if a key is a stub or undefined."""
    if key not in self._environment:
      return True
    if isinstance(self._environment[key], StubLoader):
      return True
    return False

  def Get(self, key:str) -> object:
    """Gets a value from the environment."""
    return self._environment[key]

  def ImportInjector(self, name:str, locals:dict|None=None,
                     globals:dict|None=None, fromlist:list[str]|None=None,
                     level:int|None=None) -> types.ModuleType:
    """Injects synthetic modules for build rule definitions."""
    allowed_import_targets={
      'impulse.types.stubs': {
        'os': lambda target: __import__(target),
        'Any': lambda _: None,
      },
      'impulse.types.interfaces': {
        'Package': lambda _: None
      }
    }

    if name not in allowed_import_targets:
      raise Exception(
        f'buildrule definitions may only import from '
        f'{list(allowed_import_targets.keys())}, not {name}'
      )

    synthetic_module=types.ModuleType(name)
    special_cases=allowed_import_targets[name]
    for target in (fromlist or []):
      if target in special_cases:
        synthetic_module.__dict__[target]=special_cases[target](target)
      elif target in self._environment:
        synthetic_module.__dict__[target]=self._environment.get(target)
      else:
        raise Exception(f'`{target}` could not be imported from `{name}`')
    return synthetic_module

  def LoadFile(self, file:references.File) -> None:
    """Loads a build file into the environment."""
    if file in self._loaded_files:
      return
    self._loaded_files.add(file)

    abspath=file.Absolute().Value()
    try:
      with open(abspath) as f:
        buildfile_content=f.read()
    except FileNotFoundError:
      raise exceptions.FileNotFoundException(filepath=abspath,
                                              relpath=file) from None

    try:
      compiled=compile(buildfile_content, abspath, 'exec')
      exec(compiled, self._environment)
    except exceptions.FileLoadException as e:
      raise e.Chain(abspath) from None
    except Exception as e:
      if isinstance(e, (errors.RenderableError,
                        exceptions.ImpulseBaseException)):
        raise
      _, _, tb=sys.exc_info()
      stack=[]
      curr_tb=tb
      while curr_tb:
        if curr_tb.tb_frame.f_code.co_filename == abspath:
          stack.append(curr_tb)
        curr_tb=curr_tb.tb_next
      if stack:
        target_tb=stack[-1]
        line_no=target_tb.tb_lineno
        search_text=''
        if isinstance(e, NameError):
          search_text=e.args[0].split('\'')[1]
        elif isinstance(e, AttributeError):
          search_text=e.args[0].split('\'')[-2]
        if search_text:
          raise errors.FileHighlightError(f'{type(e).__name__}: {str(e)}',
                                          abspath, search_text,
                                          line_no, line_no)
        else:
          raise exceptions.FileErrorException(f'{type(e).__name__}: {str(e)}',
                                              abspath, line_no, 0)
      raise exceptions.FileLoadException(f'{type(e).__name__}: {str(e)}',
                                         [abspath])


class StubLoader(object):
  """Loads a stub from a file when it's first called."""
  def __init__(self, env:'LazyEnvironmentLoader', name:str, filename:str):
    self._file=references.File(paths.QualifiedPath(filename))
    self._name=name
    self._env=env

  def __call__(self, *args:object, **kwargs:object) -> object:
    self._env.LoadFile(self._file)
    if self._env.IsStubOrUndefined(self._name):
      raise exceptions.FatalException(
        f'Invalid stub mapping for {self._name} => {self._file}')
    return typing.cast(typing.Callable,
                       self._env.Get(self._name))(*args, **kwargs)


class RecursiveFileParser(parsed_target.TargetArchive):
  """Loads files based on load() and buildrule statements."""
  def __init__(self, platform:parsed_target.PlatformTarget|None=None,
               **carried_args:object):
    self._carried_args=carried_args
    self._targets:dict[references.Target, parsed_target.BuildTarget]={}
    self._meta_targets:set[str]=set()
    self._loaded_files:set[references.File]=set()
    self._platforms:dict[references.Target, parsed_target.PlatformTarget]={}
    self._platform:parsed_target.PlatformTarget|None=None

    stubs={
      '//rules/builtins/builtins.py': [
        'depends_targets', 'using', 'data', 'toolchain', 'file_reference'],
      '//rules/core/C/build_defs.py': [
        'c_header', 'cpp_header', 'cc_compile', 'cc_combine',
        'cc_package_binary', 'cc_object', 'cc_binary'],
      '//rules/core/Golang/build_defs.py': [
        'go_package', 'go_binary'],
      '//rules/core/JS/build_defs.py': [
        'js_bundle'],
      '//rules/core/TS/build_defs.py': [
        'ts_bundle', 'ts_library', 'ts_binary', 'ts_modules'],
      '//rules/core/Python/build_defs.py': [
        'py_library', 'py_binary', 'py_test'],
      '//rules/core/R/build_defs.py': [
        'r_environment', 'r_process_data'],
      '//rules/core/Shell/build_defs.py': [
        'shell_script'],
      '//rules/core/Template/build_defs.py': [
        'raw_template', 'template', 'template_expand'],
      '//rules/core/Tooling/build_defs.py': [
        'npm_tool'],
      '//rules/env/Docker/build_defs.py': ['container'],
    }

    builtin_methods:dict[str, builtins.BuiltinMethod]={
      'langs': builtins.DeprecationWarning('langs'),
      'load': builtins.LoadFile(),
      'pattern': builtins.Pattern(),
      'buildrule': builtins.BuildRule(self, dict(self._carried_args)),
      'platform': builtins.Platform(self),
      'buildmacro': builtins.BuildMacro(self),
    }

    self._env=LazyEnvironmentLoader(stubs, builtin_methods)

    platpath=references.Target.Parse('//rules/platform:x64-linux-gnu')
    if platform and platform.value():
      platpath=references.Target.Parse(str(platform.value()))
    self.ParsePlatform(platpath)

  def AddMetaTarget(self, target:str) -> None: # type:ignore[override]
    """Adds a meta target."""
    self._meta_targets.add(target)

  def AddPlatformTarget(
    self, target:parsed_target.PlatformTarget
  ) -> parsed_target.PlatformTarget:
    """Adds a platform target."""
    self._platforms[target._name]=target
    return target

  def AddBuildTarget(
    self, target:parsed_target.BuildTarget
  ) -> parsed_target.BuildTarget:
    """Adds a build target."""
    self._targets[target._name]=target
    for dependency in target.GetDependencies():
      self.ParseTarget(dependency)
    return target

  def GetBuildTarget(
    self, name:references.Target
  ) -> parsed_target.BuildTarget:
    """Gets a build target by name."""
    try:
      return self._targets[name]
    except KeyError as e:
      raise exceptions.BuildTargetMissing(e.args[0]) from None

  def GetDefaultPlatformTarget(self) -> parsed_target.PlatformTarget|None:
    """Gets the default platform target."""
    return self._platform

  def SetDefaultPlatformTarget(self,
                               platform:parsed_target.PlatformTarget) -> None:
    """Sets the default platform target."""
    self._platform=platform

  def GetPlatformTarget(
    self, name:references.Target
  ) -> parsed_target.PlatformTarget:
    """Gets a platform target by name."""
    return self._platforms[name]

  def LoadBuildFile(self, file:references.File) -> None:
    """Loads a build file."""
    return self._env.LoadFile(file)

  def GetBuildTargetFromFile(
    self, file:references.File, name:str
  ) -> typing.Callable:
    """Gets a build target from a file."""
    try:
      self.LoadBuildFile(file)
    except exceptions.FileNotFoundException as e:
      raise exceptions.BuildFileNotFoundException(
        buildfile=e.filepath) from None
    try:
      return typing.cast(typing.Callable, self._env.Get(name))
    except Exception:
      raise exceptions.BuildFileMissingTarget(
        buildfile=file.Absolute(), target=name)

  def ParseTarget(self, name:references.Target) -> None:
    """Parses a target."""
    try:
      self._env.LoadFile(name.GetBuildFile())
    except exceptions.FileNotFoundException as e:
      raise exceptions.TargetCannotBeMapped(
        target=name, location=e.filepath) from None

  def ParsePlatform(self, name:references.Target) -> None:
    """Parses a platform target."""
    self.ParseTarget(name)
    assert name in self._platforms
    self._platform=self._platforms[name]

  def StageTarget(self, name:references.Target) -> None:
    """Stages a target."""
    if name not in self._targets:
      raise exceptions.BuildTargetMissing(str(name))
    self._targets[name].Stage(self)

  def GetStagedTargets(self) -> parsed_target.StagedBuildTargetSet:
    """Gets all staged targets."""
    result=parsed_target.StagedBuildTargetSet()
    for _, target in self._targets.items():
      if target._staged:
        result.AddAll(typing.cast(
          parsed_target.StagedBuildTargetSet, target._staged))
    return result

  def _stack_without_recursive_loader(self) -> list[inspect.FrameInfo]:
    return [s for s in inspect.stack()
            if not s.filename.endswith('recursive_loader.py')]

  def _get_buildfile_from_stack(self) -> str:
    build_file='Fake'
    build_file_index=1
    while not build_file.endswith('BUILD'):
      build_file=inspect.stack()[build_file_index].filename
      build_file_index+=1
    return build_file

  def _get_macro_invoker_file(self, k:int=2) -> str:
    starting_index=k # 0 and 1 are the definition of the macro.
    stack=self._stack_without_recursive_loader()
    while starting_index < len(stack):
      if stack[starting_index].filename.endswith('build_defs.py'):
        return stack[starting_index].filename
      if stack[starting_index].filename.endswith('BUILD'):
        return stack[starting_index].filename
      starting_index+=1
    return 'OH FUCK'

  def _get_macro_expansion_site(self) -> str|None:
    for frame in self._stack_without_recursive_loader():
      if frame.filename.endswith('BUILD'):
        return f'{frame.filename}:{frame.lineno}'
    return None

  def _get_macro_expansion_directory(self) -> str|None:
    for frame in self._stack_without_recursive_loader():
      if frame.filename.endswith('BUILD'):
        return os.path.dirname(frame.filename)
    return None

  def GetRulenameFromLoader(self, buildrule:str) -> object:
    """Gets the rule name from the loader."""
    return self._env.Get(buildrule)

  def GetMacroInvokerFile(self) -> str:
    """Gets the file that invoked the macro."""
    return self._get_macro_invoker_file()

  def GetAllConvertedTargets(self,
                              allow_meta:list[str]|bool=False) -> set[object]:
    """Gets all converted targets."""
    allowed_meta:list=[]
    if isinstance(allow_meta, list):
      allowed_meta=allow_meta

    def converted_targets() -> typing.Iterator[object]:
      for target in self._targets.values():
        if getattr(target, '_converted', None):
          rule=getattr(target, '_build_rule', None)
          if rule not in self._meta_targets:
            yield target._converted # type:ignore
          elif allow_meta is True:
            yield target._converted # type:ignore
          elif rule in allowed_meta:
            yield target._converted # type:ignore
          else:
            print(f'target: {rule} not in: {allow_meta}')
    result=set()
    for c in converted_targets():
      if isinstance(c, set):
        result|= c
      else:
        result.add(c)
    return result

  def StageAllTestTargets(self) -> typing.Iterator[references.Target]:
    """Stages all test targets."""
    for target, parsed in self._targets.items():
      if parsed._rule_name.endswith('_test'):
        self.StageTarget(target)
        yield target

  def StageAllTargets(self) -> typing.Iterator[references.Target]:
    """Stages all targets."""
    for target in self._targets.values():
      target.Stage(self)
      yield target._name

  def GetRulenameFromRawTarget(self, targetname:str) -> str|None:
    """Gets the rule name from a raw target name."""
    # This is the buildfile that the rule is called from
    build_file=self._get_buildfile_from_stack()
    build_path=impulse_paths.get_qualified_build_file_dir(build_file)
    build_rule=impulse_paths.convert_to_build_target(targetname, build_path)
    if (isinstance(build_rule, impulse_paths.ParsedTarget) and
        build_rule in self._targets):
      return self._targets[build_rule]._rule_name
    return None


def generate_graph(build_target:impulse_paths.ParsedTarget,
                   platform:parsed_target.PlatformTarget|None=None,
                   **kwargs:object) -> parsed_target.StagedBuildTargetSet:
  """Generates a build graph for the given target."""
  re_parser=RecursiveFileParser(platform, **kwargs)

  btstr=build_target.GetFullyQualifiedRulePath()
  trn=references.Target.Parse(btstr)
  re_parser.ParseTarget(trn)
  re_parser.StageTarget(trn)
  return re_parser.GetStagedTargets()
