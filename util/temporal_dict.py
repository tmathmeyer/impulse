
import time


__FILE_PRIVATE_NONE__ = object()


class TemporalDict(object):
  def __init__(self, hours=0, minutes=0, seconds=0):
    self._storage = {}
    self._longevity = (((hours * 60) + minutes) * 60) + seconds
    self._last_purge = int(time.time())
    self._next_purge = 0

  def _purge(self):
    current_time = int(time.time())
    if current_time < self._next_purge:
      return
    newstorage = {}
    for key, value in self._storage.items():
      purge_at, value = value
      if purge_at > current_time:
        newstorage[key] = (purge_at, value)
    self._storage = newstorage

  def __len__(self):
    self._purge()
    return len(self._storage)

  def __length_hint__(self):
    return len(self._storage)

  def __getitem__(self, key):
    self._purge()

    # Don't catch the KeyError, let it go up.
    _, value = self._storage[key]
    self._storage[key] = (self._longevity + int(time.time()), value)
    return value

  def __setitem__(self, key, value):
    self._purge()
    self._storage[key] = (self._longevity + int(time.time()), value)

  def __delitem__(self, key):
    self._purge()
    del storage[key]

  def __iter__(self):
    self._purge()
    yield from self._storage

  def __contains__(self, key):
    self._purge()
    return key in self._storage

  def get(self, key, default=__FILE_PRIVATE_NONE__):
    self._purge()
    result = None
    if default is __FILE_PRIVATE_NONE__:
      result = self._storage.get(key)[1]
    else:
      result = self._storage.get(key, default)[1]

    self._storage[key] = (self._longevity + int(time.time()), value)

  def items(self):
    for k, v in self._storage.items():
      yield k, v[1]

  def keys(self):
    return self._storage.keys()

  def values(self):
    for v in self._storage.values():
      yield v[1]