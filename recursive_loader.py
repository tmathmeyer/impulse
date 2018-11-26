
import collections
import inspect
import marshal
import re
import sys
import subprocess
import os
import pathlib
import types
import time
import json

from impulse import impulse_paths
from impulse import threaded_dependence


rules = {}
PATH_REGEX = re.compile('//(.*):(.*)')


def timestamp(filepath):
  """Gets the last modified timestamp of a file."""
  if os.path.exists(filepath):
    return os.path.getmtime(filepath)
  raise ValueError(filepath + ' does not exist!')


class Command(object):
  """A lazy shell command wrapper."""

  def __init__(self, args, pwd):
    self._pwd = pwd
    self._args = args

  def run(self):
    process = subprocess.Popen(
      self._args, 
      cwd=self._pwd,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      universal_newlines=True)
    _, err = process.communicate()
    if process.returncode != 0:
      raise threaded_dependence.CommandError(
        ' '.join(self._args) + '--> ' + err)


class Writer(object):
  """A lazy file writer wrapper."""

  def __init__(self, path, mode):
    self._path = path
    self._mode = mode
    self._calls = []

  def __enter__(self):
    self._calls = []
    return self

  def __exit__(self, a, b, c):
    pass

  def __getattr__(self, attr):
    def savecall(*args, **kwargs):
      self._calls.append((attr, args, kwargs))
    return savecall

  def run(self):
    with open(self._path, self._mode) as f:
      for fn, args, kwargs in self._calls:
        getattr(f, fn)(*args, **kwargs)


class BuildTarget(object):
  """Represents a timestamped build target."""

  def __init__(self, name):
    # target "full" name
    self.__name = name

    # root is the output directory
    self._root = self.pkg_file('')

    # input files, output files, dependant build targets
    self._inputs = set()
    self._outputs = set()
    self._depends = set()

    # target simple name
    self._name = None

    # order the commands to replay after the rule input
    # files are determined
    self._ordered_cmds = list()

    # never been built
    self._buildtime = 0

    # ensure that the root directory is created
    self.run_impulseroot('mkdir')('-p', self._root)

  @classmethod
  def ParseFile(cls, jsonfile):
    try:
      parsed = PATH_REGEX.match(jsonfile)
      jsonfile = os.path.join(
        impulse_paths.root(), 'PACKAGES',
        parsed.group(1), parsed.group(2)) + '.package.json'
      with open(jsonfile, "r") as f:
        contents = json.loads(f.read())
        result = BuildTarget(contents['full_name'])
        result._inputs.update(contents['input_files'])
        result._outputs.update(contents['output_files'])
        result._buildtime = contents['build_timestamp']
        for dep in contents['depends_on']:
          result._depends.add(cls.ParseFile(dep))
        return result
    except:
      return None

  def evaluate(self):
    previous_build = self.ParseFile(self.__name)
    required_build = previous_build is None
    if not required_build:
      for inputfile in self._inputs:
        if timestamp(inputfile) > previous_build._buildtime:
          required_build = True
          break

    if not required_build:
      for depends_on in self._depends:
        if depends_on._buildtime > previous_build._buildtime:
          required_build = True
          break

    if not required_build:
      return

    jsonfile = '{}.package.json'.format(self._name)
    with self.write_file(jsonfile) as f:
      f.write(json.dumps({
        'input_files': list(self._inputs),
        'output_files': list(self._outputs),
        'built_from': 'TODO',
        'build_timestamp': int(time.time()),
        'depends_on': list(str(d) for d in self._depends),
        'full_name': self.__name,
      }, indent=2))
    self.synchronize()

  def __str__(self):
    return self.__name

  def synchronize(self):
    for cmd in self._ordered_cmds:
      cmd.run()
    self._ordered_cmds = []

  def write_file(self, filename, outside_pkg=False):
    return self.__openfile(filename, outside_pkg, 'w+')

  def append_file(self, filename, outside_pkg=False):
    return self.__openfile(filename, outside_pkg, 'a+')

  def __openfile(self, filename, outside_pkg, mode):
    if outside_pkg:
      pkgbase = os.path.join(impulse_paths.root(), 'PACKAGES')
    else:
      pkgbase = self._root
    filename = os.path.join(pkgbase, filename)
    writer = Writer(filename, mode)
    self._ordered_cmds.append(writer)
    self._outputs.add(filename)
    return writer

  def pkg_file(self, filename):
    """Gets a full file path for a BUILD-file local file."""
    return os.path.join(
      impulse_paths.root(), 'PACKAGES', 
      self.directory(), filename)

  def vc_file(self, filename):
    return os.path.join(
      impulse_paths.root(), self.directory(), filename)

  def directory(self):
    return PATH_REGEX.match(self.__name).group(1)

  def _cmd(self, cmd, pwd=None):
    """Creates a helper function which appends command."""
    def run(*args):
      self._ordered_cmds.append(Command([cmd] + list(args),
        pwd=pwd or self._root))
    return run

  def run_pkgroot(self, cmd):
    return self._cmd(cmd, pwd=os.path.join(
      impulse_paths.root(), 'PACKAGES'))

  def run_impulseroot(self, cmd):
    return self._cmd(cmd, impulse_paths.root())

  def import_from(self, vc_file, pkg_file, keep):
    vc_file = self.vc_file(vc_file)
    pkg_file = self.pkg_file(pkg_file)
    self.cp(vc_file, pkg_file)
    if keep:
      self._tracked.add(vc_file)

  def track_output_file(self, pkg_file):
    self._outputs.add(self.pkg_file(pkg_file))

  def track_input_file(self, vc_file):
    self._inputs.add(self.vc_file(vc_file))

  def track_depends(self, depends):
    self._depends.add(BuildTarget.ParseFile(depends))

  def set_name(self, name):
    self._name = name

  def __getattr__(self, attr):
    return self._cmd(attr)

  def get_output_files(self):
    self.synchronize()
    droplen = len(
      os.path.join(impulse_paths.root(), 'PACKAGES', ''))
    for f in self._outputs:
      yield f[droplen:]
    for dep in self._depends:
      for f in dep.get_output_files():
        yield f


