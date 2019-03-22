"""IdeMpotent Python bUiLd SystEm"""

import os
import time

from impulse import impulse_paths
from impulse import threaded_dependence
from impulse import recursive_loader
from impulse import status_out
from impulse.args import args


arguments = args.ArgumentParser(complete=True)


@arguments
def build(target:impulse_paths.BuildTarget,
          debug:bool=False,
          fakeroot:args.Directory=None):
  """Builds the given target."""
  if debug:
    status_out.DEBUG = True

  if fakeroot:
    os.environ['impulse_root'] = fakeroot

  bt = impulse_paths.convert_to_build_target(
    target, impulse_paths.relative_pwd(), True)

  graph = recursive_loader.generate_graph(bt)
  pool = threaded_dependence.DependentPool(debug, 1 if debug else 6, len(graph))
  pool.input_job_graph(graph).start()



@arguments
def test(target:impulse_paths.BuildTarget,
         export:bool=False,
         fakeroot:args.Directory=None):
  """Builds a testcase and executes it."""
  if fakeroot:
    os.environ['impulse_root'] = fakeroot

  bt = impulse_paths.convert_to_build_target(
    target, impulse_paths.relative_pwd(), True)

  ruleinfo = bt.GetRuleInfo()

  if not ruleinfo.type.endswith('_test'):
    print('Can only test a test target')
    return

  graph = recursive_loader.generate_graph(bt)

  pool = threaded_dependence.DependentPool(6, len(graph))
  pool.input_job_graph(graph).start()
  pool.join()

  cmdline = '{} {}'.format(ruleinfo.output,
    'export_results' if export else 'run')
  os.system(cmdline)



@arguments
def init():
  """Initializes impulse in the current directory."""
  home = os.environ['HOME']
  if os.path.exists('{}/.config/impulse/config'.format(home)):
    override = input(('A configuration file exists, '
              'do you want to overwrite it? [y, N]'))
    if override not in ('y', 'yes', 'Y'):
      return

  print('Exporting $IMPULSE_ROOT to {}'.format(os.environ['PWD']))
  os.makedirs('{}/.config/impulse/'.format(home), exist_ok=True)
  with open('{}/.config/impulse/config'.format(home), 'w') as config:
    config.write(os.environ['PWD'])


def main():
  arguments.eval()


if __name__ == '__main__':
  main()
