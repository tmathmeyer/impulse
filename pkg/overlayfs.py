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


traced_calls = set()
def FSCall(fn):
  traced_calls.add(fn.__name__)
  return fn

""" Debug Code!

GREEN = '\033[92m'
RESET = '\033[0m'

def clean_attrs(attrd):
  if not attrd:
    return {}
  return {k: int(v) for k, v in attrd.items()}

def ShowReturnValuesForFSCalls(frame, event, arg, indent=[0]):
  def argvalues(frame):
    for argname_index in range(1, frame.f_code.co_argcount):
      yield str(frame.f_locals[frame.f_code.co_varnames[argname_index]])

  if event == "call":
    name = frame.f_code.co_name
    if name in traced_calls and frame.f_lineno < 400:
      print('{}{}({}){}'.format(GREEN, name, ', '.join(argvalues(frame)), RESET))
  elif event == "return":
    name = frame.f_code.co_name
    if name in traced_calls and frame.f_lineno < 400:
      if name == 'getattr':
        print(' --> {}'.format(clean_attrs(arg)))
      else:
        print('  --> {}'.format(arg))
      print('') # newline
  return ShowReturnValuesForFSCalls

import sys
sys.settrace(ShowReturnValuesForFSCalls)
"""

def ACCESS_ERR():
  raise fuse.FuseOSError(errno.EACCES)

class OverlayFilesystemOperations(fuse.Operations):
  """Backend file operations for the overlay filesystem."""
  def __init__(self, rw_dir: str, ro_dirs: [str], shadow_files:dict):
    self._rw_directory = rw_dir
    self._ro_directories = ro_dirs
    self._ro_files = shadow_files

     # Set of strings representing files that shouldn't be shown as
     # they have been moved away.
    self._moved_files = set()

    # A map of open file descriptors which can be used for passing through
    # operations and triggering a copy-on-write.
    # mapping from {filename -> {handle -> (handle, open-flags)}}
    self._open_files = collections.defaultdict(dict)


  def _find_shadow_nodes(self, path: str, files:bool = False) -> (str, [str]):
    """Returns either the RW copy of the file, or the RO copies."""
    if path.startswith('/'):
      path = path[1:]

    rw_copy = os.path.join(self._rw_directory, path)
    if os.path.exists(rw_copy) and path != '':
      return (rw_copy, [])

    result = set()
    for directory in self._ro_directories:
      full_path = os.path.join(directory, path)
      if os.path.exists(full_path) and full_path not in self._moved_files:
        result.add(full_path)

    if files:
      for f in self._live_ro_files():
        named_dir, maybe_for_read = self._chop_ro_file_to_fit(f, path)
        if named_dir and maybe_for_read:
          result.add(maybe_for_read)

    return (rw_copy, list(result))

  def _live_ro_files(self):
    for f in self._ro_files.keys():
      if f not in self._moved_files:
        yield f

  def _get_next_element_of(self, f: str, directory: str):
    ffq = self._ro_files.get(f, None)
    if not ffq:
      return None, None
    while len(f) >= len(directory):
      b = os.path.basename(f)
      f = os.path.dirname(f)
      ffq = os.path.dirname(ffq)
      if f == directory:
        return b, os.path.join(ffq, b)
    return None, None

  def _chop_ro_file_to_fit(self, f: str, search: str):
    ffq = self._ro_files.get(f, None)
    if not ffq:
      return None, None
    while len(f) >= len(search):
      b = os.path.basename(f)
      if f == search:
        return b, ffq
      f = os.path.dirname(f)
      ffq = os.path.dirname(ffq)
    return None, None

  def _chop_ro_file_to_fit_original(self, f: str, directory: str):
    ffq = self._ro_files.get(f, None)
    if not ffq:
      return None, None

    while len(f) >= len(directory):
      b = os.path.basename(f)
      f = os.path.dirname(f)
      ffq = os.path.dirname(ffq)
      if f == directory:
        return b, os.path.join(ffq, b)
    return None, None

  def _fallback_on_read(self, path: str, operation):
    path, ro_nodes = self._find_shadow_nodes(path, True)
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
  @FSCall
  def chmod(self, path, mode):
    return self._change_file(path, lambda p: os.chmod(p, mode))

  @FSCall
  def chown(self, path, uid, gid):
    return self._change_file(path, lambda p: os.chown(p, uid, gid))

  @FSCall
  def utimens(self, path, times=None):
    def utime(path):
      return os.utime(path, times)
    return self._change_file(path, utime)

  @FSCall
  def symlink(self, name, target):
    def _ensure_target(target):
      rw, _ = self._find_shadow_nodes(name)
      return os.symlink(rw, target)
    return self._change_file(target, _ensure_target)


  # Write from scratch - easy, just create a new node in the RW space
  @FSCall
  def mknod(self, path, mode, dev):
    path, _ = self._find_shadow_nodes(path)
    return os.mknod(path, mode, dev)

  @FSCall
  def mkdir(self, path, mode):
    path, _ = self._find_shadow_nodes(path)
    return os.mkdir(path, mode)

  @FSCall
  def truncate(self, path, length, fh=None):
    rw, ros = self._find_shadow_nodes(path)
    if ros:
      shutil.copyfile(ros[0], rw)
    with open(rw, 'r+') as f:
      f.truncate(length)

  
  # Delete methods - important to mark these files as deleted!
  @FSCall
  def rmdir(self, path):
    path, RO_nodes = self._find_shadow_nodes(path)
    self._hide_RO_nodes(RO_nodes)
    return os.rmdir(path)

  @FSCall
  def unlink(self, path):
    path, RO_nodes = self._find_shadow_nodes(path)
    self._hide_RO_nodes(RO_nodes)
    return os.unlink(path)


  # Read-only methods - easy, they never modify anything.
  @FSCall
  def getattr(self, path, fh=None):
    def stat(pw):
      st = os.lstat(pw)
      attrs = ('st_atime', 'st_ctime', 'st_gid', 'st_mode',
               'st_mtime', 'st_nlink', 'st_size', 'st_uid')
      return dict((k, getattr(st, k)) for k in attrs)
    if path == '/':
      return stat(self._rw_directory)
    return self._fallback_on_read(path, stat)

  @FSCall
  def statfs(self, path):
    def statvfs(path):
      stv = os.statvfs(path)
      return dict((k, getattr(stv, k)) for k in (
        'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail', 'f_ffree',
        'f_files', 'f_flag', 'f_frsize', 'f_namemax'))
    return self._fallback_on_read(path, statvfs)

  @FSCall
  def access(self, path, mode):
    def osaccess(path):
      if not os.access(path, mode):
        ACCESS_ERR()
    return self._fallback_on_read(path, osaccess)

  @FSCall
  def readlink(self, path):
    def _readlink(path):
      pathname = os.readlink(path)
      if pathname.startswith('/'):
        ACCESS_ERR() # TODO: might have to ban symlinks entirely.
      return pathname
    return self._fallback_on_read(path, _readlink)


  # IO methods
  @FSCall
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

  @FSCall
  def flush(self, path, handle):
    handle = self._unmap_handle(path, handle)
    return os.fsync(handle)

  @FSCall
  def fsync(self, path, fdatasync, handle):
    handle = self._unmap_handle(path, handle)
    return self.flush(handle)

  #@FSCall -- not important
  def release(self, path, handle):
    if handle in self._open_files[path]:
      os.close(self._open_files[path].pop(handle)[0])
    os.close(handle)

  def write(self, path, buf, offset, handle):
    mapped_handle, flags = self._open_files[path].get(handle, (handle, 0))
    if mapped_handle == -1: # This is a COW file, and needs to be copied!
      rw_file, ro_files = self._find_shadow_nodes(path)
      if ro_files:
        shutil.copyfile(ro_files[0], rw_file)
      self._open_files[path][handle] = (os.open(rw_file, flags), flags)
    handle = self._unmap_handle(path, handle)
    os.lseek(handle, offset, os.SEEK_SET)
    return os.write(handle, buf)

  @FSCall
  def create(self, path, mode, fi=None):
    rw_file, ro_files = self._find_shadow_nodes(path)
    if ro_files:
      raise "Can't create a file that already exists (i think?)"
    if not os.path.exists(os.path.dirname(rw_file)):
      os.makedirs(os.path.dirname(rw_file))
    return os.open(rw_file, os.O_WRONLY | os.O_CREAT, mode)

  @FSCall
  def readdir(self, path, fh):
    rw_dir, ro_dirs = self._find_shadow_nodes(path)
    dirents = set(['.', '..'])
    for rwo_dir in ro_dirs + [rw_dir]:
      if os.path.isdir(rwo_dir):
        dirents.update(os.listdir(rwo_dir))
      elif os.path.exists(rwo_dir):
        dirents.update([rwo_dir])

    for f in self._live_ro_files():
      named_dir, _ = self._get_next_element_of(f, path[1:])
      if named_dir:
        dirents.update([named_dir])
    return list(dirents)

  @FSCall
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
  @FSCall
  def link(self, target, name):
    raise "not implemented - link"





