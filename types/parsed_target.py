
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
from impulse.types import names
from impulse.types import typecheck
from impulse.util import temp_dir


RULE_STAGING_RECURSIVE_CANARY = object()
EXPORT_DIR = 'GENERATED'
PACKAGES_DIR = os.path.join(EXPORT_DIR, 'PACKAGES')
BINARIES_DIR = os.path.join(EXPORT_DIR, 'BINARIES')


class TargetLocalName(object):
  @typecheck.Assert
  def __init__(self, name:str):
    self._value = name

  @typecheck.Assert
  def Value(self) -> str:
    return self._value


class TargetReferenceName(object):
  @typecheck.Assert
  def __init__(self, name:TargetLocalName, path:paths.Path):
    self._target_name = name
    self._target_path = path.QualifiedPath()

  @typecheck.Assert
  def __repr__(self) -> str:
    return str(self)

  @typecheck.Assert
  def __str__(self) -> str:
    return self._target_path.Value() + ':' + self._target_name.Value()

  @typecheck.Assert
  def __hash__(self) -> int:
    return hash(repr(self))

  @typecheck.Assert
  def __eq__(self, other:typing.Any) -> int:
    if not isinstance(other, TargetReferenceName):
      return False
    return repr(self) == repr(other)

  @typecheck.Assert
  def GetBuildFileForTarget(self) -> paths.AbsolutePath:
    try:
      abspath = self._target_path.AbsolutePath().Value()
      return paths.AbsolutePath(os.path.join(abspath, 'BUILD'))
    except exceptions.InvalidPathException:
      raise exceptions.BuildTargetMissing(
        f'Definition for rule `{repr(self)}` not found')

  @typecheck.Assert
  def GetPackageFile(self) -> str:
    # TODO: replace return type with something defined
    return os.path.join(
      self._target_path.QualifiedPath().Value()[2:],
      self._target_name.Value()) + '.zip'

  @typecheck.Assert
  def GetRuleInfo(self) -> None:
    return None


class Target(object):
  def __init__(self, name:TargetReferenceName):
    self._name = name

  def __repr__(self) -> str:
    return f'Target[{self._name}]'


class PlatformTarget(Target):
  def __init__(self, refname_name:TargetReferenceName, **kwargs):
    super().__init__(refname_name)
    #TODO: un-sketch this class
    self._values = kwargs

  def __getattr__(self, attr):
    if attr.startswith('__'):
      raise AttributeError(attr)
    if attr not in self._values:
      raise exceptions.PlatformKeyAbsentError(
        self._values['platform_target'], attr)
    return self._values[attr]


class StagedBuildTarget(Target):
  def __init__(self, name:TargetReferenceName):
    super().__init__(name)


class StagedBuildTargetSet(object):
  __slots__ = ('_targets',)
  def __init__(self, targets=None):
    self._targets:set[StagedBuildTarget] = set(targets or set())

  def AddAll(self, targets:'StagedBuildTargetSet') -> None:
    self._targets |= targets._targets


