
@buildrule
def c_header(target, name, srcs, **args):
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
def c_object(target, name, srcs, **args):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='c_object'))
  flags = set(args.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-c'])
  binary = _compile(
    compiler=args.get('compiler', 'gcc'),
    name=name+'.o',
    include=_get_include_dirs(target, args.get('include_dirs', [])),
    srcs=' '.join(srcs),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=args.get('std', 'c11'))
  target.track(binary, O=True)

@using(_compile, _get_include_dirs)
@buildrule
def c_binary(target, name, **args):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='c_object'))
  flags = set(args.get('flags', []))
  flags.update(['-Wextra', '-Wall'])
  binary = _compile(
    compiler=args.get('compiler', 'gcc'),
    name=name,
    include=_get_include_dirs(target, args.get('include_dirs', [])),
    srcs=' '.join(args.get('srcs', [])),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=args.get('std', 'c11'))
  target.track(binary, O=True)

@using(_compile, _get_include_dirs)
@buildrule
def cpp_object(target, name, srcs, **args):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='cpp_object'))
  flags = set(args.get('flags', []))
  flags.update(['-Wextra', '-Wall', '-c'])
  binary = _compile(
    compiler=args.get('compiler', 'g++'),
    name=name+'.o',
    include=_get_include_dirs(target, args.get('include_dirs', [])),
    srcs=' '.join(srcs),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=args.get('std', 'c++17'))
  target.track(binary, O=True)

@using(_compile, _get_include_dirs)
@buildrule
def cpp_binary(target, name, **args):
  object_dependencies = ' '.join(
    target.generated_by_dependencies(ruletype='cpp_object'))
  flags = set(args.get('flags', []))
  flags.update(['-Wextra', '-Wall'])
  binary = _compile(
    compiler=args.get('compiler', 'g++'),
    name=name,
    include=_get_include_dirs(target, args.get('include_dirs', [])),
    srcs=' '.join(args.get('srcs', [])),
    objects=object_dependencies,
    flags=' '.join(flags),
    std=args.get('std', 'c++17'))
  target.track(binary, O=True)
