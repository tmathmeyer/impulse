"""IdeMpotent Python bUiLd SystEm"""

import argparse
import inspect
import os
import sys
import time

import impulse_paths
import threaded_dependence
import recursive_loader
import status_out


PARSER = argparse.ArgumentParser()
TASKS = PARSER.add_subparsers(title='tasks')


def target(parser):
  def decorator(func):
    helpmsg = func.__doc__ or func.__name__
    task = parser.add_parser(
      func.__name__,
      help=helpmsg.splitlines()[0])
    task.set_defaults(task=func.__name__)

    args_name = inspect.getargspec(func)[0]
    for arg in args_name:
      if arg != 'debug':
        task.add_argument(arg, metavar=arg[0].upper(), type=str)

    task.add_argument('--debug', default=False, action='store_true')

    def __stub__(parsed):
      func(**dict((n, getattr(parsed, n)) for n in args_name))
    return __stub__

  return decorator



def _getroot():
  config = '%s/.config/impulse/config' % os.environ['HOME']
  if os.path.exists(config):
    with open(config, 'r') as f:
      return f.read()
  raise LookupError('Impulse has not been initialized.')

def _pwd_root_relative():
  root = _getroot()
  pwd = os.environ['PWD']
  if pwd.startswith(root):
    return '/' + pwd[len(root):]
  raise ValueError('Impulse can\'t be run from outside %s.' % root)


@target(TASKS)
def build(target, debug):
  if debug:
    status_out.debug = True
  os.environ['impulse_root'] = _getroot()

  bt = impulse_paths.convert_to_build_target(target, _pwd_root_relative(), True)

  time1 = time.time()
  graph = recursive_loader.generate_graph(bt)
  time2 = time.time()

  diff = (time2-time1) * 1000
  print('loaded [%s] rules in %.2f ms' % (len(graph), diff))
  print('Starting build')

  pool = threaded_dependence.DependentPool(6)
  pool.input_job_graph(graph).start()


@target(TASKS)
def init():
  home = os.environ['HOME']
  if os.path.exists('%s/.config/impulse/config' % home):
    override = input(('A configuration file exists, '
              'do you want to overwrite it? [y, N]'))
    if override not in ('y', 'yes', 'Y'):
      return

  os.makedirs('%s/.config/impulse/' % home, exist_ok=True)
  with open('%s/.config/impulse/config' % home, 'w') as config:
    config.write(os.environ['PWD'])

@target(TASKS)
def examine(target):
  root = _getroot()
  cdir = os.environ['PWD']
  os.environ['impulse_root'] = root
  if not cdir.startswith(root):
    raise ValueError('Impulse can\'t be run from outside %s.' % root)

  bt = impulse_paths.convert_to_build_target(target, cdir, True)

  time1 = time.time()
  graph = recursive_loader.generate_graph(bt)
  time2 = time.time()

  diff = (time2-time1) * 1000
  print('loaded [%s] rules in %.2f ms' % (len(graph), diff))

  for node in graph:
    if node.name == target:
      node.print()




def main():
  a = PARSER.parse_args()
  getattr(sys.modules[__name__], a.task)(a)
  