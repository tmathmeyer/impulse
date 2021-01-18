
import inspect
import sys
import typing

from impulse.core import debug


def CheckType(generics:dict, actual, expected) -> (type, type):
  if type(expected) == list:
    if type(actual) != list:
      return type(actual), expected

    if not len(expected) == 1:
      raise TypeError('Expected list types may only have one element')

    exp2 = expected[0]
    for e in actual:
      actual_type, expected_type = CheckType(generics, e, exp2)
      if actual_type is not None:
        return [actual_type], [expected_type]
    return None, None

  if type(expected) == typing.TypeVar:
    generic_name = expected.__name__
    if generic_name not in generics:
      generics[generic_name] = type(actual)
    expected = generics[generic_name]

  if not issubclass(type(actual), expected):
    return type(actual), expected

  return None, None


class FunctionWrapper():
  def __init__(self, fn):
    self._func = fn
    self._argspec = inspect.getfullargspec(fn)
    self._spec = dict(self._argspec.annotations.items())
    self._generics = {}

  def __call__(self, *args, **kwargs):
    self._generics = {}
    self._CheckArgs(args, kwargs)
    return_value = self._func(*args, **kwargs)
    self._CheckReturn(return_value)
    return return_value

  def _CheckReturn(self, actual):
    if 'return' not in self._spec:
      return
    if type(self._spec['return']) == str:
      module = sys.modules[self._func.__module__]
      self._spec['return'] = getattr(module, self._spec[arg], None)
    actual_type, expected_type = CheckType(
      self._generics, actual, self._spec['return'])
    if actual_type is not None:
      raise TypeError(
        f'Expected type {expected_type} for return, got {actual_type}')

  def _CheckArgs(self, args, kwargs):
    argvalues = self._GetArgValues(args, kwargs)
    for arg in self._spec:
      if type(self._spec[arg]) == str:
        module = sys.modules[self._func.__module__]
        self._spec[arg] = getattr(module, self._spec[arg], None)
      if arg == 'return':
        continue
      actual_type, expected_type = CheckType(
        self._generics, argvalues[arg], self._spec[arg])
      if actual_type is not None:
        raise TypeError(
          f'Expected type {expected_type} for arg "{arg}", got {actual_type}')

  def _GetArgValues(self, args, kwargs):
    result = {a:kwargs.get(a, None) for a in self._spec}
    if self._argspec.defaults:
      last_args = self._argspec.args[-len(self._argspec.defaults):]
      for a, b in zip(last_args, self._argspec.defaults):
        result[a] = b
    for a, b in zip(self._argspec.args[:len(args)], args):
      result[a] = b
    return result


def Ensure(fn):
  def metawrapper(*args, **kwargs):
    return FunctionWrapper(fn)(*args, **kwargs)
  if debug.IsDebug('typing'):
    return metawrapper
  return fn