from __future__ import annotations
import abc
import marshal
import os
import shutil
import tempfile
import typing
import types

from impulse.core import exceptions
from impulse.core import environment
from impulse.core import threading
from impulse.pkg import overlayfs
from impulse.pkg import packaging
from impulse.types import paths
from impulse.types import references
from impulse.util import temp_dir


RULE_STAGING_RECURSIVE_CANARY = object()
EXPORT_DIR = 'GENERATED'
PACKAGES_DIR = os.path.join(EXPORT_DIR, 'PACKAGES')
BINARIES_DIR = os.path.join(EXPORT_DIR, 'BINARIES')


class BuildableTargetInterface(typing.Protocol):
  """Protocol for buildable target functions."""
  __code__:types.CodeType
  __name__:str


class Target(object):
  """Base class for all build targets."""
  _name:references.Target

  def __init__(self, name:references.Target):
    self._name = name

  def __repr__(self) ->str:
    return f'Target[{self._name}]'


class PlatformTarget(Target):
  """Represents a target platform and its properties."""
  def __init__(self, refname_name:references.Target, **kwargs:typing.Any):
    super().__init__(refname_name)
    # TODO: un-sketch this class
    self._values = kwargs

  def __getattr__(self, attr:str) ->typing.Any:
    if attr.startswith('__'):
      raise AttributeError(attr)
    if attr not in self._values:
      raise exceptions.PlatformKeyAbsentError(
        self._values.get('platform_target', str(self._name)), attr)
    return self._values[attr]


class StagedBuildTarget(Target):
  """Represents a build target that has been staged for execution."""
  def __init__(self, name:references.Target):
    super().__init__(name)


class StagedBuildTargetSet(object):
  """A set of StagedBuildTarget objects."""
  __slots__ = ('_targets',)
  def __init__(self, targets:set[StagedBuildTarget]|None = None):
    self._targets:set[StagedBuildTarget] = set(targets or set())

  def AddAll(self, targets:StagedBuildTargetSet) ->None:
    """Adds all targets from another set to this set."""
    self._targets |= targets._targets


class TargetArchive(metaclass=abc.ABCMeta):
  """Interface for an archive of build and platform targets."""
  @abc.abstractmethod
  def AddMetaTarget(self, target:Target) ->None:
    """Adds a meta target generated through a buildmacro."""

  @abc.abstractmethod
  def AddBuildTarget(self, target:BuildTarget) ->BuildTarget:
    """Adds a build target to the archive."""

  @abc.abstractmethod
  def AddPlatformTarget(self, target:PlatformTarget) ->PlatformTarget:
    """Adds a platform target to the archive."""

  @abc.abstractmethod
  def SetDefaultPlatformTarget(self, target:PlatformTarget) ->None:
    """Sets the default platform target."""

  @abc.abstractmethod
  def GetPlatformTarget(self, name:references.Target) ->PlatformTarget:
    """Gets a platform target by name."""

  @abc.abstractmethod
  def GetDefaultPlatformTarget(self) ->PlatformTarget:
    """Gets the default platform target if set."""

  @abc.abstractmethod
  def GetBuildTarget(self, name:references.Target) ->BuildTarget:
    """Gets a build target by name."""

  @abc.abstractmethod
  def GetBuildTargetFromFile(self, file:references.File, name:str) ->typing.Callable:
    """Gets a build target from a given file."""


class BuildTarget(Target):
  """Represents a build target with its rule function and arguments."""
  __slots__ = ('_name', '_func', '_kwargs', '_scope', '_tags', '_deps',
               '_includes', '_staged', '_rule_name')
  def __init__(self, name:references.Target,
               function:BuildableTargetInterface,
               kwargs:dict,
               scope:dict,
               tags:list[str]):
    super().__init__(name)
    self._func = marshal.dumps(function.__code__)
    self._deps:list[references.Target] = []
    self._includes:dict[str, bytes] = {}
    self._kwargs = self._PrecomputeDependencies(kwargs)
    self._scope = scope
    self._tags = tags
    self._staged:StagedBuildTargetSet|object|None = None
    self._rule_name = function.__name__

  def GetName(self) ->str:
    """Returns the fully qualified name of the target."""
    return str(self._name)

  def _PrecomputeDependencies(self, search:typing.Any) ->typing.Any:
    """Recursively finds target references in the rule arguments."""
    if isinstance(search, dict):
      return {k:self._PrecomputeDependencies(v) for k, v in search.items()}
    if isinstance(search, list):
      return [self._PrecomputeDependencies(i) for i in search]
    if isinstance(search, str):
      if converted := self._ConvertToTargetRefName(search):
        self._deps.append(converted)
        return converted
    return search

  def _ConvertToTargetRefName(self, item:str) ->references.Target|None:
    """Attempts to parse a string as a target reference."""
    try:
      return references.Target.Parse(item, self._name.GetDirectory())
    except exceptions.InvalidPathException:
      return None

  def GetDependencies(self) ->list[references.Target]:
    """Returns the list of dependencies for this target."""
    return list(self._deps)

  def AddIncludes(self, funcs:list[BuildableTargetInterface]) ->BuildTarget:
    """Adds additional helper functions to the rule execution environment."""
    for func in funcs:
      self._includes[func.__name__] = (marshal.dumps(func.__code__))
    return self

  def Stage(self, archive:TargetArchive) ->StagedBuildTargetSet:
    """Stages the target and its dependencies for execution."""
    if self._staged is RULE_STAGING_RECURSIVE_CANARY:
      raise exceptions.BuildTargetCycle.Cycle(self)
    if self._staged is not None and isinstance(self._staged, StagedBuildTargetSet):
      return self._staged
    self._staged = RULE_STAGING_RECURSIVE_CANARY
    try:
      return self._StageInternal(archive)
    except exceptions.BuildTargetCycle as e:
      raise e.ChainException(self) from None
    except exceptions.BuildTargetMissing as e:
      raise exceptions.ImpulseFileChainException(str(e), [str(self._name)])
    except exceptions.ImpulseFileChainException as e:
      raise e.Chain(str(self._name))

  def _StageInternal(self, archive:TargetArchive) ->StagedBuildTargetSet:
    """Internal staging logic that handles dependency resolution."""
    dependencies = StagedBuildTargetSet()
    for dependency in self._deps:
      dependencies.AddAll(archive.GetBuildTarget(dependency).Stage(archive))
    self._staged = StagedBuildTargetSet([
      StagedBuildTargetImpl(self, dependencies, archive, False, False)
    ])
    return self._staged


