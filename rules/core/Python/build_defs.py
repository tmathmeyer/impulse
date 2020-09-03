
def py_make_binary(package_name, package_file, binary_location):
  binary_file = os.path.join(binary_location, package_name)
  os.system('echo "#!/usr/bin/env python3\n" >> {}'.format(binary_file))
  os.system('cat {} >> {}'.format(package_file, binary_file))
  os.system('chmod +x {}'.format(binary_file))


def _add_files(target, srcs):
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))
  for deplib in target.Dependencies(tags=Any('py_library')):
    for f in deplib.IncludedFiles():
      target.AddFile(f)
  for deplib in target.Dependencies(tags=Any('data')):
    for f in deplib.IncludedFiles():
      target.AddFile(f)
      d = os.path.dirname(f)
      while d:
        _write_file(target, os.path.join(d, '__init__.py'), '#generated')
        d = os.path.dirname(d)


def _write_file(target, name, contents):
  if not os.path.exists(name):
    with open(name, 'w+') as f:
      f.write(contents)
  target.AddFile(name)


def _get_tools_paths(target, targets):
  for t in targets:
    yield os.path.join('bin', str(t).split(':')[-1])


@using(_add_files, _write_file)
@buildrule
def py_library(target, name, srcs, **kwargs):
  target.SetTags('py_library')
  _add_files(target, srcs + kwargs.get('data', []))

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)

@depends_targets("git://github.com/tmathmeyer/impulse//proto:protocompile")
@using(_write_file)
@buildrule
def py_proto(target, name, **kwargs):
  import subprocess
  target.SetTags('py_library')
  if 'srcs' not in kwargs or len(kwargs['srcs']) != 1:
    target.ExecutionFailed('prepare', 'srcs must have exactly one proto file')

  directory = target.GetPackageDirectory()
  command = f'./bin/protocompile --proto {directory}/{kwargs["srcs"][0]} python'
  result = subprocess.run(command, encoding='utf-8', shell=True,
    stderr=subprocess.PIPE, stdout=subprocess.PIPE)

  if result.returncode:
    target.ExecutionFailed(command, result.stderr)

  for line in result.stdout.split('\n'):
    line = line.strip()
    if line:
      target.AddFile(line)
      direct = os.path.dirname(line)
      while direct:
        _write_file(target, os.path.join(direct, '__init__.py'), '#generated')
        direct = os.path.dirname(direct)

@depends_targets("git://github.com/tmathmeyer/impulse//util:bintools")
@using(_add_files, _write_file, _get_tools_paths, py_make_binary)
@buildrule
def py_binary(target, name, **kwargs):
  target.SetTags('exe')

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)

  # Track any additional sources
  _add_files(target, kwargs.get('srcs', []) + kwargs.get('data', []))

  for tool in _get_tools_paths(target, kwargs.get('tools', [])):
    target.AddFile(tool)


  # Create the __main__ file
  main_fmt = 'from {package} import {name}\n{name}.main()\n'
  package = '.'.join(target.GetPackageDirectory().split('/'))
  main_contents = main_fmt.format(package=package, name=name)
  _write_file(target, '__main__.py', main_contents)

  # Converter from pkg to binary
  return py_make_binary


@depends_targets("//impulse/testing:unittest")
@using(_add_files, _write_file, py_make_binary)
@buildrule
def py_test(target, name, srcs, **kwargs):
  target.SetTags('exe', 'test')
  # Create the init files
  import os
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)

  # Track the sources
  _add_files(target, srcs)

  import_fmt = 'from {} import {}\n'
  main_exec = 'from impulse.testing import testmain\ntestmain.main()\n'
  main_contents = ''
  package = '.'.join(target.package_target.GetPackagePathDirOnly().split('/'))

  for src in srcs:
    main_contents += import_fmt.format(package, os.path.splitext(src)[0])
  main_contents += main_exec

  _write_file(target, '__main__.py', main_contents)
  return py_make_binary