class FilterableSet(object):
  """A set that can be filtered with key words."""

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
  def __init__(self, build_target, build_args, func, build_file_path):
    self.full_name = build_target.GetFullyQualifiedRulePath()
    self.build_args = build_args
    self.func = func
    self.converted = None
    self.access = {}
    self.build_file_path = build_file_path

  def __repr__(self):
    return str(self.build_args)

  def convert_to_graph(self, lookup):
    if not self.converted:
      dependencies = FilterableSet()
      for d in flatten(self.build_args):
        if impulse_paths.is_fully_qualified_path(d):
          if d in lookup:
            dependencies.add(lookup[d].convert_to_graph(lookup))
          else:
            raise impulse_paths.PathException(d, self.full_name)

      self.converted = DependencyGraph(self.full_name, self.func.__name__,
        dependencies, self.build_args, marshal.dumps(self.func.__code__),
        self.access, self.build_file_path)
    return self.converted

  def set_access(self, name, func):
    self.access[name] = marshal.dumps(func.__code__)


class DependencyGraph(threaded_dependence.DependentJob):
  def __init__(self, name, funcname, deps, args, decompiled_behavior, access, buildfile):
    super().__init__(deps)
    self.name = name
    self.outputs = []
    self.ruletype = funcname
    self.__args = args
    self.__decompiled_behavior = decompiled_behavior
    self.access = access
    self.defined_in_file = impulse_paths.expand_fully_qualified_path(
      os.path.join(buildfile, 'BUILD'))

    self.printed = False

  def __eq__(self, other):
    return (other.__class__ == self.__class__ and
            other.name == self.name)

  def __hash__(self):
    return hash(self.name)

  def __repr__(self):
    return self.name

  def parse_depends(d):
    return d

  def run_job(self, debug):
    try:
      code = marshal.loads(self.__decompiled_behavior)
      target = BuildTarget(self.name)
      def wrap(fn, target, **kwargs):
        target.set_name(kwargs.get('name'))
        for dep in kwargs.get('deps', []):
          target.track_depends(dep)
        for src in kwargs.get('srcs', []):
          directory = os.path.dirname(src)
          while directory:
            target.mkdir('-p', directory)
            directory = os.path.dirname(directory)
          target.track_input_file(src)
          target.import_from(pkg_file=src, vc_file=src, keep=False)
        fn(target=target, **kwargs)
        target.evaluate()
      fn = types.FunctionType(code, globals(), self.name)
      wrap(fn, target, **self.__args)
    except Exception as e:
      tb = e.__traceback__
      while tb:
        print('{}: {}'.format(
          tb.tb_frame.f_code.co_filename, tb.tb_lineno))
        tb = tb.tb_next
      raise e

