
import marshal
import os
import shutil
import tempfile
import time
import types

from impulse import impulse_paths
from impulse.core import debug
from impulse.core import exceptions
from impulse.core import threading
from impulse.pkg import overlayfs
from impulse.pkg import packaging
from impulse.util import temp_dir

EXPORT_DIR = impulse_paths.EXPORT_DIR
PACKAGES_DIR = os.path.join(EXPORT_DIR, 'PACKAGES')
BINARIES_DIR = os.path.join(EXPORT_DIR, 'BINARIES')


def GetRootRelativePath(path:str):
  root = impulse_paths.root()
  if path.startswith(root):
    return path[len(root)+1:]
  return None


def CheckRuleFile(rulefile):
  if rulefile.endswith('/impulse/impulse/recursive_loader.py'):
    return rulefile[:-28]
  if rulefile.endswith('/impulse/impulse/build_target.py'):
    return rulefile[:-24]
  return rulefile


class Any(object):
  __slots__ = ('_objects', )
  def __init__(self, *objs):
    self._objects = objs

  def __eq__(self, other):
    for each in self._objects:
      if each == other: return True
    return False


class BuildTarget(threading.GraphNode):
  """A threadable graph node object representing work to do to build."""

  def __init__(self, target_name: str, # The name of the target to build
                     func, # A marshalled function bytecode blob
                     args: dict, # The build target parameters to call func
                     rule: impulse_paths.ParsedTarget, # The ParsedTarget
                     buildrule_name: str, # The buildrule type, ex: c_header
                     scope: dict, # A map from name to marshalled bytecode
                     dependencies: set, # A set of BuildTargets dependencies
                     platform: impulse_paths.Platform, # the platform definition
                     extra_tags: list, # A list of tags that come from a target
                     can_access_internal: bool = False, # Has internal access
                     force_build:bool = False): # Always build even if recent
    super().__init__(dependencies, can_access_internal)

    # These can't be unmarshalled until we're on the other thread in |run_job|
    self._marshalled_func = func
    self._marshalled_scope = scope
    self._buildrule_args = args

    self._buildrule_pt = rule
    self._target_name = target_name
    self._buildrule_name = buildrule_name
    self._force_build = force_build

    self._package = packaging.ExportablePackage(
      rule, buildrule_name, platform, can_access_internal,
      os.path.join(impulse_paths.output_directory(), 'BINARIES'))
    self._package.SetTags(*extra_tags)

  def __eq__(self, other):
    return (other.__class__ == self.__class__ and
            other._buildrule_pt == self._buildrule_pt)

  def __hash__(self):
    return hash(str(self))

  def __repr__(self):
    return str(self)

  def __str__(self):
    return 'BuildTarget[{}]'.format(self._buildrule_pt)

  def get_name(self):
    """override"""
    return str(self._buildrule_pt)

  def data(self):
    return self._package

  def LoadToTemp(self, package_dir, binary_dir):
    return self._package.LoadToTemp(package_dir, binary_dir)

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
    self._package, needs_building, reason = self._package.NeedsBuild(
      package_dir, src_dir)
    if self._force_build:
      return True
    if self._buildrule_args.get('build_always', False):
      return True
    return needs_building

  def _CompileBuildRule(self):
    self.check_thread()
    try:
      code = marshal.loads(self._marshalled_func)
      return (
        types.FunctionType(code, self._GetExecEnv(), str(self._buildrule_name)),
        code.co_filename, self._buildrule_pt.GetBuildFileForTarget()
      )
    except Exception as e:
      raise exceptions.BuildRuleCompilationError(e)

  def _RunBuildRule(self):
    self.check_thread()
    buildrule, rule, buildfile = self._CompileBuildRule()
    try:
      return buildrule(self._package, **self._buildrule_args), rule, buildfile
    except exceptions.BuildDefsRaisesException:
      raise
    except exceptions.BuildTargetNoBuildNecessary:
      raise
    except Exception as e:
      # TODO pull snippits of the code and highlight the erroring line,
      # then print that.
      target_name = self._buildrule_args['name']
      buildrule_type = str(self._buildrule_name)
      raise exceptions.BuildDefsRaisesException(target_name, buildrule_type, e)

  def _GetBuildRuleIncludedFiles(self, buildroot, pkgdir):
    self.check_thread()
    def _unpack(obj):
      if type(obj) == list:
        for k in obj:
          for v in _unpack(k):
            yield v
      if type(obj) == str:
        yield obj
      if type(obj) == dict:
        for k, v in obj.items():
          if k in ('srcs', 'data'):
            for q in _unpack(v):
              yield q
    result = {}
    for potential in _unpack(self._buildrule_args):
      fq_path = os.path.join(buildroot, potential)
      if os.path.exists(fq_path):
        result[os.path.join(pkgdir, potential)] = fq_path
    return result


  # Entry point where jobs start
  def run_job(self, debug, internal_access=None):
    if internal_access:
      self._package.SetInternalAccess(internal_access)

    rulepath = self._buildrule_pt.GetPackagePathDirOnly()

    # Real root-relative path for packages.
    pkg_directory = os.path.join(impulse_paths.root(), PACKAGES_DIR)
    bin_directory = os.path.join(impulse_paths.root(), BINARIES_DIR)

    # Actual directory where buildfile lives.
    build_root = os.path.join(impulse_paths.root(), rulepath)

    # The input files specified in the rule in the BUILD file.
    forced_files = self._GetBuildRuleIncludedFiles(build_root, rulepath)
    included_files = {}
    included_files.update(forced_files)

    # A list of temporary directories where dependant packages are extracted
    loaded_dep_dirs = []
    for dependency in self.dependencies:
      directory, files, package = dependency.LoadToTemp(
        pkg_directory, bin_directory)
      if directory:
        loaded_dep_dirs.append(directory)
      self._package.AddDependency(package)
      forced_files.update(files)

    # The actual source files - this MUST be read only!
    ro_directory = os.path.join(impulse_paths.root())

    # Exit early, no work to do.
    if not self._NeedsBuild(pkg_directory, ro_directory):
      return

    # This is going to be where all file writes end up
    rw_directory = tempfile.mkdtemp()

    # This is where rw_directory, ro_directory, and loaded_dep_dirs get mirrored
    working_directory = tempfile.mkdtemp()

    try:
      # The final location for the .pkg file
      package_full_path = os.path.join(pkg_directory,
        self._buildrule_pt.GetPackagePkgFile())

      export_binary = None

      with overlayfs.FuseCTX(working_directory, rw_directory, forced_files,
                            *loaded_dep_dirs):
        with temp_dir.ScopedTempDirectory(working_directory):
          # Set these as the hashed input files
          self._package.SetInputFiles(included_files.keys())
          export_binary, rulefile, buildfile = self._RunBuildRule()
          rulefile = CheckRuleFile(rulefile)
          self._package.SetRuleFile(GetRootRelativePath(rulefile), rulefile)
          self._package.SetBuildFile(GetRootRelativePath(buildfile), buildfile)
          if not (internal_access and internal_access.rerun_more_deps):
            self._package = self._package.Export()
            packaging.EnsureDirectory(os.path.dirname(package_full_path))
            shutil.copyfile(self._package.filename, package_full_path)
            if self._package.is_binary_target:
              if not export_binary:
                raise Exception('{} must return a binary exporter!'.format(
                  self._buildrule_name))
              bindir = os.path.join(bin_directory, rulepath)
              packaging.EnsureDirectory(bindir)
              export_binary(self._package, self._target_name,
                            package_full_path, bindir)
    except exceptions.FilesystemSyncException:
      raise
    except exceptions.BuildTargetNoBuildNecessary:
      pass
    finally:
      shutil.rmtree(working_directory)
      shutil.rmtree(rw_directory)
      for d in self.dependencies:
        d.UnloadPackageDirectory()