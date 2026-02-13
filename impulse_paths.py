from __future__ import annotations

import os
import re
import typing
from impulse.args import args
from impulse.core import exceptions

EXPORT_DIR='GENERATED'
NOT_A_BUILD_TARGET=object()


class Environ(object):
  """A helper class to access environment variables via attributes."""
  def __getattr__(self, attr:str) -> str:
    return os.environ[attr]
  def __getitem__(self, item:str) -> str:
    return os.environ[item]
ENV=Environ()


def root() -> str:
  """
  Returns the impulse root directory, initializing it from config if
  necessary.
  """
  if 'impulse_root' not in os.environ:
    config=f'{ENV.HOME}/.config/impulse/config'
    if os.path.exists(config):
      with open(config, 'r') as f:
        os.environ['impulse_root']=f.read()
    else:
      raise LookupError('Impulse has not been initialized.')
  return os.environ['impulse_root']


def relative_pwd() -> str:
  """Returns current working directory relative to impulse root."""
  impulse_root=root()
  pwd=os.getcwd()
  if not pwd:
    raise ValueError('Unable to determine current directory')

  if pwd.startswith(impulse_root):
    return '/' + pwd[len(impulse_root):]

  msg=f'Impulse must be run inside {impulse_root}\nbut you are in {pwd}'
  raise ValueError(msg)


def output_directory() -> str:
  """Returns the absolute path to the impulse output directory."""
  return os.path.join(root(), EXPORT_DIR)


class PathException(Exception):
  """Exception raised for invalid build target paths."""
  def __init__(self, path:str, included_from:str | None=None):
    if included_from:
      self._path=f'Invalid Target: {path} Included From: {included_from}'
    else:
      self._path=f'Invalid Target: {path}'
    super(PathException, self).__init__(self._path)

  def __repr__(self) -> str:
    return 'Invalid Target:' + self._path


class LoggerEnv(dict):
  """
  A dictionary-like environment used to log build rule calls
  during BUILD file execution.
  """
  def __init__(self, called_as:str='module',
               push_up:'LoggerEnv | None'=None):
    super().__init__()
    self._calls:list[tuple[tuple[object, ...],
                           dict[str, object]]]=[]
    self._called_as=called_as
    self._push_up=push_up

  def __getitem__(self, value:str) -> 'LoggerEnv': # type:ignore[override]
    return LoggerEnv(called_as=value, push_up=self)

  def __call__(self, *args:object, **kwargs:object) -> list[object]:
    kwargs['called_as']=kwargs.get('called_as', [])
    typing.cast(list, kwargs['called_as']).append(self._called_as)
    if self._push_up:
      self._push_up(*args, **kwargs)
    else:
      self._calls.append((args, kwargs))
    return []

  def __iter__(self) -> typing.Iterator[str]: # type:ignore[override]
    """Returns an iterator over the keys in the environment."""
    return super().__iter__()

  def Calls(self) -> typing.Iterator[tuple[tuple[object, ...],
                                          dict[str, object]]]:
    """Returns an iterator over the logged build rule calls."""
    for call in self._calls:
      yield call


class RuleSpec(object):
  """Specifies the type, name, and output path of a build rule."""
  def __init__(self, target:'ParsedTarget',
               callspec:tuple[tuple[object, ...], dict[str, object]]):
    self.type=typing.cast(list, callspec[1].get('called_as', ['unknown']))[0]
    self.name=str(callspec[1].get('name', 'unknown'))
    output_type='BINARIES'
    if not (self.type.endswith('binary') or self.type.endswith('test')):
      output_type='PACKAGES'
      if not self.name.endswith('.zip'):
        self.name+='.zip'
    self.output=os.path.join(
      output_directory(), output_type, target.target_path[2:], self.name)


class ParsedTarget(object):
  """Represents a build target parsed from a string or path."""
  def __init__(self, target_name:str, target_path:str):
    self.target_name=target_name
    self.target_path=target_path

  def ParseFile(self, _:object,
                parser:typing.Callable[[str], None]) -> None:
    """Parses the BUILD file associated with this target."""
    parser(self.GetBuildFileForTarget())

  def GetBuildFileForTarget(self) -> str:
    """Returns the absolute path to the BUILD file for this target."""
    try:
      path=os.path.join(self.target_path, 'BUILD')
      return expand_fully_qualified_path(path)
    except exceptions.InvalidPathException:
      msg=f'Missing rule: {self.GetFullyQualifiedRulePath()}'
      raise exceptions.BuildTargetMissing(msg)

  def GetFullyQualifiedRulePath(self) -> str:
    """Returns the fully qualified target path (e.g., //foo/bar:baz)."""
    return self.target_path + ':' + self.target_name

  def GetPackagePkgFile(self) -> str:
    """Returns the path to the package zip file."""
    p_dir=self.GetPackagePathDirOnly()
    return os.path.join(p_dir, self.target_name) + '.zip'

  def GetPackagePathDirOnly(self) -> str:
    """Returns the directory part of the target path relative to root."""
    return self.target_path[2:]

  def GetRuleInfo(self) -> RuleSpec | None:
    """
    Executes the BUILD file to find and return information about this
    target's rule.
    """
    build_file=self.GetBuildFileForTarget()
    with open(build_file) as f:
      compiled=compile(f.read(), build_file, 'exec')
      logger=LoggerEnv()
      exec(compiled, logger)
      for call in logger.Calls():
        if call[1].get('name', None) == self.target_name:
          return RuleSpec(self, call)
    return None

  def startswith(self, chunk:str) -> bool:
    """Checks if the fully qualified path starts with the given chunk."""
    return self.GetFullyQualifiedRulePath().startswith(chunk)

  def __hash__(self) -> int:
    return hash(self.GetFullyQualifiedRulePath())

  def __eq__(self, other:object) -> bool:
    if isinstance(other, ParsedTarget):
      qual_p=self.GetFullyQualifiedRulePath()
      return qual_p == other.GetFullyQualifiedRulePath()
    return False

  def __repr__(self) -> str:
    return self.GetFullyQualifiedRulePath()