class Any(object):
  """Helper class to check if a value matches any of the provided objects."""
  __slots__ = ('_objects', )
  def __init__(self, *objs:typing.Any):
    self._objects = objs

  def __eq__(self, other:typing.Any) ->bool:
    for each in self._objects:
      if each == other: return True
    return False


class StagedBuildTargetImpl(threading.GraphNode, StagedBuildTarget):
  """Implementation of a staged build target that can be executed in a thread pool."""
  def __init__(self, target:BuildTarget, dependencies:StagedBuildTargetSet,
               archive:TargetArchive, force:bool, internal:bool):
    threading.GraphNode.__init__(self, dependencies._targets, internal)
    StagedBuildTarget.__init__(self, target._name)

    # These can't be unmarshalled or accessed on the main thread
    self._marshalled_func = target._func
    self._marshalled_includes = target._includes
    self._marshalled_kwargs = target._kwargs

    self._force_build = force
    self._buildrule_name = target._rule_name

    package_target:references.Target = target._name
    self._package = packaging.ExportablePackage(
      package_target=package_target,
      platform=archive.GetDefaultPlatformTarget(),
      ruletype=target._rule_name,
      can_access_internal=internal)

  def __eq__(self, other:typing.Any) ->bool:
    return (other.__class__ == self.__class__ and
            other._name == self._name)

  def __hash__(self) ->int:
    return hash(self._name)

  def __repr__(self) ->str:
    return f'Staged[{self._name}]'

  def LoadToTemp(self, package_dir:str, binary_dir:str) ->tuple[str, dict[str, str],
                                                                packaging.ExportablePackage]:
    """Loads the package into a temporary directory for build execution."""
    return self._package.LoadToTemp(package_dir, binary_dir)

  def UnloadPackageDirectory(self) ->None:
    """Unloads the package directory after build execution."""
    return self._package.UnloadPackageDirectory()

  def get_name(self) ->str:
    """Returns the name of the target."""
    return str(self._name)

  def data(self) ->packaging.ExportablePackage:
    """Returns the associated ExportablePackage data."""
    return self._package

  def _GetFilesIncludedInBuildDirectory(self, root:paths.AbsolutePath) ->dict[str, str]:
    """Returns a mapping of relative paths to absolute paths for files in the build directory."""
    self.check_thread()
    result = {}
    relative = root.QualPath().Value()[2:]
    for entry in self._marshalled_kwargs.get('srcs', []):
      filename = os.path.join(root.Value(), entry)
      if not os.path.exists(filename):
        raise exceptions.ListedSourceNotFound(filename, self._name)
      result[os.path.join(relative, entry)] = filename
    for entry in self._marshalled_kwargs.get('data', []):
      filename = os.path.join(root.Value(), entry)
      if not os.path.exists(filename):
        raise exceptions.ListedSourceNotFound(filename, self._name)
      result[os.path.join(relative, entry)] = filename
    return result

  def _NeedsBuild(self, package_dir:str, src_dir:str) ->bool:
    """Checks if the target needs to be rebuilt."""
    self.check_thread()
    self._package, needs_building, _ = self._package.NeedsBuild(
      package_dir, src_dir)
    if self._force_build:
      return True
    if self._marshalled_kwargs.get('build_always', False):
      return True
    return needs_building

  def _RunBuildRule(self) ->tuple[typing.Any, str, str]:
    """Executes the build rule function."""
    self.check_thread()
    buildrule, rule, buildfile = self._CompileBuildRule()
    try:
      return buildrule(self._package, **self._marshalled_kwargs), rule, buildfile
    except exceptions.BuildDefsRaisesException:
      raise
    except exceptions.BuildTargetNoBuildNecessary:
      raise
    except Exception as e:
      target_name = self._marshalled_kwargs['name']
      buildrule_type = str(self._buildrule_name)
      _, _, traceback = sys.exc_info()
      assert traceback is not None
      tb = traceback
      while tb and tb.tb_next:
        tb = tb.tb_next
      filename = tb.tb_frame.f_code.co_filename
      line_no = tb.tb_frame.f_lineno

      try:
        # Try to create a highlighted error if it's a file we can read
        if os.path.exists(filename):
          highlighted = exceptions.FileErrorException(
            f'Error in build rule `{buildrule_type}` for target `{target_name}`: {str(e)}',
            filename, line_no, 0, 0
          )
          raise exceptions.BuildDefsRaisesException(target_name,
                                                    buildrule_type,
                                                    highlighted) from None
      except:
        pass

      raise exceptions.BuildDefsRaisesException(target_name, buildrule_type, e)

  def _CompileBuildRule(self) ->tuple[types.FunctionType, str, str]:
    """Unmarshals and compiles the build rule function."""
    self.check_thread()
    try:
      code = marshal.loads(self._marshalled_func)
      return (
        types.FunctionType(code, self._GetExecEnv(), str(self._buildrule_name)),
        code.co_filename, self._name.GetBuildFile().Absolute().Value()
      )
    except Exception as e:
      raise exceptions.BuildRuleCompilationError(e)

  def _GetExecEnv(self) ->dict[str, typing.Any]:
    """Creates the execution environment for the build rule."""
    self.check_thread()
    env = globals().copy()
    for k, v in self._marshalled_includes.items():
      env[k] = types.FunctionType(marshal.loads(v), globals(), k)
    return env

  def run_job(self, debug:bool,
              internal_access:threading.UpdateGraphResponseData|None = None) ->typing.Any:
    """Runs the build job for this target."""
    # Set internal access on the package
    if internal_access:
      self._package.SetInternalAccess(internal_access)

    # The absolute path for the directory where this target is defined.
    build_root = self._name.GetDirectory().Absolute()

    # Generated files directories
    package_directory = os.path.join(environment.Root(), PACKAGES_DIR)
    binaries_directory = os.path.join(environment.Root(), BINARIES_DIR)

    # forced_files are files which have to be included in the overlayfs,
    # while included_files are the set of files which are checked when
    # calculating build update requirements.
    forced_files = self._GetFilesIncludedInBuildDirectory(build_root)
    included_files = dict(forced_files)

    # loaded_dep_dirs is the set of directories which get added as
    # overlays when overlayfs is mounted.
    loaded_dep_dirs = []
    for dependency in self.dependencies:
      directory, files, package = dependency.LoadToTemp(package_directory, binaries_directory)
      if directory:
        loaded_dep_dirs.append(directory)
      self._package.AddDependency(package)
      forced_files.update(files)

    ro_directory = environment.Root()
    if not self._NeedsBuild(package_directory, ro_directory):
      return

    pkg_rel_path = self._name.GetPackage().GetRelativePath()
    package_export_path = os.path.join(package_directory, pkg_rel_path)

    try:
      export_binary = None
      with overlayfs.FuseCTX(loaded_dep_dirs, forced_files) as working_directory:
        with temp_dir.ScopedTempDirectory(working_directory):
          # Set these as the hashed input files
          self._package.SetInputFiles(list(included_files.keys()))
          export_binary, rulefile, buildfile = self._RunBuildRule()
          rulefile = CheckRuleFile(rulefile)
          self._package.SetRuleFile(GetRootRelativePath(rulefile), rulefile)
          self._package.SetBuildFile(GetRootRelativePath(buildfile), buildfile)
          if not (internal_access and internal_access.rerun_more_deps):
            self._package = self._package.Export()
            packaging.EnsureDirectory(os.path.dirname(package_export_path))
            shutil.copyfile(self._package.filename, package_export_path)
            if self._package.is_binary_target:
              if not export_binary:
                raise Exception('{} must return a binary exporter!'.format(
                  self._buildrule_name))
              bindir = os.path.join(binaries_directory, build_root.QualPath().Value()[2:])
              packaging.EnsureDirectory(bindir)
              export_binary(self._package, self._name._target_name.Name(),
                            package_export_path, bindir)
          return export_binary
    except exceptions.FilesystemSyncException:
      raise
    except exceptions.BuildTargetNoBuildNecessary:
      pass
    finally:
      for d in self.dependencies:
        d.UnloadPackageDirectory()


def CheckRuleFile(rulefile:str) ->str:
  """Sanitizes rule file path if it's within impulse internal structure."""
  if rulefile.endswith('/impulse/impulse/recursive_loader.py'):
    return rulefile[:-28]
  if rulefile.endswith('/impulse/impulse/build_target.py'):
    return rulefile[:-24]
  return rulefile


def GetRootRelativePath(path:str) ->str|None:
  """Returns the path relative to the impulse root, or None if not within root."""
  root = environment.Root()
  if path.startswith(root):
    return path[len(root)+1:]
  return None
