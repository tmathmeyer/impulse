
import marshal
import os
import shutil
import tempfile
import time
import types

from impulse import impulse_paths
from impulse import threaded_dependence
from impulse.exceptions import exceptions
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


class BuildTarget(threaded_dependence.GraphNode):
  """A threadable graph node object representing work to do to build."""

  def __init__(self, target_name: str, # The name of the target to build
                     func, # A marshalled function bytecode blob
                     args: dict, # The build target parameters to call func
                     rule: impulse_paths.ParsedTarget, # The ParsedTarget
                     buildrule_name: str, # The buildrule type, ex: c_header
                     scope: dict, # A map from name to marshalled bytecode
                     dependencies: set, # A set of BuildTargets dependencies
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
      rule, buildrule_name, can_access_internal)

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
    self._package, needs_building = self._package.NeedsBuild(
      package_dir, src_dir)
    if self._force_build:
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
          self._package.SetRuleFile(GetRootRelativePath(rulefile), rulefile)
          self._package.SetBuildFile(GetRootRelativePath(buildfile), buildfile)
          self._package = self._package.Export()
          packaging.EnsureDirectory(os.path.dirname(package_full_path))
          shutil.copyfile(self._package.filename, package_full_path)
          if self._package.is_binary_target:
            if not export_binary:
              raise Exception('{} must return a binary exporter!'.format(
                self._buildrule_name))
            bindir = os.path.join(bin_directory, rulepath)
            packaging.EnsureDirectory(bindir)
            export_binary(self._target_name, package_full_path, bindir)
    except exceptions.FilesystemSyncException:
      raise
    finally:
      shutil.rmtree(working_directory)
      shutil.rmtree(rw_directory)
      for d in self.dependencies:
        d.UnloadPackageDirectory()


class FileParserResult(object):
  def __init__(self, name, checkout, args, pgt: 'ParsedGitTarget'):
    self._converted = BuildTarget(
      target_name = name,
      func = marshal.dumps(checkout.__code__),
      args = args,
      rule = pgt,
      buildrule_name = 'gitclone',
      scope = {},
      dependencies = set(),
      force_build = True)

  def Convert(self):
    return set([self._converted])


class MockConvertedTarget(object):
  def __init__(self, chief_dependency, converted):
    self._converted = converted
    self._chief_dependency = chief_dependency

  def Convert(self):
    return set([self._chief_dependency])


class ParsedGitTarget(impulse_paths.ParsedTarget):
  def __init__(self, url, repo, target, commit=None):
    if ':' not in target:
      raise impulse_paths.PathException(target, None)
    path, name = target.split(':')
    super().__init__(name, path)
    self._url = url
    self._commit = commit
    self._repo = repo

  def _MakeCloneTarget(self):
    target_name = f'git@{self.target_name}+clone'
    return BuildTarget(
      target_name = target_name,
      func = marshal.dumps(GitClone.__code__),
      args = {'name': self.target_name, 'url': self._url, 'repo': self._repo},
      rule = impulse_paths.ParsedTarget(target_name, self.target_path),
      buildrule_name = 'git_clone',
      scope = {},
      dependencies = set())

  def _MakeCheckoutTarget(self, clone_target):
    target_name = f'git@{self.target_name}+checkout'
    return BuildTarget(
      target_name = target_name,
      func = marshal.dumps(GitCheckout.__code__),
      args = {'name': self.target_name, 'commit': self._commit},
      rule = impulse_paths.ParsedTarget(target_name, self.target_path),
      buildrule_name = 'git_checkout',
      scope = {},
      dependencies = set([clone_target]),
      can_access_internal = True)

  def _MakeParentTarget(self, *children):
    target_name = f'git@{self.target_name}'
    return BuildTarget(
      target_name = target_name,
      func = marshal.dumps(GitRunChild.__code__),
      args = {'name': self.target_name, 'path': self.target_path},
      rule = impulse_paths.ParsedTarget(target_name, self.target_path),
      buildrule_name = 'git_parent',
      scope = {},
      dependencies = set(children),
      can_access_internal = True,
      force_build=True)


  def ParseFile(self, rfp, parser):
    clone = self._MakeCloneTarget()
    # checkout = self._MakeCheckoutTarget(clone)
    parent = self._MakeParentTarget(clone) #, checkout)
    rfp._targets[self] = MockConvertedTarget(
      parent, set([clone, parent]))


def GitClone(target, name, repo, url):
  repo_exists_path = os.path.join(impulse_paths.root(), repo)
  if not os.path.exists(repo_exists_path):
    command = f'git clone {url} {repo_exists_path}'
    clone = target.RunCommand(command)
    if clone.returncode:
      target.ExecutionFailed(command, clone.stderr)
  with open('gitlocation', 'w+') as f:
    f.write(repo_exists_path)
  target.AddFile('gitlocation')
  target.SetInputFiles([os.path.join(
    repo_exists_path, '.git', 'HEAD')])


def GitCheckout(target, name, commit):
  repo_path = None
  with open('gitlocation', 'r') as f:
    repo_path = f.read()
  new_checkout = target.Internal.temp_dir.CreateDangerousLifetimeDirectory()
  with target.Internal.temp_dir.ScopedTempDirectory(repo_path):
    command = f'git worktree add {new_checkout} {commit}'
    result = target.RunCommand(command)
    if result.returncode:
      target.ExecutionFailed(command, result.stderr)
  with open('gitlocation', 'w+') as f:
    f.write(new_checkout)
  target.AddFile('gitlocation')


def GitRunChild(target, name, path):
  constructed = impulse_paths.ParsedTarget(name, path)
  graph = target.Internal.recursive_loader.generate_graph(constructed)
  target.Internal.build_queue.InjectMoreGraph(graph)
  target.Internal.build_queue.MoveDependencyTo(constructed)
