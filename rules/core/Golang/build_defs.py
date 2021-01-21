
def ThirdParty(target, **kwargs):
  class GoGetter(object):
    def __init__(self):
      self.temp_dir = target.UseTempDir()
    def __enter__(self):
      output = self.temp_dir.__enter__()
      target.SetEnvVar('GOPATH', output)
      arch = os.path.join(output, 'pkg', kwargs.get('arch', 'linux_amd64'))
      for dependency in kwargs.get('third_party', []):
        target.Execute(f'go get {dependency}')
        archive = os.path.join(arch, f'{dependency}.a')
        yield (dependency, archive)
    def __exit__(self, *args, **kwargs):
      target.UnsetEnvVar('GOPATH')
      self.temp_dir.__exit__()
  return GoGetter()


def WriteImportCFG(target, stdlib, gopkg, arch):
  with open('importcfg', 'w+') as cfg:
    for library in stdlib:
      cfg.write(f'packagefile {library}={gopkg}/{arch}/{library}.a\n')
    for pkg in target.Dependencies(tags=Any('go_pkg')):
      package_name = os.path.dirname(pkg.filename)
      for archive in pkg.IncludedFiles():
        if archive.endswith('.a'):
          archive = os.path.join(os.getcwd(), archive)
          cfg.write(f'packagefile {package_name}={archive}\n')


def UpdateImportCFG(packages):
  with open('importcfg', 'a') as cfg:
    for dependency, archive in packages:
      cfg.write(f'packagefile {dependency}={archive}\n')


@using(ThirdParty, WriteImportCFG, UpdateImportCFG)
@buildrule
def go_package(target: 'ExportablePackage', name: str, srcs:[str], **kwargs):
  target.SetTags('go_pkg')

  WriteImportCFG(target, kwargs.get('std_include', []),
                         kwargs.get('gostdlib', '/usr/lib/go/pkg'),
                         kwargs.get('arch', 'linux_amd64'))

  srcs = list(os.path.join(target.GetPackageDirectory(), s) for s in srcs)
  with ThirdParty(target, **kwargs) as packages:
    UpdateImportCFG(packages)
    obj_file = os.path.join(target.GetPackageDirectory(), name+'.a')
    src_str = ' '.join(srcs)
    target.Execute(
      f'go tool compile '
      f'-trimpath . '
      f'-importcfg importcfg '
      f'-o {obj_file} '
      f'-pack {src_str}')
    target.AddFile(obj_file)
    target.AddFile('importcfg')


@using(ThirdParty, WriteImportCFG, UpdateImportCFG)
@buildrule
def go_binary(target: 'ExportablePackage', name:str, srcs:[str], **kwargs):
  if len(srcs) != 1:
    target.ExecutionFailed('go_binary.srcs must contain only the main file')
  mainfile = os.path.join(target.GetPackageDirectory(), srcs[0])
  target.SetTags('exe')

  # Default std include for making a binary.
  std_include = set([
    'errors', 'internal/bytealg', 'internal/cpu', 'internal/fmtsort',
    'internal/oserror', 'internal/poll', 'internal/race',
    'internal/reflectlite', 'internal/syscall/execenv', 'internal/syscall/unix',
    'internal/testlog', 'io', 'math', 'math/bits', 'os', 'reflect', 'runtime',
    'runtime/internal/atomic', 'runtime/internal/math', 'runtime/internal/sys',
    'sort', 'strconv', 'sync', 'sync/atomic', 'syscall', 'time', 'unicode',
    'unicode/utf8', 'fmt'])

  std_include.update(kwargs.get('std_include', []))

  WriteImportCFG(target, std_include,
                         kwargs.get('gostdlib', '/usr/lib/go/pkg'),
                         kwargs.get('arch', 'linux_amd64'))

  binary = os.path.join(target.GetPackageDirectory(), 'exe')
  with ThirdParty(target, **kwargs) as packages:
    UpdateImportCFG(packages)
    os.system('cp importcfg ~/')
    with target.UseTempDir() as tmp:
      object_file = os.path.join(tmp, 'main.o')
      binary_intermediate = os.path.join(tmp, 'exe')
      importcfg = '-importcfg importcfg'
      print(target.Execute(
        f'go tool compile -o {object_file} {importcfg} {mainfile}'))
      print(target.Execute(
        f'go tool link -o {binary_intermediate} {importcfg} {object_file}',
        ))#f'cp {binary_intermediate} {binary}')
      os.system(f'tree {tmp}')
      os.system('tree')
      os.system(f'type {binary_intermediate}')
      target.AddFile(binary)

  def export_binary(_, package_name, package_file, binary_location):
    binary_file = os.path.join(binary_location, package_name)
    os.system('tree')
    target.Execute(f'cp {binary} {binary_file}')

  return export_binary
