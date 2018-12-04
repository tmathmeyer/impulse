@buildrule
def c_header(target, name, srcs, **args):
  for src in srcs:
    target.track(src, I=True, O=True)

@buildrule
def c_object(target, name, srcs, **args):
  import os
  object_dependencies = list(target.generated_by_dependencies(
    ruletype='c_object'))
  cmd_fmt = 'gcc -o {bin} -I{incl} -c {srcs} {objs} {flags} {d_flags}'
  cmd = cmd_fmt.format(**{
    'bin': name + '.o',
    'incl': target.get_true_root(),
    'srcs': ' '.join(srcs),
    'objs': ' '.join(object_dependencies),
    'flags': ' '.join(args.get('flags', [])),
    'd_flags': '-std=c11 -Wextra -Wall',
  })
  os.system(cmd)
  print(cmd)
  target.track(name + '.o', O=True)

@buildrule
def c_binary(target, name, **args):
  import os
  object_dependencies = list(target.generated_by_dependencies(
    ruletype='c_object'))
  cmd_fmt = 'gcc -o {bin} -I{incl} {srcs} {objs} {flags} {d_flags}'
  os.system(cmd_fmt.format(**{
    'bin': name,
    'incl': target.get_true_root(),
    'srcs': ' '.join(args.get('srcs', [])),
    'objs': ' '.join(object_dependencies),
    'flags': ' '.join(args.get('flags', [])),
    'd_flags': '-std=c11 -Wextra -Wall',
  }))
  target.track(name, O=True)

"""
@buildrule_depends(c_object)
def c_object_nostd(name, srcs, **args):
  flags = args.setdefault('flags', [])
  flags += [
    '-nostdinc', '-fno-stack-protector', '-m64', '-g'
  ]
  c_object(name, srcs, **args)
"""