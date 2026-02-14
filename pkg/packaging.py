from __future__ import annotations

import abc
import hashlib
import json
import os
import subprocess
import tempfile
import time
import typing
import zipfile

from impulse.types import references
from impulse.core import errors
from impulse.core import exceptions
from impulse.util import temp_dir
from impulse.core import debug
from impulse import impulse_paths

if typing.TYPE_CHECKING:
  from impulse.core import threading


NOT_THE_SAME=object()


def EnsureDirectory(directory:str) -> None:
  """Ensures that the given directory exists."""
  if directory and not os.path.exists(directory):
    os.makedirs(directory, exist_ok=True)


class Hasher(metaclass=abc.ABCMeta):
  """Abstract base class for components that can compute file hashes."""
  @abc.abstractmethod
  def GetHash(self, filename:str) -> str:
    """Returns the hash of the given file."""
    raise NotImplementedError()

  def MD5(self, filename:str) -> str:
    """Computes the MD5 hash of a file."""
    hash_md5=hashlib.md5()
    try:
      with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
          hash_md5.update(chunk)
      return hash_md5.hexdigest()
    except FileNotFoundError:
      return '----'


class HashedFile(object):
  """Represents a file along with its computed hash."""
  __slots__=('file', 'hash')

  def __init__(self, file:str, package:Hasher):
    self.file=file
    self.hash=package.GetHash(file)

  def dict(self) -> dict[str, str]:
    """Returns a dictionary representation of the hashed file."""
    return {'file': self.file, 'hash': self.hash}

  def __eq__(self, other:object) -> bool:
    if not isinstance(other, HashedFile):
      return False
    return self.file == other.file and self.hash == other.hash

  def __hash__(self) -> int:
    return hash(f'{self.file}//{self.hash}')


class ExportedPackage(object):
  """A read-only wrapper around a build package archive."""
  def __init__(self,
               filename:str,
               json_data:dict|None=None,
               export_binary:typing.Callable|None=None):
    self.filename=filename
    self.included_files:list[str]=[]
    self.package_target:references.Target|None=None
    self.build_timestamp:float=0.0
    if json_data:
      self.__dict__.update(json_data)
    if export_binary:
      self.ExportBinary=export_binary

  def NeedsBuild(self) -> tuple['ExportedPackage', bool, str|None]:
    """Exported packages are already built, so always returns False."""
    return self, False, None

  def IncludedFiles(self) -> list[str]:
    """Returns the list of files included in this package."""
    return list(self.included_files)

  def GetPropagatedData(self, key:str) -> object:
    """Retrieves data propagated from dependencies."""
    if key in self.__dict__:
      return self.__dict__[key]
    if '_propagated_data' in self.__dict__:
      if key in self.__dict__['_propagated_data']:
        return self.__dict__['_propagated_data'][key]
    return []

  def RunCommand(self, command:str) -> subprocess.CompletedProcess:
    """Executes a shell command."""
    return subprocess.run(command,
                          encoding='utf-8',
                          shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)

  def Execute(self, *cmds:str) -> None:
    """Executes a series of shell commands."""
    for command in cmds:
      try:
        r=self.RunCommand(command)
        if r.returncode:
          msg=f'command "{command}" failed:\n{r.stdout}\n{r.stderr}'
          raise errors.FatalError(msg)
      except Exception as e:
        if isinstance(e, errors.FatalError):
          raise
        raise errors.FatalError(f'command "{command}" failed: {str(e)}')

  def FatalError(self, msg:str) -> typing.NoReturn:
    """Raises a fatal error."""
    raise errors.FatalError(msg)

  def __str__(self) -> str:
    return '{}@{}'.format(str(self.package_target), self.build_timestamp)

  def __repr__(self) -> str:
    return str(self)

  def __getitem__(self, name:str) -> object:
    return getattr(self, name)


