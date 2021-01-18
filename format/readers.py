
from impulse.core import exceptions
from impulse.core import interface
from impulse.util import typecheck


class LocalEnvironParser(dict):
  @typecheck.Ensure
  def __init__(self, reader:'FileReader'):
    self._reader = reader
    self._data = {}

  def __getitem__(self, name):
    method = getattr(self._reader, f'call_{name}', None)
    if method is not None:
      return method
    def wrapper(*args, **kwargs):
      return getattr(self._reader, 'call')(name, args, kwargs)
    return wrapper

  def __setitem__(self, name, value):
    self._data[name] = value

  def GetExecData(self):
    return self._data


class FileReader():
  def __init__(self):
    self._environ = LocalEnvironParser(self)
    self._filename = None

  def ReadFile(self, file):
    self._filename = file
    with open(file) as f:
      try:
        exec(compile(f.read(), file, 'exec'), self._environ)
      except exceptions.ImpulseBaseException as e:
        raise exceptions.ImpulseBaseException(
          f'{str(e)}\nFound parsing {file}') from None

  def GetFile(self):
    return self._filename


@interface.IFace
class BuildFileReaderImpl(FileReader):
  
  def call_langs(self, *langs):
    pass

  def call_load(self, *loads):
    pass

  def call_pattern(self, pattern):
    pass

  def call_git_repo(self, url, repo, target):
    pass

  def call(self, name, args, kwargs):
    pass
