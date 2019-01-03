
def make_initfiles_from_srcs(target, srcs):
  import os
  directories = set([''])
  for src in srcs:
    directory = os.path.dirname(src)
    while directory:
      directories.add(directory)
      directory = os.path.dirname(directory)
    target.track(src, I=True, O=True)

  for directory in directories:
    initfile = os.path.join(directory, '__init__.py')
    with open(initfile, 'w+') as f:
      f.write('# auto-generated\n')
    target.track(initfile, O=True)

@using(make_initfiles_from_srcs)
@buildrule
def py_library(target, name, srcs, **kwargs):
  make_initfiles_from_srcs(target, srcs)

@using(make_initfiles_from_srcs)
@buildrule
def py_binary(target, name, **kwargs):
  make_initfiles_from_srcs(target, kwargs.get('srcs', []))

  if os.path.exists(name):
    os.system('rm {}'.format(name))

  with target.writing_temp_files():
    package = '.'.join(target.build_path().split('/'))
    mainfile = '__main__.py'
    with open(mainfile, 'w+') as f:
      f.write('from {} import {}\n'.format(package, name))
      f.write('{}.main()\n'.format(name))

    zip_files = list(target.generated_by_dependencies(ruletype='py_library'))
    my_files = list(target.generated_by_dependencies(ruletype='py_binary'))
    zipname = '{}/{}.zip'.format(target.build_path(), name)
    os.system('zip -r {} {} {} 2>&1 > /dev/null'.format(zipname,
      mainfile, ' '.join(zip_files + my_files)))

    executable_name = '{}/{}'.format(target.build_path(), name)
    with open(executable_name, 'w+') as f:
      f.write('#!/usr/bin/env python3\n')
    os.system('cat {} >> {}'.format(zipname, executable_name))
    os.system('chmod +x {}'.format(executable_name))
    target.copy_from_tmp(executable_name)