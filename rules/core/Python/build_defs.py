
import os

@buildrule
def py_library(name, srcs, **args):
  depends(inputs=srcs, outputs=['__init__.py'] + srcs)
  initfile, *outputs = build_outputs()

  init_dir_names = set()
  for name in outputs:
    if os.path.dirname(name):
      init_dir_names.add(os.path.dirname(name))

  for D in init_dir_names:
    command('mkdir -p {}'.format(D))
    command('touch {}/__init__.py'.format(D))

  command('touch {}'.format(initfile))

  for I, O in zip(srcs, outputs):
    command('cp {} {}'.format(local_file(I), O))

@buildrule
def py_binary(name, srcs, **args):
  depends(inputs=srcs, outputs=[name, name+'.zip'] + srcs)
  finalexe, finalzip, *srcouts = build_outputs()
  for I, O in zip(srcs, srcouts):
    command('cp {} {}'.format(local_file(I), O))

  mainfile = '__main__.py'
  package = '.'.join(directory().split('/'))
  write_file(mainfile, 'from {} import {}'.format(package, name))
  write_file(mainfile, '{}.main()'.format(name))

  libs = dependencies.filter(ruletype='py_library')
  deplibs = ' '.join(map(compose(os.path.dirname, first, build_outputs), libs))

  command('zip -r {} __main__.py {}'.format(finalzip, deplibs))

  write_file(finalexe, '#!/usr/bin/env python3')
  append_file(finalexe, finalzip)
  command('chmod +x {}'.format(finalexe))
  command('rm {}'.format(mainfile))
