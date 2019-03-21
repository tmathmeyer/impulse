def _compile(compiler, name, include, srcs, objects, flags, std):
  import os
  cmd_fmt = '{compiler} -o {name} {include} {srcs} {objects} {flags} -std={std}'
  command = cmd_fmt.format(**locals())
  os.system(command)
  return name


def _get_include_dirs(target, includes):
  includes.append(target.GetPackageDirectory())
  return ' '.join('-I{}'.format(d)
   for d in includes)


def _get_objects(target):
  for deplib in target.Dependencies(package_ruletype='cpp_object'):
    for obj in deplib.IncludedFiles():
      yield obj


def _get_src_files(target, srcs):
  for src in srcs:
    yield os.path.join(target.GetPackageDirectory(), src)


@using(_get_src_files)
@buildrule
def c_header(target, name, srcs, **kwargs):
  for src in _get_src_files(target, srcs):
    target.AddFile(src)


@using(_compile, _get_include_dirs, _get_objects, _get_src_files)
@buildrule
def cpp_object(target, name, srcs, **kwargs):
  objects = list(_get_objects(target))
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wall', '-c'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=os.path.join(target.GetPackageDirectory(), name+'.o'),
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(_get_src_files(target, srcs)),
    objects=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))

  target.AddFile(binary)


@using(_compile, _get_include_dirs, _get_objects, _get_src_files)
@buildrule
def cpp_binary(target, name, **kwargs):
  objects = _get_objects(target)
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wall'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=os.path.join(target.GetPackageDirectory(), name),
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(_get_src_files(target, kwargs.get('srcs', []))),
    objects=' '.join(objects),
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
  objects = _get_objects(target)
  # We need the -lpthread for gtest
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-lpthread'])

  include_dirs = kwargs.get('include_dirs', []) + [
    'googletest/googletest/include',
    'googletest/googletest',
  ]

  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=os.path.join(target.GetPackageDirectory(), name),
    include=_get_include_dirs(target, include_dirs),
    srcs=' '.join(_get_src_files(target, kwargs.get('srcs', []))),
    objects=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.AddFile(binary)

  def export_binary(package_name, package_file, binary_location):
    package_exe = os.path.join(target.GetPackageDirectory(), package_name)
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(package_exe, binary_file))

  return export_binary