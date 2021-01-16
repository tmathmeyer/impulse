
import inspect

def Ensure(fn, debug=lambda x:x):
  argspec = inspect.getfullargspec(fn)
  annotations = argspec.annotations
  def replacement(*args, **kwargs):
    argvalues = {a:kwargs.get(a, None) for a in argspec.args}
    if argspec.defaults:
      last_args = argspec.args[-len(argspec.defaults):]
      for a,b in zip(last_args, argspec.defaults):
        argvalues[a] = b
    for a,b in zip(argspec.args[:len(args)], args):
      argvalues[a] = b

    debug(argvalues)
    debug(argspec)
    for n,t in argspec.annotations.items():
      if n == 'return':
        continue
      if type(t) != str:
        actual = str(type(argvalues[n]))
        if not issubclass(type(argvalues[n]), t):
          raise TypeError(
            f'Expected type {str(t)} for "{n}", got {actual}')
      else:
        actual = str(type(argvalues[n]))
        expanded = f"<class '{fn.__module__}.{t}'>"
        if t != actual and expanded != actual:
          raise TypeError(
            f'Expected type {t} or {expanded} for "{n}", got {actual}')

    retval = fn(*args, **kwargs)
    if 'return' in argspec.annotations:
      t = argspec.annotations['return']
      if type(t) != str:
        if not issubclass(type(retval), t):
          raise TypeError(
            f'Expected type {str(t)} for return, got {type(retval)}')
      else:
        actual = str(type(retval))
        expanded = f"<class '{fn.__module__}.{t}'>"
        if t != actual and expanded != actual:
          raise TypeError(
            f'Expected type {t} or {expanded} for return, got {actual}')


    return retval
  return replacement

def Debug(fn):
  return Ensure(fn, print)