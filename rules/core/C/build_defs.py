def _compile(compiler, name, include, srcs, objects, flags, std):
  import os
  cmd_fmt = '{compiler} -o {name} {include} {srcs} {objects} {flags} -std={std}'
  command = cmd_fmt.format(**locals())
  os.system(command)
  return name

def _get_include_dirs(target, includes):
  includes.append(target.buildroot[0])
  with_include = ['-I{}'.format(d) for d in includes]
  return ' '.join(with_include)

def _get_objects(target):
  levels = len(target.buildroot[1].split('/'))
  prepend = os.path.join(*(['..'] * levels))
  objects = []
  for deplib in target.Dependencies(package_ruletype='cpp_object'):
    for f in deplib.IncludedFiles():
      objects.append(os.path.join(prepend, f))
  return objects

@buildrule
def c_header(target, name, srcs, **kwargs):
  for src in srcs:
    target.AddFile(src, False)

@using(_compile, _get_include_dirs, _get_objects)
@buildrule
def cpp_object(target, name, srcs, **kwargs):
  objects = _get_objects(target)

  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-c'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=name+'.o',
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(srcs),
    objects=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.AddFile(binary, True)
  for src in srcs:
    target.AddFileInputOnly(src)

@using(_compile, _get_include_dirs, _get_objects)
@buildrule
def cpp_binary(target, name, **kwargs):
  objects = _get_objects(target)
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=name,
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(kwargs.get('srcs', [])),
    objects=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.AddFile(binary, True)
  for src in kwargs.get('srcs', []):
    target.AddFileInputOnly(src)

  def export_binary(package_name, package_file, binary_location):
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(os.path.join(target.buildroot[1], binary),
      binary_file))

  return export_binary


@depends_targets("//googletest:googletest")
@using(_compile, _get_include_dirs, _get_objects)
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
    name=name,
    include=_get_include_dirs(target, include_dirs),
    srcs=' '.join(kwargs.get('srcs', [])),
    objects=' '.join(objects),
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.AddFile(binary, True)
  for src in kwargs.get('srcs', []):
    target.AddFileInputOnly(src)

  def export_binary(package_name, package_file, binary_location):
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(os.path.join(target.buildroot[1], binary),
      binary_file))

  return export_binary