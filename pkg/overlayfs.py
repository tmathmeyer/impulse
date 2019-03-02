#!/usr/bin/env python3

import collections
import errno
import fuse
import os
import shutil
import signal
import sys
import multiprocessing
import inspect


def ACCESS_ERR():
  raise fuse.FuseOSError(errno.EACCES)

def _dbg_print():
  sidx = 1
  while inspect.stack()[sidx][3].startswith('_'):
    sidx += 1
  print(inspect.stack()[sidx][3])


class OverlayFilesystemOperations(fuse.Operations):
  """Backend file operations for the overlay filesystem."""
  def __init__(self, rw_dir: str, ro_dirs: [str], ro_files: [str]):
    self._rw_directory = rw_dir
    self._ro_directories = ro_dirs
    self._ro_files = ro_files

     # Set of strings representing files that shouldn't be shown as
     # they have been moved away.
    self._moved_files = set()

    # A map of open file descriptors which can be used for passing through
    # operations and triggering a copy-on-write.
    # mapping from {filename -> {handle -> (handle, open-flags)}}
    self._open_files = collections.defaultdict(dict)


  def _find_shadow_nodes(self, path: str) -> (str, [str]):
    """Returns either the RW copy of the file, or the RO copies."""
    _dbg_print()
    if path.startswith('/'):
      path = path[1:]

    rw_copy = os.path.join(self._rw_directory, path)
    if os.path.exists(rw_copy) and path != '':
      return (rw_copy, [])

    result = []
    for directory in self._ro_directories:
      full_path = os.path.join(directory, path)
      if os.path.exists(full_path) and full_path not in self._moved_files:
        result.append(full_path)
    for file in self._ro_files:
      if file.startswith(path):
        result.append(file)
    return (rw_copy, result)

  def _fallback_on_read(self, path: str, operation):
    path, ro_nodes = self._find_shadow_nodes(path)
    if ro_nodes: # RW version doesn't exist
      return operation(ro_nodes[0])
    return operation(path)

  def _unmap_handle(self, path, handle):
    mapped_handle, flags = self._open_files[path].get(handle, (handle, 0))
    # If the file was remapped to something else, we need to open that instead.
    return handle if mapped_handle == -1 else mapped_handle

  def _hide_RO_nodes(self, ro_nodes: [str]):
    self._moved_files.update(ro_nodes)

  def _change_file(self, path: str, operation, failure=ACCESS_ERR):
    writable_node, ro_nodes = self._find_shadow_nodes(path)
    if ro_nodes: # no RW version of the file could be found - 
                 # we need to copy it. The operation will be called
                 # in the next block.
      shutil.copyfile(ro_nodes[0], writable_node)
    return operation(writable_node)


  # Copy on write methods - these change properties of the file which
  # means the file needs to be copied before use.
  def chmod(self, path, mode):
    return self._change_file(path, lambda p: os.chmod(p, mode))

  def chown(self, path, uid, gid):
    return self._change_file(path, lambda p: os.chown(p, uid, gid))

  def utimens(self, path, times=None):
    def utime(path):
      return os.utime(path, times)
    return self._change_file(path, utime)

  def symlink(self, name, target):
    def _ensure_target(target):
      rw, _ = self._find_shadow_nodes(name)
      return os.symlink(rw, target)
    return self._change_file(target, _ensure_target)


  # Write from scratch - easy, just create a new node in the RW space
  def mknod(self, path, mode, dev):
    path, _ = self._find_shadow_nodes(path)
    return os.mknod(path, mode, dev)

  def mkdir(self, path, mode):
    path, _ = self._find_shadow_nodes(path)
    return os.mkdir(path, mode)

  
  # Delete methods - important to mark these files as deleted!
  def rmdir(self, path):
    path, RO_nodes = self._find_shadow_nodes(path)
    self._hide_RO_nodes(RO_nodes)
    return os.rmdir(path)

  def unlink(self, path):
    path, RO_nodes = self._find_shadow_nodes(path)
    self._hide_RO_nodes(RO_nodes)
    return os.unlink(path)


  # Read-only methods - easy, they never modify anything.
  def getattr(self, path, fh=None):
    def stat(pw):
      st = os.lstat(pw)
      attrs = ('st_atime', 'st_ctime', 'st_gid', 'st_mode',
               'st_mtime', 'st_nlink', 'st_size', 'st_uid')
      return dict((k, getattr(st, k)) for k in attrs)
    if path == '/':
      return stat(self._rw_directory)
    return self._fallback_on_read(path, stat)

  def statfs(self, path):
    def statvfs(path):
      stv = os.statvfs(path)
      return dict((k, getattr(stv, k)) for k in (
        'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail', 'f_ffree',
        'f_files', 'f_flag', 'f_frsize', 'f_namemax'))
    return self._fallback_on_read(path, statvfs)

  def access(self, path, mode):
    def osaccess(path):
      if not os.access(path, mode):
        ACCESS_ERR()
    return self._fallback_on_read(path, osaccess)

  def readlink(self, path):
    def _readlink(path):
      pathname = os.readlink(path)
      if pathname.startswith('/'):
        ACCESS_ERR() # TODO: might have to ban symlinks entirely.
      return pathname
    return self._fallback_on_read(path, _readlink)


  # IO methods
  def open(self, original_path, flags):
    if flags & (os.O_RDONLY|os.O_WRONLY|os.O_RDWR) == os.O_RDONLY:
      return self._fallback_on_read(original_path, lambda p: os.open(p, flags))
    def copy_on_write_open(path):
      file_desc = os.open(path, flags)
      if not path.startswith(self._rw_directory):
        # Default state for a COW remapping file is (-1, flags)
        # the -1 signifies that it has not been remapped, and flags
        # is used to re-open the file after a write causing a copy.
        self._open_files[original_path][file_desc] = (-1, flags)
      return file_desc
    return self._fallback_on_read(original_path, copy_on_write_open)

  def read(self, path, length, offset, handle):
    handle = self._unmap_handle(path, handle)
    os.lseek(handle, offset, os.SEEK_SET)
    return os.read(handle, length)

  def flush(self, path, handle):
    handle = self._unmap_handle(path, handle)
    return os.fsync(handle)

  def fsync(self, path, fdatasync, handle):
    handle = self._unmap_handle(path, handle)
    return self.flush(handle)

  def release(self, path, handle):
    if handle in self._open_files[path]:
      os.close(self._open_files[path].pop(handle)[0])
    os.close(handle)

  def write(self, path, buf, offset, handle):
    mapped_handle, flags = self._open_files[path].get(handle, (handle, 0))
    if mapped_handle == -1: # This is a COW file, and needs to be copied!
      rw_file, ro_files = self._find_shadow_nodes(path)
      shutil.copyfile(ro_files[0], rw_file)
      self._open_files[path][handle] = (os.open(rw_file, flags), flags)
    handle = self._unmap_handle(path, handle)
    os.lseek(handle, offset, os.SEEK_SET)
    return os.write(handle, buf)

  def create(self, path, mode, fi=None):
    rw_file, ro_files = self._find_shadow_nodes(path)
    if ro_files:
      raise "Can't create a file that already exists (i think?)"
    if not os.path.exists(os.path.dirname(rw_file)):
      os.makedirs(os.path.dirname(rw_file))
    return os.open(rw_file, os.O_WRONLY | os.O_CREAT, mode)

  def readdir(self, path, fh):
    rw_dir, ro_dirs = self._find_shadow_nodes(path)
    dirents = set(['.', '..'])
    for rwo_dir in ro_dirs + [rw_dir]:
      if os.path.isdir(rwo_dir):
        dirents.update(os.listdir(rwo_dir))
      else:
        dirents.update([rwo_dir])
    return dirents

  def rename(self, old, new):
    rw_old, ro_old = self._find_shadow_nodes(old)
    rw_new, ro_new = self._find_shadow_nodes(new)
    self._moved_files.update(ro_new) # any files which could be backing
                                     # the new location need to be marked hidden

    if ro_old: # The source file was read-only in the old location
      shutil.copyfile(ro_old[0], rw_new)
      self._moved_files.update(ro_old) # Hide all source files
    elif os.path.exists(rw_old): # File is in RW, so just move it.
      shutil.move(rw_old, rw_new)


  # Not implemented
  def link(self, target, name):
    raise "not implemented"


  def truncate(self, path, length, fh=None):
    raise "not implemented"




