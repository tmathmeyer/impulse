
import glob
import inspect
import marshal
import os

from impulse import impulse_paths
from impulse import build_target

from impulse.exceptions import exceptions


INVALID_RULE_RECURSION_CANARY = object()


class RecursiveFilterSetter(object):
  def __init__(self, struct, test_fn):
    self._struct = struct
    self._breadcrumbs = {}
    self._converted = list(self._GenerateBreadcrumbs(test_fn))

  def _GenerateBreadcrumbs(self, test_fn):
    def iterate(crumb, current):
      if crumb == None:
        crumb = []
      if type(current) == dict:
        for key, val in current.items():
          yield from iterate(crumb + [key], val)
      elif type(current) == list:
        for i, val in enumerate(current):
          yield from iterate(crumb + [i], val)
      else:
        v = test_fn(current)
        if v:
          yield (v, crumb)

    for set_to, crumb in iterate(None, self._struct):
      obj = self._struct
      for c in crumb[:-1]:
        obj = obj[c]
      obj[crumb[-1]] = set_to
      yield set_to

  def Converted(self):
    yield from self._converted


class ParsedBuildTarget(impulse_paths.ConvertableTargetBase):
  def __init__(self, name, func, args, build_rule, ruletype, evaluator,
               carried_args):
    self._func = marshal.dumps(func.__code__)
    self._name = name
    self._args = args
    self._build_rule = build_rule
    self._rule_type = ruletype
    self._evaluator = evaluator
    self._carried_args = carried_args
    self._converted = None
    self._scope = {}

    def _ConvertToBuildrule(txt):
      try:
        return impulse_paths.convert_to_build_target(
          txt, self._build_rule.target_path, True)
      except:
        return None

    self._conversion_list = RecursiveFilterSetter(
      self._args, _ConvertToBuildrule)

  def Convert(self):
    # If we try to convert this rule again while conversion is in progress
    # we need to fail, as a cyclic graph can't be built. Conversion is
    # single threaded, so this test-and-set will suffice.
    if self._converted is INVALID_RULE_RECURSION_CANARY:
      raise exceptions.BuildTargetCycle.Cycle(self)
    if not self._converted:
      self._converted = INVALID_RULE_RECURSION_CANARY
      try:
        self._converted = self._CreateConverted()
      except exceptions.BuildTargetCycle as e:
        raise e.ChainException(self)
    return self._converted

  def GetGeneratedRules(self):
    if self._converted:
      yield self._converted

  def GetDependencies(self):
    return self._conversion_list.Converted()

  def _CreateConverted(self):
    # set(build_target.BuildTarget)
    dependencies = set()
    # Convert all 'deps' into edges between BuildTargets
    for target in self.GetDependencies():
      try:
        dependencies.add(self._evaluator.ConvertTarget(target))
      except exceptions.BuildTargetMissing:
        raise exceptions.BuildTargetMissingFrom(str(target), self._build_rule)

    def recall_convert(obj):
      if isinstance(obj, impulse_paths.ParsedTarget):
        return self._evaluator._targets[obj].Convert()
    RecursiveFilterSetter(self._args, recall_convert)

    # Create a BuildTarget graph node
    return build_target.BuildTarget(
      self._name, self._func, self._args, self._build_rule,
      self._rule_type, self._scope, dependencies, **self._carried_args)

  def AddScopes(self, funcs):
    if list(self.GetGeneratedRules()):
      raise exceptions.FatalException(f'Failed to add scope functions to {self}')
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
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))


class RecursiveFileParser(object):
  """Loads files based on load() and buildrule statements."""
  def __init__(self, carried_args):
    self._carried_args = carried_args
    self._targets = {} # Map[BuildTarget->ParsedBuildTarget]
    self._loaded_files = set() # We don't want to load files multiple times

    # We need to store the environment across compilations, since it allows
    # files to call eachother's functions.
    self._environ = {
      'load': self._load_files,
      'buildrule': self._buildrule,
      'buildrule_macro': self._buildrule_macro,
      'using': self._using,
      'pattern': self._find_files_pattern,
      'depends_targets': self._depends_on_targets,
      'data': self._buildrule(_data_buildrule),
      'git_repo': build_target.ParsedGitTarget,
      'langs': self._load_core_langs,
    }

  def ParseTarget(self, target: impulse_paths.ParsedTarget):
    target.ParseFile(self, self._ParseFile)

  def ConvertTarget(self, target):
    if target not in self._targets:
      raise exceptions.BuildTargetMissing(target)
    return self._targets[target].Convert()

  def _ParseFile(self, file: str):
    if file not in self._loaded_files:
      self._loaded_files.add(file)
      with open(file) as f:
        try:
          exec(compile(f.read(), file, 'exec'), self._environ)
        except NameError as e:
          # TODO: this needs to be fixed, since there could be _other_ name
          # errors, not just rule-not-found ones.
          raise exceptions.NoSuchRuleType(e.args[0].split('\'')[1])
        except Exception as e:
          # Wrap any exception that we get, so we don't have crashes
          raise exceptions.FileImportException(e, file)

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

  def _get_buildfile_from_stack(self):
    build_file = 'Fake'
    build_file_index = 1
    while not build_file.endswith('BUILD'):
      build_file = inspect.stack()[build_file_index].filename
      build_file_index += 1
    return build_file

  def _buildrule_macro(self, fn):
    return fn

  def _buildrule(self, fn):
    """Decorates a function allowing it to be used as a target buildrule."""
    
    # Store the type of buildrule
    buildrule_name = fn.__name__

    # all params to a build rule must be keyword!
    def replacement(**kwargs):
      # 'name' is a required argument!
      assert 'name' in kwargs
      name = kwargs['name']

      # This is the buildfile that the rule is called from
      build_file = self._get_buildfile_from_stack()

      # Directory of the buildfile
      build_path = impulse_paths.get_qualified_build_file_dir(build_file)

      # This is an 'impulse_paths.ParsedTarget' object
      build_rule = impulse_paths.convert_name_to_build_target(name, build_path)

      # Create a ParsedBuildTarget which can be converted into the graph later.
      self._targets[build_rule] = ParsedBuildTarget(
        name, fn, kwargs, build_rule, buildrule_name, self, self._carried_args)

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
      self._ParseFile(impulse_paths.expand_fully_qualified_path(
        f'//rules/core/{file}/build_defs.py'))

  def GetAllConvertedTargets(self):
    def converted_targets():
      for target in self._targets.values():
        if target.GetGeneratedRules():
          yield from target.GetGeneratedRules()
    result = set()
    for c in converted_targets():
      result.add(c)
    return result

  def ConvertAllTestTargets(self):
    for target, parsed in self._targets.items():
      if parsed._rule_type.endswith('_test'):
        self.ConvertTarget(target)
        yield target


def generate_graph(build_target, **kwargs):
  re = RecursiveFileParser(kwargs)
  re.ParseTarget(build_target)
  re.ConvertTarget(build_target)
  return re.GetAllConvertedTargets()
