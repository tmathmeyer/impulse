
import inspect
import os
import sys
import typing

from impulse import impulse_paths

from impulse.core import exceptions
from impulse.types import builtins
from impulse.types import references
from impulse.types import parsed_target
from impulse.types import paths
from impulse.types import typecheck


class LazyEnvironmentLoader(builtins.EnvironmentLoader):
  def __init__(self, stub_map:dict[str, list[str]], builtin_methods:dict[str, builtins.BuiltinMethod]):
    self._loaded_files = set()
    self._environment = builtin_methods
    for builtin in self._environment.values():
      builtin.Attach(self)
    for file, names in stub_map.items():
      for name in names:
        self._environment[name] = StubLoader(self, name, file)

  @typecheck.Assert
  def IsStubOrUndefined(self, key:str) -> bool:
    if key not in self._environment:
      return True
    if isinstance(self._environment[key], StubLoader):
      return True
    return False

  @typecheck.Assert
  def Get(self, key:str) -> typing.Any:
    return self._environment[key]

  @typecheck.Assert
  def LoadFile(self, file:references.File) -> None:
    if file in self._loaded_files:
      return
    self._loaded_files.add(file)

    abspath = file.Absolute().Value()
    try:
      with open(abspath) as f:
        buildfile_content = f.read()
    except FileNotFoundError as e:
      raise exceptions.FileImportException(e, file)

    try:
      compiled = compile(buildfile_content, abspath, 'exec')
      exec(compiled, self._environment)
    except NameError as e:
      _, _, traceback = sys.exc_info()
      previous_frame = traceback.tb_next.tb_frame
      filename = previous_frame.f_code.co_filename
      line_no = previous_frame.f_lineno
      missing_name = e.args[0].split('\'')[1]
      raise exceptions.NoSuchRuleType(filename, line_no, missing_name)
    except Exception as e:
      raise exceptions.FileImportException(e, file)


class StubLoader(object):
  def __init__(self, env:LazyEnvironmentLoader, name:str, filename:str):
    self._file = references.File(paths.QualifiedPath(filename).AbsolutePath())
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
  def __init__(self, platform=None, **carried_args):
    self._carried_args = carried_args
    self._targets:dict[references.Target, parsed_target.BuildTarget] = {}
    self._meta_targets = set() # Set[str]
    self._loaded_files = set() # We don't want to load files multiple times
    self._platforms = {} # All the so-far-declared platforms
    self._platform = None # The selected platform

    stubs = {
      '//rules/builtins/builtins.py': [
        'depends_targets', 'using', 'data', 'toolchain'],
      '//rules/core/C/build_defs.py': [
        'c_header', 'cpp_header', 'cc_compile', 'cc_combine', 'cc_package_binary', 'cc_object', 'cc_binary'],
      '//rules/core/Golang/build_defs.py': [
        'go_package', 'go_binary'],
      '//rules/core/JS/build_defs.py': [
        'js_module'],
      '//rules/core/Python/build_defs.py': [
        'py_library', 'py_binary', 'py_test'],
      '//rules/core/R/build_defs.py': [
        'r_environment', 'r_process_data'],
      '//rules/core/Shell/build_defs.py': [
        'shell_script'],
      '//rules/core/Template/build_defs.py': [
        'raw_template', 'template', 'template_expand'],
    }

    builtin_methods = {
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

  def AddMetaTarget(self, target:None):
    self._meta_targets.add(target)

  def AddPlatformTarget(self, target:parsed_target.PlatformTarget) -> parsed_target.PlatformTarget:
    self._platforms[target._name] = target
    return target

  def AddBuildTarget(self, target:parsed_target.BuildTarget) -> parsed_target.BuildTarget:
    self._targets[target._name] = target
    for dependency in target.GetDependencies():
      self.ParseTarget(dependency)
    return target

  def GetBuildTarget(self, name:references.Target) -> parsed_target.Target:
    return self._targets[name]

  def GetDefaultPlatformTarget(self) -> parsed_target.Target:
    return self._platform

  def SetDefaultPlatformTarget(self, platform:parsed_target.PlatformTarget):
    self._platform = platform

  def GetPlatformTarget(self, name:references.Target) -> parsed_target.Target:
    return self._platforms[name]

  def GetBuildTargetFromFile(self, file:references.File, name:str) -> typing.Callable:
    self._env.LoadFile(file)
    return self._env.Get(name)

  @typecheck.Assert
  def ParseTarget(self, name:references.Target) -> None:
    #TODO: make LoadFile take an AbsolutePath
    self._env.LoadFile(name.GetBuildFile())

  @typecheck.Assert
  def ParsePlatform(self, name:references.Target) -> None:
    self.ParseTarget(name)
    assert name in self._platforms
    self._platform = self._platforms[name]

  @typecheck.Assert
  def StageTarget(self, name:references.Target) -> None:
    if name not in self._targets:
      raise exceptions.BuildTargetMissing(name)
    self._targets[name].Stage(self)

  @typecheck.Assert
  def StageAllTargets(self) -> None:
    for target in self._targets.values():
      target.Stage(self)

  @typecheck.Assert
  def GetStagedTargets(self) -> parsed_target.StagedBuildTargetSet:
    result = parsed_target.StagedBuildTargetSet()
    for _, target in self._targets.items():
      if target._staged:
        result.AddAll(target._staged)
    return result




  def _stack_without_recursive_loader(self):
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

  def GetRulenameFromLoader(self, buildrule:str):
    return self._environ.get(buildrule)

  def GetMacroInvokerFile(self):
    return self._get_macro_invoker_file()

  def GetAllConvertedTargets(self, allow_meta=None):
    allow_meta = allow_meta or []
    def converted_targets():
      for target in self._targets.values():
        if target._converted:
          if target._build_rule not in self._meta_targets:
            yield target._converted
          elif allow_meta is True:
            yield target._converted
          elif target._build_rule in allow_meta:
            yield target._converted
          else:
            print(f'target: {target._build_rule} not in: {allow_meta}')
    result = set()
    for c in converted_targets():
      result |= c
    return result

  def ConvertAllTestTargets(self):
    for target, parsed in self._targets.items():
      if parsed._rule_type.endswith('_test'):
        self.StageTarget(target)
        yield target

  def GetRulenameFromRawTarget(self, targetname) -> str:
    # This is the buildfile that the rule is called from
    build_file = self._get_buildfile_from_stack()
    build_path = impulse_paths.get_qualified_build_file_dir(build_file)
    build_rule = impulse_paths.convert_to_build_target(targetname, build_path)
    if build_rule in self._targets:
      return self._targets[build_rule]._rule_type
    return None


def generate_graph(build_target:impulse_paths.ParsedTarget,
                   allow_meta:bool=False,
                   platform=None,
                   **kwargs):
  allow_meta = allow_meta or [build_target]
  re = RecursiveFileParser(platform, **kwargs)

  btstr = build_target.GetFullyQualifiedRulePath()
  trn = references.Target.Parse(btstr)
  re.ParseTarget(trn)
  re.StageTarget(trn)
  targets = re.GetStagedTargets()._targets
  return targets
