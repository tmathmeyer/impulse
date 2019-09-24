
def py_make_binary(package_name, package_file, binary_location):
  binary_file = os.path.join(binary_location, package_name)
  os.system('echo "#!/usr/bin/env python3\n" >> {}'.format(binary_file))
  os.system('cat {} >> {}'.format(package_file, binary_file))
  os.system('chmod +x {}'.format(binary_file))


def _add_files(target, srcs):
  for src in srcs:
    for path in target.DataValueOf(src):
      target.AddFile(os.path.join(target.GetPackageDirectory(), path))
  for deplib in target.Dependencies(package_ruletype='py_library'):
    for f in deplib.IncludedFiles():
      target.AddFile(f)


def _write_file(target, name, contents):
  if not os.path.exists(name):
    with open(name, 'w+') as f:
      f.write(contents)
  target.AddFile(name)


def _get_includes_paths(target, targets):
  for t in targets:
    yield from target.DataValueOf(t)


@using(_add_files, _write_file)
@buildrule
def py_library(target, name, srcs, **kwargs):
  _add_files(target, srcs + kwargs.get('data', []))

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)


@depends_targets("//impulse/util:bintools")
@using(_add_files, _write_file, _get_includes_paths, py_make_binary)
@buildrule
def py_binary(target, name, **kwargs):
  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)

  # Track any additional sources
  _add_files(target, kwargs.get('srcs', []) + kwargs.get('data', []))

  includelist = []
  for include in _get_includes_paths(target, kwargs.get('tools', [])):
    target.AddFile(include)
    includelist.append(include)
  if includelist:
    _write_file(target, os.path.join('bin', '__init__.py'), '#generated')

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
