from __future__ import annotations

import glob
import os
import shutil
import signal
import subprocess
import threading
import zipfile
import zipimport
import typing

from impulse.util import temp_dir


class ResourceOpener(object):
  """Handles opening resources that may be packaged inside a zip file."""
  __slots__=('_extracted', '_extracted_cleanup', '_oldsignal')

  def __init__(self) -> None:
    self._extracted:str | None=None
    self._extracted_cleanup=False
    self._oldsignal:object=None

  def __del__(self) -> None:
    self._Quit()

  def _Quit(self, *args:object) -> None:
    """Cleans up extracted resources."""
    extracted, do_clean=self._extracted, self._extracted_cleanup
    self._extracted, self._extracted_cleanup=None, None
    if extracted and do_clean:
      try:
        import shutil
        shutil.rmtree(extracted)
      except (ImportError, TypeError):
        # Probably a shutdown, do nothing
        pass
    self._TeardownSignal()

  def Open(self, filename:str, mode:str='r') -> typing.IO:
    """Opens a resource file."""
    return open(self.Get(filename), mode)

  def Read(self, filename:str) -> str:
    """Reads the content of a resource file."""
    with open(self.Get(filename), 'r') as f:
      return f.read()

  def OpenGlob(self, fileRegex:str, mode:str='r') -> typing.IO | None:
    """Opens the first file matching a glob pattern."""
    for file in glob.glob(self.Get(fileRegex)):
      return open(file, mode)
    return None

  def Get(self, filename:str, binary:bool=False) -> str:
    """Returns the absolute path to a resource file."""
    if self._extracted is None:
      self._Extract()
    if self._extracted is None:
      raise FileNotFoundError(filename)
    result=os.path.join(self._extracted, filename)
    if binary:
      os.system(f'chmod +x {result}')
    return result

  def Dir(self) -> str:
    """Returns the directory where resources are extracted."""
    if self._extracted is None:
      self._Extract()
    if self._extracted is None:
      raise NotADirectoryError()
    return self._extracted

  def _CreateSignal(self) -> None:
    """Registers a signal handler for cleanup on exit."""
    if threading.current_thread() is threading.main_thread():
      self._oldsignal=signal.signal(signal.SIGINT, self._Quit)

  def _TeardownSignal(self) -> None:
    """Restores the original signal handler."""
    if self._oldsignal is None:
      return
    try:
      if threading.current_thread() is threading.main_thread():
        oldsignal, self._oldsignal=self._oldsignal, None
        signal.signal(signal.SIGINT, oldsignal) # type:ignore
    except (AttributeError, ImportError):
      pass

  def _Extract(self) -> None:
    """Extracts resources if running from a zip file."""
    if not isinstance(__loader__, zipimport.zipimporter): # type:ignore
      self._extracted='.'
    else:
      try:
        self._CreateSignal()
        temp_directory=temp_dir.CreateDangerousLifetimeDirectory()
        # type:ignore
        with zipfile.ZipFile(__loader__.archive, 'r') as zip_ref:
          zip_ref.extractall(temp_directory)
        self._extracted_cleanup=True
        self._extracted=temp_directory
      except Exception as error:
        print(error)


Resources=ResourceOpener()
