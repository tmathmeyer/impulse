
import os
import re

from impulse.args import args

from impulse.exceptions import exceptions

EXPORT_DIR = 'GENERATED'
NOT_A_BUILD_TARGET = object()


def root():
  if 'impulse_root' not in os.environ:
    config = '{}/.config/impulse/config'.format(os.environ['HOME'])
    if os.path.exists(config):
      with open(config, 'r') as f:
        os.environ['impulse_root'] = f.read()
    else:
      raise LookupError('Impulse has not been initialized.')
  return os.environ['impulse_root']


def relative_pwd():
  impulse_root = root()
  pwd = os.getcwd()
  if not pwd:
    raise ValueError('Unable to determine current directory')

  if pwd.startswith(impulse_root):
    return '/' + pwd[len(impulse_root):]

  raise ValueError(
    f'Impulse must be run inside {impulse_root}\nbut you are in {pwd}')


def output_directory():
  return os.path.join(root(), EXPORT_DIR)


class PathException(Exception):
  def __init__(self, path, included_from=None):
    if included_from:
      self._path = 'Invalid Target: {} Included From: {}'.format(
        path, included_from)
    else:
      self._path = 'Invalid Target: {}'.format(path)
    super(PathException, self).__init__(self._path)

  def __repr__(self):
    return 'Invalid Target: ' + self._path


class LoggerEnv(dict):
  def __init__(self, called_as='module', push_up=None):
    self._calls = []
    self._called_as = called_as
    self._push_up = push_up

  def __getitem__(self, value):
    return LoggerEnv(called_as=value, push_up=self)

  def __call__(self, *args, **kwargs):
    kwargs['called_as'] = kwargs.get('called_as', [])
    kwargs['called_as'].append(self._called_as)
    if self._push_up:
      self._push_up(*args, **kwargs)
    else:
      self._calls.append((args, kwargs))
    return []

  def __iter__(self):
    for call in self._calls:
      yield call


class RuleSpec(object):
  def __init__(self, target, callspec):
    self.type = callspec[1].get('called_as')[0]
    self.name = callspec[1].get('name')
    output_type = 'BINARIES'
    if self.type.endswith('_container'):
      output_type = 'PACKAGES'
    self.output = os.path.join(
      output_directory(), output_type, target.target_path[2:], self.name)


class ParsedTarget(object):
  def __init__(self, target_name, target_path):
    self.target_name = target_name
    self.target_path = target_path

  def ParseFile(self, _, parser):
    parser(self.GetBuildFileForTarget())

  def GetBuildFileForTarget(self):
    return expand_fully_qualified_path(os.path.join(self.target_path, 'BUILD'))

  def GetFullyQualifiedRulePath(self):
    return self.target_path + ':' + self.target_name

  def GetPackagePkgFile(self):
    return os.path.join(self.GetPackagePathDirOnly(), self.target_name) + '.zip'

  def GetPackagePathDirOnly(self):
    return self.target_path[2:]

  def GetRuleInfo(self):
    build_file = self.GetBuildFileForTarget()
    with open(build_file) as f:
      compiled = compile(f.read(), build_file, 'exec')
      logger = LoggerEnv()
      exec(compiled, logger)
      for call in logger:
        if call[1].get('name', None) == self.target_name:
          return RuleSpec(self, call)

  def startswith(self, chunk):
    return self.GetFullyQualifiedRulePath().startswith(chunk)

  def __hash__(self):
    return hash(self.GetFullyQualifiedRulePath())

  def __eq__(self, other):
    if isinstance(other, ParsedTarget):
      return self.GetFullyQualifiedRulePath() == other.GetFullyQualifiedRulePath()
    return False

  def __repr__(self):
    return self.GetFullyQualifiedRulePath()


def convert_name_to_build_target(name, loaded_from_dir):
  return ParsedTarget(name, loaded_from_dir)


def convert_to_build_target(target, loaded_from_dir, quit_on_err=False):
  if isinstance(target, ParsedTarget):
    return target

  if is_relative_path(target):
    return ParsedTarget(target[1:], loaded_from_dir)

  if is_fully_qualified_path(target):
    _target = target.split(':')
    if len(_target) <= 1:
      raise PathException(target)
    return ParsedTarget(_target[1], _target[0])

  if target.startswith('git://') or target.startswith('git@'):
    giturl, target = target.rsplit('//', 1)
    basename = os.path.basename(giturl)
    gen_repo_name = os.path.join(root(), basename)
    if not os.path.exists(gen_repo_name):
      os.system(' '.join(['git clone', giturl, gen_repo_name]))
    if target.startswith(':'):
      target = f'//{basename}{target}'
    else:
      target = f'//{basename}/{target}'
    return convert_to_build_target(target, '//'+basename, quit_on_err)

  if quit_on_err:
    raise PathException(target)

  return NOT_A_BUILD_TARGET


def expand_fully_qualified_path(path):
  if not is_fully_qualified_path(path):
    raise exceptions.InvalidPathException(path,
      'Path is not repository-relative (missing starting //)')
  return os.path.join(root(), path[2:])


def is_fully_qualified_path(path):
  return path.startswith('//')


def is_relative_path(path):
  return path.startswith(':')


def get_qualified_build_file_dir(build_file_path):
  reg = re.compile(os.path.join(root(), '(.*)/BUILD'))
  try:
    return '//' + reg.match(build_file_path).group(1)
  except:
    print('{} didnt match {}'.format(
      os.path.join(root(), '(.*)/BUILD'), build_file_path))
    raise


class BuildTarget(args.ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    if not stub:
      for value in cls._parse_from_local_build_file():
        yield ':' + value
    elif stub.startswith(':'):
      for value in cls._parse_from_local_build_file():
        if value.startswith(stub[1:]):
          yield value
    elif stub.startswith('//'):
      yield from  cls._parse_partial_target(stub[2:])
    elif stub == '/':
      yield from  cls._parse_partial_target(stub[1:])

  @classmethod
  def _parse_from_local_build_file(cls):
    build_path = os.path.join(os.environ['PWD'], 'BUILD')
    if os.path.exists(build_path):
      for value in cls._parse_from_build_file(build_path):
        yield value

  @classmethod
  def _parse_from_build_file(cls, path_exists):
    with open(path_exists) as f:
      compiled = compile(f.read(), path_exists, 'exec')
      logger = LoggerEnv()
      exec(compiled, logger)
      for call in logger:
        if 'name' in call[1]:
          yield call[1]['name']

  @classmethod
  def _parse_targets_in_file(cls, path, target_stub):
    build_file = os.path.join(path, 'BUILD')
    if os.path.exists(build_file):
      for target in cls._parse_from_build_file(build_file):
        if target.startswith(target_stub):
          yield target

  @classmethod
  def _parse_partial_target(cls, path):
    build_root = root()
    path = os.path.join(build_root, path)
    if ':' in path:
      yield from cls._parse_targets_in_file(*path.split(':'))

    if ':' not in path:
      for directory in args.Directory.get_completion_list(path):
        if not directory.endswith('/'):
          for entry in cls._parse_targets_in_file(directory, ''):
            yield '//' + directory[len(build_root)+1:] + ':' + entry
        yield '//' + directory[len(build_root)+1:]
