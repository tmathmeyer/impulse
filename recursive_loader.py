
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
  """
  Loads files into a shared environment lazily.
  Handles buildrule stubs and restricted imports.
  """
  def __init__(self, stub_map: dict[str, list[str]], builtin_methods: dict[str, builtins.BuiltinMethod]):
    self._loaded_files: set[references.File] = set()
    self._environment: dict[str, typing.Any] = builtin_methods
    for builtin in self._environment.values():
      if isinstance(builtin, builtins.BuiltinMethod):
        builtin.Attach(self)
    for file, names in stub_map.items():
      for name in names:
        self._environment[name] = StubLoader(self, name, file)
    self._environment['__builtins__'] = dict(__builtins__) # type: ignore[unresolved-reference, name-defined]
    self._environment['__builtins__']['__import__'] = self.ImportInjector

  def IsStubOrUndefined(self, key: str) -> bool:
    """Checks if a key is either missing or still a stub."""
    if key not in self._environment:
      return True
    if isinstance(self._environment[key], StubLoader):
      return True
    return False

  def Get(self, key: str) -> typing.Any:
    """Returns the value associated with the key from the environment."""
    return self._environment[key]

  def ImportInjector(self, name: str, locals: dict | None = None, globals: dict | None = None,
                     fromlist: list[str] | None = None, level: int | None = None) -> types.ModuleType:
    """Restricts imports in BUILD files and rule files to allowed targets."""
    # declare allowed imports along with special cases used when importing from them
    allowed_import_targets = {
      # Stubs are just documented function stubs for the decorators used in declaring buildrules
      'impulse.types.stubs': {
        'os': lambda target: __import__(target),
        'Any': lambda _: None,
      },

      # Interfaces are essentially just classes which can be used for type annotations in buildrules
      'impulse.types.interfaces': {
        'Package': lambda _: None
      }
    }

    if name not in allowed_import_targets:
      raise Exception(f'buildrule definitions may only import from {list(allowed_import_targets.keys())}, not {name}')

    synthetic_module = types.ModuleType(name)
    special_cases = allowed_import_targets[name]
    for target in (fromlist or []):
      if target in special_cases:
        synthetic_module.__dict__[target] = special_cases[target](target)
      elif target in self._environment:
        synthetic_module.__dict__[target] = self._environment.get(target)
      else:
        raise Exception(f'`{target}` could not be imported from `{name}`')
    return synthetic_module

  def LoadFile(self, file: references.File) -> None:
    """Loads and executes a file into the shared environment."""
    if file in self._loaded_files:
      return
    self._loaded_files.add(file)

    abspath = file.Absolute().Value()
    try:
      with open(abspath) as f:
        buildfile_content = f.read()
    except FileNotFoundError:
      raise exceptions.FileNotFoundException(filepath=abspath, relpath=file) from None

    try:
      compiled = compile(buildfile_content, abspath, 'exec')
      exec(compiled, self._environment)
    except NameError as e:
      _, _, traceback = sys.exc_info()
      assert traceback is not None
      previous_frame = traceback.tb_next.tb_frame # type: ignore[union-attr]
      filename = previous_frame.f_code.co_filename
      line_no = previous_frame.f_lineno
      missing_name = e.args[0].split('\'')[1]
      raise errors.FileHighlightError(f'Invalid symbol: `{missing_name}`',
                                      filename, missing_name, line_no, line_no)
    except AttributeError as e:
      _, _, traceback = sys.exc_info()
      assert traceback is not None
      # Walk up the traceback to find the actual call site in the loaded file
      tb: types.TracebackType | None = traceback
      while tb and tb.tb_next:
        tb = tb.tb_next
      filename = tb.tb_frame.f_code.co_filename if tb else abspath
      line_no = tb.tb_frame.f_lineno if tb else 1
      raise errors.FileHighlightError(f'Attribute error: {str(e)}',
                                      filename, str(e).split()[-1].strip("'"), line_no, line_no)
    except exceptions.FileLoadException as e:
      raise e.Chain(abspath) from None
    except Exception as e:
      _, _, traceback = sys.exc_info()
      assert traceback is not None
      tb = traceback
      while tb and tb.tb_next:
        tb = tb.tb_next
      filename = tb.tb_frame.f_code.co_filename if tb else abspath
      line_no = tb.tb_frame.f_lineno if tb else 1
      raise errors.FileHighlightError(f'Error during file execution: {str(e)}',
                                      filename, '', line_no, line_no)


