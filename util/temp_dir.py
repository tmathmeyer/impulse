import os
import tempfile

class ScopedTempDirectory(object):
  def __init__(self, temp_directory=None):
    self._temp_directory = temp_directory
    self._old_directory = None
    self._delete_on_exit = not temp_directory

  def __enter__(self):
    if not self._temp_directory:
      self._temp_directory = tempfile.mkdtemp()
    self._old_directory = os.getcwd()
    os.chdir(self._temp_directory)

  def __exit__(self, *args):
    os.chdir(self._old_directory)
    if self._delete_on_exit:
      os.rmdir(self._temp_directory)