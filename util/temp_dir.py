import os
import tempfile

class ScopedTempDirectory(object):
  def __init__(self, temp_directory=None, delete_non_empty=False):
    self._temp_directory = temp_directory
    self._old_directory = None
    self._delete_on_exit = not temp_directory
    self._delete_non_empty = delete_non_empty

  def _getcwd(self):
    while True:
      try:
        return os.getcwd()
      except:
        pass

  def __enter__(self):
    if not self._temp_directory:
      self._temp_directory = tempfile.mkdtemp()
    self._old_directory = self._getcwd()
    os.chdir(self._temp_directory)

  def __exit__(self, *args):
    os.chdir(self._old_directory)
    if self._delete_on_exit:
      if self._delete_non_empty:
        os.system('rm -rf {}'.format(self._temp_directory))
      else:
        os.rmdir(self._temp_directory)

def CreateDangerousLifetimeDirectory():
  return tempfile.mkdtemp()