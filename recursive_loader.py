
import inspect
import marshal
import re
import os
import pathlib
import types

import impulse_paths
import build_defs_runtime
import threaded_dependence
import build_defs_runtime


rules = {}

class FilterableSet(object):
  def __init__(self, *args):
    self.wrapped = set(args)

  def __iter__(self):
    return self.wrapped.__iter__()

  def __getattr__(self, attr):
    if attr == 'wrapped':
      return set()
    return getattr(self.wrapped, attr)

  def filter(self, **kwargs):
    matching = [x for x in self.wrapped if self._matches(x, kwargs)]
    return FilterableSet(*matching)

  def _matches(self, x, props):
    for k,v in props.items():
      if not hasattr(x, k):
        return False
      if getattr(x, k) != v:
        return False
    return True


class PreGraphNode(object):
  def __init__(self, build_target, build_args, func):
    self.full_name = build_target.GetFullyQualifiedRulePath()
    self.build_args = build_args
    self.func = func
    self.converted = None
    self.access = {}

  def __repr__(self):
    return str(self.build_args)

  def convert_to_graph(self, lookup):
    if not self.converted:
      dependencies = FilterableSet()
      for d in flatten(self.build_args):
        if impulse_paths.is_fully_qualified_path(d):
          dependencies.add(lookup[d].convert_to_graph(lookup))

      self.converted = DependencyGraph(self.full_name, self.func.__name__,
        dependencies, self.build_args, marshal.dumps(self.func.__code__),
        self.access)
    return self.converted

  def set_access(self, name, func):
    self.access[name] = marshal.dumps(func.__code__)


class DependencyGraph(threaded_dependence.DependentJob):
  def __init__(self, name, funcname, deps, args, decompiled_behavior, access):
    super().__init__(deps)
    self.name = name
    self.outputs = []
    self.ruletype = funcname
    self.__args = args
    self.__decompiled_behavior = decompiled_behavior
    self.access = access

    self.printed = False

  def __eq__(self, other):
    return other.name == self.name

  def __hash__(self):
    return hash(self.name)

  def __repr__(self):
    return self.name

  def run_job(self, debug):
    env = build_defs_runtime.env(
      self, self.name, self.ruletype, self.dependencies, debug)
    try:
      code = marshal.loads(self.__decompiled_behavior)
      types.FunctionType(code, env, self.name)(**self.__args)
      module_finished_path = env['deptoken'](self)
      try:
        os.makedirs(os.path.dirname(module_finished_path))
      except:
        pass
      with open(module_finished_path, 'w') as f:
        for output in self.outputs:
          f.write(output)
    except build_defs_runtime.RuleFinishedException:
      pass
    except TypeError:
      #TODO maybe make this check more robust instead of catching.
      err_template = 'target "%s" missing required argument(s) "%s"'
      function_object = types.FunctionType(code, env, self.name)
      all_args = inspect.getargspec(function_object).args
      missing_args = filter(lambda arg: arg not in self.__args.keys(), all_args)
      missing = ', '.join(missing_args)
      raise
      #raise threaded_dependence.CommandError(err_template % (self.name, missing))

  def d_print(self, indent):
    if not self.printed:
      self.printed = True
      print(' ' * indent + str(self))
      for d in self.dependencies:
        d.d_print(indent+1)
  def q_print(self):
    self.printed = False
    for d in self.dependencies:
      d.q_print()

  def print(self):
    self.d_print(0)
    self.q_print()


def flatten(item):
  if isinstance(item, str):
    yield item

  if isinstance(item, list):
    for i in item:
      for x in flatten(i):
        yield x

  if isinstance(item, dict):
    for i in item.values():
      for x in flatten(i):
        yield x


def _add_to_ruleset(pre_graph_node):
  rules[pre_graph_node.full_name] = pre_graph_node


def _load_recursive_dependencies(all_keys, build_path):
  return dict((key, _convert_load_vals(val, build_path))
    for key, val in all_keys.items())


def _convert_load_vals(value, build_path):
  if isinstance(value, str):
    target = impulse_paths.convert_to_build_target(value, build_path)
    if target is not impulse_paths.NOT_A_BUILD_TARGET:
      _parse_runtime_file(target.GetBuildFileForTarget())
      return target.GetFullyQualifiedRulePath()

  if isinstance(value, list):
    return [_convert_load_vals(v, build_path) for v in value]

  return value


already_loaded_files = set()
def _parse_runtime_file(build_or_defs_file_path):
  if build_or_defs_file_path in already_loaded_files:
    return
  already_loaded_files.add(build_or_defs_file_path)
  with open(build_or_defs_file_path) as f:
    exec(compile(f.read(), build_or_defs_file_path, 'exec'), _definition_env)


def CreatePreGraphNode(args_to_target, build_path, func):
  name = args_to_target.get('name')
  build_target = impulse_paths.convert_name_to_build_target(name, build_path)
  dep_targets = _load_recursive_dependencies(args_to_target, build_path)
  return PreGraphNode(build_target, dep_targets, func)


def _create_replacement_function(dependencies, wrapped):
  def replacement(**kwargs): # All args MUST BE KEYWORD
    build_file = inspect.stack()[1].filename
    build_file_path = impulse_paths.get_qualified_build_file_dir(build_file)
    cpgn = CreatePreGraphNode(kwargs, build_file_path, wrapped)
    for dep_func in dependencies:
      cpgn.set_access(dep_func.wraps.__name__, func.wraps)
    _add_to_ruleset(cpgn)
  replacement.wraps = wrapped
  return replacement


def buildrule(func):
  return _create_replacement_function([], func)


def buildrule_depends(*dependencies):
  def decorate(func):
    return _create_replacement_function(dependencies, func)
  return decorate


def load_modules(*args):
  for build_defs in args:
    _parse_runtime_file(impulse_paths.expand_fully_qualified_path(build_defs))


_definition_env = {
  'load': load_modules,
  'buildrule': buildrule,
  'buildrule_depends': buildrule_depends
}


def generate_graph(build_target):
  _parse_runtime_file(build_target.GetBuildFileForTarget())

  rules[build_target.GetFullyQualifiedRulePath()].convert_to_graph(rules)
  generated = set()
  for rule in rules.values():
    if rule.converted is not None:
      generated.add(rule.converted)
  return generated

