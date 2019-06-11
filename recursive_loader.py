
import glob
import inspect
import marshal
import os

from impulse import impulse_paths
from impulse import build_target

from impulse.exceptions import exceptions


INVALID_RULE_RECURSION_CANARY = object()


class ParsedBuildTarget(object):
  def __init__(self, name, func, args, build_rule, ruletype, evaluator):
    self._func = marshal.dumps(func.__code__)
    self._name = name
    self._args = args
    self._build_rule = build_rule
    self._rule_type = ruletype
    self._evaluator = evaluator
    self._converted = None
    self._scope = {}

  def Convert(self):
    # If we try to convert this rule again while conversion is in progress
    # we need to fail, as a cyclic graph can't be built. Conversion is
    # single threaded, so this test-and-set will suffice.
    if self._converted is INVALID_RULE_RECURSION_CANARY:
      raise exceptions.BuildTargetCycle()
    if not self._converted:
      self._converted = INVALID_RULE_RECURSION_CANARY
      self._converted = self._CreateConverted()
    return self._converted

  def _get_all_seems_like_buildrule_patterns(self):
    def get_all(some, probably):
      if type(some) == str:
        v = probably(some)
        if v:
          yield v
      elif type(some) == dict:
        for v in get_all(some.items(), probably):
          yield v
      else:
        try:
          for l in some:
            for v in get_all(l, probably):
              yield v
        except TypeError:
          pass
    def is_buildrule(txt):
      try:
        return impulse_paths.convert_to_build_target(
          txt, self._build_rule.target_path, True)
      except:
        return None
    return get_all(self._args, is_buildrule)

  def _CreateConverted(self):
    # set(build_target.BuildTarget)
    dependencies = set()

    # Convert all 'deps' into edges between BuildTargets
    for target in self._get_all_seems_like_buildrule_patterns():
      try:
        dependencies.add(self._evaluator.ConvertTarget(target))
      except exceptions.BuildTargetMissing:
        raise exceptions.BuildTargetMissingFrom(str(target), self._build_rule)

    # Create a BuildTarget graph node
    return build_target.BuildTarget(
      self._name, self._func, self._args, self._build_rule,
      self._rule_type, self._scope, dependencies)

  def AddScopes(self, funcs):
    if self._converted:
      raise "TOO LATE" # TODO raise a real error...
    for func in funcs:
      self._scope[func.__name__] = (marshal.dumps(func.__code__))
    return self


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
  def __init__(self):
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
      'data': self._buildrule(_data_buildrule)
    }

  def ParseTarget(self, target: impulse_paths.ParsedTarget):
    self._ParseFile(target.GetBuildFileForTarget())

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
    build_directory = impulse_paths.get_qualified_build_file_dir(build_file)[2:]
    pattern = os.path.join(build_directory, p)
    try:
      return [f[len(build_directory)+1:] for f in glob.glob(pattern)] or []
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
        name, fn, kwargs, build_rule, buildrule_name, self)

      # Parse the dependencies and evaluate them too.
      for dep in kwargs.get('deps', []):
        if impulse_paths.is_fully_qualified_path(dep):
          self.ParseTarget(impulse_paths.convert_to_build_target(dep, None))

      # The wrapper functions (using, depends, etc) need the ParsedBuildTarget
      return self._targets[build_rule]

    return replacement

  def _load_files(self, *args):
    for loading in args:
      self._ParseFile(impulse_paths.expand_fully_qualified_path(loading))

  def GetAllConvertedTargets(self):
    def converted_targets():
      for target in self._targets.values():
        if target._converted:
          yield target._converted
    return set(converted_targets())

  def ConvertAllTestTargets(self):
    for target, parsed in self._targets.items():
      if parsed._rule_type.endswith('_test'):
        self.ConvertTarget(target)
        yield target


def generate_graph(build_target):
  re = RecursiveFileParser()
  re.ParseTarget(build_target)
  re.ConvertTarget(build_target)
  return re.GetAllConvertedTargets()
