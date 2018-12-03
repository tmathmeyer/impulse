#!/usr/bin/env python3

import collections
import errno
import fuse
import os
import shutil
import signal
import sys
import multiprocessing


class FuseWrapper(fuse.Operations):
  def __init__(self, ro, rw):
    self._ro = ro
    self._rw = rw
    self._cow_fds = collections.defaultdict(dict)
    self._hidden = []

  def _truncate(self, path):
    if path.startswith('/'):
      path = path[1:]
    return (os.path.join(self._ro, path),
            os.path.join(self._rw, path))
  
  def _copy_on_write(self, path, operation, on_fail):
    ro, rw = self._truncate(path)
    if os.path.exists(rw):
      return operation(rw)
    elif os.path.exists(ro):
      if os.path.isdir(ro):
        os.makedirs(rw)
      else:
        if not os.path.exists(os.path.dirname(rw)):
          os.makedirs(os.path.dirname(rw))
        shutil.copyfile(ro, rw)
      return operation(rw)
    else:
      return on_fail(path)

  def _fallback_on_read(self, path, operation):
    ro, rw = self._truncate(path)
    if os.path.exists(rw):
      return operation(rw, self._rw)
    return operation(ro, self._ro)

  def _fall_ahead_on_read(self, path, operation):
    ro, rw = self._truncate(path)
    if os.path.exists(ro):
      return operation(ro, self._ro)
    return operation(rw, self._rw)

  def _access_fail(self, path):
    raise fuse.FuseOSError(errno.EACCES)





  # Copy on write methods

  def chmod(self, path, mode):
    def _chmod(path):
      return os.chmod(path, mode)
    return self._copy_on_write(path, _chmod, self._access_fail)

  def chown(self, path, uid, gid):
    def _chown(path):
      return os.chown(path, mode)
    return self._copy_on_write(path, _chown, self._access_fail)

  def symlink(self, name, target):
    def _ensure_target(target):
      _, rw = self._truncate(name)
      return os.symlink(rw, target)
    return _copy_on_write(target, _ensure_target)






  # Write from scratch - or - delete methods

  def mknod(self, path, mode, dev):
    _, path = self._truncate(path)
    return os.mknod(path, mode, dev)
  
  def rmdir(self, path):
    _, path = self._truncate(path)
    return os.rmdir(path)

  def mkdir(self, path, mode):
    _, path = self._truncate(path)
    return os.mkdir(path, mode)

  def unlink(self, path):
    _, path = self._truncate(path)
    os.unlink(path)

  def link(self, target, name):
    raise "not implemented"




  # Readonly methods

  def getattr(self, path, fh=None):
    def _getattr(_path, _):
      st = os.lstat(_path)
      return dict((k, getattr(st, k)) for k in (
        'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink',
        'st_size', 'st_uid'))
    if path == '/':
      return _getattr(self._rw, self._rw)
    return self._fall_ahead_on_read(path, _getattr)
    
  def readlink(self, path):
    def _readlink(path, root):
      pathname = os.readlink(path)
      if pathname.startswith('/'):
        return os.path.relpath(pathname, root)
      return pathname
    return self._fallback_on_read(path, _readlink)

  def statfs(self, path):
    def _statfs(path, _):
      stv = os.statvfs(path)
      return {k:getattr(stv, k) for k in (
        'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail', 'f_ffree',
        'f_files', 'f_flag', 'f_frsize', 'f_namemax')}
    return self._fallback_on_read(path, _statfs)

  def access(self, path, mode):
    if mode & 32768:
      ro, rw = self._truncate(path)
      if os.path.exists(ro):
        if os.path.isdir(ro):
          os.makedirs(rw)
        else:
          if not os.path.exists(os.path.dirname(rw)):
            os.makedirs(os.path.dirname(rw))
          shutil.copyfile(ro, rw)

    mode &= 32767
    def _access(path, root):
      if not os.access(path, mode):
        self._access_fail(path)
    return self._fallback_on_read(path, _access)




  # IO methods

  def open(self, path, flags):
    def _open(path, _):
      return os.open(path, flags)

    def _cow_open(_path, root):
      fd = os.open(_path, flags)
      if root == self._ro:
        self._cow_fds[path][fd] = (-1, flags)
      return fd

    if flags & (os.O_RDONLY|os.O_WRONLY|os.O_RDWR) == os.O_RDONLY:
      return self._fallback_on_read(path, _open)
    else:
      return self._fallback_on_read(path, _cow_open)

  def read(self, path, length, offset, fh):
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    os.lseek(fh, offset, os.SEEK_SET)
    return os.read(fh, length)

  def flush(self, path, fh):
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    return os.fsync(fh)

  def fsync(self, path, fdatasync, fh):
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    return self.flush(path, fh)

  def release(self, path, fh):
    if fh not in self._cow_fds[path]:
      return os.close(fh)
    mapped, _ = self._cow_fds[path].pop(fh)
    if mapped != fh:
      os.close(mapped)
    return os.close(fh)

  def write(self, path, buf, offset, fh):
    fd_remap = self._cow_fds[path]
    mapped_fh, flags = fd_remap.get(fh, (fh, 0))
    if mapped_fh == -1:
      ro, rw = self._truncate(path)
      if not os.path.exists(os.path.dirname(rw)):
        os.makedirs(os.path.dirname(rw))
      shutil.copyfile(ro, rw)
      mapped_fh = self.open(path, flags)
      self._cow_fds[path][fh] = (mapped_fh, 0)
      fh = mapped_fh

    os.lseek(fh, offset, os.SEEK_SET)
    return os.write(fh, buf)

  def create(self, path, mode, fi=None):
    _, rw = self._truncate(path)
    if not os.path.exists(os.path.dirname(rw)):
      os.makedirs(os.path.dirname(rw))
    return os.open(rw, os.O_WRONLY | os.O_CREAT, mode)

  def readdir(self, path, fh):
    ro, rw = self._truncate(path)
    dirents = set(['.', '..'])
    if os.path.isdir(ro):
      dirents.update(os.listdir(ro))
    # TODO - when renaming, make sure to fix FD's and to
    # filter this list of entries to hide things in RO

    if os.path.isdir(rw):
      dirents.update(os.listdir(rw))
    return list(dirents)
  
  def rename(self, old, new):
    def _rename(path, root):
      if root == self._ro:
        self._hidden.append(path)

      _, rw = self._truncate(new)
      if not os.path.exists(os.path.dirname(rw)):
        os.makedirs(os.path.dirname(rw))

      if root == self._ro:
        shutil.copyfile(path, rw)
      else:
        shutil.move(path, rw)
      

    return self._fallback_on_read(old, _rename)

  

  # Not implemented

  def utimens(self, path, times=None):
    pass

  def truncate(self, path, length, fh=None):
    pass





def run_fuse_thread(mount, ro, rw):
  fuse.FUSE(FuseWrapper(ro, rw), mount,
    nothreads=True,
    foreground=True)

class FuseCTX(object):
  def __init__(self, mount, ro, rw):
    self._mount = mount
    self._ro = ro
    self._rw = rw

  def __enter__(self):
    self._oldsignal = signal.signal(signal.SIGINT, self._quit)
    self._thread = multiprocessing.Process(target=run_fuse_thread,
      args=(self._mount, self._ro, self._rw))
    self._thread.start()
    self._ensure_mount()

  def _ensure_mount(self):
    while not os.path.ismount(self._mount):
      pass

  def _quit(self):
    os.system('fusermount -u {}'.format(self._mount))
    self._thread.join()
    signal.signal(signal.SIGINT, self._oldsignal)

  def __exit__(self, *args):
    self._quit()


if __name__ == '__main__':
  with FuseCTX(sys.argv[1], sys.argv[2], sys.argv[3]):
    f = open('{}/foo.txt'.format(sys.argv[1]), 'w+')
    f.write('barbarbar')
    f.close()
  
  