
@buildrule
def c_header(target, name, srcs, **kwargs):
  for src in srcs:
    target.track(src, I=True, O=True)


def _compile(compiler, name, include, srcs, objects, flags, std):
  import os
  cmd_fmt = '{compiler} -o {name} {include} {srcs} {objects} {flags} -std={std}'
  command = cmd_fmt.format(**locals())
  os.system(command)
  return name

def _get_include_dirs(target, includes):
  includes.append(target.get_true_root())
  with_include = ['-I{}'.format(d) for d in includes]
  return ' '.join(with_include)

@using(_compile, _get_include_dirs)
@buildrule
def c_object(target, name, srcs, **kwargs):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='c_object'))
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-c'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'gcc'),
    name=name+'.o',
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(srcs),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=kwargs.get('std', 'c11'))
  target.track(binary, O=True)

@using(_compile, _get_include_dirs)
@buildrule
def c_binary(target, name, **kwargs):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='c_object'))
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'gcc'),
    name=name,
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(kwargs.get('srcs', [])),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=kwargs.get('std', 'c11'))
  target.track(binary, O=True)

@using(_compile, _get_include_dirs)
@buildrule
def cpp_object(target, name, srcs, **kwargs):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='cpp_object'))
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-c'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=name+'.o',
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(srcs),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.track(binary, O=True)

@using(_compile, _get_include_dirs)
@buildrule
def cpp_binary(target, name, **kwargs):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='cpp_object'))
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall'])
  binary = _compile(
    compiler=kwargs.get('compiler', 'g++'),
    name=name,
    include=_get_include_dirs(target, kwargs.get('include_dirs', [])),
    srcs=' '.join(kwargs.get('srcs', [])),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=kwargs.get('std', 'c++17'))
  target.track(binary, O=True)


@depends_targets("//googletest:googletest")
@using(_compile, _get_include_dirs)
@buildrule
def cpp_test(target, name, **kwargs):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='cpp_object'))

  # We need the -lpthread for gtest
  flags = set(kwargs.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-lpthread'])

  # make sure the src files are tracked when we jump out to the
  # global export directory
  srcfiles = list(target.get_full_src_files(kwargs.get('srcs', [])))
  for src in kwargs.get('srcs', []):
    target.track(src, I=True)

  include_dirs = kwargs.get('include_dirs', []) + [
    'googletest/googletest/include',
    'googletest/googletest',
  ]

  with target.writing_temp_files():
    binary = _compile(
      compiler=kwargs.get('compiler', 'g++'),
      name=os.path.join(target.build_path(), name),
      include=_get_include_dirs(target, include_dirs),
      srcs=' '.join(srcfiles),
      objects=object_dependencies,
      flags=' '.join(flags),
      std=kwargs.get('std', 'c++17'))
    target.copy_from_tmp(binary)