
import glob
import inspect
import os
import sys
import typing

from impulse import impulse_paths

from impulse.core import debug
from impulse.core import exceptions
from impulse.loaders import buildmacro
from impulse.types import typecheck
from impulse.types import parsed_target
from impulse.types import paths


INVALID_RULE_RECURSION_CANARY = object()


def GetCallSite() -> tuple[str, int]:
  caller = inspect.stack()[2]
  return caller.filename, caller.lineno


class EnvironmentLoader(object):
  pass


class BuiltinMethod(object):
  def __init__(self):
    self._loader = None

  @typecheck.Assert
  def Attach(self, loader:EnvironmentError) -> None:
    self._loader = loader

  def _get_buildfile_from_stack(self):
    build_file = 'Fake'
    build_file_index = 1
    while not build_file.endswith('BUILD'):
      build_file = inspect.stack()[build_file_index].filename
      build_file_index += 1
    return build_file


class DeprecationWarning(BuiltinMethod):
  def __init__(self, method:str):
    super().__init__()
    self._method = method

  def __call__(self, *_, **__):
    file, line = GetCallSite()
    debug.DebugMsg(f'[{file}:{line}]: The {self._method} method is deprecated')


class LoadFile(BuiltinMethod):
  def __call__(self, *files):
    for loading in files:
      self._loader.LoadFile(impulse_paths.expand_fully_qualified_path(loading))


class Pattern(BuiltinMethod):
  @typecheck.Assert
  def _get_buildfile_from_stack(self) -> str:
    build_file = 'Fake'
    build_file_index = 1
    while not build_file.endswith('BUILD'):
      build_file = inspect.stack()[build_file_index].filename
      build_file_index += 1
    return build_file

  def __call__(self, pattern:str):
    build_file = self._get_buildfile_from_stack()
    build_directory = impulse_paths.get_qualified_build_file_dir(build_file)
    build_directory = impulse_paths.expand_fully_qualified_path(build_directory)
    pattern = os.path.join(build_directory, pattern)
    try:
      files = glob.glob(pattern)
      files = [f[len(build_directory)+1:] for f in files]
      return files
    except Exception as e:
      return []


class Platform(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive):
    self._archive = archive

  def __call__(self, **kwargs):
    assert 'name' in kwargs
    name = kwargs['name']
    build_file = self._get_buildfile_from_stack()
    reference_name = parsed_target.GetTargetReferenceFromInvocation(
      parsed_target.TargetLocalName(name),
      paths.AbsolutePath(build_file))
    return self._archive.AddPlatformTarget(parsed_target.PlatformTarget(
      reference_name, **kwargs))


class BuildRule(BuiltinMethod):
  def __init__(self, archive:parsed_target.TargetArchive, cmdline:dict):
    self.______thing = archive
    self._archive = archive
    self._cmdline = cmdline

  def __call__(self, fn):
    # Store the type of buildrule
    buildrule_name = fn.__name__

    #debug.DebugMsg(f'Registering build rule: {buildrule_name}')

    # all params to a build rule must be keyword!
    def replacement(DBBG=False, **kwargs):
      # 'name' is a required argument!
      assert 'name' in kwargs
      name = kwargs['name']

      # add any extra tags a user sers
      extra_tags = kwargs.get('tags', [])

      # This is the buildfile that the rule is called from
      build_file = kwargs.get('buildfile', self._get_buildfile_from_stack())

      reference_name = parsed_target.GetTargetReferenceFromInvocation(
        parsed_target.TargetLocalName(name),
        paths.AbsolutePath(build_file))

      return self._archive.AddBuildTarget(
        parsed_target.BuildTarget(
          reference_name, fn, kwargs, self._cmdline, extra_tags))

    return replacement


class BuildMacro(BuiltinMethod):
  def __init__(self, thing):
    self.______thing = thing

  def __call__(self, fn):
    return buildmacro.Buildmacro(self.______thing, fn)


