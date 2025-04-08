"""IdeMpotent Python bUiLd SystEm"""

import json
import glob
import os
import sys
import typing

from impulse import impulse_paths
from impulse import recursive_loader
from impulse.args import args
from impulse.core import debug
from impulse.core import errors
from impulse.core import exceptions
from impulse.core import threading
from impulse.format import format as fmt
from impulse.util import temp_dir
from impulse.types import parsed_target
from impulse.types import paths
from impulse.types import references

command = args.ArgumentParser(complete=True)


def setup(enable_debug:bool, fakeroot:typing.Optional[args.Directory]) -> None:
  """Sets up debug and path info."""
  if enable_debug:
    debug.EnableDebug()
  fakeroot = typing.cast(args.Directory, fakeroot)
  if fakeroot and fakeroot.value():
    os.environ['impulse_root'] = typing.cast(str, fakeroot.value())


def build_and_await(debug:bool, graph:parsed_target.StagedBuildTargetSet, N:int=6) -> None:
  """Starts a pool with N threads and waits for graph run completion."""
  pool = threading.DependentPool(N, debug=debug)
  pool.Start(graph._targets)
  pool.join()


def fix_build_target(
  target:impulse_paths.BuildTarget
) -> impulse_paths.ParsedTarget:
  """Converts some given path to a build target path."""
  return impulse_paths.convert_to_build_target(
    target.value(), impulse_paths.relative_pwd(), True
  )


def GetStagedRuleInfo(target:parsed_target.StagedBuildTarget):
  pt = impulse_paths.convert_to_build_target(str(target),
                                             impulse_paths.relative_pwd(),
                                             True)
  return pt.GetRuleInfo()


def graph_for_directory(project=None, testonly:bool=False) -> (
    list[parsed_target.StagedBuildTarget], parsed_target.StagedBuildTargetSet):
  directory = os.getcwd()
  if project:
    directory = os.path.join(impulse_paths.root(), project)

  rfp = recursive_loader.RecursiveFileParser()
  for filename in glob.iglob(directory + '/**/BUILD', recursive=True):
    rfp.LoadBuildFile(references.File(paths.AbsolutePath(filename)))

  targets = []
  if testonly:
    targets = list(rfp.StageAllTestTargets())
  else:
    targets=list(rfp.StageAllTargets())
  return targets, rfp.GetStagedTargets()


@command
def build(
  target:impulse_paths.BuildTarget,
  platform:impulse_paths.BuildTarget=None,
  debug:bool=False,
  force:bool=False,
  fakeroot:args.Directory=None,
  threads:int=6,
  hackermode:bool=False
):
  """Builds the given target."""
  if hackermode:
    os.system('impulse build //impulse:impulse')
    binary = f'{impulse_paths.root()}/GENERATED/BINARIES/impulse/impulse'
    os.system(f'{binary} build {target.value()} --debug --force')
    return

  setup(debug, fakeroot)
  parsed_target = fix_build_target(target)
  build_and_await(
    debug,
    recursive_loader.generate_graph(
      parsed_target, platform=platform, force_build=force, allow_meta=True
    ), threads
  )
  return parsed_target.GetRuleInfo()


@command
def targets(
  fakeroot:args.Directory=None,
  testonly:bool=False,
  project:str=None,
  roots:bool=False,
  debug:bool=False,
):
  """Lists all buildable targets."""
  setup(debug, fakeroot)
  targets, _ = graph_for_directory(project, testonly)
  for target in targets:
    print(target)


@command
def sitehost(
  target:impulse_paths.BuildTarget,
  debug:bool=False,
  force:bool=False,
  fakeroot:args.Directory=None
):
  ruleinfo = build(target, debug=debug, force=force, fakeroot=fakeroot)
  print(ruleinfo.type, ruleinfo.name, ruleinfo.output)
  if ruleinfo.type != 'website':
    print('Only website targets can be run')
    return
  with temp_dir.ScopedTempDirectory(delete_non_empty=True):
    os.system(f'unzip {ruleinfo.output}')
    os.system('tree')
    os.system('python3 -m http.server 8000')



@command
def run(
  target:impulse_paths.BuildTarget,
  debug:bool=False,
  fakeroot:args.Directory=None
):
  """Builds a binary and executes it."""
  ruleinfo = build(target=target, debug=debug, force=False, fakeroot=fakeroot)
  if not ruleinfo.type.endswith('_binary'):
    print('Only binary targets can be run')
    return
  os.system(ruleinfo.output)


@command
def docker(
  target:impulse_paths.BuildTarget,
  debug:bool=False,
  fakeroot:args.Directory=None,
  norun:bool=False
):
  """Builds a docker container from the target."""
  ruleinfo = build(target=target, debug=debug, force=False, fakeroot=fakeroot)
  if not ruleinfo.type == 'container':
    print(f'Only docker containers can be run: {ruleinfo.type}')
    return
  container = os.path.basename(ruleinfo.output)
  with temp_dir.ScopedTempDirectory(delete_non_empty=True):
    os.system(f'unzip {ruleinfo.output}')
    os.system(f'docker build -t {container[:-4]} .')
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
def test(
  target:impulse_paths.BuildTarget,
  debug:bool=False,
  fakeroot:args.Directory=None,
):
  """Builds a testcase and executes it."""
  ruleinfo = build(target, None, debug, False, fakeroot)
  if not ruleinfo.output.endswith('_test'):
    print('Only test targets can be run')
    return
  sys.exit(os.WEXITSTATUS(os.system(f'{ruleinfo.output} run')))


@command
def testsuite(
  project:str=None,
  debug:bool=False,
  threads:int=6,
  fakeroot:args.Directory=None
):
  setup(debug, fakeroot)
  targets, buildgraph = graph_for_directory(project, True)
  build_and_await(debug, buildgraph, threads)

  for staged_build_target in targets:
    binary = GetStagedRuleInfo(staged_build_target).output
    print(f'Running `{binary} run`')
    errcode = os.WEXITSTATUS(os.system(f'{binary} run'))
    if errcode != 0:
      sys.exit(errcode)


@command
def format(fakeroot:args.Directory=None):
  '''Formats all buildfiles'''
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
    override = input(
      ('A configuration file exists, '
       'do you want to overwrite it? [y, N]')
    )
    if override not in ('y', 'yes', 'Y'):
      return
  print(f'Exporting $IMPULSE_ROOT to {os.environ["PWD"]}')
  os.makedirs(f'{home}/.config/impulse/', exist_ok=True)
  with open(f'{home}/.config/impulse/config', 'w') as config:
    config.write(os.environ['PWD'])


def main():
  try:
    command.eval()
    return 0
  except errors.RenderableError as e:
    print(str(e))
    return 1


if __name__ == '__main__':
  sys.exit(main())
