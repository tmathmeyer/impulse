"""IdeMpotent Python bUiLd SystEm"""

import json
import glob
import os
import sys
import time
import typing

from impulse import impulse_paths
from impulse import recursive_loader
from impulse.args import args
from impulse.core import debug
from impulse.core import exceptions
from impulse.core import job_printer
from impulse.core import threading
from impulse.util import temp_dir
from impulse.util import tree_builder
from impulse.format import format as fmt


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
  pool = threading.DependentPool(N, debug=debug)
  pool.Start(graph)
  pool.join()


def fix_build_target(target:impulse_paths.BuildTarget
  ) -> impulse_paths.ParsedTarget:
  """Converts some given path to a build target path."""
  return impulse_paths.convert_to_build_target(target.value(),
    impulse_paths.relative_pwd(), True)


def graph_for_directory(project=None, testonly=False):
  directory = os.getcwd()
  if project:
    directory = os.path.join(impulse_paths.root(), project)

  rfp = recursive_loader.RecursiveFileParser(carried_args={})
  for filename in glob.iglob(directory + '/**/BUILD', recursive=True):
    rfp._ParseFile(filename)

  targets = []
  if testonly:
    return list(rfp.ConvertAllTestTargets()), rfp.GetAllConvertedTargets(
      allow_meta=True)
  else:
    rfp.ConvertAllTargets()
    targets = rfp.GetAllConvertedTargets(allow_meta=True)
    return targets, targets


def check_exactly(count, *args):
  for arg in args:
    if arg:
      count -= 1
    if count < 0:
      return False
  return not count


def get_target_from_graph(target, graph):
  target = fix_build_target(target)
  for node in graph:
    if target.GetFullyQualifiedRulePath() == node.get_name():
      return node


@command
def build(target:impulse_paths.BuildTarget,
          platform:impulse_paths.BuildTarget=None,
          debug:bool=False,
          force:bool=False,
          fakeroot:args.Directory=None,
          threads:int=6,
          hackermode:bool=False):
  """Builds the given target."""
  if hackermode:
    os.system('impulse build //impulse:impulse')
    binary = f'{impulse_paths.root()}/GENERATED/BINARIES/impulse/impulse'
    os.system(f'{binary} build {target.value()} --debug --force')
    return

  setup(debug, fakeroot)
  parsed_target = fix_build_target(target)
  build_and_await(debug, recursive_loader.generate_graph(
    parsed_target,
    platform=platform,
    force_build=force,
    allow_meta=True), threads)
  return parsed_target.GetRuleInfo()


@command
def info(target:impulse_paths.BuildTarget,
         fakeroot:args.Directory=None,
         debug:bool=False,
         tree:bool=False,
         deps:bool=False,
         consumers:bool=False):
  """Displays info about a target"""
  setup(debug, fakeroot)
  if check_exactly(tree, deps, consumers):
    print('Must specify exactly _one_ of --tree, --deps, or --consumers')
    return
  parsed_target = fix_build_target(target)
  if tree:
    tree_builder.BuildTree(
      recursive_loader.generate_graph(
        parsed_target, allow_meta=True)).Print()
    return

  graph = None
  if deps:
    graph = recursive_loader.generate_graph(parsed_target, allow_meta=True)
  if consumers:
    graph = set(graph_for_directory(None, False)[0])
  selected = get_target_from_graph(target, graph)
  print(selected.get_name())

  if deps:
    for dep in selected.dependencies:
      print(f'  {dep.get_name()}')

  if consumers:
    for target in graph:
      if selected in target.dependencies:
        print(f'  {target.get_name()}')



@command
def targets(fakeroot:args.Directory=None,
            project:str=None,
            roots:bool=False,
            debug:bool=False,):
  """Lists targets."""
  setup(debug, fakeroot)
  targets = set(graph_for_directory(project, False)[0])
  if roots:
    for target in set(targets):
      for dep in target.dependencies:
        if dep in targets:
          targets.remove(dep)
  for target in targets:
    print(target.get_name())


@command
def run(target:impulse_paths.BuildTarget,
        debug:bool=False,
        fakeroot:args.Directory=None):
  """Builds a testcase and executes it."""
  ruleinfo = build(target, debug, False, fakeroot)
  if not ruleinfo.type.endswith('_binary'):
    print('Only binary targets can be run')
    return
  os.system(ruleinfo.output)


@command
def docker(target:impulse_paths.BuildTarget,
           platform:impulse_paths.BuildTarget=None,
           debug:bool=False,
           fakeroot:args.Directory=None,
           norun:bool=False):
  """Builds a docker container from the target."""
  ruleinfo = build(target, debug, False, fakeroot)
  if not ruleinfo.type == 'container':
    print('Only docker containers can be run')
    return
  container = os.path.basename(ruleinfo.output)
  with temp_dir.ScopedTempDirectory(delete_non_empty=True):
    os.system(f'unzip {ruleinfo.output}')
    os.system(f'docker build -t {container} .')
    if norun:
      return
    with open('pkg_contents.json', 'r') as f:
      docker_args = json.loads(f.read())['docker_args'][0]
      run_cmd = 'docker run -d '
      if docker_args['ports']:
        run_cmd += '-P '
      run_cmd += f'{container}:latest'
      os.system(run_cmd)


@command
def test(target:impulse_paths.BuildTarget,
         debug:bool=False,
         notermcolor:bool=False,
         fakeroot:args.Directory=None,
         filter:str=None):
  """Builds a testcase and executes it."""
  ruleinfo = build(target, debug, False, fakeroot)
  if not ruleinfo.type.endswith('_test'):
    print('Only test targets can be run')
    return

  ntc = args.Forward("notermcolor")
  filter = args.Forward("filter")
  print(filter)
  os.system(f'{ruleinfo.output} run {ntc} {filter}')


@command
def testsuite(project:str=None,
              debug:bool=False,
              notermcolor:bool=False,
              threads:int=6,
              filter:str=None,
              fakeroot:args.Directory=None):
  setup(debug, fakeroot)
  targets, graph = graph_for_directory(project, True)
  build_and_await(debug, None, graph, threads)

  ntc = args.Forward("notermcolor")
  filter = args.Forward("filter")
  for builder in targets:
    os.system(f'{builder.GetRuleInfo().output} run {ntc} {filter}')


@command
def format(fakeroot:args.Directory=None):
  setup(False, fakeroot)
  directory = impulse_paths.root()
  files = {}
  for filename in glob.iglob(directory + '/**/BUILD', recursive=True):
    reader = fmt.FormattingBuildFileReader()
    reader.ReadFile(filename)
    files[filename] = reader.PrintFormat().strip()

  for filename, contents in files.items():
    with open(filename, 'r') as f:
      if f.read().strip() == contents:
        continue
    with open(filename, 'w') as f:
      f.write(contents)


@command
def init():
  """Initializes impulse in the current directory."""
  home = os.environ['HOME']
  if os.path.exists(f'{home}/.config/impulse/config'):
    override = input(('A configuration file exists, '
              'do you want to overwrite it? [y, N]'))
    if override not in ('y', 'yes', 'Y'):
      return
  print(f'Exporting $IMPULSE_ROOT to {os.environ["PWD"]}')
  os.makedirs(f'{home}/.config/impulse/', exist_ok=True)
  with open(f'{home}/.config/impulse/config', 'w') as config:
    config.write(os.environ['PWD'])



def main():
  try:
    command.eval()
  except exceptions.ImpulseBaseException as e:
    print(str(e))

if __name__ == '__main__':
  main()
