from __future__ import annotations

import os
import tempfile
import typing


class ScopedTempDirectory(object):
  """
  Context manager that creates a temporary directory, changes the working
  directory to it, and optionally cleans it up on exit.
  """
  def __init__(self, temp_directory:str|None=None,
               delete_non_empty:bool=False):
    self._temp_directory=temp_directory
    self._old_directory:str|None=None
    self._delete_on_exit=not temp_directory
    self._delete_non_empty=delete_non_empty
    self._exited=True

  def _getcwd(self) -> str:
    """Robustly gets the current working directory."""
    while True:
      try:
        return os.getcwd()
      except Exception:
        # Sometimes getcwd fails if the directory was deleted
        os.chdir('/')

  def __enter__(self) -> str:
    self._exited=False
    if not self._temp_directory:
      self._temp_directory=tempfile.mkdtemp()
    self._old_directory=self._getcwd()
    os.chdir(self._temp_directory)
    return self._temp_directory

  def __exit__(self, *args:object, **kwargs:object) -> None:
    if self._exited:
      return
    self._exited=True
    if self._old_directory:
      os.chdir(self._old_directory)
    if self._delete_on_exit and self._temp_directory:
      if self._delete_non_empty:
        import shutil
        shutil.rmtree(self._temp_directory,ignore_errors=True)
      else:
        try:
          os.rmdir(self._temp_directory)
        except OSError:
          pass


def CreateDangerousLifetimeDirectory() -> str:
  """Creates a temporary directory that must be manually cleaned up."""
  return tempfile.mkdtemp()
