
def py_make_binary(target, package_name, package_file, binary_location):
  def _get_exe(minversion):
    if not minversion:
      return 'python3'
    import sys
    if minversion[1] >= sys.version_info.minor:
      return f'python3.{minversion[1]}'

  binary_file = os.path.join(binary_location, package_name)
  minversion = target.GetPropagatedData('minversion')
  pyversion = _get_exe(minversion)

  try:
    target.Execute(f'which {pyversion}')
  except:
    target.FatalError(f'Minimum python version {pyversion} not found')

  target.Execute(
    f'echo "#!/usr/bin/env {pyversion}\n" > {binary_file}',
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


def _version_check(target, kwargs):
  def _parse_version(vstr):
    if vstr is None:
      return None
    splitz = vstr.split('.')
    splitz += (['0'] * (3 - len(splitz)))
    return [int(x) for x in splitz]

  def _lt(a, b):
    assert a is not None and b is not None
    assert len(a) == 3 and len(b) == 3
    for (aa, bb) in zip(a, b):
      if aa < bb:
        return True
      if aa > bb:
        return False
    return False

  def _noversion(x):
    return x is None or len(x) != 3

  def _version_min(a, b):
    if _noversion(a) and _noversion(b):
      return None
    elif _noversion(a):
      return b
    elif _noversion(b):
      return a
    elif _lt(a, b):
      return a
    return b

  def _version_max(a, b):
    if _noversion(a) and _noversion(b):
      return None
    elif _noversion(a):
      return b
    elif _noversion(b):
      return a
    elif _lt(a, b):
      return b
    return a

  minversion = _parse_version(kwargs.get('minversion', None))
  maxversion = _parse_version(kwargs.get('maxversion', None))
  for deplib in target.Dependencies(package_ruletype='py_library'):
    minversion = _version_max(minversion, deplib.GetPropagatedData('minversion'))
    maxversion = _version_min(maxversion, deplib.GetPropagatedData('maxversion'))

  if not _noversion(minversion) and not _noversion(maxversion):
    if _lt(maxversion < minversion):
      target.ExecutionFailed(
        'Minimum package version is greater than maximum package version')

  if minversion is not None:
    for decimal in minversion:
      target.PropagateData('minversion', decimal)
  if maxversion is not None:
    for decimal in maxversion:
      target.PropagateData('maxversion', decimal)
  return minversion, maxversion


@using(_add_files, _write_file, _get_recursive_pips, _version_check)
@buildrule
def py_library(target, name, srcs, **kwargs):
  target.SetTags('py_library')
  _add_files(target, srcs + kwargs.get('data', []))
  for pip in _get_recursive_pips(target, kwargs):
    target.PropagateData('pips', pip)

  _version_check(target, kwargs)

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
       _get_pip_metadata, _get_recursive_pips, _version_check)
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

  _version_check(target, kwargs)

  # Converter from pkg to binary
  return py_make_binary


@depends_targets("//impulse/testing:unittest")
@using(_add_files, _write_file, py_make_binary, _version_check)
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
  _version_check(target, kwargs)
  return py_make_binary
