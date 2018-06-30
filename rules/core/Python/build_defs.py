@buildrule
def py_library(name, srcs, **args):
  def convert_src_to_init(src):
    filename = src.split('.')
    assert len(filename) == 2, 'python files may not contain .\'s'
    return filename[0] + '/__init__.py'

  depends(inputs=srcs, outputs= [name+'.zip'] + [
    convert_src_to_init(s) for s in srcs
  ])

  zip_file, *init_files = build_outputs()
  root_init = directory().split('/')[0] + '/__init__.py'
  add_output(root_init)
  command('touch {}'.format(root_init))

  for s, o in zip(srcs, init_files):
    command('cp {} {}'.format(local_file(s), o))

  tmp_output = zip_file+'.part'
  exclude = r'-x \*.zip \*.tmp \*.bin'
  command('zip -r {} {} {} {}'.format(tmp_output, root_init, directory(), exclude))

  libs = dependencies.filter(ruletype='py_library')
  deplibs = ' '.join(map(compose(first, build_outputs), libs))
  command('zipmerge {} {} {}'.format(zip_file, tmp_output, deplibs))
  command('rm {}'.format(tmp_output))



@buildrule
def py_binary(name, srcs, **args):
  def convert_src_to_init(src):
    filename = src.split('.')
    assert len(filename) == 2, 'python files may not contain .\'s'
    return filename[0] + '/__init__.py'

  depends(inputs=srcs, outputs=[
    name+'.bin',
    name+'.tmp.zip',
    name+'.zip',
    convert_src_to_init(srcs[0])
  ])
  binary, tmp_output, zip_bin, initfile = build_outputs()
  mainfile = '__main__.py'

  command('cp {} {}'.format(local_file(srcs[0]), initfile))
  package = '.'.join(directory().split('/'))
  write_file(mainfile, 'from {} import {}'.format(package, name));
  write_file(mainfile, '{}.main()'.format(name));
  exclude = r'-x \*.zip \*.tmp \*.bin'
  command('zip -r {} {} {} {}'.format(tmp_output, mainfile, directory(), exclude))

  libs = dependencies.filter(ruletype='py_library')
  deplibs = ' '.join(map(compose(first, build_outputs), libs))

  command('zipmerge {} {} {}'.format(zip_bin, tmp_output, deplibs))
  write_file(binary, '#!/usr/bin/env python')
  append_file(binary, zip_bin)
  command('chmod +x %s' % binary)