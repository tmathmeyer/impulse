import json
import marshal
import os
import re
import tempfile
import time
import traceback
import types

from impulse import exceptions
from impulse import impulse_paths
from impulse import threaded_dependence
from impulse import rw_fs

RULE_REGEX = re.compile('//(.*):(.*)')
EXPORT_DIR = 'PACKAGES'


class SetDirectory(object):
  def __init__(self, directory):
    self._dir = directory

  def __enter__(self):
    self._old = os.getcwd()
    os.chdir(self._dir)
    while not os.listdir('.'):
      os.chdir(self._dir)

  def __exit__(self, *args):
    os.chdir(self._old)


def target2package(target):
  rulepath, rulename = RULE_REGEX.match(str(target)).groups()
  pkgfile = os.path.join(impulse_paths.root(), EXPORT_DIR, rulepath,
    '{}.package.json'.format(rulename))
  return PackageInfo.Import(pkgfile, str(target))


class PackageInfo(object):
  def __init__(self):
    self.depends_on_files = set()
    self.depends_on_targets = set()
    self.generated_files = set()
    self.package_target = None
    self.package_name = None

    # critical to take the timestamp early;
    # if a file changes _while_ the builder
    # is running, we want to try to pick it up
    self.build_timestamp = int(time.time())

  def __repr__(self):
    return str(self.package_target)

  @classmethod
  def Import(clz, file, target):
    instance = clz()
    instance.package_target = target
    instance.package_name = file
    try:
      with open(file) as f:
        contents = json.loads(f.read())
        for key in instance.__dict__.keys():
          imported = contents.get(key, None)
          assert imported is not None  # TODO(raise a better error here)
          setattr(instance, key, imported)
        instance.depends_on_targets = set(
          target2package(target) for target in instance.depends_on_targets)
        instance.depends_on_files = set(instance.depends_on_files)
        instance.generated_files = set(instance.generated_files)
        return instance
    except FileNotFoundError:
      instance.depends_on_files = set(['BUILD'])
      instance.build_timestamp = 0
      return instance
    except Exception as e:
      traceback.print_exc()
      return instance

  def export(self):
    assert self.package_name is not None
    if self.build_timestamp == 0:
      self.build_timestamp = int(time.time())
    with open(self.package_name, 'w+') as f:
      env = {}
      for k, v in self.__dict__.items():
        if isinstance(v, set):
          env[k] = list(str(e) for e in v)
        else:
          env[k] = v
      f.write(json.dumps(env, indent=2))



class BuildTarget(threaded_dependence.DependentJob):
  def __init__(self, name, func, args, rule, dependencies):
    super().__init__(dependencies)
    self._func = func
    self._args = args
    self._name = name
    self._build_rule = rule

  def __eq__(self, other):
    return (
      other.__class__ == self.__class__ and
      other._build_rule == self._build_rule
    )

  def __hash__(self):
    return hash(self._build_rule)

  def __repr__(self):
    return str(self._build_rule)

  def _needs_build(self, pkg):
    def all_timestamps():
      for f in pkg.depends_on_files:
        if os.path.exists(f):
          yield int(os.path.getmtime(f))
        else:
          yield pkg.build_timestamp + 1
      for p in pkg.depends_on_targets:
        yield p.build_timestamp
    for timestamp in all_timestamps():
      if timestamp > pkg.build_timestamp:
        return True
    return False

  def _ensure_directory(self, directory):
    if not os.path.exists(directory):
      os.makedirs(directory)

  def build_path(self):
    return RULE_REGEX.match(str(self._build_rule)).groups()[0]

  def build_name(self):
    return RULE_REGEX.match(str(self._build_rule)).groups()[1]

  def track(self, file, I=False, O=False):
    if I or O:
      os.access(file, mode=32768|os.F_OK)
    if I:
      self._package_info.depends_on_files.add(file)
    if O:
      self._package_info.generated_files.add(file)

  def generated_by_dependencies(self, filter=None):
    def iterate_output(pkg):
      for f in pkg.generated_files:
        rulepath,_ = RULE_REGEX.match(str(pkg)).groups()
        yield os.path.join(rulepath, f)
      for pkg in pkg.depends_on_targets:
        for i in iterate_output(pkg):
          yield i

    for i in iterate_output(self._package_info):
      yield i

  def writing_temp_files(self):
    superself = self
    class TempFiles(object):
      def __enter__(self):
        tmpdirname = tempfile.mkdtemp()
        rw_directory = tempfile.mkdtemp()
        ro_directory = os.path.join(impulse_paths.root(), EXPORT_DIR)
        self._ctx = rw_fs.FuseCTX(tmpdirname, ro_directory, rw_directory)
        self._old = os.getcwd()
        self._ctx.__enter__()
        os.chdir(tmpdirname)
        while not os.listdir('.'):
          os.chdir(tmpdirname)

      def __exit__(self, *args):
        os.chdir(self._old)
        self._ctx.__exit__(*args)
    return TempFiles()

  def copy_from_tmp(self, copyname):
    # method only called when within a temp directory!
    export_to = os.path.join(
      impulse_paths.root(), EXPORT_DIR,
      self.build_path(), os.path.basename(copyname))
    os.system('cp {} {}'.format(copyname, export_to))
    self._package_info.generated_files.add(
      os.path.join(self.build_path(), os.path.basename(copyname)))


  # Entry point where jobs start
  def run_job(self, debug):
    rulepath, rulename = RULE_REGEX.match(str(self._build_rule)).groups()
    rw_directory = os.path.join(impulse_paths.root(), EXPORT_DIR, rulepath)
    ro_directory = os.path.join(impulse_paths.root(), rulepath)
    package_filename = rulename + '.package.json'
    self._ensure_directory(rw_directory)
    tmpdirname = tempfile.mkdtemp()

    with rw_fs.FuseCTX(tmpdirname, ro_directory, rw_directory):
      with SetDirectory(tmpdirname):
        self._package_info = PackageInfo.Import(package_filename, str(self))
        for depends in self.dependencies:
          self._package_info.depends_on_targets.add(
            target2package(depends))

        if self._needs_build(self._package_info):
          code = None
          fn = None
          try:
            code = marshal.loads(self._func)
            fn = types.FunctionType(code, globals(), str(self._build_rule))
          except:
            print('couldnt compile')
            raise exceptions.BuildRuleCompilationError()

          try:
            fn(self, name=self._name, **self._args)
          except Exception as e:
            raise exceptions.BuildRuleRuntimeError(e)

        self._package_info.export()
        print('exported')