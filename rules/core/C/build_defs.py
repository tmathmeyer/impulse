@buildrule
def c_headers(name, srcs, **args):
  depends(inputs=srcs, outputs=srcs)
  for src in srcs:
    copy(local_file(src))

@buildrule
def c_object(name, srcs, **args):
  depends(inputs=srcs, outputs=[name+'.o'])

  object_dependencies = dependencies.filter(ruletype='c_object')
  objects = ' '.join(sum(map(build_outputs, object_dependencies), []))

  sources = ' '.join(local_file(src) for src in srcs)

  cmd = 'gcc -o %s -I%s -c %s %s -std=c11 -Wextra -Wall' % (
    build_outputs()[0], PWD, sources, objects)

  for flag in args.get('flags', []):
    cmd += (' ' + flag)
  command(cmd)

@buildrule
def c_binary(name, **args):
  srcs = args.get('srcs', [])
  depends(inputs=srcs, outputs=[name])

  objects = ' '.join(sum(map(build_outputs, dependencies), []))
  sources = ' '.join(local_file(src) for src in srcs)

  cmd = 'gcc -o %s -I%s %s %s -std=c11 -Wextra -Wall' % (
    build_outputs()[0], PWD, sources, objects)

  for flag in args.get('flags', []):
    cmd += (' ' + flag)

  command(cmd)

@buildrule_depends(c_object)
def c_object_nostd(name, srcs, **args):
  flags = args.setdefault('flags', [])
  flags += [
    '-nostdinc', '-fno-stack-protector', '-m64', '-g'
  ]
  c_object(name, srcs, **args)