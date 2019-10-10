
import atexit
import os
import pkgutil
import stat

from impulse.util import temp_dir


resource_dir = None


def GetResourcePath(pkg_path:str, exe=False) -> str:
  global resource_dir
  if not CreateResourceDir():
    raise LookupError(f'Could not load resource {pkg_path}')

  filedata = pkgutil.get_data(*pkg_path.rsplit('/', 1))
  if filedata is None:
    raise LookupError(f'Could not load resource {pkg_path}')
  outdir = os.path.join(resource_dir, os.path.dirname(pkg_path))
  os.makedirs(outdir, exist_ok=True)
  filename = os.path.join(outdir, os.path.basename(pkg_path))
  with open(filename, 'wb') as f:
    f.write(filedata)
  if exe:
    os.chmod(filename, stat.S_IRWXU)
  return filename


def UnloadResourceDir():
  global resource_dir
  if not resource_dir:
    return
  delete_this = resource_dir
  resource_dir = None
  atexit.unregister(UnloadResourceDir)
  os.system(f'rm -rf {delete_this}')


def CreateResourceDir():
  global resource_dir
  if resource_dir:
    return resource_dir

  resource_dir = temp_dir.CreateDangerousLifetimeDirectory()
  return resource_dir
