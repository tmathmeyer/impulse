#!/usr/bin/env python3

import collections
import errno
import fuse
import os
import shutil
import signal
import sys
import threading


class FuseWrapper(fuse.Operations):
  def __init__(self, ro, rw):
    self._ro = ro
    self._rw = rw
    self._cow_fds = collections.defaultdict(dict)
    self._fd_remap = {}

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
        print('copying {} to {}'.format(ro, rw))
      return operation(rw)
    else:
      return on_fail(path)

  def _fallback_on_read(self, path, operation):
    ro, rw = self._truncate(path)
    if os.path.exists(rw):
      return operation(rw, self._rw)
    return operation(ro, self._ro)

  def _access_fail(self, path):
    print('failed to access file = {}'.format(path))
    raise fuse.FuseOSError(errno.EACCES)





  # Copy on write methods

  def chmod(self, path, mode):
    print('WTF', file=sys.stderr)
    def _chmod(path):
      return os.chmod(path, mode)
    return self._copy_on_write(path, _chmod, self._access_fail)

  def chown(self, path, uid, gid):
    print('WTF', file=sys.stderr)
    def _chown(path):
      return os.chown(path, mode)
    return self._copy_on_write(path, _chown, self._access_fail)

  def symlink(self, name, target):
    print('WTF', file=sys.stderr)
    def _ensure_target(target):
      _, rw = self._truncate(name)
      return os.symlink(rw, target)
    return _copy_on_write(target, _ensure_target)






  # Write from scratch - or - delete methods

  def mknod(self, path, mode, dev):
    print('WTF', file=sys.stderr)
    _, path = self._truncate(path)
    return os.mknod(path, mode, dev)
  
  def rmdir(self, path):
    print('WTF', file=sys.stderr)
    _, path = self._truncate(path)
    return os.rmdir(path)

  def mkdir(self, path, mode):
    print('WTF', file=sys.stderr)
    _, path = self._truncate(path)
    return os.mkdir(path, mode)

  def unlink(self, path):
    print('WTF', file=sys.stderr)
    raise "unlink not defined"

  def link(self, target, name):
    print('WTF', file=sys.stderr)
    return self._operations.link(path, target, name)




  # Readonly methods

  def getattr(self, path, fh=None):
    print('getattr {}'.format(path), file=sys.stderr)
    def _getattr(path, _):
      st = os.lstat(path)
      return {k:getattr(st, k) for k in (
        'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink',
        'st_size', 'st_uid')}
    return self._fallback_on_read(path, _getattr)
    
  def readlink(self, path):
    def _readlink(path, root):
      pathname = os.readlink(path)
      if pathname.startswith('/'):
        return os.path.relpath(pathname, root)
      return pathname
    return self._fallback_on_read(path, _readlink)

  def statfs(self, path):
    print('ststfs {}'.format(path), file=sys.stderr)
    def _statfs(path, _):
      stv = os.statvfs(path)
      return {k:getattr(stv, k) for k in (
        'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail', 'f_ffree',
        'f_files', 'f_flag', 'f_frsize', 'f_namemax')}
    return self._fallback_on_read(path, _statfs)

  def access(self, path, mode):
    print('access {}'.format(path), file=sys.stderr)
    def _access(path, _):
      if not os.access(path, mode):
        self._access_fail(path)
    return self._fallback_on_read(path, _access)




  # IO methods

  def open(self, path, flags):
    print('open {}'.format(path), file=sys.stderr)
    def _open(path, _):
      print('open RO', file=sys.stderr)
      fd = os.open(path, flags)
      print('fd = {}'.format(fd), file=sys.stderr)
      return fd

    def _cow_open(_path, root):
      print('open COW', file=sys.stderr)
      fd = os.open(_path, flags)
      if root == self._ro:
        self._cow_fds[path][fd] = (-1, flags)
      print('fd = {}'.format(fd), file=sys.stderr)
      return fd

    fd = None
    if flags & (os.O_RDONLY|os.O_WRONLY|os.O_RDWR) == os.O_RDONLY:
      fd = self._fallback_on_read(path, _open)
    else:
      fd = self._fallback_on_read(path, _cow_open)

    print('retfd = {}'.format(fd))
    return fd

  def read(self, path, length, offset, fh):
    print('read {}'.format(path), file=sys.stderr)
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    os.lseek(fh, offset, os.SEEK_SET)
    return os.read(fh, length)

  def flush(self, path, fh):
    print('flush {}'.format(path), file=sys.stderr)
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    return os.fsync(fh)

  def fsync(self, path, fdatasync, fh):
    print('fsync {}'.format(path), file=sys.stderr)
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    return self.flush(path, fh)

  def release(self, path, fh):
    print('release {}'.format(path), file=sys.stderr)
    fd_remap = self._cow_fds[path]
    mapped_fh, _ = self._cow_fds[path].get(fh, (fh, 0))
    if mapped_fh != -1:
      fh = mapped_fh
    return os.close(fh)

  def write(self, path, buf, offset, fh):
    print('write {}'.format(path), file=sys.stderr)
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
    print('create {}'.format(path), file=sys.stderr)
    _, rw = self._truncate(path)
    return os.open(rw, os.O_WRONLY | os.O_CREAT, mode)

  def readdir(self, path, fh):
    print('readdir {}'.format(path), file=sys.stderr)
    ro, rw = self._truncate(path)
    dirents = set(['.', '..'])
    if os.path.isdir(ro):
      dirents.update(os.listdir(ro))
    if os.path.isdir(rw):
      dirents.update(os.listdir(rw))
    
    # TODO - when renaming, make sure to fix FD's and to
    # filter this list of entries to hide things in RO
    return list(dirents)
  
  

  # Not implemented

  def rename(self, old, new):
    print('skipping rename on "{}" -> "{}"'.format(old, new), file=sys.stderr)
    pass

  def utimens(self, path, times=None):
    print('skipping utimens on "{}"'.format(path), file=sys.stderr)
    pass

  def truncate(self, path, length, fh=None):
    print('skipping truncation on "{}"'.format(path), file=sys.stderr)
    pass





def run_fuse_thread(mount, ro, rw):
  print("mounting ro='{}' and rw='{}' at '{}'".format(
    ro, rw, mount))
  fuse.FUSE(FuseWrapper(ro, rw), mount,
    nothreads=False,
    foreground=True)

class FuseCTX(object):
  def __init__(self, mount, ro, rw):
    self._mount = mount
    self._ro = ro
    self._rw = rw

  def __enter__(self):
    self._thread = threading.Thread(target=run_fuse_thread,
      args=(self._mount, self._ro, self._rw))
    self._thread.start()

  def __exit__(self, *args):
    print('attempting to kill it!')
    signal.pthread_kill(self._thread.ident, signal.SIGTERM)

