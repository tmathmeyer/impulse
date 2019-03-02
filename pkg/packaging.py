
import os
import time


class ExportedPackage(object):
  """Read-only package wrapper."""
  def __init__(self, filename: str, json:dict = None):
    self._filename = filename
    if json:
      self.__dict__.update(json)


class ExportablePackage(object):
  """A wrapper class for building an package file."""
  def __init__(self, package_name: str, is_binary: bool, ruletype: str):
    self.included_files = []
    self.depends_on_targets = []
    self.package_name = package_name
    self.build_timestamp = int(time.time())
    self.is_binary_target = is_binary
    self.package_ruletype = ruletype

  def _GetJson(self) -> str:
    return json.dumps(self.__dict__, indent=2)

  def _GetHash(self, filename: str) -> str:
    return ''

  def AddFile(self, filename: str):
    assert os.path.isfile(filename)
    self.included_files.append(filename, self._GetHash(filename))

  def AddDependency(self, dep_name: str):
    self.depends_on_targets.append(dep_name)

  def Export() -> ExportedPackage:
    with open('pkg_contents.json', 'w+') as f:
      f.write(self._GetJson())
    cmd = 'zip {} pkg_contents.json {}'
    filename = self.package_name # TODO: get a real path from here...
    cmd = zipcmd.format(filename, ' '.join(x[1] for x in self.included_files))
    os.system(cmd)
    os.system('rm pkg_contents.json')
    return ExportedPackage(filename, self._GetJson())






