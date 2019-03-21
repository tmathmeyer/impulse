
import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile

from impulse.exceptions import exceptions


def EnsureDirectory(directory):
  if not os.path.exists(directory):
    os.makedirs(directory)


def MD5(fname):
  hash_md5 = hashlib.md5()
  with open(fname, "rb") as f:
      for chunk in iter(lambda: f.read(4096), b""):
          hash_md5.update(chunk)
  return hash_md5.hexdigest()


class ScopedTempDirectory(object):
  def __init__(self, temp_directory=None):
    self._temp_directory = temp_directory
    self._old_directory = None
    self._delete_on_exit = not temp_directory

  def __enter__(self):
    if not self._temp_directory:
      self._temp_directory = tempfile.mkdtemp()
    self._old_directory = os.getcwd()
    os.chdir(self._temp_directory)

  def __exit__(self, *args):
    os.chdir(self._old_directory)
    if self._delete_on_exit:
      os.rmdir(self._temp_directory)


class ExportedPackage(object):
  """Read-only package wrapper."""
  def __init__(self, filename: str, json: dict=None, export_binary=None):
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


class ExportablePackage(object):
  """A wrapper class for building a package file."""
  def __init__(self, package_target, ruletype: str):
    self.included_files = []
    self.input_files = []
    self.depends_on_targets = []
    self.package_target = package_target
    self.build_timestamp = int(time.time())
    self.is_binary_target = ruletype.endswith(
      '_binary') or ruletype.endswith('_test')
    self.package_ruletype = ruletype

    self._export_binary = None

  def _GetJson(self) -> str:
    copydict = {}
    for k, v in self.__dict__.items():
      if not k.startswith('_') and k != 'buildroot':
        copydict[k] = v
      if k == 'package_target':
        copydict[k] = str(v)
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

  def SetInputFiles(self, files:[str]):
    for f in files:
      self.input_files.append([f, self._GetHash(f)])

  def AddFile(self, filename: str):
    self.included_files.append(filename)

  def AddDependency(self, dependency):
    self.depends_on_targets.append(dependency)

  def GetPackageName(self):
    return self.package_target.GetPackagePkgFile()

  def GetPackageDirectory(self):
    return self.package_target.GetPackagePathDirOnly()

  def ExecutionFailed(self, command):
    raise exceptions.BuildDefsRaisesException(self.package_target.target_name,
      self.package_ruletype, command)

  def Export(self) -> ExportedPackage:
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

    return self, False

  def LoadToTemp(self, package_directory):
    # Extract this into a temp-dir
    package_name = os.path.join(package_directory,
      self.package_target.GetPackagePkgFile())

    package_contents = None

    # Temp directory to write to
    self._extracted_dir = tempfile.mkdtemp()
    with ScopedTempDirectory(self._extracted_dir):
      unzip = 'unzip {} 2>&1 > /dev/null'.format(package_name)
      os.system(unzip)
      with open('pkg_contents.json') as f:
        package_contents = json.loads(f.read())
    return self._extracted_dir, ExportedPackage(
      self.package_target.GetPackagePkgFile(), package_contents)

  def UnloadPackageDirectory(self):
    shutil.rmtree(self._extracted_dir)

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

