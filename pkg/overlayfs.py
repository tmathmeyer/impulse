#!/usr/bin/env python3

import contextlib
import os
import subprocess
import tempfile


@contextlib.contextmanager
def FuseCTX(ro, files):
  workdir = tempfile.mkdtemp()
  mountpoint = tempfile.mkdtemp()
  scratch = tempfile.mkdtemp()
  lower_basedir = tempfile.mkdtemp()
  lower_dirs = ':'.join([lower_basedir, *ro])

  options = f'lowerdir={lower_dirs},upperdir={scratch},workdir={workdir},userxattr'
  unshare_cmd = ['mount', '-t', 'overlay', 'overlay', '-o', options, mountpoint]
  try:
    subprocess.run(unshare_cmd)
    for file, real in files.items():
      destination = os.path.join(mountpoint, file)
      os.system(f'mkdir -p {os.path.dirname(destination)}')
      os.system(f'cp {real} {destination}')
    yield mountpoint
  finally:
    os.system(f'umount {mountpoint}')
    os.system(f'rm -rf {workdir}')
    os.system(f'rm -rf {mountpoint}')
    os.system(f'rm -rf {scratch}')
    os.system(f'rm -rf {lower_basedir}')