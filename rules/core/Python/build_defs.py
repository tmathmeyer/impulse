def write_mainfile(contents):
  mainfile = '__main__.py'
  with open(mainfile, 'w+') as f:
    f.write(contents)
    return mainfile


def create_ziparchive(target, mainfile, srcs, name):
  import os
  def ensure_all_init_files(srcs):
    directories = set()
    for src in srcs:
      if src.endswith('.py'):
        directory = os.path.dirname(src)
        while directory:
          directories.add(directory)
          directory = os.path.dirname(directory)
      yield src

    for directory in directories:
      initfile = os.path.join(directory, '__init__.py')
      with open(initfile, 'w+') as f:
        f.write('# auto-generated\n')
      yield initfile

  files_to_zip = list(target.generated_by_dependencies(ruletype='py_library'))
  files_to_zip += srcs
  files_to_zip = list(ensure_all_init_files(files_to_zip))


  zipname = '{}/{}.zip'.format(target.build_path(), name)
  zipcmd = 'zip -r {} {} {} 2>&1 > /dev/null'.format(
    zipname, mainfile, ' '.join(files_to_zip))

  os.system(zipcmd)
  return zipname



def concat_crunchbang(exec_name, crunch_cmd, exec_file):
  import os
  with open(exec_name, 'w+') as f:
    f.write('#!{}\n'.format(crunch_cmd))
  os.system('cat {} >> {}'.format(exec_file, exec_name))
  os.system('chmod +x {}'.format(exec_name))
  return exec_name


@buildrule
def py_library(target, name, srcs, **kwargs):
  for src in srcs:
    target.track(src, I=True, O=True)


@using(create_ziparchive, concat_crunchbang, write_mainfile)
@buildrule
def py_binary(target, name, **kwargs):

  # Track any files that might only be in this build rule's srcs
  for src in kwargs.get('srcs', []):
    target.track(src, I=True, O=False)

  # delete the previous binary, if it exists
  import os
  if os.path.exists(name):
    os.system('rm {}'.format(name))

  # write the binary file
  with target.writing_temp_files():
    main_fmt = 'from {package} import {name}\n{name}.main()\n'
    package = '.'.join(target.build_path().split('/'))
    mainfile = write_mainfile(main_fmt.format(package=package, name=name))
    srcfiles = list(target.get_full_src_files(kwargs.get('srcs', [])))
    zipname = create_ziparchive(target, mainfile, srcfiles, name)
    exec_name = concat_crunchbang(
      '{}/{}'.format(target.build_path(), name),
      '/usr/bin/env python3',
      zipname)
    target.copy_from_tmp(exec_name)


@depends_targets("//impulse/testing:unittest")
@using(create_ziparchive, concat_crunchbang, write_mainfile)
@buildrule
def py_test(target, name, srcs, **kwargs):

  # Track any files that might only be in this build rule's srcs
  for src in srcs:
    target.track(src, I=True, O=False)

  # delete the previous binary, if it exists
  import os
  if os.path.exists(name):
    os.system('rm {}'.format(name))

  # write the binary file
  with target.writing_temp_files():
    import_fmt = 'from {} import {}\n'
    main_exec = 'from impulse.testing import testmain\ntestmain.main()\n'
    main_contents = ''
    for src in srcs:
      main_contents += import_fmt.format(
        '.'.join(target.build_path().split('/')), os.path.splitext(src)[0])
    main_contents += main_exec

    mainfile = write_mainfile(main_contents)
    srcfiles = list(target.get_full_src_files(srcs))
    zipname = create_ziparchive(target, mainfile, srcfiles, name)

    exec_name = concat_crunchbang(
      '{}/{}'.format(target.build_path(), name),
      '/usr/bin/env python3',
      zipname)
    target.copy_from_tmp(exec_name)