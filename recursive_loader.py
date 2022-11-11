
import glob
import inspect
import marshal
import os
import sys

from impulse import impulse_paths
from impulse import build_target

from impulse.core import debug
from impulse.core import exceptions
from impulse.loaders import buildmacro
from impulse.util import resources
from impulse.util import typecheck


INVALID_RULE_RECURSION_CANARY = object()


class ParsedBuildTarget(object):
  def __init__(self, name, func, args, build_rule, ruletype, evaluator,
               carried_args, extra_tags):
    self._func = marshal.dumps(func.__code__)
    self._name = name
    self._args = args
    self._build_rule = build_rule
    self._rule_type = ruletype
    self._evaluator = evaluator
    self._carried_args = carried_args
    self._extra_tags = extra_tags
    self._converted = None
    self._scope = {}

  def Convert(self, platform):
    # If we try to convert this rule again while conversion is in progress
    # we need to fail, as a cyclic graph can't be built. Conversion is
    # single threaded, so this test-and-set will suffice.
    if self._converted is INVALID_RULE_RECURSION_CANARY:
      raise exceptions.BuildTargetCycle.Cycle(self)
    if not self._converted:
      self._converted = INVALID_RULE_RECURSION_CANARY
      try:
        self._converted = self._CreateConverted(platform)
      except exceptions.BuildTargetCycle as e:
        raise e.ChainException(self)
    return self._converted

  def _update_arg_dependencies_get_list(self):
    def iterate(update_object, probably):
      if type(update_object) == dict:
        replace = {}
        result = []
        for k, v in update_object.items():
          recrep, recres = iterate(v, probably)
          replace[k] = recrep
          result += recres
        return replace, result
      elif type(update_object) in (list, tuple):
        replace = []
        result = []
        for v in update_object:
          recrep, recres = iterate(v, probably)
          replace.append(recrep)
          result += recres
        return replace, result
      else:
        x = probably(update_object)
        if x is not None:
          return x, [x]
        return update_object, []
    def is_buildrule(txt):
      try:
        return impulse_paths.convert_to_build_target(
          txt, self._build_rule.target_path, True)
      except:
        return None
    self._args, result = iterate(self._args, is_buildrule)
    return result

  def GetDependencies(self):
    return list(self._update_arg_dependencies_get_list())

  def _CreateConverted(self, platform):
    # set(build_target.BuildTarget)
    dependencies = set()
    # Convert all 'deps' into edges between BuildTargets
    for target in self._update_arg_dependencies_get_list():
      try:
        dependencies |= self._evaluator.ConvertTarget(target)
      except exceptions.BuildTargetMissing:
        raise exceptions.BuildTargetMissingFrom(
          str(target), self._build_rule) from None

    # Create a BuildTarget graph node
    return set([build_target.BuildTarget(
      self._name, self._func, self._args, self._build_rule,
      self._rule_type, self._scope, dependencies, platform,
      self._extra_tags, **self._carried_args)])

  def AddScopes(self, funcs):
    if self._converted:
      raise "TOO LATE" # TODO raise a real error...
    for func in funcs:
      self._scope[func.__name__] = (marshal.dumps(func.__code__))
    return self

  def GetName(self):
    return str(self._name)


def increase_stack_arg_decorator(replacement):
  # This converts 'replacement' into a decorator that takes args
  def _superdecorator(self, *args, **kwargs):
    # This is the actual 'decorator' which gets called
    def _decorator(fn):
      # This is what replacement would have created to decorate the function
      replaced = replacement(self, fn, *args, **kwargs)
      # This is what the decorated function is replaced with
      def newfn(*args, **kwargs):
        kwargs['__stack__'] = kwargs.get('__stack__', 1) + 2
        replaced(*args, **kwargs)
      return newfn
    return _decorator
  return _superdecorator


def _data_buildrule(target, name, srcs):
  target.SetTags('data')
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))


def _transform_rule(target, name, tags, rule, tool=None):
  target.SetTags(*tags)
  import subprocess
  
  rule = next(target.Dependencies(
    package_target=rule.GetFullyQualifiedRulePath()))
  tool_pkg = next(target.Dependencies(
    package_target=tool.GetFullyQualifiedRulePath()), None)

  if tool_pkg is not None and 'exe' not in tool_pkg.tags:
    target.ExecutionFailed('', f'{tool} is not an executable')

  for f in rule.IncludedFiles():
    if tool_pkg:
      command = f'bin/{tool.target_name} {f}'
      result = subprocess.run(command,
        encoding='utf-8', shell=True,
        stderr=subprocess.PIPE, stdout=subprocess.PIPE)
      if result.returncode:
        target.ExecutionFailed(command, result.stderr)
      for outputfile in result.stdout.split('\n'):
        if outputfile.strip():
          target.AddFile(outputfile.strip())
    else:
      target.AddFile(f)