def flatten(item):
  if isinstance(item, str):
    yield item

  if isinstance(item, list):
    for i in item:
      for x in flatten(i):
        yield x

  if isinstance(item, dict):
    for i in item.values():
      if not isinstance(i, str):
        for x in flatten(i):
          yield x


def _add_to_ruleset(pre_graph_node):
  rules[pre_graph_node.full_name] = pre_graph_node


def _load_recursive_dependencies(all_keys, build_path):
  return dict((key, _convert_load_vals(val, build_path))
    for key, val in all_keys.items())


class InvalidBuildRule(Exception):
  pass

class InvalidBuildRuleWithTarget(Exception):
  def __init__(self, target):
    self.target = target

class InvalidIncludeError(Exception):
  def __init__(self, rule):
    self.rule = rule

class InvalidIncludeErrorWithLocation(Exception):
  def __init__(self, rule, target):
    self.rule = rule
    self.target = target

class InvalidBuildFile(Exception):
  def __init__(self, build_file, errormsg):
    self.build_file = build_file
    self.errormsg = errormsg

class SilentException(Exception):
  pass


def _convert_load_vals(value, build_path):
  if isinstance(value, str):
    target = impulse_paths.convert_to_build_target(value, build_path)
    if target is not impulse_paths.NOT_A_BUILD_TARGET:
      try:
        _parse_runtime_file(target.GetBuildFileForTarget())
        return target.GetFullyQualifiedRulePath()
      except InvalidBuildRule as e:
        raise InvalidBuildRuleWithTarget(target)
      except InvalidIncludeError as e:
        raise InvalidIncludeErrorWithLocation(e.rule, target)

  if isinstance(value, list):
    return [_convert_load_vals(v, build_path) for v in value]

  return value

already_loaded_files = set()
def _parse_runtime_file(build_or_defs_file_path):
  if build_or_defs_file_path in already_loaded_files:
    return
  already_loaded_files.add(build_or_defs_file_path)
  try:
    with open(build_or_defs_file_path) as f:
      compiled = compile(f.read(), build_or_defs_file_path, 'exec')
      exec(compiled, _definition_env)
  except FileNotFoundError:
    raise InvalidBuildRule()
  except InvalidBuildRuleWithTarget as err:
    raise InvalidIncludeError(err.target)


def CreatePreGraphNode(args_to_target, build_path, func):
  name = args_to_target.get('name')
  build_target = impulse_paths.convert_name_to_build_target(name, build_path)
  dep_targets = _load_recursive_dependencies(args_to_target, build_path)
  return PreGraphNode(build_target, dep_targets, func, build_path)


def _create_replacement_function(dependencies, wrapped, required_deps):
  required_deps = required_deps or []
  def replacement(**kwargs): # All args MUST BE KEYWORD
    if 'deps' in kwargs:
      kwargs['deps'] = list(set(kwargs['deps']) | set(required_deps))
    else:
      kwargs['deps'] = required_deps
    build_file = inspect.stack()[1].filename
    build_file_path = impulse_paths.get_qualified_build_file_dir(build_file)
    cpgn = CreatePreGraphNode(kwargs, build_file_path, wrapped)
    for dep_func in dependencies:
      cpgn.set_access(dep_func.wraps.__name__, dep_func.wraps)
    _add_to_ruleset(cpgn)
  replacement.wraps = wrapped
  return replacement


def buildrule(fn, required_deps=None, imports=None):
  return _create_replacement_function(
    imports or [], fn, required_deps or [])


def buildrule_depends(*dependencies, required_deps=None):
  def decorate(func):
    return buildrule(func, required_deps, dependencies)
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
  try:
    return _generate_graph(build_target)
  except InvalidIncludeErrorWithLocation as e:
    msg = "rule {} included from {} is invalid".format(
      e.rule.GetFullyQualifiedRulePath(), e.target.GetBuildFileForTarget())
    print(msg)
    return set()
  except InvalidBuildFile as e:
    print('{} in {}'.format(e.errormsg, e.build_file))
    raise SilentException()

def _generate_graph(build_target):
  try:
    _parse_runtime_file(build_target.GetBuildFileForTarget())
  except InvalidIncludeError as e:
    raise InvalidIncludeErrorWithLocation(e.rule, build_target)

  rules[build_target.GetFullyQualifiedRulePath()].convert_to_graph(rules)
  generated = set()
  for rule in rules.values():
    if rule.converted is not None:
      generated.add(rule.converted)
  return generated

