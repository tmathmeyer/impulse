
import os
import re
import sys

from impulse.args import args

def root():
  return os.environ['impulse_root']

NOT_A_BUILD_TARGET = object()


def getroot():
  config = '%s/.config/impulse/config' % os.environ['HOME']
  if os.path.exists(config):
    with open(config, 'r') as f:
      return f.read()
  raise LookupError('Impulse has not been initialized.')


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

class ParsedTarget(object):
  def __init__(self, target_name, target_path):
    self.target_name = target_name
    self.target_path = target_path

  def GetBuildFileForTarget(self):
    return expand_fully_qualified_path(self.target_path + '/BUILD')

  def GetFullyQualifiedRulePath(self):
    return self.target_path + ':' + self.target_name

  def __hash__(self):
    return hash(self.GetFullyQualifiedRulePath())

  def __eq__(self, other):
    if isinstance(other, ParsedTarget):
      return self.GetFullyQualifiedRulePath() == other.GetFullyQualifiedRulePath()
    return False

  def __repr__(self):
    return str(self.__dict__)


def convert_name_to_build_target(name, loaded_from_dir):
  return ParsedTarget(name, loaded_from_dir)


def convert_to_build_target(target, loaded_from_dir, quit_on_err=False):
  if is_relative_path(target):
    return ParsedTarget(target[1:], loaded_from_dir)

  if is_fully_qualified_path(target):
    _target = target.split(':')
    if len(_target) <= 1:
      raise PathException(target)
    return ParsedTarget(_target[1], _target[0])

  if target.startswith('git://'):
    giturl, target = target.split('%', 1)
    basename = os.path.basename(giturl)
    gen_repo_name = os.path.join(os.environ['impulse_root'], basename)
    if not os.path.exists(gen_repo_name):
      os.system(' '.join(['git clone', giturl, gen_repo_name]))
    return convert_to_build_target(target, '//'+basename, quit_on_err)

  if quit_on_err:
    raise PathException(target)

  return NOT_A_BUILD_TARGET

def expand_fully_qualified_path(path):
  if not is_fully_qualified_path(path):
    sys.exit('%s needs to be fully qualified' % path)
  return os.path.join(root(), path[2:])

def is_fully_qualified_path(path):
  return path.startswith('//')

def is_relative_path(path):
  return path.startswith(':')

def get_qualified_build_file_dir(build_file_path):
  reg = re.compile(os.path.join(os.environ['impulse_root'], '(.*)/BUILD'))
  return '//' + reg.match(build_file_path).group(1)

class LoggerEnv(dict):
  def __init__(self):
    self._calls = []

  def __getitem__(self, value):
    return self

  def __call__(self, *args, **kwargs):
    self._calls.append((args, kwargs))

  def __iter__(self):
    for call in self._calls:
      yield call

class BuildTarget(args.ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    if stub == '?':
      for value in cls._parse_from_local_build_file():
        yield ':' + value
    elif stub.startswith(':'):
      for value in cls._parse_from_local_build_file():
        if value.startswith(stub[1:-1]):
          yield value
    elif stub.startswith('//'):
      for path in cls._parse_partial_target(stub[2:]):
        yield path
    elif stub == '/?':
      yield '//'

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
    if target_stub.endswith('?'):
      target_stub = target_stub[:-1]
    build_file = os.path.join(path, 'BUILD')
    if os.path.exists(build_file):
      for target in cls._parse_from_build_file(build_file):
        if target.startswith(target_stub):
          yield target

  @classmethod
  def _parse_partial_target(cls, path):
    build_root = getroot()
    path = os.path.join(build_root, path)
    if ':' in path:
      for value in cls._parse_targets_in_file(*path.split(':')):
        yield value

    if ':' not in path:
      for directory in args.Directory.get_completion_list(path):
        yield '//' + directory[len(build_root)+1:]
