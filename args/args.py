
import argparse
import inspect
import sys


def target(parser):
  def decorator(func):
    helpmsg = func.__doc__ or func.__name__
    task = parser.add_parser(
      func.__name__,
      help=helpmsg.splitlines()[0])
    task.set_defaults(task=func.__name__)

    args_name = inspect.getargspec(func)[0]
    for arg in args_name:
      if arg != 'debug':
        task.add_argument(arg, metavar=arg[0].upper(), type=str)

    task.add_argument('--debug', default=False, action='store_true')

    def __stub__(parsed):
      try:
        func(**dict((n, getattr(parsed, n)) for n in args_name))
      except recursive_loader.SilentException:
        pass
    return __stub__

  return decorator


class ArgumentParser(object):
  def __init__(self):
    self._parser = argparse.ArgumentParser()
    self._subparser = self._parser.add_subparsers(title='tasks')
    self._methods = {}

  def __call__(self, func):
    methodname = func.__name__
    methodhelp = func.__doc__ or methodname
    typespec = func.__annotations__

    self._methods[methodname] = func
    task = self._subparser.add_parser(
      methodname, help=methodhelp.splitlines()[0])

    task.set_defaults(task=methodname)
    methodargs = inspect.getfullargspec(func)[0]

    for arg, info in inspect.signature(func).parameters.items():
      argtype = info.annotation
      default = info.default

      if argtype == inspect.Parameter.empty:
        self._invalid_syntax(func, arg)
        return

      action = 'store'
      if argtype == bool:
        action = 'store_true'

      if default == inspect.Parameter.empty:
        task.add_argument(arg, type=argtype, action=action)
      elif argtype == bool:
        task.add_argument('--'+arg, default=default, action=action)
      else:
        task.add_argument('--'+arg, type=argtype, default=default)
    return func

  def _exec_func(self, func, args):
    _args = {}
    for arg, _ in inspect.signature(func).parameters.items():
      if hasattr(args, arg):
        _args[arg] = getattr(args, arg)
    func(**_args)

  def _invalid_syntax(self, func, argname):
    decorator_call = inspect.stack()[2]
    msg = 'Argument {} requires type annotation.'.format(argname)
    filepath = decorator_call.filename
    lineno = decorator_call.lineno
    codeline = decorator_call.code_context
    raise SyntaxError(msg, (filepath, lineno, 0, codeline))

  def eval(self):
    parsed = self._parser.parse_args()
    if 'task' in parsed:
      self._exec_func(self._methods[parsed.task], parsed)
    else:
      self._parser.print_help(sys.stderr)
