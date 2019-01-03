
import inspect
import marshal
import re

from impulse import impulse_paths
from impulse import build_target


class BuildTargetIntermediary(object):
  def __init__(self, name, func, args, build_rule, ruletype, evaluator):
    self._func = marshal.dumps(func.__code__)
    self._name = name
    self._args = args
    self._build_rule = build_rule
    self._rule_type = ruletype
    self._evaluator = evaluator
    self._converted = None
    self._scope = {}

  def convert(self):
    dependencies = set()
    for dep in self._args.get('deps', []):
      target = impulse_paths.convert_to_build_target(
        dep, self._build_rule.target_path)
      dependencies.add(self._evaluator._targets[target].convert())
    self._converted = build_target.BuildTarget(
      self._name, self._func, self._args, self._build_rule,
      self._rule_type, self._scope, dependencies)
    return self._converted

  def add_scopes(self, funcs):
    for func in funcs:
      self._scope[func.__name__] = (marshal.dumps(func.__code__))


class FileImportException(Exception):
  def __init__(self, exc, file):
    super(exc)


class RuleEvaluator(object):

  def __init__(self):
    self._targets = {}
    self._loaded_files = set()
    self._environ = {
      'load': self._load_files,
      'buildrule': self._buildrule,
      'using': self._using,
    }

  def get_graph_from_target(self, target):
    self._targets[target].convert()
    def converted_targets():
      for target in self._targets.values():
        if target._converted:
          yield target._converted
    return set(converted_targets())

  def parse_target(self, target):
    if not isinstance(target, impulse_paths.ParsedTarget):
      raise ValueError('{} is a not a parsed target object'.format(target))
    self._parse_file(target.GetBuildFileForTarget())

  def _using(self, *includes):
    def _decorator(fn):
      def replacement(*args, **kwargs):
        kwargs['__stack__'] = 2
        fn(*args, **kwargs).add_scopes(includes)
      return replacement
    return _decorator

  def _buildrule(self, fn):
    # py_library, for example
    build_as = fn.__name__
    # all params to a build rule should be keyword
    # name is _required_
    def replacement(name, **kwargs):
      # Get our build target & paths
      build_file = inspect.stack()[kwargs.get('__stack__', 1)].filename
      build_file_path = impulse_paths.get_qualified_build_file_dir(build_file)
      build_rule = impulse_paths.convert_name_to_build_target(
        name, build_file_path)
      # save this target call to evaluate in the graph later
      self._targets[build_rule] = BuildTargetIntermediary(
        name, fn, kwargs, build_rule, build_as, self)
      # Parse the dependencies and evaluate them too
      for dep in kwargs.get('deps', []):
        if impulse_paths.is_fully_qualified_path(dep):
          self.parse_target(
            impulse_paths.convert_to_build_target(dep, None))
      return self._targets[build_rule]
    return replacement

  def _parse_file(self, file):
    if file in self._loaded_files:
      return
    self._loaded_files.add(file)
    with open(file) as f:
      try:
        compiled = compile(f.read(), file, 'exec')
        exec(compiled, self._environ)
      except Exception as e:
        raise FileImportException(e, file)

  def _load_files(self, *args):
    for loading in args:
      self._parse_file(impulse_paths.expand_fully_qualified_path(loading))


def generate_graph(build_target):
  re = RuleEvaluator()
  re.parse_target(build_target)
  return re.get_graph_from_target(build_target)