class ExportablePackage(Hasher):
  """Represents a package being built."""
  def __init__(self,
               package_target:references.Target,
               platform:'parsed_target.PlatformTarget|None',
               ruletype:str,
               can_access_internal:bool=False):
    self.package_target=package_target
    self.package_ruletype=ruletype
    self.is_binary_target=(ruletype.endswith('_binary') or
                             ruletype.endswith('_test'))
    self.included_files:list[str]=[]
    self.depends_on_targets:list[ExportablePackage|ExportedPackage]=[]
    self.tags:set[str]=set()
    self.build_timestamp=time.time()
    self.rule_file:HashedFile|None=None
    self.build_file:HashedFile|None=None
    self.input_files:list[HashedFile]=[]

    self._platform=platform
    self._binaries_location=''
    self._previous_build_timestamp=0.0
    self._extracted_dir:str|None=None
    self._internal_access:'threading.UpdateGraphResponseData|None'=None
    self._export_binary:typing.Callable|None=None
    self._exec_env:dict[str, str]={}
    self._exec_env_str=''

  def GetHash(self, filename:str) -> str:
    """Returns the MD5 hash of the file."""
    return self.MD5(filename)

  def SetInternalAccess(self,
                        access:'threading.UpdateGraphResponseData') -> None:
    """Sets the internal access object for dynamic graph updates."""
    self._internal_access=access

  def SetBinaryExporter(self, exporter:typing.Callable) -> None:
    """Sets the function used to export binaries."""
    self._export_binary=exporter

  def _GetJson(self) -> str:
    """Returns a JSON string representing the package metadata."""
    data={
      'package_target': str(self.package_target),
      'package_ruletype': self.package_ruletype,
      'is_binary_target': self.is_binary_target,
      'included_files': self.included_files,
      'depends_on_targets': [
        (str(t.package_target), t.build_timestamp)
        for t in self.depends_on_targets
      ],
      'tags': list(self.tags),
      'build_timestamp': self.build_timestamp,
      'platform': self._platform._values if self._platform else {},
    }
    if self.rule_file:
      data['rule_file']=self.rule_file.dict()
    if self.build_file:
      data['build_file']=self.build_file.dict()
    data['input_files']=[f.dict() for f in self.input_files]
    return json.dumps(data)

  def SetInputFiles(self, files:list[str]) -> None:
    """Sets the list of input files and computes their hashes."""
    self.input_files=[HashedFile(f, self) for f in files]

  def SetRuleFile(self, file:str, hashpath:str) -> None:
    """Sets the build rule file and its hash path."""
    self.rule_file=HashedFile(hashpath, self)

  def SetBuildFile(self, file:str, hashpath:str) -> None:
    """Sets the BUILD file and its hash path."""
    self.build_file=HashedFile(hashpath, self)

  def AddFile(self, filename:str) -> None:
    """Adds a file to the output package."""
    self.included_files.append(filename)

  def AddDirectory(self, directory:str) -> None:
    """Adds all files within a directory to the output package."""
    for dirname, _, files in os.walk(directory):
      for file in files:
        self.AddFile(os.path.join(dirname, file))

  def AddDependency(self,
                    dependency:ExportablePackage|ExportedPackage) -> None:
    """Adds a dependency on another target."""
    if dependency not in self.depends_on_targets:
      self.depends_on_targets.append(dependency)

  def GetPackageName(self) -> str:
    """Returns the relative path of the package archive."""
    return self.package_target.GetPackage().GetRelativePath()

  def GetPackageDirectory(self) -> str:
    """Returns the package's directory relative to root."""
    return self.package_target.GetDirectory().Relative().Value()[2:]

  def ExecutionFailed(self, command:str, stderr:str) -> None:
    """Raises an exception indicating a build command failure."""
    raise exceptions.BuildDefsRaisesException(
      str(self.package_target.GetName()),
      self.package_ruletype, command + "\n\n" + stderr)

  def FatalError(self, msg:str) -> typing.NoReturn:
    """Raises a fatal error."""
    raise errors.FatalError(msg)

  def ExecutionNotRequired(self) -> None:
    """Raises an exception indicating that no build is necessary."""
    raise exceptions.BuildTargetNoBuildNecessary()

  def GetBinariesDir(self) -> str:
    """Returns the directory where binaries are exported."""
    return self._binaries_location

  def GetPreviousBuildTimestamp(self) -> float:
    """Returns the timestamp of the previous build, if any."""
    return self._previous_build_timestamp

  def GetPlatform(self) -> 'parsed_target.PlatformTarget|None':
    """Returns the target platform definition."""
    return self._platform

  def RunCommand(self, command:str) -> subprocess.CompletedProcess:
    """Executes a shell command."""
    return subprocess.run(command,
                          encoding='utf-8',
                          shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)

  def Export(self) -> ExportedPackage:
    """Exports the package by creating a zip archive."""
    r=self.RunCommand('pwd')
    if r.returncode:
      raise errors.FatalError(f'{r.returncode} => {r.stderr}')

    r=self.RunCommand('touch pkg_contents.json')
    if r.returncode:
      raise errors.FatalError('Cant create new pkg_contents.json')

    with open('pkg_contents.json', 'w+') as f:
      f.write(self._GetJson())
    filename=self.GetPackageName()
    EnsureDirectory(os.path.dirname(filename))
    subprocess.check_output(['zip', '--symlinks', filename, 'pkg_contents.json',
                             *self.included_files])
    os.system('rm pkg_contents.json')
    return ExportedPackage(filename, self.__dict__, self._export_binary)

  def _GetPreviousBuild(self, package_dir:str) -> dict|None:
    """Attempts to load metadata from a previously built package."""
    try:
      archive_path=os.path.join(package_dir, self.GetPackageName())
      with zipfile.ZipFile(archive_path, 'r') as archive:
        return json.loads(archive.read('pkg_contents.json'))
    except Exception:
      return None

  def NeedsBuild(self, package_dir:str, src_dir:str) -> \
      tuple['ExportablePackage', bool, str|None]:
    """Checks if the package needs rebuilding."""
    previous_build=self._GetPreviousBuild(package_dir)
    if not previous_build:
      return self, True, 'No previous build'

    if 'platform' not in previous_build:
      return self, True, 'No platform set on previous build'

    for platkey, value in previous_build.get('platform', {}).items():
      if (self._platform and
          self._platform._values.get(platkey, NOT_THE_SAME) != value):
        return self, True, f'platform value|{platkey}|differs'

    self._previous_build_timestamp=previous_build.get('build_timestamp', 0)

    prev_dict={target: time for target, time in \
                previous_build['depends_on_targets']}
    curr_dict={str(target.package_target): target.build_timestamp \
                for target in self.depends_on_targets}

    if len(prev_dict) != len(curr_dict):
      return self, True, 'previous dependencies differ to current ones'

    for k, prev_time in prev_dict.items():
      if k not in curr_dict:
        return self, True, f'{k} (from previous build) not found in current'
      if curr_dict[k] > prev_time:
        return self, True, f'{k} (from previous build) has been rebuilt'

    for src in previous_build['input_files']:
      full_path=os.path.join(src_dir, src['file'])
      if self.MD5(full_path) != src['hash']:
        return self, True, f'hash of input file {full_path} has changed'

    check_files=[]
    if previous_build.get('build_file'):
      check_files.append(previous_build['build_file'])
    if previous_build.get('rule_file'):
      check_files.append(previous_build['rule_file'])
    for fh in check_files:
      full_path=os.path.join(src_dir, fh['file'])
      if self.MD5(full_path) != fh['hash']:
        return self, True, f'hash of file {full_path} has changed'

    return self, False, None

  def LoadToTempAttempt(self, bin_dir:str) -> \
      tuple[str|None, dict[str, str], ExportedPackage]:
    """Internal method to load package contents into a temporary directory."""
    with open('pkg_contents.json', 'r+') as f:
      package_contents=json.loads(f.read())
      exported_package=ExportedPackage(
        self.package_target.GetPackage().GetRelativePath(), package_contents)
      if self.is_binary_target:
        relative_binary=os.path.join(
          self.package_target.GetDirectory().Relative().Value()[2:],
          self.package_target.GetName().Name())
        full_path_binary=os.path.join(bin_dir, relative_binary)
        binary_location=os.path.join('bin',
                                     self.package_target.GetName().Name())
        return None, {binary_location: full_path_binary}, exported_package
      else:
        return self._extracted_dir, {}, exported_package

  def MakeTempDir(self) -> str:
    """Creates a temporary directory."""
    return tempfile.mkdtemp()

  def UseTempDir(self) -> object:
    """Returns a context manager for a temporary directory."""
    wrapper=self
    class DirManager(object):
      def __init__(self) -> None:
        self._directory:str|None=None
      def __enter__(self) -> str:
        self._directory=wrapper.MakeTempDir()
        assert self._directory is not None
        return self._directory
      def __exit__(self, *args:object, **kwargs:object) -> None:
        if self._directory:
          wrapper.RunCommand(f'rm -rf {self._directory}')
        self._directory=None
    return DirManager()

  def LoadToTemp(self, pkg_dir:str, bin_dir:str) -> \
      tuple[str|None, dict[str, str], ExportablePackage|ExportedPackage]:
    """Extracts package into temporary directory for build execution."""
    if self._extracted_dir:
      self.UnloadPackageDirectory()
    self._extracted_dir=self.MakeTempDir()
    package_name=os.path.join(pkg_dir,
      self.package_target.GetPackage().GetRelativePath())

    if not os.path.exists(package_name):
       return None, {}, self

    extract=f'unzip {package_name} -d {self._extracted_dir}'
    r=self.RunCommand(extract)
    if r.returncode:
      raise errors.FatalError(f'{extract} ===> {r.stderr}')

    with temp_dir.ScopedTempDirectory(self._extracted_dir):
      try:
        return self.LoadToTempAttempt(bin_dir)
      except Exception:
        raise exceptions.FilesystemSyncException()

  def UnloadPackageDirectory(self) -> None:
    """Removes the temporary directory used for extraction."""
    if self._extracted_dir and os.path.exists(self._extracted_dir):
      try:
        self.RunCommand(f'rm -rf {self._extracted_dir}')
      except FileNotFoundError:
        print(f'{self._extracted_dir} COULD NOT BE DELETED!')
    self._extracted_dir=None

  def Dependencies(self, **filters:object) -> \
      typing.Iterator[ExportablePackage|ExportedPackage]:
    """Yields dependencies that match the provided filters."""
    def yieldPackage(pkg:object) -> bool:
      for k, v in filters.items():
        valueof=getattr(pkg, k, None)
        if valueof is None:
          return False
        if isinstance(valueof, str) and valueof != v:
          return False
        if isinstance(valueof, (set, list, tuple)) and v not in valueof:
          return False
        if callable(v) and not v(valueof):
          return False
      return True

    for package in self.depends_on_targets:
      if yieldPackage(package):
        yield package

  def SetTags(self, *tags:str) -> None:
    """Adds tags to the package."""
    self.tags.update(set(tags))

  def Execute(self, *cmds:str) -> None:
    """Executes a series of shell commands."""
    for command in cmds:
      full_cmd=f'{self._exec_env_str} {command}' if self._exec_env_str \
                else command
      try:
        r=self.RunCommand(full_cmd)
        if r.returncode:
          raise errors.FatalError(
            f'command "{full_cmd}" failed:\n{r.stdout}\n{r.stderr}')
      except Exception as e:
        if isinstance(e, errors.FatalError):
          raise
        raise errors.FatalError(f'command "{full_cmd}" failed: {str(e)}')

  def SetEnvVar(self, var:str, value:str) -> None:
    """Sets an environment variable for command execution."""
    self._exec_env[var]=value
    self._update_exec_env_str()

  def IsDebug(self) -> bool:
    """Returns True if debugging is enabled."""
    return debug.IsDebug()

  def UnsetEnvVar(self, var:str) -> None:
    """Removes an environment variable."""
    self._exec_env.pop(var, None)
    self._update_exec_env_str()

  def _update_exec_env_str(self) -> None:
    """Updates the string representation of the execution environment."""
    self._exec_env_str=' '.join(f'{k}={v}' for k,v in self._exec_env.items())

  def IncludedFiles(self) -> list[str]:
    """Returns a list of all files included in the package."""
    return list(self.included_files)

  def Semaphor(self) -> object:
    """Returns a context manager for a file-based lock."""
    pkg=self
    class Sem(object):
      def __init__(self) -> None:
        self._lockfile=os.path.join(impulse_paths.root(), '.lockfile')
        self._has_lockfile=not pkg.RunCommand('which lockfile').returncode
      def __enter__(self) -> None:
        if self._has_lockfile:
          pkg.RunCommand(f'lockfile {self._lockfile}')
        else:
          self._spinlock()
      def __exit__(self, *args:object, **kwargs:object) -> None:
        pkg.RunCommand(f'rm -rf {self._lockfile}')
      def _spinlock(self) -> None:
        success=False
        while not success:
          while os.path.exists(self._lockfile):
            time.sleep(2)
            continue
          success=not pkg.RunCommand(f'mkdir {self._lockfile}').returncode
    return Sem()

  def __del__(self) -> None:
    """Ensures that temporary directories are cleaned up."""
    if self._extracted_dir:
      if os.path.exists(self._extracted_dir):
        self.UnloadPackageDirectory()
