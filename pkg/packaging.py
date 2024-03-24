
import abc
import hashlib
import json
import os
import random
import shutil
import subprocess
import tempfile
import time
import typing
import zipfile

from impulse.core import exceptions
from impulse.util import temp_dir
from impulse.core import debug
from impulse import impulse_paths


NOT_THE_SAME = object()


def EnsureDirectory(directory):
  if not os.path.exists(directory):
    os.makedirs(directory, exist_ok=True)


class Hasher(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def GetHash(self, filename:str) -> str:
    raise NotImplementedError()

  def MD5(self, filename:str) -> str:
    hash_md5 = hashlib.md5()
    try:
      with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
          hash_md5.update(chunk)
      return hash_md5.hexdigest()
    except FileNotFoundError:
      return '----'


class HashedFile(object):
  __slots__ = ('file', 'hash')

  def __init__(self, file:str, package:Hasher):
    self.file = file
    self.hash = package.GetHash(file)

  def dict(self):
    return {'file': self.file, 'hash': self.hash}

  def __eq__(self, other:object) -> bool:
    if type(other) != type(self):
      return False
    if getattr(other, 'file', None) != self.file:
      return False
    if getattr(other, 'hash', None) != self.hash:
      return False
    return True

  def __hash__(self):
    return hash(f'{self.file}//{self.hash}')


class ExportedPackage(object):
  """Read-only package wrapper."""
  def __init__(self,
               filename: str,
               json: dict=None,
               export_binary=None):
    self.filename = filename
    if json:
      self.__dict__.update(json)
    if export_binary:
      self.ExportBinary = export_binary

  def NeedsBuild(self):
    return self, False, None

  def IncludedFiles(self):
    return [file for file in self.included_files]

  def GetPropagatedData(self, key):
    if key in self.__dict__:
      return self.__dict__[key]
    if '_propagated_data' in self.__dict__:
      if key in self.__dict__['_propagated_data']:
        return self.__dict__['_propagated_data'][key]
    return []

  def RunCommand(self, command):
    return subprocess.run(command,
                          encoding='utf-8',
                          shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)

  def Execute(self, *cmds):
    for command in cmds:
      try:
        r = self.RunCommand(command)
        if r.returncode:
          raise exceptions.FatalException(f'command "{command}" failed.')
      except:
        raise exceptions.FatalException(f'command "{command}" failed.')

  def FatalError(self, msg:str):
    raise exceptions.FatalException(msg)

  def __str__(self):
    return '{}@{}'.format(str(self.package_target), self.build_timestamp)

  def __repr__(self):
    return str(self)

  def __getitem__(self, name:str):
    return getattr(self, name)


class UtilHelper(object):
  def __init__(self, buildqueue_ref):
    self.temp_dir = temp_dir
    self.recursive_loader = __import__('impulse').recursive_loader
    self.build_queue = buildqueue_ref


class ExportablePackage(Hasher):
  """A wrapper class for building a package file."""

  def __init__(self, package_target, ruletype: str,
               platform:impulse_paths.Platform,
               can_access_internal: bool=False,
               binaries_location: str=''):
    self._extracted_dir = None

    self.included_files:typing.List[str] = []
    self.input_files:typing.Set[HashedFile] = set()
    self.depends_on_targets:typing.List[str] = []
    self.build_file:HashedFile
    self.rule_file:HashedFile
    self.tags:typing.Set[str] = set()

    self.package_target = package_target
    self.build_timestamp = int(time.time())
    self.is_binary_target = str(ruletype).endswith(
      '_binary') or str(ruletype).endswith('_test')
    self.package_ruletype = ruletype
    self.execution_count = 0

    self._export_binary = None
    self._can_access_internal = can_access_internal
    self._buildqueue_ref = None
    self._binaries_location = binaries_location
    self._previous_build_timestamp = 0
    self._exec_env = {}
    self._exec_env_str = ''
    self._propagated_data = {}
    self._platform = platform

  def __getstate__(self):
    return self.__dict__.copy()

  def __setstate__(self, state):
    self.__dict__.update(state)
    self._extracted_dir = None

  def __getattribute__(self, attr):
    if attr in ('Internal', 'SetInternalAccess'):
      if self._can_access_internal:
        if attr == 'Internal':
          return UtilHelper(self._buildqueue_ref)
        if attr == 'SetInternalAccess':
          return object.__getattribute__(self, attr)
      raise AttributeError
    return object.__getattribute__(self, attr)

  def _GetJson(self) -> str:
    copydict = {}
    for k, v in self.__dict__.items():
      if not k.startswith('_') and k != 'buildroot':
        copydict[k] = v
      if k == 'package_target':
        copydict[k] = str(v)
      if k == 'included_files':
        copydict[k] = sorted(list(set(v)))
      if k == 'depends_on_targets':
        copydict[k] = [[d.package_target, d.build_timestamp] for d in v]
      if k == 'input_files':
        copydict[k] = sorted(list(e.dict() for e in v), key=lambda x:x['file'])
      if k == 'build_file':
        copydict[k] = v.dict()
      if k == 'rule_file':
        copydict[k] = v.dict()
      if k == 'tags':
        copydict[k] = list(v)
      if k == '_platform':
        copydict['platform'] = v._values

    for k, v in self._propagated_data.items():
      if k not in copydict:
        copydict[k] = v

    return json.dumps(copydict, indent=2)

  def Help(self):
    for potential in dir(self):
      if potential.startswith('__'):
        continue
      try:
        potential = getattr(self, potential)
      except:
        continue
      if not callable(potential):
        continue
      if not hasattr(potential, '__doc__') or potential.__doc__ is None:
        continue
      print(f'{potential.__name__}:')
      print(f'  {potential.__doc__}')

  def GetHash(self, filename:str) -> str:
    '''Gets the hash of a file, given its name'''
    try:
      return self.MD5(filename)
    except FileNotFoundError as e:
      raise exceptions.ListedSourceNotFound(filename,
        str(self.package_target)) from e
    except IsADirectoryError:
      raise exceptions.ListedSourceNotFound(
        filename, str(self.package_target))

  def PropagateData(self, key, data):
    if key not in self._propagated_data:
      self._propagated_data[key] = []
    self._propagated_data[key].append(data)

  def SetInternalAccess(self, access):
    self._buildqueue_ref = access

  def SetInputFiles(self, files:typing.List[str]):
    for f in files:
      self.input_files.add(HashedFile(f, self))

  def SetRuleFile(self, file:str, hashpath:str):
    self.rule_file = HashedFile(hashpath, self)

  def SetBuildFile(self, file:str, hashpath:str):
    self.build_file = HashedFile(hashpath, self)

  def AddFile(self, filename:str):
    '''Adds a file to the output package.'''
    self.included_files.append(filename)

  def AddDependency(self, dependency):
    '''Add a dependency on another target.'''
    if dependency not in self.depends_on_targets:
      self.depends_on_targets.append(dependency)

  def GetPackageName(self) -> str:
    '''Gets the name of the package.'''
    return self.package_target.GetPackage().GetRelativePath()

  def GetPackageDirectory(self):
    '''Gets the package source directory.'''
    return self.package_target.GetDirectory().Relative().Value()[2:]

  def ExecutionFailed(self, command:str, stderr:str):
    '''Triggers an exception with given cmdline and stderr.'''
    raise exceptions.BuildDefsRaisesException(self.package_target._target_name.Value(),
      self.package_ruletype, command + "\n\n" + stderr)

  def ExecutionNotRequired(self):
    raise exceptions.BuildTargetNoBuildNecessary()

  def GetBinariesDir(self) -> str:
    '''Gets the directory where binaries are exported to.'''
    return self._binaries_location

  def GetPreviousBuildTimestamp(self):
    '''Gets the timestamp for when this rule was previously built.'''
    return self._previous_build_timestamp

  def GetPlatform(self):
    return self._platform

  def RunCommand(self, command):
    '''Executes a command.'''
    return subprocess.run(command,
                          encoding='utf-8',
                          shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)

  def Export(self) -> ExportedPackage:
    r = self.RunCommand('pwd')
    if r.returncode:
      raise exceptions.FatalException(f'{r.returncode} => {r.stderr}')

    r = self.RunCommand('touch pkg_contents.json')
    if r.returncode:
      raise exceptions.FatalException('Cant create new pkg_contents.json')

    with open('pkg_contents.json', 'w+') as f:
      f.write(self._GetJson())
    cmd = 'zip --symlinks {} pkg_contents.json {} 2>&1 > /dev/null'
    filename = self.GetPackageName()
    cmd = cmd.format(filename, ' '.join(self.included_files))
    EnsureDirectory(os.path.dirname(filename))
    os.system(cmd)
    os.system('rm pkg_contents.json')
    return ExportedPackage(filename, self.__dict__, self._export_binary)

  def _GetPreviousBuild(self, package_dir):
    try:
      archive = zipfile.ZipFile(
        os.path.join(package_dir, self.GetPackageName()), 'r')
      return json.loads(archive.read('pkg_contents.json'))
    except Exception as e:
      return None

  def NeedsBuild(self, package_dir, src_dir):
    previous_build = self._GetPreviousBuild(package_dir)
    if not previous_build:
      return self, True, 'No previous build'

    if 'platform' not in previous_build:
      return self, True, 'No platform set on previous build'

    for platkey, value in previous_build.get('platform', []).items():
      if self._platform._values.get(platkey, NOT_THE_SAME) != value:
        return self, True, f'platform value |{platkey}| differs'

    self._previous_build_timestamp = previous_build.get('build_timestamp', 0)

    prev_dict = {}
    curr_dict = {}

    for target, time in previous_build['depends_on_targets']:
      prev_dict[target] = time

    for target in self.depends_on_targets:
      curr_dict[str(target.package_target)] = target.build_timestamp

    if len(prev_dict) != len(curr_dict):
      return self, True, 'previous dependencies differ to current ones'

    for k in prev_dict.keys():
      if k not in curr_dict:
        return self, True, f'{k} (from previous build) not found in current'
      if curr_dict[k] > prev_dict[k]:
        return self, True, f'{k} (from previous build) has been rebuilt'

    for src in previous_build['input_files']:
      full_path = os.path.join(src_dir, src['file'])
      if self.MD5(full_path) != src['hash']:
        return self, True, f'hash of input file {full_path} has changed'

    check_files = []
    if previous_build.get('build_file', None):
      check_files.append(previous_build['build_file'])
    if previous_build.get('rule_file', None):
      check_files.append(previous_build['rule_file'])
    for fh in check_files:
      full_path = os.path.join(src_dir, fh['file'])
      if self.MD5(full_path) != fh['hash']:
        return self, True, f'hash of file {full_path} has changed'

    return self, False, None

  def LoadToTempAttempt(self, bin_dir) -> (str, dict, 'ExportedPackage'):
    with open('pkg_contents.json', 'r+') as f:
      package_contents = json.loads(f.read())
      exported_package = ExportedPackage(
        self.package_target.GetPackage().GetRelativePath(), package_contents)
      if self.is_binary_target:
        relative_binary = os.path.join(
          self.package_target.GetPackagePathDirOnly(),
          self.package_target.target_name)
        full_path_binary = os.path.join(bin_dir, relative_binary)
        binary_location = os.path.join('bin', self.package_target.target_name)
        return None, {binary_location: full_path_binary}, exported_package
      else:
        return self._extracted_dir, {}, exported_package

  def MakeTempDir(self) -> str:
    '''Makes a temporary directory. Please clean up after yourself.'''
    exists = True
    chrs = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    dirname = ''
    while exists:
      dirname = '__impulse__' + ''.join(random.choice(chrs) for i in range(10))
      if not os.path.exists(f'/tmp/{dirname}'):
        exists = False
    r = self.RunCommand(f'mkdir -p /tmp/{dirname}')
    if r.returncode:
      raise exceptions.FatalException(f'MKDIR FAILED -> {r.stdout}')
    return f'/tmp/{dirname}'

  def UseTempDir(self):
    '''Context manage for a temporary directory that auto cleans up.'''
    wrapper = self
    class DirManager(object):
      def __init__(self):
        self._directory = None
      def __enter__(self):
        self._directory = wrapper.MakeTempDir()
        return self._directory
      def __exit__(self, *args, **kwargs):
        wrapper.RunCommand(f'rm -rf {self._directory}')
        self._directory = None
    return DirManager()

  def LoadToTemp(self, pkg_dir, bin_dir):
    # Temp directory to write to (deleted on object destruction)
    if self._extracted_dir:
      self.UnloadPackageDirectory()
    self._extracted_dir = self.MakeTempDir()
    package_name = os.path.join(pkg_dir,
      self.package_target.GetPackage().GetRelativePath())

    extract = f'unzip {package_name} -d {self._extracted_dir}'
    r = self.RunCommand(f'test -e {self._extracted_dir}')
    if r.returncode:
      raise exceptions.FatalException(f'{self._extracted_dir} does not exist')
    r = self.RunCommand(extract)
    if r.returncode:
      raise exceptions.FatalException(f'{extract} ===> {r.stderr}')

    with temp_dir.ScopedTempDirectory(self._extracted_dir):
      try:
        return self.LoadToTempAttempt(bin_dir)
      except:
        raise exceptions.FilesystemSyncException()

  def UnloadPackageDirectory(self):
    if self._extracted_dir and os.path.exists(self._extracted_dir):
      try:
        self.RunCommand(f'rm -rf {self._extracted_dir}')
      except FileNotFoundError:
        print(f'{self._extracted_dir} COULD NOT BE DELETED!')
    self._extracted_dir = None

  def Dependencies(self, **filters):
    '''Generates a list targets that this target depends on.'''
    def yieldPackage(pkg):
      for k, v in filters.items():
        valueof = getattr(pkg, k, None)
        if valueof == None:
          return False
        if type(valueof) == str and valueof != v:
          return False
        if type(valueof) in (set, list, tuple) and v not in valueof:
          return False
        if type(v).__name__ == 'function' and not v(valueof):
          return False
      return True

    for package in self.depends_on_targets:
      if yieldPackage(package):
        yield package

  def SetTags(self, *tags):
    '''Adds tags to this target.'''
    self.tags.update(set(tags))

  def Execute(self, *cmds):
    '''Executes |cmds| in order.'''
    for command in cmds:
      command = f'{self._exec_env_str} {command}'
      try:
        r = self.RunCommand(command)
        if r.returncode:
          raise exceptions.FatalException(
            f'command "{command}" failed:\n{r.stdout}\n{r.stderr}')
      except Exception as e:
        if type(e) == exceptions.FatalException:
          raise
        raise exceptions.FatalException(f'command "{command}" failed.')

  def SetEnvVar(self, var, value):
    '''Sets an environment variable for execution.'''
    self._exec_env[var] = value
    self._update_exec_env_str()

  def IsDebug(self):
    return debug.IsDebug()

  def UnsetEnvVar(self, var):
    '''Unsets an environment variable for execution.'''
    self._exec_env.pop(var)
    self._update_exec_env_str()

  def _update_exec_env_str(self):
    self._exec_env_str = ' '.join(f'{k}={v}' for k,v in self._exec_env.items())

  def IncludedFiles(self):
    '''A list of all files included in this package.'''
    return [f for f in self.included_files]

  def Semaphor(pkg):
    class Sem(object):
      def __init__(self):
        self._lockfile = os.path.join(impulse_paths.root(), '.lockfile')
        self._has_lockfile = not pkg.RunCommand('which lockfile').returncode
      def __enter__(self):
        if self._has_lockfile:
          pkg.RunCommand(f'lockfile {self._lockfile}')
        else:
          self._spinlock()
      def __exit__(self, *args, **kwargs):
        pkg.RunCommand(f'rm -rf {self._lockfile}')
      def _spinlock(self):
        success = False
        while not success:
          while os.path.exists(self._lockfile):
            time.sleep(2)
            continue
          success = not pkg.RunCommand(f'mkdir {self._lockfile}').returncode
    return Sem()


  def __del__(self):
    if self._extracted_dir:
      if os.path.exists(self._extracted_dir):
        self.UnloadPackageDirectory()