def run_fuse_thread(mount, rw_file, shadow_dirs, shadow_files):
  fuse.FUSE(OverlayFilesystemOperations(rw_file, shadow_dirs, shadow_files),
    mount, nothreads=True, foreground=True)


class FuseCTX(object):
  def __init__(self, mountpoint, rw, shadows):
    self._mount = mountpoint
    self._rw = rw
    self._shadow_dirs = []
    self._shadow_files = []
    for shadow in shadows:
      if os.path.isfile(shadow):
        self._shadow_files.append(shadow)
      else:
        self._shadow_dirs.append(shadow)

  def __enter__(self):
    self._oldsignal = signal.signal(signal.SIGINT, self._quit)
    self._thread = multiprocessing.Process(target=run_fuse_thread,
      args=(self._mount, self._rw, self._shadow_dirs, self._shadow_files))
    self._thread.start()
    while not os.path.ismount(self._mount):
      pass

  def __exit__(self, *args):
    self._quit()

  def _quit(self):
    os.system('fusermount -u {}'.format(self._mount))
    self._thread.join()
    self.signal(signal.SIGINT, self._oldsignal)




if __name__ == '__main__':
  fmt = 'mounting {} as overlay of rw:{} ro:[{}]'
  print(fmt.format(sys.argv[1], sys.argv[2], ', '.join(sys.argv[3:])))
  fs = FuseCTX(sys.argv[1], sys.argv[2], sys.argv[3:])
  run_fuse_thread(fs._mount, fs._rw, fs._shadow_dirs, fs._shadow_files)
  