class LazyEnvironmentLoader(EnvironmentLoader):
  def __init__(self, stub_map:dict[str, list[str]], builtins:dict[str, BuiltinMethod]):
    self._loaded_files = set()
    self._environment = builtins
    for builtin in self._environment.values():
      builtin.Attach(self)
    for file, names in stub_map.items():
      for name in names:
        self._environment[name] = StubLoader(self, name, file)

  def IsStubOrUndefined(self, key:str) -> bool:
    if key not in self._environment:
      return True
    if isinstance(self._environment[key], StubLoader):
      return True
    return False

  def Get(self, key:str) -> typing.Any:
    return self._environment[key]

  def LoadFile(self, file_path:str):
    if file_path in self._loaded_files:
      return
    self._loaded_files.add(file_path)
    try:
      with open(file_path) as f:
        buildfile_content = f.read()
    except FileNotFoundError as e:
      raise exceptions.FileImportException(e, file_path)

    try:
      compiled = compile(buildfile_content, file_path, 'exec')
      exec(compiled, self._environment)
    except NameError as e:
      _, _, traceback = sys.exc_info()
      previous_frame = traceback.tb_next.tb_frame
      filename = previous_frame.f_code.co_filename
      line_no = previous_frame.f_lineno
      missing_name = e.args[0].split('\'')[1]
      raise exceptions.NoSuchRuleType(filename, line_no, missing_name)
    except Exception as e:
      raise exceptions.FileImportException(e, file_path)


class StubLoader(object):
  def __init__(self, env:LazyEnvironmentLoader, name:str, filename:str):
    self._filename = impulse_paths.expand_fully_qualified_path(filename)
    self._name = name
    self._env = env

  def __call__(self, *args, **kwargs):
    self._env.LoadFile(self._filename)
    if self._env.IsStubOrUndefined(self._name):
      raise exceptions.FatalException(
        f'Invalid stub mapping for {self._name} => {self._filename}')
    return self._env.Get(self._name)(*args, **kwargs)


class RecursiveFileParser(parsed_target.TargetArchive):
  """Loads files based on load() and buildrule statements."""
  def __init__(self, platform=None, **carried_args):
    self._carried_args = carried_args
    self._targets:dict[parsed_target.TargetReferenceName, parsed_target.BuildTarget] = {}
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

    builtins = {
      'langs': DeprecationWarning('langs'),
      'load': LoadFile(),
      'pattern': Pattern(),
      'buildrule': BuildRule(self, dict(self._carried_args)),
      'platform': Platform(self),
      'buildmacro': BuildMacro(self),
    }

    self._env = LazyEnvironmentLoader(stubs, builtins)

    platpath = parsed_target.ParseTargetReferenceFromString(
      '//rules/platform:x64-linux-gnu')
    if platform and platform.value():
      #self.ParsePlatform(platform.value())
      platpath = parsed_target.ParseTargetReferenceFromString(
        platform.value())

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

  def GetBuildTarget(self, name:parsed_target.TargetReferenceName) -> parsed_target.Target:
    return self._targets[name]

  def GetDefaultPlatformTarget(self) -> parsed_target.Target:
    return self._platform

  def SetDefaultPlatformTarget(self, platform:parsed_target.PlatformTarget):
    self._platform = platform

  def GetPlatformTarget(self, name:parsed_target.TargetReferenceName) -> parsed_target.Target:
    return self._platforms[name]

  @typecheck.Assert
  def ParseTarget(self, name:parsed_target.TargetReferenceName) -> None:
    #TODO: make LoadFile take an AbsolutePath
    self._env.LoadFile(name.GetBuildFileForTarget().Value())

  @typecheck.Assert
  def ParsePlatform(self, name:parsed_target.TargetReferenceName) -> None:
    self.ParseTarget(name)
    assert name in self._platforms
    self._platform = self._platforms[name]

  @typecheck.Assert
  def StageTarget(self, name:parsed_target.TargetReferenceName) -> None:
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
  trn = parsed_target.ParseTargetReferenceFromString(btstr)

  re.ParseTarget(trn)
  re.StageTarget(trn)

  targets = re.GetStagedTargets()._targets

  for target in targets:
    print(target, len(target.dependencies))

  #return targets
  return targets

  #re.StageTarget(build_target)
  #return re.GetAllConvertedTargets(allow_meta=True)
  return set()