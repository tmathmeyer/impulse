
def py_make_binary(target, package_name, package_file, binary_location):
  binary_file = os.path.join(binary_location, package_name)
  target.Execute(
    f'echo "#!/usr/bin/env python3\n" > {binary_file}',
    f'cat {package_file} >> {binary_file}',
    f'chmod +x {binary_file}')


def _add_files(target, srcs):
  for src in srcs:
    added_file = os.path.join(target.GetPackageDirectory(), src)
    if not os.path.exists(added_file):
      target.ExecutionFailed(f'CHECKFILE {added_file}', 'file does not exist')
    target.AddFile(added_file)
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


def _get_recursive_pips(target, kwargs):
  my_pips = set(kwargs.get('pips', []))
  for dep in target.Dependencies(tags=Any('py_library', 'py_binary')):
    my_pips.update(set(dep.GetPropagatedData('pips')))
  return list(my_pips)

@using(_add_files, _write_file, _get_recursive_pips)
@buildrule
def py_library(target, name, srcs, **kwargs):
  target.SetTags('py_library')
  _add_files(target, srcs + kwargs.get('data', []))
  for pip in _get_recursive_pips(target, kwargs):
    target.PropagateData('pips', pip)

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

  def GetOtherNameCombinations(pip):
    dash = pip.replace('_', '-')
    under = pip.replace('-', '_')
    return [
      under[0].upper() + under[1:],
      under[0].lower() + under[1:],
      dash[0].upper() + dash[1:],
      dash[0].lower() + dash[1:],
    ]

  def GetPipEgg(pip, req, retry=True):
    verz = r'\d+(.\d+)+'
    egg_fmt = rf'-py{py_version}.egg'
    dist_fmt = rf'\.dist'
    dir_fmt = rf'{pip}-{verz}(({egg_fmt})|({dist_fmt}))-info'
    for file in os.listdir(lib_path):
      if re.match(dir_fmt, file):
        return f'{lib_path}/{file}'
    if retry:
      for name in GetOtherNameCombinations(pip):
        try:
          return GetPipEgg(name, req, False)
        except:
          pass
    raise ValueError(
      f'Cant find {pip} installation, required by {req} (checked {lib_path})')

  def ParseRequirementLine(line):
    match = re.match(r'([a-zA-Z0-9-_]+).*', line.strip())
    return match.groups()[0]

  pips = [(p,'root') for p in pips]
  parsed_pips = []

  while pips:
    pip, req = pips[0]
    if pip in parsed_pips:
      continue
    parsed_pips.append(pip)
    pips = pips[1:]
    egg_info = GetPipEgg(pip, req)
    if os.path.exists(f'{egg_info}/requires.txt'):
      with open(f'{egg_info}/requires.txt', 'r') as f:
        for line in f.readlines():
          if not line.strip():
            break;
          pips.append((ParseRequirementLine(line), pip))
    if os.path.exists(f'{egg_info}/top_level.txt'):
      with open(f'{egg_info}/top_level.txt', 'r') as f:
        packages.append(f.read().split('\n')[0].strip())
    elif os.path.exists(f'{lib_path}/{pip}'):
      packages.append(pip)

  result = []
  for p in packages:
    lib = f'{lib_path}/{p}'
    if os.path.exists(lib):
      result.append((p, lib))
    elif os.path.exists(f'{lib}.py'):
      result.append((p, f'{lib}.py'))
  return result


@depends_targets("//impulse/util:bintools")
@using(_add_files, _write_file, _get_tools_paths, py_make_binary,
       _get_pip_metadata, _get_recursive_pips)
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

  for pip in _get_recursive_pips(target, kwargs):
    target.PropagateData('pips', pip)

  # Create the __main__ file
  main_contents = f'from {package} import {mainfile}\n{mainfile}.main()\n'
  _write_file(target, '__main__.py', main_contents)
  for pkgname, pkgpath in _get_pip_metadata(_get_recursive_pips(target, kwargs)):
    os.system(f'cp -r {pkgpath} {pkgname}')
    for dn, _, files in os.walk(pkgname):
      for file in files:
        sourcefile = f'{dn}/{file}'
        if '__pycache__' not in sourcefile:
          target.AddFile(sourcefile)

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

  main_exec = 'from impulse.testing import testmain\ntestmain.main()\n'
  main_contents = ''
  package = '.'.join(target.package_target.GetPackagePathDirOnly().split('/'))

  for src in srcs:
    main_contents += f'from {package} import {os.path.splitext(src)[0]}\n'
  main_contents += main_exec

  _write_file(target, '__main__.py', main_contents)
  return py_make_binary
