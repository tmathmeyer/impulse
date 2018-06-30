
import os
import re
import sys

def root():
  return os.environ['impulse_root']

NOT_A_BUILD_TARGET = object()

class BuildTarget(object):
  def __init__(self, target_name, target_path):
    self.target_name = target_name
    self.target_path = target_path

  def GetBuildFileForTarget(self):
    return expand_fully_qualified_path(self.target_path + '/BUILD')

  def GetFullyQualifiedRulePath(self):
    return self.target_path + ':' + self.target_name

  def __hash__(self):
    return hash(self.GetFullRulePath())

  def __eq__(self, other):
    if isinstance(other, BuildTarget):
      return self.GetFullRulePath() == other.GetFullRulePath()
    return False

  def __repr__(self):
    return str(self.__dict__)


def convert_name_to_build_target(name, loaded_from_dir):
  return BuildTarget(name, loaded_from_dir)


def convert_to_build_target(target, loaded_from_dir, quit_on_err=False):
  if is_relative_path(target):
    return BuildTarget(target[1:], loaded_from_dir)

  if is_fully_qualified_path(target):
    target = target.split(':')
    assert len(target) > 1
    return BuildTarget(target[1], target[0])

  if target.startswith('git://'):
    giturl, target = target.split('%', 1)
    basename = os.path.basename(giturl)
    gen_repo_name = os.path.join(os.environ['impulse_root'], basename)
    if not os.path.exists(gen_repo_name):
      os.system(' '.join(['git clone', giturl, gen_repo_name]))
    return convert_to_build_target(target, '//'+basename, quit_on_err)

  if quit_on_err:
    sys.exit('Could not parse %s as build rule' % target)

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