

import json
import marshal
import os
import re
import tempfile
import time
import types

from impulse import exceptions
from impulse import impulse_paths
from impulse import threaded_dependence
from impulse import rw_fs

RULE_REGEX = re.compile('//(.*):(.*)')
EXPORT_DIR = 'PACKAGES2'


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


class PackageInfo(object):
  def __init__(self):
    self.depends_on_files = []
    self.depends_on_targets = []
    self.generated_files = []
    self.package_target = None

    # critical to take the timestamp early;
    # if a file changes _while_ the builder
    # is running, we want to try to pick it up
    self.build_timestamp = int(time.time())

  @classmethod
  def Import(clz, file):
    instance = clz()
    instance.package_target = file
    try:
      with open(file) as f:
        contents = json.loads(f.read())
        for key in instance.__dict__.keys():
          imported = contents.get(key, None)
          assert imported is not None  # TODO(raise a better error here)
          setattr(instance, key, imported)
        return instance
    except Exception as e:
      instance.build_timestamp = 0
      return instance

  def export(self):
    assert self.package_target is not None
    if self.build_timestamp == 0:
      self.build_timestamp = int(time.time())
    with open(self.package_target, 'w+') as f:
      print('what the fuck lmao')
      f.write(json.dumps(self.__dict__, indent=2))



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

  def _needs_build(self, PackageInfo):
    return True

  def _ensure_directory(self, directory):
    if not os.path.exists(directory):
      os.makedirs(directory)

  # Entry point where jobs start
  def run_job(self, debug):
    rulepath, rulename = RULE_REGEX.match(str(self._build_rule)).groups()
    rw_directory = os.path.join(impulse_paths.root(), EXPORT_DIR, rulepath)
    ro_directory = os.path.join(impulse_paths.root(), rulepath)
    package_filename = rulename + '.package.json'
    self._ensure_directory(rw_directory)
    tmpdirname = tempfile.mkdtemp()

    print(tmpdirname)
    with rw_fs.FuseCTX(tmpdirname, ro_directory, rw_directory):
      with SetDirectory(tmpdirname):
        print('a')
        package_info = PackageInfo.Import(package_filename)
        package_info.depends_on_files.append('BUILD')
        print('b')

        if self._needs_build(package_info):
          print('c')
          code = None
          fn = None
          try:
            code = marshal.loads(self._func)
            print('d')
            fn = types.FunctionType(code, globals(), str(self._build_rule))
          except:
            print('couldnt compile')
            raise exceptions.BuildRuleCompilationError()

          print('e')
          try:
            print('foo')
            #fn(self, name=self._name, **self._args)
          except Exception as e:
            raise exceptions.BuildRuleRuntimeError(e)

        print('f')
        try:
          package_info.export()
        except Exception as e:
          print(e)
        print('g')