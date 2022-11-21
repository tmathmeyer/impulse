


def _add_pkg_deps(target):
  for deplib in target.Dependencies(tags='rpkg'):
    for pkg in deplib.IncludedFiles():
      target.AddFile(pkg)

@using(_add_pkg_deps)
@buildrule
def r_binary_package(target, name, **kwargs):
  target.SetTags('rpkg')
  import requests
  url = f'https://cran.r-project.org/web/packages/{name}/index.html'
  for line in str(requests.get(url).content.decode('utf-8')).split('\n'):
    if f'<a href="../../../src/contrib/{name}' in line:
      pkg = line.split('"')[1].split('/')[-1].strip()
      target.Execute(f'wget https://cran.r-project.org/src/contrib/{pkg}')
      target.AddFile(pkg)
  _add_pkg_deps(target)


@using(_add_pkg_deps)
@buildrule
def r_source_package(target, name, srcs, **kwargs):
  target.SetTags('rpkg')
  def GetVersion():
    with open(f'{name}/DESCRIPTION', 'r') as f:
      for line in f.readlines():
        if line.startswith('Version: '):
          return line[9:].strip()
  pwd = os.getcwd()
  os.chdir(target.GetPackageDirectory())
  os.chdir('..')
  target.Execute(f'R CMD build {name}')
  archive = f'{name}_{GetVersion()}.tar.gz'
  target.Execute(f'mv {archive} ..')
  os.chdir(pwd)
  target.AddFile(archive)
  _add_pkg_deps(target)


@buildrule
def r_environment(target, name, **kwargs):
  if not os.path.exists('rlib'):
    target.Execute('mkdir rlib')

  pkgs = []
  for deplib in target.Dependencies(tags='rpkg'):
    for pkg in deplib.IncludedFiles():
      pkgs.append(pkg)

  failed = []
  change = True
  while change:
    for pkg in pkgs:
      try:
        target.Execute(f'R CMD INSTALL {pkg} --library=rlib')
      except Exception as e:
        failed.append(pkg)

    if len(failed) == 0:
      change = False
    elif len(failed) == len(pkgs):
      return
    else:
      pkgs = failed
      failed = []

  for root, dirs, files in os.walk('rlib'):
    for file in files:
      target.AddFile(os.path.join(root, file))


@buildrule
def r_process_data(target, name, srcs, **kwargs):
  file = f'{target.GetPackageDirectory()}/{name}'
  script = os.path.join(target.GetPackageDirectory(), srcs[0])
  target.Execute(f'Rscript {script} {file}')
  target.AddFile(file)
