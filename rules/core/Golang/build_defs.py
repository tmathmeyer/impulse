
def ImportCFG(t, a):
  class ImportCFGCls():
    def __init__(self, target, target_args):
      self._target = target
      self._args = target_args
      self._arch = self._args.get('arch', 'linux_amd64')
      self._temp_dir = None

    def _include_std(self, packages):
      stdinclude = self._args.get('std_include', [])
      stdsrc = self._args.get('gostdlib', '/usr/lib/go/pkg')
      for library in stdinclude:
        packages.add(f'packagefile {library}={stdsrc}/{self._arch}/{library}.a')

    def _include_dependencies(self, packages):
      for dependency in self._target.Dependencies(tags=Any('go_pkg')):
        package = os.path.dirname(dependency.filename)
        package_location = os.path.splitext(dependency.filename)[0]
        packages.add(f'packagefile {package}={package_location}.a')
        for depfile in dependency.IncludedFiles():
          if depfile.endswith('importcfg'):
            with open(depfile) as f:
              for subdep in f.readlines():
                packages.add(subdep.strip())
          if depfile.endswith('.a'):
            self._target.AddFile(depfile)

    def _include_third_party(self, packages):
      self._temp_dir = self._target.UseTempDir()
      temp_dir = self._temp_dir.__enter__()
      self._target.SetEnvVar('GOPATH', temp_dir)
      temp_arch = os.path.join(temp_dir, 'pkg', self._arch)
      for third_party_lib in self._args.get('third_party', []):
        archive = os.path.join(temp_arch, f'{third_party_lib}.a')
        bundle = f'third_party/{third_party_lib}.a'
        self._target.Execute(f'go get {third_party_lib}')
        self._target.Execute(f'mkdir -p {os.path.dirname(bundle)}')
        self._target.Execute(f'cp {archive} {bundle}')
        packages.add(f'packagefile {third_party_lib}={bundle}')
        self._target.AddFile(bundle)

    def __enter__(self):
      packages = set()
      self._include_std(packages)
      self._include_dependencies(packages)
      self._include_third_party(packages)
      
      with open('importcfg', 'w') as f:
        for package in sorted(list(packages)):
          f.write(f'{package}\n')

    def __exit__(self, *args, **kwargs):
      self._target.UnsetEnvVar('GOPATH')
      self._temp_dir.__exit__(*args, **kwargs)
  return ImportCFGCls(t, a)


@using(ImportCFG)
@buildrule
def go_package(target: 'ExportablePackage', name: str, srcs:[str], **kwargs):
  target.SetTags('go_pkg')
  srcs = list(os.path.join(target.GetPackageDirectory(), s) for s in srcs)

  with ImportCFG(target, kwargs):
    obj_file = os.path.join(target.GetPackageDirectory(), name+'.a')
    src_str = ' '.join(srcs)
    target.Execute(f'cp importcfg ~/{name}.importcfg')
    target.Execute(
      f'go tool compile '
      f'-trimpath . '
      f'-importcfg importcfg '
      f'-complete '
      f'-std '
      f'-+ '
      f'-o {obj_file} '
      f'-pack {src_str}')
    target.AddFile(obj_file)
    target.AddFile('importcfg')


def ReRunWithSTD(target, command, max_tries, kwargs):
  if max_tries == 0:
    return command, None  # Error, capture output from previous stack frame
  kwargs['std_include'] = set(kwargs.get('std_include', set()))
  result = None
  with ImportCFG(target, kwargs):
    target.Execute(f'cp importcfg ~/importcfg')
    result = target.RunCommand(command)
  if not result.returncode:
    return None, None # No Errors!
  new_packages = False
  for line in result.stdout.split('\n'):
    if line.strip().startswith('cannot find package'):
      package = line.split(' ')[3]
      kwargs['std_include'].add(package)
      new_packages = True
  if not new_packages:
    return command, result.stderr
  cmd, stderr = ReRunWithSTD(target, command, max_tries - 1, kwargs)
  if cmd is None:
    return None, None
  return cmd, stderr or result.stderr


@using(ImportCFG, ReRunWithSTD)
@buildrule
def go_binary(target: 'ExportablePackage', name:str, srcs:[str], **kwargs):
  if len(srcs) != 1:
    target.ExecutionFailed('go_binary.srcs must contain only the main file')
  mainfile = os.path.join(target.GetPackageDirectory(), srcs[0])
  target.SetTags('exe')

  compile_command = (
    f'go tool compile -o main.o -importcfg importcfg -complete -std -+ -pack '
    f'-trimpath . {mainfile}')
  link_command = 'go tool link -o {} -importcfg importcfg -buildmode=exe main.o'

  errcmd, stderr = ReRunWithSTD(target, compile_command, 10, kwargs)
  if errcmd is not None:
    target.ExecutionFailed(errcmd, stderr)

  # go tool link does some wonky shit that breaks my overlay fs
  with target.UseTempDir() as tmp:
    link_command = link_command.format(f'{tmp}/main')
    errcmd, stderr = ReRunWithSTD(target, link_command, 10, kwargs)
    if errcmd is not None:
      target.ExecutionFailed(errcmd, stderr)
    target.Execute(f'cp {tmp}/main ./main')

  def export_binary(_, package_name, package_file, binary_location):
    binary_file = os.path.join(binary_location, package_name)
    target.Execute(f'cp main {binary_file}')

  return export_binary
