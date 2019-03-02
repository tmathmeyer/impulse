
import marshal
import os
import re
import shutil
import tempfile
import time
import traceback
import types

from impulse import exceptions
from impulse import impulse_paths
from impulse import threaded_dependence

from impulse.pkg import overlayfs
from impulse.pkg import packaging

RULE_REGEX = re.compile('//(.*):(.*)')
EXPORT_DIR = impulse_paths.EXPORT_DIR
PACKAGES_DIR = os.path.join(EXPORT_DIR, 'PACKAGES')
BINARIES_DIR = os.path.join(EXPORT_DIR, 'BINARIES')




class BuildTarget(threaded_dependence.DependentJob):
  """A threadable graph node object representing work to do to build."""

  def __init__(self, target_name: str, # The name of the target to build
                     func, # A marshalled function bytecode blob
                     args: dict, # The build target parameters to call func with
                     rule: impulse_paths.ParsedTarget, # The ParsedTarget
                     buildrule_name: str, # The buildrule type (ie: py_library) 
                     scope: dict, # A map from name to marshalled bytecode
                     dependencies: set): # A set of BuildTargets dependencies
    super().__init__(dependencies)

    # These can't be unmarshalled until we're on the other thread in |run_job|
    self._marshalled_func = func
    self._marshalled_scope = scope
    self._buildrule_args = args

    self._buildrule_pt = rule
    self._target_name = target_name
    self._buildrule_name = buildrule_name

    self._package = packaging.ExportablePackage(rule, buildrule_name)

  def __eq__(self, other):
    return (other.__class__ == self.__class__ and
            other._buildrule_pt == self._buildrule_pt)

  def __hash__(self):
    return hash(str(self))

  def __repr__(self):
    return str(self)

  def __str__(self):
    return 'BuildTarget[{}]'.format(self._buildrule_pt)

  def LoadToTemp(self, package_name):
    return self._package.LoadToTemp(package_name)

  def UnloadPackageDirectory(self):
    return self._package.UnloadPackageDirectory()

  def _GetExecEnv(self):
    self.check_thread()
    environment = globals()
    for k, v in self._marshalled_scope.items():
      environment[k] = types.FunctionType(marshal.loads(v), globals(), k)
    return environment

  def _NeedsBuild(self, package_dir, src_dir):
    self.check_thread()
    self._package, needs_building = self._package.NeedsBuild(
      package_dir, src_dir)
    return needs_building

  def _CompileBuildRule(self):
    self.check_thread()
    try:
      code = marshal.loads(self._marshalled_func)
      return types.FunctionType(code, self._GetExecEnv(),
        str(self._buildrule_name))
    except Exception as e:
      print(e)
      raise exceptions.BuildRuleCompilationError()

  def _RunBuildRule(self):
    self.check_thread()
    buildrule = self._CompileBuildRule()
    try:
      return buildrule(self._package, **self._buildrule_args)
    except Exception as e:
      traceback.print_exc()
      raise exceptions.BuildRuleRuntimeError(e)

  # Entry point where jobs start
  def run_job(self, debug):

    rulepath, rulename = RULE_REGEX.match(str(self._buildrule_pt)).groups()

    # Real root-relative path for packages.
    pkg_directory = os.path.join(impulse_paths.root(), PACKAGES_DIR)

    # A list of temporary directories where dependant packages are extracted
    loaded_dep_dirs = []
    for dependency in self.dependencies:
      directory, package = dependency.LoadToTemp(pkg_directory)
      loaded_dep_dirs.append(directory)
      self._package.AddDependency(package)

    # The actual source files - this MUST be read only!
    ro_directory = os.path.join(impulse_paths.root())

    # Exit early, no work to do.
    if not self._NeedsBuild(pkg_directory, ro_directory):
      raise exceptions.BuildTargetNeedsNoUpdate()

    # This is going to be where all file writes end up
    rw_directory = tempfile.mkdtemp()

    # This is where rw_directory, ro_directory, and loaded_dep_dirs get mirrored
    working_directory = tempfile.mkdtemp()

    # The final location for the .pkg file
    package_full_path = os.path.join(pkg_directory,
      self._buildrule_pt.GetPackagePkgFile())

    export_binary = None

    with overlayfs.FuseCTX(working_directory, rw_directory, ro_directory,
                          *loaded_dep_dirs):
      with packaging.ScopedTempDirectory(working_directory):
        with packaging.ScopedTempDirectory(rulepath):
          self._package.buildroot = (working_directory, rulepath)
          export_binary = self._RunBuildRule()
        self._package = self._package.Export()
        packaging.EnsureDirectory(os.path.dirname(package_full_path))
        shutil.copyfile(self._package.filename, package_full_path)
        if self._package.is_binary_target:
          if not export_binary:
            raise Exception('{} must return a binary exporter!'.format(
              self._buildrule_name))
          bindir = os.path.join(impulse_paths.root(), BINARIES_DIR,
            self._buildrule_pt.GetPackagePathDirOnly())
          packaging.EnsureDirectory(bindir)
          export_binary(self._target_name, package_full_path, bindir)

    shutil.rmtree(working_directory)
    shutil.rmtree(rw_directory)
    for d in self.dependencies:
      d.UnloadPackageDirectory()