
def _get_src_files(target, srcs):
  for src in srcs:
    yield os.path.join(target.GetPackageDirectory(), src)


def _write_importcfg(gopkg, stdinc, deps, filename):
  with open(filename, 'w+') as f:
    f.write(f'packagefile runtime={gopkg}/linux_amd64/runtime.a\n')
    for stdlib in stdinc:
      f.write(f'packagefile {stdlib}={gopkg}/linux_amd64/{stdlib}.a\n')
    for dep in deps:
      path, pkg = dep.package_target.split(':')
      path = path[2:]
      f.write(f'packagefile {pkg}={path}/_pkg_.a\n')


def _build_go_archive(target, write_fn, name, srcs, **kwargs):
  import os
  import subprocess

  # Create all the needed files
  go_version = kwargs.get('go_version', '1.10')
  gopkg = f'/usr/lib/go-{go_version}/pkg'
  go_compiler = f'{gopkg}/tool/linux_amd64/compile'
  go_output = os.path.join(target.GetPackageDirectory(), '_pkg_.a')
  go_input_files = ' '.join(srcs)

  dep_packages = list(target.Dependencies(package_ruletype='go_pkg'))
  for pkg in dep_packages:
    for archive in pkg.IncludedFiles():
      target.AddFile(archive)

  go_cmd = (f'{go_compiler} '
            f'-o {go_output} '
            f'-trimpath . '
            f'-D ./ '
            f'-importcfg importcfg '
            f'-pack -c=2 '
            f'{go_input_files} ')
  write_fn(gopkg, kwargs.get('std', []), dep_packages, 'importcfg')
  result = subprocess.run(go_cmd, encoding='utf-8', shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)
  if result.returncode:
    target.ExecutionFailed('go build', result.stdout)

  return go_output


@using(_get_src_files, _write_importcfg, _build_go_archive)
@buildrule
def go_pkg(target, name, srcs, **kwargs):
  srcs = _get_src_files(target, srcs)
  archive = _build_go_archive(
    target, _write_importcfg, name, srcs, **kwargs)
  target.AddFile(archive)


@using(_get_src_files, _write_importcfg, _build_go_archive)
@buildrule
def go_binary(target, name, srcs, **kwargs):
  srcs = _get_src_files(target, srcs)
  archive = _build_go_archive(
    target, _write_importcfg, name, srcs, **kwargs)

  go_version = kwargs.get('go_version', '1.10')
  gopkg = f'/usr/lib/go-{go_version}/pkg'
  _write_importcfg(gopkg, [
    'fmt', 'io', 'os', 'reflect', 'unicode', 'strconv',
    'syscall', 'sync', 'math', 'errors', 'time',
    'runtime/internal/sys',
    'runtime/internal/atomic',
    'unicode/utf8',
    'internal/testlog',
    'internal/poll',
    'internal/race',
    'internal/cpu',
    'sync/atomic',
  ], target.Dependencies(package_ruletype='go_pkg'), 'importcfg.link')
  
  import os
  binary_name = os.path.join(target.GetPackageDirectory(), name)
  golinker = f'{gopkg}/tool/linux_amd64/link'
  go_cmd = (f'{golinker} '
            f'-o {binary_name} '
            f'-importcfg importcfg.link '
            f'-buildmode=exe -extld=gcc '
            f'{archive}')

  import subprocess
  result = subprocess.run(go_cmd, encoding='utf-8', shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)
  if result.returncode:
    target.ExecutionFailed(go_cmd, result.stderr)

  target.AddFile(binary_name)
    
  def export_binary(package_name, package_file, binary_location):
    package_exe = os.path.join(target.GetPackageDirectory(), package_name)
    binary_file = os.path.join(binary_location, package_name)
    os.system('cp {} {}'.format(package_exe, binary_file))

  return export_binary