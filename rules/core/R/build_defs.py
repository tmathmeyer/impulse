
def _get_pkg_dep_tree(pkglist):
  import requests
  import dataclasses

  pkgmap = {}
  @dataclasses.dataclass
  class RPackage:
    name:str
    archive:str
    dlfrom:str
    deps:['RPackage']

  def get_package(name, packages):
    host = 'https://cran.r-project.org'
    if name in packages:
      return packages[name]
    url = f'{host}/web/packages/{name}/index.html'
    
    parse_archive = False
    parse_depends = False
    dependencies = []
    archive = None
    
    for line in str(requests.get(url).content.decode('utf-8')).split('\n'):
      line = line.strip()
      if line == '<td>Depends:</td>':
        parse_depends = True
        continue

      if line == '<td> Package&nbsp;source: </td>':
        parse_archive = True
        continue

      if line == '<td>Imports:</td>':
        parse_depends = True
        continue

      if parse_depends:
        for part in line.split('"'):
          if 'index.html' in part:
            dependencies.append(part.split('/')[1])

      if parse_archive:
        pkg = line.split('"')[1].split('/')[-1].strip()
        archive = pkg

      parse_archive = False
      parse_depends = False

    package = RPackage(
      name,
      archive,
      f'{host}/src/contrib/{pkg}',
      [get_package(p, packages) for p in dependencies])
    packages[name] = package
    return package

  for package in pkglist:
    get_package(package, pkgmap)

  return pkgmap.values()


@using(_get_pkg_dep_tree)
@buildrule
def r_environment(target, packages, **kwargs):
  if not os.path.exists('rlib'):
    target.Execute('mkdir rlib')

  pkgs = []
  for deplib in target.Dependencies(tags='rpkg'):
    for pkg in deplib.IncludedFiles():
      pkgs.append(pkg)

  installed = []
  pending = _get_pkg_dep_tree(packages)
  while pending:
    not_installed = []
    for pkg in pending:
      if all(dep.name in installed for dep in pkg.deps):
        target.Execute(f'wget {pkg.dlfrom}')
        target.Execute(f'R CMD INSTALL {pkg.archive} --library=rlib')
        installed.append(pkg.name)
      else:
        not_installed.append(pkg)
    if len(pending) == len(not_installed):
      raise ValueError('could not install: ', pending)
    pending = not_installed

  for root, dirs, files in os.walk('rlib'):
    for file in files:
      target.AddFile(os.path.join(root, file))


@buildrule
def r_process_data(target, name, srcs, **kwargs):
  file = f'{target.GetPackageDirectory()}/{name}'
  script = os.path.join(target.GetPackageDirectory(), srcs[0])
  target.Execute(f'Rscript {script} {file}')
  target.AddFile(file)
  target.AddFile(script)