def run_fuse_thread(mount, rw_file, shadow_dirs, shadow_files):
  fuse.FUSE(OverlayFilesystemOperations(rw_file, shadow_dirs, shadow_files),
    mount, nothreads=True, foreground=True)


class FuseCTX(object):
  def __init__(self, mountpoint, rw, files=None, *shadows):
    self._mount = mountpoint
    self._rw = rw
    self._shadow_dirs = []
    self._files = files or {}
    for shadow in shadows:
      if not os.path.isfile(shadow):
        self._shadow_dirs.append(shadow)

  def __enter__(self):
    self._oldsignal = signal.signal(signal.SIGINT, self._quit)
    self._thread = multiprocessing.Process(target=run_fuse_thread,
      args=(self._mount, self._rw, self._shadow_dirs, self._files))
    self._thread.start()
    while not os.path.ismount(self._mount):
      pass

  def __exit__(self, *args):
    self._quit()

  def _quit(self):
    os.system('fusermount -u {}'.format(self._mount))
    self._thread.join()
    signal.signal(signal.SIGINT, self._oldsignal)




if __name__ == '__main__':
  fmt = 'mounting {} as overlay of rw:{} ro:[{}]'
  print(fmt.format(sys.argv[1], sys.argv[2], ', '.join(sys.argv[3:])))
  fs = FuseCTX(sys.argv[1], sys.argv[2], *sys.argv[3:])
  run_fuse_thread(fs._mount, fs._rw, fs._shadow_dirs, [])
  