def _toolchain_rule(target, name, srcs, links, **args):
  target.SetTags('toolchain')
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))

  for link in links:
    linkname = os.path.join(target.GetPackageDirectory(), link)
    linktarget = os.path.join(impulse_paths.root(), linkname)
    os.system(f'ln -sf {linktarget} {linkname}')
    target.AddFile(linkname)


class RecursiveFileParser(object):
  """Loads files based on load() and buildrule statements."""
  def __init__(self, platform=None, **carried_args):
    self._carried_args = carried_args
    self._targets = {} # Map[BuildTarget->ParsedBuildTarget]
    self._meta_targets = set() # Set[str]
    self._loaded_files = set() # We don't want to load files multiple times
    self._platforms = {} # All the so-far-declared platforms
    self._platform = None # The selected platform

    # We need to store the environment across compilations, since it allows
    # files to call eachother's functions.
    self._environ = {
      'load': self._load_files,
      'buildrule': self._buildrule,
      'buildmacro': self._buildmacro,
      'using': self._using,
      'pattern': self._find_files_pattern,
      'depends_targets': self._depends_on_targets,
      'data': self._buildrule(_data_buildrule),
      'git_repo': build_target.ParsedGitTarget,
      'langs': self._load_core_langs,
      'transform': self._buildrule(_transform_rule),
      'toolchain': self._buildrule(_toolchain_rule),
      'platform': self._generate_platform_config,
    }

    if platform and platform.value():
      self.ParsePlatform(platform.value())
    else:
      self.ParsePlatform('//rules/platform:x64-linux-gnu')

  def ParsePlatform(self, platstr):
    plat_target = impulse_paths.convert_to_build_target(
      platstr, impulse_paths.relative_pwd(), True)
    self.ParseTarget(plat_target)
    assert plat_target in self._platforms
    self._platform = self._platforms[plat_target]

  def ParseTarget(self, target: impulse_paths.ParsedTarget):
    target.ParseFile(self, self._ParseFile)

  def ConvertTarget(self, target):
    if target not in self._targets:
      raise exceptions.BuildTargetMissing(target)
    return self._targets[target].Convert(self._platform)

  def _ParseFile(self, file: str):
    return self._ParseFileFromLocation(file, file)

  def _ParseFileFromLocation(self, file:str, location:str):
    if debug.IsDebug():
      print(f'Loading File: {file}')
    if file not in self._loaded_files:
      self._loaded_files.add(file)
      try:
        with open(location) as f:
          try:
            exec(compile(f.read(), location, 'exec'), self._environ)
          except NameError as e:
            # TODO: this needs to be fixed, since there could be _other_ name
            # errors, not just rule-not-found ones.
            _, _, traceback = sys.exc_info()
            # drop the frame that is just this file calling exec above.
            previous_frame = traceback.tb_next.tb_frame
            filename = previous_frame.f_code.co_filename
            line_no = previous_frame.f_lineno
            missing_name = e.args[0].split('\'')[1]
            raise exceptions.NoSuchRuleType(filename, line_no, missing_name)
          except Exception as e:
            # Wrap any exception that we get, so we don't have crashes
            raise exceptions.FileImportException(e, file)
      except FileNotFoundError as e:
        # Wrap any exception that we get, so we don't have crashes
        raise exceptions.FileImportException(e, file)

  def _generate_platform_config(self, **kwargs):
    assert 'name' in kwargs
    name = kwargs['name']
    build_file = self._get_buildfile_from_stack()
    build_path = impulse_paths.get_qualified_build_file_dir(build_file)
    build_rule = impulse_paths.convert_name_to_build_target(name, build_path)
    self._platforms[build_rule] = impulse_paths.Platform(
      platform_target=repr(build_rule), **kwargs)

  @increase_stack_arg_decorator
  def _depends_on_targets(self, fn, *targets):
    """Used to decorate a buildrule to state that _all_ targets of that type
       must also depend on the set of targets listed here."""
    def replacement(*args, **kwargs):
      # join the dependencies and call the wrapped function.
      kwargs['deps'] = kwargs.get('deps', []) + list(targets)
      return fn(*args, **kwargs)
    return replacement

  @increase_stack_arg_decorator
  def _using(self, fn, *includes):
    """Used to decorate a buildrule to allow it to call other functions in the
       build_defs file. Normally each function is a separate functional unit."""
    def replacement(*args, **kwargs):
      return fn(*args, **kwargs).AddScopes(includes)
    return replacement

  def _find_files_pattern(self, p):
    build_file = self._get_buildfile_from_stack()
    build_directory = impulse_paths.get_qualified_build_file_dir(build_file)
    build_directory = impulse_paths.expand_fully_qualified_path(build_directory)
    pattern = os.path.join(build_directory, p)
    try:
      files = glob.glob(pattern)
      files = [f[len(build_directory)+1:] for f in files]
      return files
    except Exception as e:
      return []

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

  def _buildmacro(self, fn):
    return buildmacro.Buildmacro(self, fn)

  def _buildrule(self, fn):
    """Decorates a function allowing it to be used as a target buildrule."""
    
    # Store the type of buildrule
    buildrule_name = fn.__name__

    if debug.IsDebug():
      print(f'Adding Buildrule: {buildrule_name}')

    # all params to a build rule must be keyword!
    def replacement(DBBG=False, **kwargs):
      # 'name' is a required argument!
      assert 'name' in kwargs
      name = kwargs['name']

      # add any extra tags a user sers
      extra_tags = kwargs.get('tags', [])

      # This is the buildfile that the rule is called from
      build_file = kwargs.get('buildfile', self._get_buildfile_from_stack())

      # Directory of the buildfile
      build_path = impulse_paths.get_qualified_build_file_dir(build_file)

      # This is an 'impulse_paths.ParsedTarget' object
      build_rule = impulse_paths.convert_name_to_build_target(name, build_path)

      # Create a ParsedBuildTarget which can be converted into the graph later.
      self._targets[build_rule] = ParsedBuildTarget(
        name, fn, kwargs, build_rule, buildrule_name,
        self, self._carried_args, extra_tags)

      # Parse the dependencies and evaluate them too.
      for dep in self._targets[build_rule].GetDependencies():
        self.ParseTarget(dep)

      # The wrapper functions (using, depends, etc) need the ParsedBuildTarget
      return self._targets[build_rule]

    return replacement

  def _load_files(self, *args):
    for loading in args:
      self._ParseFile(impulse_paths.expand_fully_qualified_path(loading))

  def _load_core_langs(self, *args):
    for file in args:
      expanded = impulse_paths.expand_fully_qualified_path(
        f'//rules/core/{file}/build_defs.py')
      try:
        self._ParseFile(expanded)
      except FileNotFoundError as e:
        self._loaded_files.remove(expanded)
        embeddedPath = f'impulse/rules/core/{file}/build_defs.py'
        embeddedBuildDef = resources.Resources.Get(embeddedPath)
        self._ParseFileFromLocation(expanded, embeddedBuildDef)

  def LoadFile(self, rulefile:str):
    return self._load_files(rulefile)

  def GetRulenameFromLoader(self, buildrule:str):
    return self._environ.get(buildrule)

  def GetMacroInvokerFile(self):
    return self._get_macro_invoker_file()

  def AddMetaTarget(self, target):
    self._meta_targets.add(target)

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
        self.ConvertTarget(target)
        yield target

  def ConvertAllTargets(self):
    for target, parsed in self._targets.items():
      if target.GetFullyQualifiedRulePath() not in self._meta_targets:
        self.ConvertTarget(target)

  def GetRulenameFromRawTarget(self, targetname) -> str:
    # This is the buildfile that the rule is called from
    build_file = self._get_buildfile_from_stack()
    build_path = impulse_paths.get_qualified_build_file_dir(build_file)
    build_rule = impulse_paths.convert_to_build_target(targetname, build_path)
    if build_rule in self._targets:
      return self._targets[build_rule]._rule_type
    return None


@typecheck.Ensure
def generate_graph(build_target:impulse_paths.ParsedTarget,
                   allow_meta:bool=False,
                   platform=None,
                   **kwargs):
  allow_meta = allow_meta or [build_target]
  re = RecursiveFileParser(platform, **kwargs)
  re.ParseTarget(build_target)
  re.ConvertTarget(build_target)
  return re.GetAllConvertedTargets(allow_meta=True)