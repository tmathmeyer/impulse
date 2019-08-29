"""IdeMpotent Python bUiLd SystEm"""

import glob
import os
import sys
import time

from impulse import impulse_paths
from impulse import threaded_dependence
from impulse import recursive_loader
from impulse import status_out
from impulse.args import args
from impulse.util import temp_dir
from impulse.util import tree_builder


command = args.ArgumentParser(complete=True)



def setup(debug:bool, fakeroot:str):
  if debug:
    status_out.DEBUG = True
  if fakeroot:
    os.environ['impulse_root'] = fakeroot


def build_and_await(debug:bool, graph:set):
  pool = threaded_dependence.DependentPool(
    debug, 1 if debug else 6, len(graph))
  pool.input_job_graph(graph).start()
  pool.join()


def fix_build_target(target:str) -> impulse_paths.ParsedTarget:
  return impulse_paths.convert_to_build_target(target,
    impulse_paths.relative_pwd(), True)


@command
def build(target:impulse_paths.BuildTarget,
          debug:bool=False,
          force:bool=False,
          fakeroot:args.Directory=None):
  """Builds the given target."""
  setup(debug, fakeroot)
  target = fix_build_target(target)
  build_and_await(debug, recursive_loader.generate_graph(target,
    force_build=force))

@command
def print_tree(target:impulse_paths.BuildTarget,
               fakeroot:args.Directory=None):
  """Builds the given target."""
  setup(False, fakeroot)
  target = fix_build_target(target)
  tree = recursive_loader.generate_graph(target)
  tree = tree_builder.BuildTree(tree)
  if tree:
    tree.Print()
  else:
    print('ERROR')


@command
def run(target:impulse_paths.BuildTarget,
        debug:bool=False,
        fakeroot:args.Directory=None):
  """Builds a testcase and executes it."""
  setup(debug, fakeroot)
  target = fix_build_target(target)
  ruleinfo = target.GetRuleInfo()
  if not ruleinfo.type.endswith('_binary'):
    print('Can only run a binary target')
    return
  build_and_await(debug, recursive_loader.generate_graph(target))
  os.system(ruleinfo.output)


@command
def docker(target:impulse_paths.BuildTarget,
           debug:bool=False,
           fakeroot:args.Directory=None):
  setup(debug, fakeroot)
  target = fix_build_target(target)
  ruleinfo = target.GetRuleInfo()
  if not ruleinfo.type.endswith('_container'):
    print('Can only containerize a container target')
    return
  build_and_await(debug, recursive_loader.generate_graph(target))

  extractcmd = 'unzip {}'.format(ruleinfo.output)
  with temp_dir.ScopedTempDirectory(delete_non_empty=True):
    os.system(extractcmd)
    dockercmd = 'docker build -t {} .'.format(os.path.basename(ruleinfo.output))
    os.system(dockercmd)


@command
def test(target:impulse_paths.BuildTarget,
         export:bool=False,
         debug:bool=False,
         fakeroot:args.Directory=None):
  """Builds a testcase and executes it."""
  setup(debug, fakeroot)
  target = fix_build_target(target)
  ruleinfo = target.GetRuleInfo()
  if not ruleinfo.type.endswith('_test'):
    print('Can only test a binary target')
    return
  build_and_await(debug, recursive_loader.generate_graph(target))
  cmdline = '{} {}'.format(ruleinfo.output,
    'export_results' if export else 'run')
  os.system(cmdline)


@command
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


@command
def testsuite(project:str=None, debug:bool=False, fakeroot:args.Directory=None):
  if debug:
    status_out.DEBUG = True

  if fakeroot:
    os.environ['impulse_root'] = fakeroot

  directory = os.getcwd()
  if project:
    directory = os.path.join(impulse_paths.root(), project)

  rfp = recursive_loader.RecursiveFileParser()
  for filename in glob.iglob(directory + '/**/BUILD', recursive=True):
    rfp._ParseFile(filename)

  builders = list(rfp.ConvertAllTestTargets())
  
  graph = rfp.GetAllConvertedTargets()
  pool = threaded_dependence.DependentPool(debug, 6, len(graph))
  pool.input_job_graph(graph).start()
  pool.join()

  for builder in builders:
    ruleinfo = builder.GetRuleInfo()
    cmdline = '{} {}'.format(ruleinfo.output, 'run')
    os.system(cmdline)


def main():
  command.eval()


if __name__ == '__main__':
  main()
