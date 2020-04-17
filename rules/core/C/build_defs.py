def _compile(target, compiler, name, include, srcs, objs, flags, std):
  import subprocess
  if std:
    cmd_fmt = '{compiler} -o {name} {include} {srcs} {objs} {flags} -std={std}'
  else:
    cmd_fmt = '{compiler} -o {name} {include} {srcs} {objs} {flags}'
  command = cmd_fmt.format(**locals())
  result = subprocess.run(command,
    encoding='utf-8', shell=True,
    stderr=subprocess.PIPE, stdout=subprocess.PIPE)
  if result.returncode:
    target.ExecutionFailed(command, result.stderr)
  return name


def _get_include_dirs(target, includes):
  includes.append(target.GetPackageDirectory())
  return '-I. ' + ' '.join('-I{}'.format(d)
   for d in includes)


def _get_objects(target, tags):  # cpp_library cpp_object
  for tag in tags:
    for deplib in target.Dependencies(tags=tag):
      for obj in deplib.IncludedFiles():
        yield obj


def _get_src_files(target, srcs):
  for src in srcs:
    yield os.path.join(target.GetPackageDirectory(), src)


@using(_get_src_files)
@buildrule
def c_header(target, name, srcs, **kwargs):
  target.SetTags('c_header')
  for src in _get_src_files(target, srcs):
    target.AddFile(src)
  for deplib in target.Dependencies(tags='c_header'):
    for f in deplib.IncludedFiles():
      target.AddFile(f)

@using(_get_src_files)
@buildrule
def cpp_header(target, name, srcs, **kwargs):
  target.SetTags('cpp_header')
  for src in _get_src_files(target, srcs):
    target.AddFile(src)
  for deplib in target.Dependencies(tags='cpp_header'):
    for f in deplib.IncludedFiles():
      target.AddFile(f)


@using(_compile, _get_include_dirs, _get_objects, _get_src_files)
@buildrule
def cpp_object(target, name, srcs, **kwargs):
  compiler = kwargs.get('compiler', 'g++')
  lang = 'c' if compiler == 'gcc' else 'cpp'
  target.SetTags(f'{lang}_input')

  objects = list(_get_objects(target, [f'{lang}_input']))
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wall', '-c', '-fdiagnostics-color=always'])
  binary = _compile(
    target=target,
    compiler=compiler,
    name=os.path.join(target.GetPackageDirectory(), name+'.o'),
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(_get_src_files(target, srcs)),
    objs=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))

  target.AddFile(binary)

@using(_compile, _get_objects)
@buildrule
def cpp_library(target, name, deps, **kwargs):
  target.SetTags('c_input', 'cpp_input')
  objects = list(_get_objects(target, ['c_input', 'cpp_input']))
  flags = set(kwargs.get('flags', []))
  flags.update(['-r'])
  binary = _compile(
    target=target,
    compiler=kwargs.get('compiler', 'ld'),
    name=os.path.join(target.GetPackageDirectory(), name+'.o'),
    objs=' '.join(objects),
    flags=' '.join(flags),
    std='',
    include='',
    srcs='')

  target.AddFile(binary)


@using(_compile, _get_include_dirs, _get_objects, _get_src_files)
@buildrule
def cpp_binary(target, name, **kwargs):
  compiler = kwargs.get('compiler', 'g++')
  lang = 'c' if compiler == 'gcc' else 'cpp'
  target.SetTags('exe')

  objects = _get_objects(target, [f'{lang}_input'])
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wall', '-fdiagnostics-color=always'])
  binary = _compile(
    target=target,
    compiler=compiler,
    name=os.path.join(target.GetPackageDirectory(), name),
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(_get_src_files(target, kwargs.get('srcs', []))),
    objs=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.AddFile(binary)

  def export_binary(package_name, package_file, binary_location):
    package_exe = os.path.join(target.GetPackageDirectory(), package_name)
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(package_exe, binary_file))

  return export_binary


@depends_targets("//googletest:googletest", "//googletest:googletest_headers")
@using(_compile, _get_include_dirs, _get_objects, _get_src_files)
@buildrule
def cpp_test(target, name, **kwargs):
  target.SetTags('exe', 'test')
  objects = _get_objects(target, ['cpp_input'])
  # We need the -lpthread for gtest
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-lpthread', '-fdiagnostics-color=always'])

  include_dirs = kwargs.get('include_dirs', []) + [
    'googletest/googletest/include',
    'googletest/googletest',
  ]

  binary = _compile(
    target=target,
    compiler=kwargs.get('compiler', 'g++'),
    name=os.path.join(target.GetPackageDirectory(), name),
    include=_get_include_dirs(target, include_dirs),
    srcs=' '.join(_get_src_files(target, kwargs.get('srcs', []))),
    objs=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.AddFile(binary)

  def export_binary(package_name, package_file, binary_location):
    package_exe = os.path.join(target.GetPackageDirectory(), package_name)
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(package_exe, binary_file))

  return export_binary