def convert_name_to_build_target(name:str, loaded_from_dir:str) -> \
    ParsedTarget:
  """Converts a target name and directory into a ParsedTarget."""
  return ParsedTarget(name, loaded_from_dir)


def convert_to_build_target(target:str | ParsedTarget, loaded_from_dir:str,
                           quit_on_err:bool=False) -> ParsedTarget | object:
  if isinstance(target, ParsedTarget):
    return target

  if is_relative_path(target):
    return ParsedTarget(target[1:], loaded_from_dir)

  if is_fully_qualified_path(target):
    _target=target.split(':')
    if len(_target) <= 1:
      raise PathException(target)
    return ParsedTarget(_target[1], _target[0])

  if quit_on_err:
    raise PathException(target)

  return NOT_A_BUILD_TARGET


def expand_fully_qualified_path(path:str) -> str:
  """Expands repository-qualified path (//foo) to absolute path."""
  if not is_fully_qualified_path(path):
    msg='Path is not repository-relative (missing starting //)'
    raise exceptions.InvalidPathException(path, msg)
  return os.path.join(root(), path[2:])


def is_fully_qualified_path(path:str) -> bool:
  """Returns True if the path is repository-qualified (starts with //)."""
  return path.startswith('//')


def is_relative_path(path:str) -> bool:
  """Returns True if path is relative to current BUILD file (starts with :)."""
  return path.startswith(':')


def get_qualified_build_file_dir(build_file_path:str) -> str:
  """Returns repository-qualified dir path for BUILD/build_defs.py."""
  build_pat=re.compile(os.path.join(root(), '(.*)/BUILD'))
  defs_pat=re.compile(os.path.join(root(), '(.*)/build_defs.py'))
  build_match=build_pat.match(build_file_path)
  defs_match=defs_pat.match(build_file_path)
  if build_match:
    return '//' + build_match.group(1)
  if defs_match:
    return '//' + defs_match.group(1)
  msg='targets must be defined in BUILD files or in build_defs.py macros'
  raise exceptions.InvalidPathException(msg, build_file_path)


class Platform():
  def __init__(self, **kwargs:object):
    self._values=kwargs

  def __getattr__(self, attr:str) -> object:
    if attr.startswith('__'):
      raise AttributeError(attr)
    if attr not in self._values:
      raise exceptions.PlatformKeyAbsentError(
        str(self._values['platform_target']), attr)
    return self._values[attr]


class BuildTarget(args.ArgComplete):
  @classmethod
  def get_completion_list(cls, stub:str) -> typing.Iterator[str]:
    if not stub:
      for value in cls._parse_from_local_build_file():
        yield ':' + value
    elif stub.startswith(':'):
      for value in cls._parse_from_local_build_file():
        if value.startswith(stub[1:]):
          yield value
    elif stub.startswith('//'):
      yield from cls._parse_partial_target(stub[2:])
    elif stub == '/':
      yield from cls._parse_partial_target(stub[1:])

  @classmethod
  def _parse_from_local_build_file(cls) -> typing.Iterator[str]:
    pwd=os.environ.get('PWD', '')
    build_path=os.path.join(pwd, 'BUILD')
    if os.path.exists(build_path):
      for value in cls._parse_from_build_file(build_path):
        yield value

  @classmethod
  def _parse_from_build_file(cls, build_file_path:str) -> typing.Iterator[str]:
    with open(build_file_path) as f:
      compiled=compile(f.read(), build_file_path, 'exec')
      logger=LoggerEnv()
      exec(compiled, logger)
      for call in logger.Calls():
        if 'name' in call[1]:
          yield str(call[1]['name'])

  @classmethod
  def _parse_targets_in_file(cls, path:str, target_stub:str) -> \
      typing.Iterator[str]:
    build_file=os.path.join(path, 'BUILD')
    if os.path.exists(build_file):
      for target in cls._parse_from_build_file(build_file):
        if target.startswith(target_stub):
          yield target

  @classmethod
  def _parse_partial_target(cls, path:str) -> typing.Iterator[str]:
    build_root=root()
    path=os.path.join(build_root, path)
    if ':' in path:
      yield from cls._parse_targets_in_file(*path.split(':'))

    if ':' not in path:
      for directory in args.Directory.get_completion_list(path):
        if not directory.endswith('/'):
          for entry in cls._parse_targets_in_file(directory, ''):
            yield '//' + directory[len(build_root)+1:] + ':' + entry
        yield '//' + directory[len(build_root)+1:]
