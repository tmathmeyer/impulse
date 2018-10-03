@buildrule
def cpp_header(name, srcs, **args):
  depends(inputs=srcs, outputs=srcs)
  for src in srcs:
    copy(local_file(src), dirname(src))

@buildrule
def cpp_object(name, srcs, **args):
  depends(inputs=srcs, outputs=[name+'.o'])

  object_dependencies = dependencies.filter(ruletype='cpp_object')

  command('g++ -o {} {} -c {} {} --std=c++17 -Wextra -Wall {}'.format(
    build_outputs()[0],
    ' '.join(['-I'+os.path.join(PWD, a) for a in args.get('linkdirs', [])]),
    ' '.join(local_file(src) for src in srcs),
    ' '.join(sum(map(build_outputs, object_dependencies), [])),
    ' '.join(args.get('flags', []))))



@buildrule
def cpp_binary(name, **args):
  srcs = args.get('srcs', [])
  depends(inputs=srcs, outputs=[name])

  objects = ' '.join(sum(map(build_outputs, dependencies), []))
  sources = ' '.join(local_file(src) for src in srcs)

  object_dependencies = dependencies.filter(ruletype='cpp_object')

  command('g++ -o {} {} {} {} --std=c++17 -Wextra -Wall {}'.format(
    build_outputs()[0],
    ' '.join(['-I'+os.path.join(PWD, a) for a in args.get('linkdirs', [])]),
    ' '.join(local_file(src) for src in srcs),
    ' '.join(sum(map(build_outputs, object_dependencies), [])),
    ' '.join(args.get('flags', []))))