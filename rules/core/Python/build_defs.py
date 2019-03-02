def py_write_mainfile(target, contents):
  mainfile = os.path.join(target.buildroot[0], '__main__.py')
  with open(mainfile, 'w+') as f:
    f.write(contents)
  target.DependFile('__main__.py')

def py_track_files(target, srcs):
  for src in srcs:
    target.AddFile(src, False)
  for deplib in target.Dependencies(package_ruletype='py_library'):
    for f in deplib.IncludedFiles():
      target.DependFile(f)

def py_create_inits(target):
  def makefile(path):
    if not os.path.exists(path):
      with open(path, 'w+') as f:
        f.write('# auto-generated\n')
    target.DependFile(path[len(target.buildroot[0])+1:])

  d = target.buildroot[1]
  while d:
    makefile(os.path.join(target.buildroot[0], d, '__init__.py'))
    d = os.path.dirname(d)

def py_make_binary(package_name, package_file, binary_location):
  binary_file = os.path.join(binary_location, package_name)
  os.system('echo "#!/usr/bin/env python3\n" >> {}'.format(binary_file))
  os.system('cat {} >> {}'.format(package_file, binary_file))
  os.system('chmod +x {}'.format(binary_file))

@using(py_track_files, py_create_inits)
@buildrule
def py_library(target, name, srcs, **kwargs):
  py_track_files(target, srcs)
  py_create_inits(target)


@using(py_track_files, py_create_inits, py_write_mainfile, py_make_binary)
@buildrule
def py_binary(target, name, **kwargs):
  py_create_inits(target)
  py_track_files(target, kwargs.get('srcs', []))
  main_fmt = 'from {package} import {name}\n{name}.main()\n'
  package = '.'.join(target.package_target.GetPackagePathDirOnly().split('/'))
  py_write_mainfile(target, main_fmt.format(package=package, name=name))
  return py_make_binary

@depends_targets("//impulse/testing:unittest")
@using(py_track_files, py_create_inits, py_write_mainfile, py_make_binary)
@buildrule
def py_test(target, name, srcs, **kwargs):
  py_create_inits(target)
  py_track_files(target, srcs)

  import_fmt = 'from {} import {}\n'
  main_exec = 'from impulse.testing import testmain\ntestmain.main()\n'
  main_contents = ''
  package = '.'.join(target.package_target.GetPackagePathDirOnly().split('/'))
  import os
  for src in srcs:
    main_contents += import_fmt.format(package, os.path.splitext(src)[0])
  main_contents += main_exec

  py_write_mainfile(target, main_contents)
  return py_make_binary
