
import glob
import os
import shutil
import signal
import subprocess
import threading
import zipfile
import zipimport

from impulse.util import temp_dir


class ResourceOpener(object):
  __slots__ = ('_extracted', '_extracted_cleanup', '_oldsignal')
  def __init__(self):
    self._extracted = None
    self._extracted_cleanup = False
    self._oldsignal = None

  def __del__(self):
    self._Quit()

  def _Quit(self):
    extracted, do_clean = self._extracted, self._extracted_cleanup
    self._extracted, self._extracted_cleanup = None, None
    if extracted and do_clean:
      import shutil
      shutil.rmtree(extracted)
    self._TeardownSignal()

  def Open(self, filename, mode='r'):
    return open(self.Get(filename), mode)

  def OpenGlob(self, fileRegex, mode='r'):
    for file in glob.glob(self.Get(fileRegex)):
      return open(file, mode)

  def Get(self, filename):
    if self._extracted == None:
      self._Extract()
    if self._extracted == None:
      raise FileNotFoundError(filename)
    return os.path.join(self._extracted, filename)

  def Dir(self):
    if self._extracted == None:
      self._Extract()
    if self._extracted == None:
      raise NotADirectoryError()
    return self._extracted

  def _CreateSignal(self):
    if threading.current_thread() is threading.main_thread():
      self._oldsignal = signal.signal(signal.SIGINT, self._Quit)

  def _TeardownSignal(self):
    if self._oldsignal is None:
      return
    if threading.current_thread() is threading.main_thread():
      oldsignal, self._oldsignal = self._oldsignal, None
      signal.signal(signal.SIGINT, oldsignal)

  def _Extract(self):
    if not isinstance(__loader__, zipimport.zipimporter):
      self._extracted = '.'
    else:
      try:
        self._CreateSignal()
        temp_directory = temp_dir.CreateDangerousLifetimeDirectory()
        with zipfile.ZipFile(__loader__.archive, 'r') as zip_ref:
          zip_ref.extractall(temp_directory)
        self._extracted_cleanup = True
        self._extracted = temp_directory
      except Exception as error:
        print(error)


Resources = ResourceOpener()