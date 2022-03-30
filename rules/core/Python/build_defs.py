
def py_make_binary(target, package_name, package_file, binary_location):
  binary_file = os.path.join(binary_location, package_name)
  target.Execute(
    f'echo "#!/usr/bin/env python3\n" >> {binary_file}',
    f'cat {package_file} >> {binary_file}',
    f'chmod +x {binary_file}')


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


def _get_pip_metadata(pips):
  import sysconfig
  import re
  lib_path = sysconfig.get_path('platlib', sysconfig.get_default_scheme())
  py_version = lib_path.split('/')[3][6:]
  packages = []
  while pips:
    pip = pips[0]
    pips = pips[1:]
    verz = r'\d+(.\d+)+'
    egg_fmt = f'{pip}-{verz}-py{py_version}.egg-info'
    egg_info = None
    for file in os.listdir(lib_path):
      if re.match(egg_fmt, file):
        egg_info = f'{lib_path}/{file}'
        break
    if egg_info == None:
      raise ValueError(f'Error! Cant find {pip} installation')
    if os.path.exists(f'{egg_info}/requires.txt'):
      with open(f'{egg_info}/requires.txt', 'r') as f:
        for line in f.readlines():
          if not line.strip():
            break;
          pips.append(line.split('>=')[0])
    with open(f'{egg_info}/top_level.txt', 'r') as f:
      packages.append(f.read().strip())
  return [(p, f'{lib_path}/{p}') for p in packages]



@depends_targets("//impulse/util:bintools")
@using(_add_files, _write_file, _get_tools_paths, py_make_binary,
       _get_pip_metadata)
@buildrule
def py_binary(target, name, **kwargs):
  target.SetTags('exe')
  srcs = kwargs.get('srcs', [])

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    if not os.path.exists(directory):
      break
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)

  # Track any additional sources
  _add_files(target, srcs + kwargs.get('data', []))

  for tool in _get_tools_paths(target, kwargs.get('tools', [])):
    target.AddFile(tool)

  mainfile = name
  package = '.'.join(target.GetPackageDirectory().split('/'))
  if kwargs.get('mainfile', None) is not None:
    mainfile = kwargs.get('mainfile').rstrip('py').rstrip('.')
    if kwargs.get('mainpackage', None) is not None:
      package = kwargs.get('mainpackage')
  elif f'{name}.py' not in srcs:
    if len(srcs) == 1:
      mainfile = srcs[0].rstrip('py').rstrip('.')

  # Create the __main__ file
  main_contents = f'from {package} import {mainfile}\n{mainfile}.main()\n'
  _write_file(target, '__main__.py', main_contents)
  for pkgname, pkgpath in _get_pip_metadata(kwargs.get('pips', [])):
    os.system(f'cp -r {pkgpath} {pkgname}')
    for dn, _, files in os.walk(pkgname):
      for file in files:
        target.AddFile(f'{dn}/{file}')

  # Converter from pkg to binary
  return py_make_binary


@depends_targets("//impulse/testing:unittest")
@using(_add_files, _write_file, py_make_binary)
@buildrule
def py_test(target, name, srcs, **kwargs):
  target.SetTags('exe', 'test')
  _add_files(target, srcs + kwargs.get('data', []))
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
    main_contents += f'from {package} import {os.path.splitext(src)[0]}\n'
  main_contents += main_exec

  _write_file(target, '__main__.py', main_contents)
  return py_make_binary