class TargetArchive(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def AddMetaTarget(self, target:Target):
    '''Adds a meta target generated thru a buildmacro'''

  @abc.abstractmethod
  def AddBuildTarget(self, target:Target):
    '''Adds a build target'''

  @abc.abstractmethod
  def AddPlatformTarget(self, target:Target):
    '''Adds a platform target'''

  @abc.abstractmethod
  def SetDefaultPlatformTarget(self, target:Target):
    '''Sets the default platform target'''

  @abc.abstractmethod
  def GetPlatformTarget(self, name:TargetReferenceName) -> Target:
    '''Gets a platform target by name'''

  @abc.abstractmethod
  def GetDefaultPlatformTarget(self) -> Target:
    '''Gets the default platform target if set'''

  @abc.abstractmethod
  def GetBuildTarget(self, name:TargetReferenceName) -> Target:
    '''Gets a build target by name'''


class BuildTarget(Target):
  __slots__ = ('_name', '_func', '_kwargs', '_scope', '_tags', '_deps', '_includes', '_staged')
  def __init__(self, name:TargetReferenceName,
               function:typing.Callable,
               kwargs:dict,
               scope:dict,
               tags:list[str]):
    super().__init__(name)
    self._func = marshal.dumps(function.__code__)
    self._deps = []
    self._includes = {}
    self._kwargs = self._PrecomputeDependencies(kwargs)
    self._scope = scope
    self._tags = tags
    self._staged = None
    self._rule_name = function.__name__

  def GetName(self) -> str:
    return str(self._name)

  @typecheck.Assert
  def _PrecomputeDependencies(self, search:typing.Any) -> typing.Any:
    if type(search) == dict:
      return {k:self._PrecomputeDependencies(v) for k,v in search.items()}
    if type(search) == list:
      return [self._PrecomputeDependencies(i) for i in search]
    if type(search) == str:
      if converted := self._ConvertToTargetRefName(search):
        self._deps.append(converted)
        return converted
    return search

  @typecheck.Assert
  def _ConvertToTargetRefName(self, item:str) -> TargetReferenceName|None:
    if not len(item):
      return None
    if item[0] == ':':
      return TargetReferenceName(
        TargetLocalName(item[1:]),
        self._name._target_path.QualifiedPath())
    if item.startswith('//'):
      target = item.split(':')
      if len(target) != 2:
        raise exceptions.InvalidPathException(
          item, 'Malformatted buildrule')
      path, name = target
      return TargetReferenceName(TargetLocalName(name), paths.QualifiedPath(path))
    return None

  def GetDependencies(self) -> list[TargetReferenceName]:
    return list(self._deps)

  def AddIncludes(self, funcs:list[typing.Callable]) -> 'BuildTarget':
    for func in funcs:
      self._includes[func.__name__] = (marshal.dumps(func.__code__))
    return self

  @typecheck.Assert
  def Stage(self, archive:TargetArchive) -> StagedBuildTargetSet:
    if self._staged is RULE_STAGING_RECURSIVE_CANARY:
      raise exceptions.BuildTargetCycle.Cycle(self)
    if self._staged is not None:
      return self._staged
    self._staged = RULE_STAGING_RECURSIVE_CANARY
    try:
      return self._StageInternal(archive)
    except exceptions.BuildTargetCycle as e:
      raise e.ChainException(self)

  @typecheck.Assert
  def _StageInternal(self, archive:TargetArchive) -> StagedBuildTargetSet:
    print(self._name)
    dependencies = StagedBuildTargetSet()
    for dependency in self._deps:
      dependencies.AddAll(archive.GetBuildTarget(dependency).Stage(archive))
    self._staged = StagedBuildTargetSet([
      StagedBuildTargetImpl(self, dependencies, archive, False, False)
    ])
    return self._staged


class Any(object):
  __slots__ = ('_objects', )
  def __init__(self, *objs):
    self._objects = objs

  def __eq__(self, other):
    for each in self._objects:
      if each == other: return True
    return False


class StagedBuildTargetImpl(threading.GraphNode, StagedBuildTarget):
  def __init__(self, target:BuildTarget, dependencies:StagedBuildTargetSet, archive:TargetArchive, force:bool, internal:bool):
    threading.GraphNode.__init__(self, dependencies._targets, internal)
    StagedBuildTarget.__init__(self, target._name)

    # These can't be unmarshalled or accessed on the main thread
    self._marshalled_func = target._func
    self._marshalled_includes = target._includes
    self._marshalled_kwargs = target._kwargs

    self._force_build = force
    self._buildrule_name = target._rule_name
    self._package = packaging.ExportablePackage(
      target._name, target._rule_name, archive.GetDefaultPlatformTarget(), internal)

  def __eq__(self, other:typing.Any) -> bool:
    return (other.__class__ == self.__class__ and
            other._name == self._name)

  def __hash__(self) -> str:
    return hash(self._name)

  def __repr__(self) -> str:
    return f'Staged[{self._name}]'

  def LoadToTemp(self, package_dir:str, binary_dir:str) -> None:
    return self._package.LoadToTemp(package_dir, binary_dir)

  @typecheck.Assert
  def UnloadPackageDirectory(self) -> None:
    return self._package.UnloadPackageDirectory()

  @typecheck.Assert
  def get_name(self) -> None:
    return str(self._name)

  @typecheck.Assert
  def data(self) -> packaging.ExportablePackage:
    return self._package

  @typecheck.Assert
  def _GetFilesIncludedInBuildDirectory(self, root:paths.AbsolutePath) -> dict:
    self.check_thread()
    result = {}
    relative = root.QualifiedPath().Value()[2:]
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

  @typecheck.Assert
  def _NeedsBuild(self, package_dir:str, src_dir:str) -> bool:
    self.check_thread()
    self._package, needs_building, _ = self._package.NeedsBuild(
      package_dir, src_dir)
    if self._force_build:
      return True
    if self._marshalled_kwargs.get('build_always', False):
      return True
    return needs_building

  @typecheck.Assert
  def _RunBuildRule(self) -> typing.Any:
    self.check_thread()
    buildrule, rule, buildfile = self._CompileBuildRule()
    try:
      print(self._marshalled_kwargs)
      return buildrule(self._package, **self._marshalled_kwargs), rule, buildfile
    except exceptions.BuildDefsRaisesException:
      raise
    except exceptions.BuildTargetNoBuildNecessary:
      raise
    except Exception as e:
      # TODO pull snippits of the code and highlight the erroring line,
      # then print that.
      target_name = self._marshalled_kwargs['name']
      buildrule_type = str(self._buildrule_name)
      raise exceptions.BuildDefsRaisesException(target_name, buildrule_type, e)

  @typecheck.Assert
  def _CompileBuildRule(self) -> tuple[types.FunctionType, str, str]:
    self.check_thread()
    try:
      code = marshal.loads(self._marshalled_func)
      return (
        types.FunctionType(code, self._GetExecEnv(), str(self._buildrule_name)),
        code.co_filename, self._name.GetBuildFileForTarget().Value()
      )
    except Exception as e:
      raise exceptions.BuildRuleCompilationError(e)

  @typecheck.Assert
  def _GetExecEnv(self) -> dict:
    self.check_thread()
    environment = globals()
    for k, v in self._marshalled_includes.items():
      environment[k] = types.FunctionType(marshal.loads(v), globals(), k)
    return environment

  def run_job(self, debug:bool, internal_access:None=None) -> None:
    # Set internal access on the packae
    if internal_access:
      self._package.SetInternalAccess(internal_access)

    # The absolute path for the directory where this target is defined.
    build_root = self._name._target_path.AbsolutePath()

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
    print(build_root.Value(), forced_files)

    ro_directory = environment.Root()
    if not self._NeedsBuild(package_directory, ro_directory):
      return

    rw_directory = tempfile.mkdtemp()
    working_directory = tempfile.mkdtemp()

    package_export_path = os.path.join(package_directory, self._name.GetPackageFile())

    try:
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
            packaging.EnsureDirectory(os.path.dirname(package_export_path))
            shutil.copyfile(self._package.filename, package_export_path)
            if self._package.is_binary_target:
              if not export_binary:
                raise Exception('{} must return a binary exporter!'.format(
                  self._buildrule_name))
              bindir = os.path.join(binaries_directory, build_root.QualifiedPath().Value()[2:])
              packaging.EnsureDirectory(bindir)
              export_binary(self._package, self._name._target_name.Value(),
                            package_export_path, bindir)
    except exceptions.FilesystemSyncException:
      raise
    except exceptions.BuildTargetNoBuildNecessary:
      pass
    finally:
      shutil.rmtree(working_directory)
      shutil.rmtree(rw_directory)
      for d in self.dependencies:
        d.UnloadPackageDirectory()


def CheckRuleFile(rulefile):
  print('CHECKING', rulefile)
  if rulefile.endswith('/impulse/impulse/recursive_loader.py'):
    return rulefile[:-28]
  if rulefile.endswith('/impulse/impulse/build_target.py'):
    return rulefile[:-24]
  return rulefile


def GetRootRelativePath(path:str):
  root = environment.Root()
  if path.startswith(root):
    return path[len(root)+1:]
  return None


@typecheck.Assert
def GetTargetReferenceFromInvocation(name:TargetLocalName,
                                     path:paths.Path) -> TargetReferenceName:
  directory, file = path.SplitFile()
  if file not in ('BUILD', 'build_defs.py'):
    raise exceptions.InvalidPathException(
      'Targets must be defined in BUILD files or in macro invocations',
      path)
  return TargetReferenceName(name, directory)


@typecheck.Assert
def ParseTargetReferenceFromString(content:str) -> TargetReferenceName:
  if not content.startswith('//'):
    raise exceptions.InvalidPathException(
      'Traget must be a qualified path (start with //)', content)
  split = content.split(':')
  if len(split) != 2:
    raise exceptions.InvalidPathException(
      'Target must be a qualified path (//path/to/build:rulename)', content)
  path, name = split
  return TargetReferenceName(TargetLocalName(name), paths.QualifiedPath(path))

