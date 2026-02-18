from impulse.types.stubs import buildrule
from impulse.types.stubs import depends_targets
from impulse.types.stubs import using
from impulse.types.stubs import os
from impulse.types.stubs import Any


def py_make_binary(target, package_name, package_file, binary_location):
  def _get_exe(minversion):
    if not minversion:
      return 'python3'
    import sys
    if minversion[1] <= sys.version_info.minor:
      return f'python3.{sys.version_info.minor}'
    target.FatalError(f'Requires Minimum version: {minversion}, system version is {sys.version_info}')

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
      pwd = os.getcwd()
      target.ExecutionFailed(f'CHECKFILE {added_file}', f'file does not exist in {pwd}')
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
  my_python_packages = set(kwargs.get('python_packages', []))
  for dep in target.Dependencies(tags=Any('py_library', 'py_binary')):
    my_python_packages.update(set(dep.GetPropagatedData('python_packages')))
  return list(my_python_packages)


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
    target.PropagateData('python_packages', pip)

  _version_check(target, kwargs)

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)


@buildrule
def python_package_install(target, name, **kwargs):
  target.SetTags('py_library')
  if not os.path.exists('__packagelist__'):
    return

  with open('__packagelist__', 'r') as f:
    packages = f.readlines()

  if not packages:
    return

  packages = [p.strip() for p in packages]

  target.Execute('which uv')
  import sys
  version = f'{sys.version_info.major}.{sys.version_info.minor}'
  target.Execute(f'uv venv -q --python {version}')
  flags = '' if target.IsDebug() else '-q'
  for package in packages:
    target.Execute(f'uv pip install {package} {flags}')
  package_dir = f'.venv/lib/python{version}/site-packages'

  for library in os.listdir(package_dir):
    if library == '__pycache__':
      continue
    if library.endswith('.dist-info'):
      continue
    if library.endswith('.py'):
      target.AddFile(library)
    target.Execute(f'cp -r {package_dir}/{library} {library}')
    for dn, _, files in os.walk(library):
      init_file = os.path.join(dn, '__init__.py')
      if not os.path.exists(init_file):
        target.Execute(f'touch {init_file}')
        target.AddFile(init_file)
      if '__pycache__' not in dn:
        for file in files:
          target.AddFile(os.path.join(dn, file))


@buildrule
def python_package_list(target, name, **kwargs):
  my_python_packages = set(kwargs.get('python_packages', []))
  for dep in target.Dependencies(tags=Any('py_library', 'py_binary')):
    my_python_packages.update(set(dep.GetPropagatedData('python_packages')))
  with open('__packagelist__', 'w+') as f:
    for package in my_python_packages:
      f.write(f'{package}\n')
  target.AddFile('__packagelist__')


@buildrule
def python_main_target(target, name, srcs, **kwargs):
  target.SetTags('py_library')
  mainfile = name
  package = '.'.join(target.GetPackageDirectory().split('/'))
  if kwargs.get('mainfile', None) is not None:
    mainfile = kwargs.get('mainfile').rstrip('py').rstrip('.')
    if kwargs.get('mainpackage', None) is not None:
      package = kwargs.get('mainpackage')
  elif f'{name}.py' not in srcs:
    if len(srcs) == 1:
      mainfile = srcs[0].rstrip('py').rstrip('.')

  with open('__main__.py', 'w+') as f:
    f.write('\n'.join([
      f'from {package} import {mainfile}',
      f'import sys',
      f'sys.exit({mainfile}.main())']))
  target.AddFile('__main__.py')


@buildrule
def python_main_test_target(target, name, srcs, **kwargs):
  with open('__main__.py', 'w+') as f:
    target.SetTags('py_library')
    main_exec = 'from impulse.testing import testmain\ntestmain.main()\n'
    main_contents = ''

    relapath = target.package_target.GetDirectory().Relative().RelativeLocation()
    package = '.'.join(relapath.split('/'))

    for src in srcs:
      main_contents += f'from {package} import {os.path.splitext(src)[0]}\n'
    main_contents += main_exec
    f.write(main_contents)
  target.AddFile('__main__.py')


@depends_targets("//impulse/util:bintools")
@using(_add_files, _write_file, _get_tools_paths, py_make_binary, _version_check)
@buildrule
def py_internal_binary(target, name, **kwargs):
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

  _version_check(target, kwargs)

  # Converter from pkg to binary
  return py_make_binary


@depends_targets("//impulse/testing:unittest")
@using(_add_files, _write_file, py_make_binary, _version_check)
@buildrule
def py_internal_test(target, name, srcs, **kwargs):
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

  _version_check(target, kwargs)
  return py_make_binary


@buildmacro
def py_test(macro_env, name, **kwargs):
  package_list_name = f'{name}_package_list'
  package_install_name = f'{name}_package_install'
  package_mainfile_name = f'{name}_mainfile_build'

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'python_package_list',
    args = {
      'name': package_list_name,
      'deps': kwargs.get('deps', []),
      'python_packages': kwargs.get('python_packages', []),
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'python_package_install',
    args = {
      'name': package_install_name,
      'deps': [ f':{package_list_name}', ],
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'python_main_test_target',
    args = {
      'name': package_mainfile_name,
      'srcs': kwargs.get('srcs', []),
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'py_internal_test',
    args = {
      'name': name,
      'srcs': kwargs.get('srcs', []),
      'data': kwargs.get('data', []),
      'deps': kwargs.get('deps', []) + [
        f':{package_install_name}',
        f':{package_mainfile_name}',
      ],
    })


@buildmacro
def py_binary(macro_env, name, **kwargs):
  package_list_name = f'{name}_package_list'
  package_install_name = f'{name}_package_install'
  package_mainfile_name = f'{name}_mainfile_build'

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'python_package_list',
    args = {
      'name': package_list_name,
      'deps': kwargs.get('deps', []),
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'python_package_install',
    args = {
      'name': package_install_name,
      'deps': [ f':{package_list_name}', ],
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'python_main_target',
    args = {
      'name': package_mainfile_name,
      'srcs': kwargs.get('srcs', []),
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'py_internal_binary',
    args = {
      'name': name,
      'srcs': kwargs.get('srcs', []),
      'data': kwargs.get('data', []),
      'deps': kwargs.get('deps', []) + [
        f':{package_install_name}',
        f':{package_mainfile_name}',
      ],
    })