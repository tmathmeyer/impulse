@buildrule
def py_library(target, name, srcs, **kwargs):
  import os
  directories = set()
  for src in srcs:
    directory = os.path.join(
      target.directory(), os.path.dirname(src))
    while directory:
      directories.add(directory)
      directory = os.path.dirname(directory)
    target.track_output_file(src)
  for directory in directories:
    initfile = os.path.join(directory, '__init__.py')
    with target.write_file(initfile, outside_pkg=True) as f:
      f.write('# auto-generated\n')

@buildrule
def py_binary(target, name, **kwargs):
  # just like py-library
  import os
  directories = set()
  for src in kwargs.get('srcs', []):
    directory = os.path.join(
      target.directory(), os.path.dirname(src))
    while directory:
      directories.add(directory)
      directory = os.path.dirname(directory)
    target.track_output_file(src)
  for directory in directories:
    initfile = os.path.join(directory, '__init__.py')
    with target.write_file(initfile, outside_pkg=True) as f:
      f.write('# auto-generated\n')

  # Generate a mainfile
  mainfile = '__main__.py'
  package = '.'.join(target.directory().split('/'))
  with target.write_file(mainfile, outside_pkg=True) as f:
    f.write('from {} import {}\n'.format(package, name))
    f.write('{}.main()\n'.format(name))

  # write the zip file
  zipname = target.pkg_file(name + '.zip')
  zip = target.run_pkgroot('zip')
  zip(zipname, *list(target.get_output_files()))

  # create executable header
  with target.write_file(name) as f:
    f.write('#!/usr/bin/env python3\n')

  # cat zip file into the executable
  exename = target.pkg_file(name)
  target.synchronize()
  os.system('cat {} >> {}'.format(zipname, exename))
  target.chmod('+x', exename)
  target.track_output_file(name)

