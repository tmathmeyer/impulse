
import hashlib
import json
import os
import random
import shutil
import subprocess
import tempfile
import time
import zipfile

from impulse.exceptions import exceptions
from impulse.util import temp_dir


def EnsureDirectory(directory):
  if not os.path.exists(directory):
    os.makedirs(directory, exist_ok=True)


def MD5(fname):
  hash_md5 = hashlib.md5()
  try:
    with open(fname, "rb") as f:
      for chunk in iter(lambda: f.read(4096), b""):
        hash_md5.update(chunk)
    return hash_md5.hexdigest()
  except FileNotFoundError:
    return '----'



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
    return self, False

  def IncludedFiles(self):
    return [file for file in self.included_files]

  def __str__(self):
    return '{}@{}'.format(str(self.package_target), self.build_timestamp)

  def __repr__(self):
    return str(self)


class UtilHelper(object):
  def __init__(self, buildqueue_ref):
    self.temp_dir = temp_dir
    self.recursive_loader = __import__('impulse').recursive_loader
    self.build_queue = buildqueue_ref


class ExportablePackage(object):
  """A wrapper class for building a package file."""
  def __init__(self, package_target, ruletype: str,
               can_access_internal: bool=False,
               binaries_location: str=''):
    self.included_files = []
    self.input_files = []
    self.depends_on_targets = []
    self.build_file = []
    self.rule_file = []
    self.package_target = package_target
    self.build_timestamp = int(time.time())
    self.is_binary_target = ruletype.endswith(
      '_binary') or ruletype.endswith('_test')
    self.package_ruletype = ruletype
    
    self._execution_count = 0
    self._export_binary = None
    self._extracted_dir = None
    self._can_access_internal = can_access_internal
    self._buildqueue_ref = None
    self._binaries_location = binaries_location
    self._packages_map = {}

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
    return json.dumps(copydict, indent=2)

  def _GetHash(self, filename: str) -> str:
    try:
      return MD5(filename)
    except FileNotFoundError as e:
      raise exceptions.ListedSourceNotFound(filename,
        str(self.package_target)) from e
    except IsADirectoryError:
      raise exceptions.ListedSourceNotFound(
        filename, str(self.package_target))

  def SetInternalAccess(self, access):
    self._buildqueue_ref = access

  def SetInputFiles(self, files:[str]):
    for f in files:
      self.input_files.append([f, self._GetHash(f)])

  def SetRuleFile(self, file:str, hashpath:str):
    if file:
      self.rule_file = [file, self._GetHash(hashpath)]

  def SetBuildFile(self, file:str, hashpath:str):
    if file:
      self.build_file = [file, self._GetHash(hashpath)]

  def AddFile(self, filename: str):
    self.included_files.append(filename)

  def AddDependency(self, dep, exported_package):
    if exported_package not in self.depends_on_targets:
      self.depends_on_targets.append(exported_package)
      self._packages_map[dep] = exported_package

  def GetPackageName(self):
    return self.package_target.GetPackagePkgFile()

  def GetPackageDirectory(self):
    return self.package_target.GetPackagePathDirOnly()

  def ExecutionFailed(self, command, stderr):
    raise exceptions.BuildDefsRaisesException(self.package_target.target_name,
      self.package_ruletype, command + "\n\n" + stderr)

  def GetBinariesDir(self):
    return self._binaries_location

  def RunCommand(self, command):
    return subprocess.run(command,
                          encoding='utf-8',
                          shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)

  def DataValueOf(self, datavalue):
    if type(datavalue) == str:
      yield datavalue
    else:
      yield from self._packages_map[datavalue].included_files

  def Export(self) -> ExportedPackage:
    r = self.RunCommand('pwd')
    if r.returncode:
      raise exceptions.FatalException(f'{r.returncode} => {r.stderr}')

    r = self.RunCommand('touch pkg_contents.json')
    if r.returncode:
      raise exceptions.FatalException('Cant create new pkg_contents.json')

    with open('pkg_contents.json', 'w+') as f:
      f.write(self._GetJson())
    cmd = 'zip {} pkg_contents.json {} 2>&1 > /dev/null'
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
      return self, True

    prev_dict = {}
    curr_dict = {}

    for target, time in previous_build['depends_on_targets']:
      prev_dict[target] = time

    for target in self.depends_on_targets:
      curr_dict[str(target.package_target)] = target.build_timestamp

    if len(prev_dict) != len(curr_dict):
      return self, True

    for k in prev_dict.keys():
      if k not in curr_dict:
        return self, True
      if curr_dict[k] > prev_dict[k]:
        return self, True

    for src in previous_build['input_files']:
      full_path = os.path.join(src_dir, src[0])
      if MD5(full_path) != src[1]:
        return self, True

    check_files = []
    if previous_build.get('build_file', None):
      check_files.append(previous_build['build_file'])
    if previous_build.get('rule_file', None):
      check_files.append(previous_build['rule_file'])
    for f, h in check_files:
      full_path = os.path.join(src_dir, f)
      if MD5(full_path) != h:
        return self, True

    return self, False

  def LoadToTempAttempt(self, bin_dir):
    with open('pkg_contents.json', 'r+') as f:
      package_contents = json.loads(f.read())
      exported_package = ExportedPackage(
        self.package_target.GetPackagePkgFile(), package_contents)
      if self.is_binary_target:
        relative_binary = os.path.join(
          self.package_target.GetPackagePathDirOnly(),
          self.package_target.target_name)
        full_path_binary = os.path.join(bin_dir, relative_binary)
        binary_location = os.path.join('bin', self.package_target.target_name)
        return None, {binary_location: full_path_binary}, exported_package
      else:
        return self._extracted_dir, {}, exported_package

  def MakeTempDir(self):
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


  def LoadToTemp(self, pkg_dir, bin_dir):
    # Temp directory to write to (deleted on object destruction)
    if self._extracted_dir:
      self.UnloadPackageDirectory()
    self._extracted_dir = self.MakeTempDir()
    package_name = os.path.join(pkg_dir,
      self.package_target.GetPackagePkgFile())

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
    for package in self.depends_on_targets:
      yieldme = True
      for k, v in filters.items():
        if yieldme and getattr(package, k, None) != v:
          yieldme = False
      if yieldme:
        yield package

  def IncludedFiles(self):
    return [f for f in self.included_files]

  def __del__(self):
    if self._extracted_dir:
      if os.path.exists(self._extracted_dir):
        self.UnloadPackageDirectory()

