
import os

@buildrule
def zip_files(name, srcs, **_):
  command('zip {} {}'.format(name, ' '.join(srcs)))

@buildrule
def merge_zips(name, *zips, **_):
  command('zipmerge {} {}'.format(name, ' '.join(zips)))

@buildrule_depends(zip_files, merge_zips)
def py_library(name, srcs, **args):
  depends(inputs=srcs, outputs=[name + '.zip', '__init__.py'] + srcs)

  zipfile, initfile, *outputs = build_outputs()
  bundle_files = set(outputs)
  bundle_files.add(initfile)

  command('touch {}'.format(initfile))

  uniq_dirs = set(os.path.dirname(n) for n in outputs if os.path.dirname(n))
  for D in uniq_dirs:
    init_file = '{}/__init__.py'.format(D)
    bundle_files.add(init_file)
    command('mkdir -p {}'.format(D))
    command('touch {}'.format(init_file))

  for I, O in zip(srcs, outputs):
    command('cp {} {}'.format(local_file(I), O))

  tmp_file = zipfile+'.tmp'
  zip_files(tmp_file, bundle_files)

  libs = dependencies.filter(ruletype='py_library')
  depzips = map(compose(first, build_outputs), libs)
  merge_zips(zipfile, tmp_file, *depzips)


@buildrule_depends(zip_files, merge_zips)
def py_binary(name, srcs, **args):
  depends(inputs=srcs, outputs=[name, name+'.zip'] + srcs)
  mainfile = '__main__.py'

  finalexe, zipfile, *srcouts = build_outputs()
  bundle_files = set(srcouts)
  bundle_files.add(mainfile)

  uniq_dirs = set(os.path.dirname(n) for n in srcouts if os.path.dirname(n))

  for D in uniq_dirs:
    init_file = '{}/__init__.py'.format(D)
    bundle_files.add(init_file)
    command('mkdir -p {}'.format(D))
    command('touch {}'.format(init_file))

  for I, O in zip(srcs, srcouts):
    command('cp {} {}'.format(local_file(I), O))

  package = '.'.join(directory().split('/'))
  write_file(mainfile, 'from {} import {}'.format(package, name))
  write_file(mainfile, '{}.main()'.format(name))

  tmp_file = zipfile+'.tmp'
  zip_files(tmp_file, bundle_files)

  libs = dependencies.filter(ruletype='py_library')
  depzips = map(compose(first, build_outputs), libs)
  merge_zips(zipfile, tmp_file, *depzips)

  write_file(finalexe, '#!/usr/bin/env python3')
  append_file(finalexe, zipfile)
  command('chmod +x {}'.format(finalexe))
  command('rm {}'.format(mainfile))