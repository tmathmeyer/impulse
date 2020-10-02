"""IdeMpotent Python bUiLd SystEm"""

import glob
import os
import sys
import time
import typing

from impulse import impulse_paths
from impulse import threaded_dependence
from impulse import recursive_loader
from impulse import status_out
from impulse.core import debug
from impulse.args import args
from impulse.util import temp_dir
from impulse.util import tree_builder


command = args.ArgumentParser(complete=True)



def setup(enable_debug:bool, fakeroot:typing.Optional[args.Directory]) -> None:
  """Sets up debug and path info."""
  if enable_debug:
    debug.EnableDebug()
  fakeroot = typing.cast(args.Directory, fakeroot)
  if fakeroot.value():
    os.environ['impulse_root'] = typing.cast(str, fakeroot.value())


def build_and_await(debug:bool, graph:set, N:int=6) -> None:
  """Starts a pool with N threads and waits for graph run completion."""
  pool = threaded_dependence.ThreadPool(N, debug=debug)
  pool.Start(graph)
  pool.join()


def fix_build_target(target:impulse_paths.BuildTarget
  ) -> impulse_paths.ParsedTarget:
  """Converts some given path to a build target path."""
  return impulse_paths.convert_to_build_target(target.value(),
    impulse_paths.relative_pwd(), True)


@command
def build(target:impulse_paths.BuildTarget,
          debug:bool=False,
          force:bool=False,
          fakeroot:args.Directory=None):
  """Builds the given target."""
  setup(debug, fakeroot)
  parsed_target = fix_build_target(target)
  build_and_await(debug, recursive_loader.generate_graph(parsed_target,
    force_build=force, allow_meta=True))

@command
def print_tree(target:impulse_paths.BuildTarget,
               fakeroot:args.Directory=None,
               debug:bool=False):
  """Builds the given target."""
  setup(debug, fakeroot)
  parsed_target = fix_build_target(target)
  tree = recursive_loader.generate_graph(parsed_target, allow_meta=True)
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
  parsed_target = fix_build_target(target)
  ruleinfo = parsed_target.GetRuleInfo()
  if not ruleinfo.type.endswith('_binary'):
    print('Can only run a binary target')
    return
  build_and_await(debug, recursive_loader.generate_graph(parsed_target))
  os.system(ruleinfo.output)


@command
def docker(target:impulse_paths.BuildTarget,
           debug:bool=False,
           fakeroot:args.Directory=None):
  """Builds a docker container from the target."""
  setup(debug, fakeroot)
  parsed_target = fix_build_target(target)
  ruleinfo = parsed_target.GetRuleInfo()
  if not ruleinfo.type == 'container':
    print('Can only containerize a container target')
    return
  build_and_await(
    debug, recursive_loader.generate_graph(parsed_target, allow_meta=True))

  extractcmd = 'unzip {}'.format(ruleinfo.output)
  with temp_dir.ScopedTempDirectory(delete_non_empty=True):
    os.system(extractcmd)
    dockercmd = 'docker build -t {} .'.format(os.path.basename(ruleinfo.output))
    os.system(dockercmd)


@command
def test(target:impulse_paths.BuildTarget,
         debug:bool=False,
         notermcolor:bool=False,
         fakeroot:args.Directory=None):
  """Builds a testcase and executes it."""
  setup(debug, fakeroot)
  parsed_target = fix_build_target(target)
  ruleinfo = parsed_target.GetRuleInfo()
  if not ruleinfo.type.endswith('_test'):
    print('Can only test a binary target')
    return
  build_and_await(debug, recursive_loader.generate_graph(parsed_target))
  cmdline = '{} {} {}'.format(
    ruleinfo.output, 'run', '--notermcolor' if notermcolor else '')
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
def testsuite(project:str=None,
              debug:bool=False,
              notermcolor:bool=False,
              threads:int=6,
              fakeroot:args.Directory=None):
  setup(debug, fakeroot)

  directory = os.getcwd()
  if project:
    directory = os.path.join(impulse_paths.root(), project)

  rfp = recursive_loader.RecursiveFileParser(carried_args={})
  for filename in glob.iglob(directory + '/**/BUILD', recursive=True):
    rfp._ParseFile(filename)

  builders = list(rfp.ConvertAllTestTargets())
  
  graph = rfp.GetAllConvertedTargets()
  pool = threaded_dependence.ThreadPool(debug=debug, poolcount=threads)
  pool.Start(graph)
  pool.join()

  for builder in builders:
    ruleinfo = builder.GetRuleInfo()
    cmdline = '{} {} {}'.format(
      ruleinfo.output, 'run', '--notermcolor' if notermcolor else '')
    os.system(cmdline)

@command
def buildall(project:str=None,
             debug:bool=False,
             fakeroot:args.Directory=None):
  setup(debug, fakeroot)

  directory = os.getcwd()
  if project:
    directory = os.path.join(impulse_paths.root(), project)

  rfp = recursive_loader.RecursiveFileParser(carried_args={})
  for filename in glob.iglob(directory + '/**/BUILD', recursive=True):
    rfp._ParseFile(filename)

  rfp.ConvertAllTargets()
  graph = rfp.GetAllConvertedTargets()
  pool = threaded_dependence.ThreadPool(debug=debug, poolcount=6)
  pool.Start(graph)
  pool.join()


def main():
  command.eval()


if __name__ == '__main__':
  main()