class StubLoader(object):
  def __init__(self, env:LazyEnvironmentLoader, name:str, filename:str):
    self._file = references.File(paths.QualifiedPath(filename).AbsPath())
    self._name = name
    self._env = env

  def __call__(self, *args, **kwargs):
    self._env.LoadFile(self._file)
    if self._env.IsStubOrUndefined(self._name):
      raise exceptions.FatalException(
        f'Invalid stub mapping for {self._name} => {self._file}')
    return self._env.Get(self._name)(*args, **kwargs)


class RecursiveFileParser(parsed_target.TargetArchive):
  """Loads files based on load() and buildrule statements."""
  def __init__(self, platform: impulse_paths.BuildTarget | None = None, **carried_args: typing.Any):
    self._carried_args = carried_args
    self._targets: dict[references.Target, parsed_target.BuildTarget] = {}
    self._meta_targets: set[str] = set()
    self._loaded_files: set[references.File] = set() # We don't want to load files multiple times
    self._platforms: dict[references.Target, parsed_target.PlatformTarget] = {} # All the so-far-declared platforms
    self._platform: parsed_target.PlatformTarget | None = None # The selected platform

    stubs = {
      '//rules/builtins/builtins.py': [
        'depends_targets', 'using', 'data', 'toolchain', 'file_reference'],
      '//rules/core/C/build_defs.py': [
        'c_header', 'cpp_header', 'cc_compile', 'cc_combine', 'cc_package_binary', 'cc_object', 'cc_binary'],
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

    builtin_methods: dict[str, typing.Any] = {
      'langs': builtins.DeprecationWarning('langs'),
      'load': builtins.LoadFile(),
      'pattern': builtins.Pattern(),
      'buildrule': builtins.BuildRule(self, dict(self._carried_args)),
      'platform': builtins.Platform(self),
      'buildmacro': builtins.BuildMacro(self),
    }

    self._env = LazyEnvironmentLoader(stubs, builtin_methods)

    platpath = references.Target.Parse('//rules/platform:x64-linux-gnu')
    if platform and platform.value():
      platpath = references.Target.Parse(platform.value())
    self.ParsePlatform(platpath)

  def AddMetaTarget(self, target: str) -> None: # type: ignore[override]
    """Adds a meta target generated through a buildmacro."""
    self._meta_targets.add(target)

  def AddPlatformTarget(self, target: parsed_target.PlatformTarget) -> parsed_target.PlatformTarget:
    """Adds a platform target to the parser."""
    self._platforms[target._name] = target
    return target

  def AddBuildTarget(self, target: parsed_target.BuildTarget) -> parsed_target.BuildTarget:
    """Adds a build target to the parser and recursively parses its dependencies."""
    self._targets[target._name] = target
    for dependency in target.GetDependencies():
      self.ParseTarget(dependency)
    return target

  def GetBuildTarget(self, name: references.Target) -> parsed_target.BuildTarget:
    """Returns a build target by name."""
    try:
      return self._targets[name]
    except KeyError as e:
      raise exceptions.BuildTargetMissing(e.args[0]) from None

  def GetDefaultPlatformTarget(self) -> parsed_target.PlatformTarget:
    """Returns the default platform target."""
    assert self._platform is not None
    return self._platform

  def SetDefaultPlatformTarget(self, platform: parsed_target.PlatformTarget) -> None:
    """Sets the default platform target."""
    self._platform = platform

  def GetPlatformTarget(self, name: references.Target) -> parsed_target.PlatformTarget:
    """Returns a platform target by name."""
    return self._platforms[name]

  def LoadBuildFile(self, file: references.File) -> None:
    """Loads a BUILD file."""
    return self._env.LoadFile(file)

  def GetBuildTargetFromFile(self, file: references.File, name: str) -> typing.Callable:
    """Returns a build rule function from a specific file."""
    try:
      self.LoadBuildFile(file)
    except exceptions.FileNotFoundException as e:
      raise exceptions.BuildFileNotFoundException(buildfile=e.filepath) from None
    try:
      return self._env.Get(name)
    except:
      raise exceptions.BuildFileMissingTarget(buildfile=file.Absolute().Value(), target=name)

  def ParseTarget(self, name: references.Target) -> None:
    """Parses the BUILD file that defines the given target."""
    try:
      self._env.LoadFile(name.GetBuildFile())
    except exceptions.FileNotFoundException as e:
      raise exceptions.TargetCannotBeMapped(target=str(name), location=e.filepath) from None

  def ParsePlatform(self, name: references.Target) -> None:
    """Parses and selects a platform target."""
    self.ParseTarget(name)
    assert name in self._platforms
    self._platform = self._platforms[name]

  def StageTarget(self, name: references.Target) -> None:
    """Stages a target for execution."""
    if name not in self._targets:
      raise exceptions.BuildTargetMissing(str(name))
    self._targets[name].Stage(self)

  def GetStagedTargets(self) -> parsed_target.StagedBuildTargetSet:
    """Returns the set of all staged build targets."""
    result = parsed_target.StagedBuildTargetSet()
    for _, target in self._targets.items():
      if target._staged and isinstance(target._staged, parsed_target.StagedBuildTargetSet):
        result.AddAll(target._staged)
    return result

  def _stack_without_recursive_loader(self) -> list[inspect.FrameInfo]:
    return [s for s in inspect.stack()
            if not s.filename.endswith('recursive_loader.py')]

  def _get_buildfile_from_stack(self):
    build_file = 'Fake'
    build_file_index = 1
    while not build_file.endswith('BUILD'):
      build_file = inspect.stack()[build_file_index].filename
      build_file_index += 1
    return build_file

  def _get_macro_invoker_file(self, k=2):
    starting_index = k # 0 and 1 are the definition of the macro.
    stack = self._stack_without_recursive_loader()
    while starting_index < len(stack):
      if stack[starting_index].filename.endswith('build_defs.py'):
        return stack[starting_index].filename
      if stack[starting_index].filename.endswith('BUILD'):
        return stack[starting_index].filename
      starting_index += 1
    return 'OH FUCK'

  def _get_macro_expansion_site(self):
    for frame in self._stack_without_recursive_loader():
      if frame.filename.endswith('BUILD'):
        return f'{frame.filename}:{frame.lineno}'

  def _get_macro_expansion_directory(self):
    for frame in self._stack_without_recursive_loader():
      if frame.filename.endswith('BUILD'):
        return os.path.dirname(frame.filename)

  def GetRulenameFromLoader(self, buildrule: str) -> typing.Any:
    """Returns the rule function from the loader's environment."""
    return self._env._environment.get(buildrule)

  def GetMacroInvokerFile(self):
    return self._get_macro_invoker_file()

  def GetAllConvertedTargets(self, allow_meta:list[str]|bool=False):
    allowed_meta:list = []
    if type(allow_meta) is list:
      allowed_meta = allow_meta
    def converted_targets():
      for target in self._targets.values():
        if target._converted:
          if target._build_rule not in self._meta_targets:
            yield target._converted
          elif allow_meta is True:
            yield target._converted
          elif target._build_rule in allowed_meta:
            yield target._converted
          else:
            print(f'target: {target._build_rule} not in: {allow_meta}')
    result = set()
    for c in converted_targets():
      result |= c
    return result

  def StageAllTestTargets(self):
    for target, parsed in self._targets.items():
      if parsed._rule_name.endswith('_test'):
        self.StageTarget(target)
        yield target

  def StageAllTargets(self):
    for target in self._targets.values():
      target.Stage(self)
      yield target

  def GetRulenameFromRawTarget(self, targetname: str) -> str | None:
    """Returns the rule name for a raw target string."""
    # This is the buildfile that the rule is called from
    build_file = self._get_buildfile_from_stack()
    build_path = impulse_paths.get_qualified_build_file_dir(build_file)
    build_rule = impulse_paths.convert_to_build_target(targetname, build_path)
    if isinstance(build_rule, references.Target) and build_rule in self._targets:
      return self._targets[build_rule]._rule_name
    return None


def generate_graph(build_target:impulse_paths.ParsedTarget,
                   platform=None,
                   **kwargs):
  re = RecursiveFileParser(platform, **kwargs)

  btstr = build_target.GetFullyQualifiedRulePath()
  trn = references.Target.Parse(btstr)
  re.ParseTarget(trn)
  re.StageTarget(trn)
  return re.GetStagedTargets()
