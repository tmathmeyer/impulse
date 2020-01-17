
def _get_src_files(target, srcs):
  for src in srcs:
    yield os.path.join(target.GetPackageDirectory(), src)


def _write_importcfg(gopkg, stdinc, deps, filename):
  with open(filename, 'w+') as f:
    f.write(f'packagefile runtime={gopkg}/linux_amd64/runtime.a\n')
    for stdlib in stdinc:
      f.write(f'packagefile {stdlib}={gopkg}/linux_amd64/{stdlib}.a\n')
    for dep in deps:
      path, _ = dep.package_target.split(':')
      path = path[2:]
      f.write(f'packagefile {path}={path}/_pkg_.a\n')
      for included_file in dep.IncludedFiles():
        if included_file.endswith('importcfg'):
          with open(included_file, 'r') as cat:
            f.write(cat.read())

  import os
  os.system(f'cat {filename} | sort | uniq >> tmp && mv tmp {filename}')


def _build_go_archive(target, write_fn, name, srcs, **kwargs):
  import os
  import subprocess

  # Create all the needed files
  gopkg = f'/usr/lib/go/pkg'
  go_compiler = f'{gopkg}/tool/linux_amd64/compile'
  go_output = os.path.join(target.GetPackageDirectory(), '_pkg_.a')
  importcfg = os.path.join(target.GetPackageDirectory(), 'importcfg')
  go_input_files = ' '.join(srcs)

  dep_packages = list(target.Dependencies(package_ruletype='go_pkg'))
  for pkg in dep_packages:
    for f in pkg.IncludedFiles():
      if f.endswith('_pkg_.a'):
        target.AddFile(f)

  go_cmd = (f'{go_compiler} '
            f'-o {go_output} '
            f'-trimpath . '
            f'-D ./ '
            f'-importcfg {importcfg} '
            f'-pack -c=2 '
            f'{go_input_files} ')
  write_fn(gopkg, kwargs.get('std', []), dep_packages, importcfg)
  result = subprocess.run(go_cmd, encoding='utf-8', shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)
  if result.returncode:
    target.ExecutionFailed('go build', go_cmd + '\n' + result.stdout)
  return go_output, importcfg


def _extract_archives_from_error(err_msg):
  import re
  archives = set()
  for line in err_msg.split('\n'):
    if line:
      match = re.match(r'cannot find package (\S+) \(using \-importcfg\)', line)
      if not match:
        return None
      archives.add(match.group(1))
  return archives


@using(_get_src_files, _write_importcfg, _build_go_archive)
@buildrule
def go_pkg(target, name, srcs, **kwargs):
  srcs = _get_src_files(target, srcs)
  archive, importcfg = _build_go_archive(
    target, _write_importcfg, name, srcs, **kwargs)
  target.AddFile(archive)
  target.AddFile(importcfg)


@using(_get_src_files, _write_importcfg, _build_go_archive,
       _extract_archives_from_error)
@buildrule
def go_binary(target, name, srcs, **kwargs):
  srcs = _get_src_files(target, srcs)
  archive, importcfg = _build_go_archive(
    target, _write_importcfg, name, srcs, **kwargs)

  gopkg = f'/usr/lib/go/pkg'
  
  import os
  import subprocess
  binary_name = os.path.join(target.GetPackageDirectory(), name)
  mmap_output_name = '/tmp/impulse-mmap-optional-output-file'
  golinker = f'{gopkg}/tool/linux_amd64/link'
  go_cmd = (f'{golinker} '
            f'-o {mmap_output_name} '
            f'-importcfg importcfg '
            f'-buildmode=exe -extld=gcc '
            f'{archive}')

  def export_binary(package_name, package_file, binary_location):
    package_exe = os.path.join(target.GetPackageDirectory(), package_name)
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(package_exe, binary_file))

  added_archives = set()
  setsize = -1
  while len(added_archives) != setsize:
    setsize = len(added_archives)
    _write_importcfg(gopkg, list(added_archives),
                     target.Dependencies(package_ruletype='go_pkg'),
                     'importcfg')
    result = subprocess.run(
      go_cmd, encoding='utf-8', shell=True,
      stderr=subprocess.PIPE,
      stdout=subprocess.PIPE)

    if not result.returncode:
      os.system(f'mv {mmap_output_name} {binary_name}')
      target.AddFile(binary_name)
      return export_binary

    new_libraries = _extract_archives_from_error(result.stdout)
    if new_libraries:
      added_archives.update(new_libraries)

  target.ExecutionFailed('go build', go_cmd + '\n' + result.stderr)
  return None