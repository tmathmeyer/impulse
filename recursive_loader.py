
import glob
import inspect
import marshal
import os

from impulse import impulse_paths
from impulse import build_target

from impulse.exceptions import exceptions
from impulse.util import resources


INVALID_RULE_RECURSION_CANARY = object()


class ParsedBuildTarget(object):
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

  def _CreateConverted(self):
    # set(build_target.BuildTarget)
    dependencies = set()
    # Convert all 'deps' into edges between BuildTargets
    for target in self._update_arg_dependencies_get_list():
      try:
        dependencies |= self._evaluator.ConvertTarget(target)
      except exceptions.BuildTargetMissing:
        raise exceptions.BuildTargetMissingFrom(str(target), self._build_rule)

    # Create a BuildTarget graph node
    return set([build_target.BuildTarget(
      self._name, self._func, self._args, self._build_rule,
      self._rule_type, self._scope, dependencies, **self._carried_args)])

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
      'buildmacro': self._buildmacro,
      'using': self._using,
      'pattern': self._find_files_pattern,
      'depends_targets': self._depends_on_targets,
      'data': self._buildrule(_data_buildrule),
      'git_repo': build_target.ParsedGitTarget,
      'langs': self._load_core_langs,
      'transform': self._buildrule(_transform_rule)
    }

  def ParseTarget(self, target: impulse_paths.ParsedTarget):
    target.ParseFile(self, self._ParseFile)

  def ConvertTarget(self, target):
    if target not in self._targets:
      raise exceptions.BuildTargetMissing(target)
    return self._targets[target].Convert()

  def _ParseFile(self, file: str):
    return self._ParseFileFromLocation(file, file)

  def _ParseFileFromLocation(self, file:str, location:str):
    if file not in self._loaded_files:
      self._loaded_files.add(file)
      with open(location) as f:
        try:
          exec(compile(f.read(), location, 'exec'), self._environ)
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

  def _buildmacro(self, fn):
    class MockArg(object):
      def __init__(self, argname, appended=None, prepended=None):
        self._argname = argname
        self._appended = appended
        self._prepended = prepended

      def __add__(self, other):
        if self._appended is not None:
          return MockArg(self._argname, self._appended + other, self._prepended)
        return MockArg(self._argname, other, self._prepended)

      def prepend(self, other):
        if self._prepended is not None:
          return MockArg(self._argname, self._appended, other + self._prepended)
        return MockArg(self._argname, self._appended, other)

      def eval(self, kwargs):
        if self._argname in kwargs:
          value = kwargs[self._argname]
          if self._prepended is not None:
            value = self._prepended + value
          if self._appended is not None:
            value += self._appended
          return self._check_value(value, kwargs)
        raise ValueError('TODO IMPLEMENT BETTER ERROR')

      def _check_value(self, value, kwargs):
        if type(value) == list:
          return [self._check_value(v, kwargs) for v in value]
        if type(value) == dict:
          return {k:self._check_value(v, kwargs) for k,v in value.items()}
        if type(value) == MockArg:
          return value.eval(kwargs)
        return value

    class MacroExpander(object):
      def __init__(self, loader):
        self._loader = loader
        self.macros = []

      def ImitateRule(self, rulefile, rulename, args):
        self._loader._load_files(rulefile)
        rule = self._loader._environ.get(rulename)
        if rule is None:
          raise exceptions.NoSuchRuleType(rulename)
        def Wrapper(**kwargs):
          argbuilder = {}
          for asName, value in args.items():
            if type(value) != MockArg:
              argbuilder[asName] = value
            else:
              argbuilder[asName] = value.eval(kwargs)
          rule(**argbuilder)
        self.macros.append(Wrapper)

    mock_args = {}
    expander = MacroExpander(self)
    for arg, info in inspect.signature(fn).parameters.items():
      if str(info).startswith('**'):
        raise exceptions.MacroException(
          fn.__name__, 'macro', 'Glob arguments disallowed')
      if '=' in str(info):
        raise exceptions.MacroException(
          fn.__name__, 'macro', 'Default arguments disallowed')
      if arg != 'macro_env':
        mock_args[arg] = MockArg(arg)

    fn(expander, **mock_args)
    def replacement(**kwargs):
      for macro in expander.macros:
        macro(**kwargs)
    return replacement



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
      expanded = impulse_paths.expand_fully_qualified_path(
        f'//rules/core/{file}/build_defs.py')
      try:
        self._ParseFile(expanded)
      except FileNotFoundError as e:
        self._loaded_files.remove(expanded)
        embeddedPath = f'impulse/rules/core/{file}/build_defs.py'
        embeddedBuildDef = resources.Resources.Get(embeddedPath)
        self._ParseFileFromLocation(expanded, embeddedBuildDef)

  def GetAllConvertedTargets(self):
    def converted_targets():
      for target in self._targets.values():
        if target._converted:
          yield target._converted
    result = set()
    for c in converted_targets():
      result |= c
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
