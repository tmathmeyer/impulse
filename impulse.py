"""IdeMpotent Python bUiLd SystEm"""

import argparse
import inspect
import os
import sys
import time

from impulse import impulse_paths
from impulse import threaded_dependence
from impulse import recursive_loader
from impulse import status_out
from impulse.args import args

arguments = args.ArgumentParser(complete=True)


def _pwd_root_relative():
  root = os.environ['impulse_root']
  pwd = os.environ['PWD']
  if pwd.startswith(root):
    return '/' + pwd[len(root):]
  raise ValueError('Impulse can\'t be run from outside %s.' % root)


@arguments
def build(target:impulse_paths.BuildTarget,
          debug:bool=False,
          fakeroot:args.Directory=None):
  """Builds the given target."""
  if debug:
    status_out.debug = True
  os.environ['impulse_root'] = fakeroot or impulse_paths.getroot()

  bt = impulse_paths.convert_to_build_target(target, _pwd_root_relative(), True)

  time1 = time.time()
  graph = recursive_loader.generate_graph(bt)
  time2 = time.time()

  diff = (time2-time1) * 1000

  pool = threaded_dependence.DependentPool(6, len(graph))
  pool.input_job_graph(graph).start()


@arguments
def init():
  """Initializes impulse in the current directory."""
  home = os.environ['HOME']
  if os.path.exists('%s/.config/impulse/config' % home):
    override = input(('A configuration file exists, '
              'do you want to overwrite it? [y, N]'))
    if override not in ('y', 'yes', 'Y'):
      return

  os.makedirs('%s/.config/impulse/' % home, exist_ok=True)
  with open('%s/.config/impulse/config' % home, 'w') as config:
    config.write(os.environ['PWD'])


def main():
  arguments.eval()


if __name__ == '__main__':
  main()
