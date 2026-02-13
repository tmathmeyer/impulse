
import contextlib
import os
import subprocess
import tempfile
import typing


@contextlib.contextmanager
def FuseCTX(ro:list[str], files:dict[str, str]) -> typing.Iterator[str]:
  """
  Creates a temporary FUSE overlay filesystem context.

  Args:
    ro: A list of directory paths to be used as lower (read-only) layers.
    files: A mapping of relative paths in the mount to absolute source paths.

  Yields:
    The path to the mountpoint where the overlay filesystem is mounted.
  """
  workdir=tempfile.mkdtemp()
  mountpoint=tempfile.mkdtemp()
  scratch=tempfile.mkdtemp()
  lower_basedir=tempfile.mkdtemp()
  lower_dirs=':'.join([lower_basedir, *ro])

  # Removed userxattr as it was causing warnings/errors in some environments
  options=f'lowerdir={lower_dirs},upperdir={scratch},workdir={workdir}'
  fuse_cmd=['fuse-overlayfs', '-o', options, mountpoint]

  try:
    subprocess.run(fuse_cmd, check=True)
    for rel_path, abs_path in files.items():
      destination=os.path.join(mountpoint, rel_path)
      os.makedirs(os.path.dirname(destination), exist_ok=True)
      subprocess.run(['cp', abs_path, destination], check=True)
    yield mountpoint
  finally:
    subprocess.run(['fusermount3', '-uz', mountpoint], check=False)
    for d in [workdir, mountpoint, scratch, lower_basedir]:
      subprocess.run(['rm', '-rf', d], check=False)
