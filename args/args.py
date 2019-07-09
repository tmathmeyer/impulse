
import abc
import argparse
import inspect
import os
import subprocess
import sys

class ArgComplete(metaclass=abc.ABCMeta):

  def __init__(self, wrapped):
    self.wrapped = wrapped

  @classmethod
  @abc.abstractmethod
  def get_completion_list(self, stub):
    raise NotImplementedError()


class Directory(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    assert(stub[-1] == '?')
    dirs = list(cls._get_directories(stub[:-1]))
    if len(dirs) == 1:
      yield dirs[0]
      yield dirs[0] + '/'
    else:
      for d in dirs:
        yield d

  @classmethod
  def _get_directories(cls, stub):
    cmd = 'compgen -o bashdefault -o default -o nospace -F _cd {}'.format(stub)
    stdout =  subprocess.Popen(cmd, shell=True,
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in stdout.stdout.readlines():
      f = line.decode().replace('\n', '').replace('//', '/')
      if os.path.isdir(f):
        yield f


class ArgumentParser(object):
  def __init__(self, complete=True):
    self._parser = argparse.ArgumentParser()
    self._subparser = self._parser.add_subparsers(title='tasks')
    self._methods = {}
    self._complete = complete

  def __call__(self, func):
    methodname = func.__name__
    methodhelp = func.__doc__ or methodname
    typespec = func.__annotations__

    self._methods[methodname] = {
      'func': func,
      'args': {}
    }
    task = self._subparser.add_parser(
      methodname, help=methodhelp.splitlines()[0])

    task.set_defaults(task=methodname)
    methodargs = inspect.getfullargspec(func)[0]

    for arg, info in inspect.signature(func).parameters.items():
      argtype = info.annotation
      default = info.default

      if argtype == inspect.Parameter.empty:
        self._invalid_syntax(func, arg, 'type annotation')
        return

      action = 'store'
      if argtype == bool:
        action = 'store_true'
        if default == inspect.Parameter.empty:
          self._invalid_syntax(func, arg, 'a default value')

      if default == inspect.Parameter.empty:
        self._methods[methodname]['args'][arg] = argtype
        task.add_argument(arg, type=argtype, action=action)
      elif argtype == bool:
        self._methods[methodname]['args']['--'+arg] = None
        task.add_argument('--'+arg, default=default, action=action)
      else:
        self._methods[methodname]['args']['--'+arg] = argtype
        task.add_argument('--'+arg, type=argtype, default=default)
    return func

  def _exec_func(self, func, args):
    _args = {}
    for arg, _ in inspect.signature(func).parameters.items():
      if hasattr(args, arg):
        userarg = getattr(args, arg)
        if isinstance(userarg, ArgComplete):
          userarg = userarg.wrapped
        _args[arg] = userarg
    func(**_args)

  def _invalid_syntax(self, func, argname, missing):
    decorator_call = inspect.stack()[2]
    msg = 'Argument {} requires {}.'.format(argname, missing)
    filepath = decorator_call.filename
    lineno = decorator_call.lineno
    codeline = decorator_call.code_context
    raise SyntaxError(msg, (filepath, lineno, 0, codeline))

  def _get_options_for_param(self, argtype, param):
    assert(param[-1] == '?')
    if argtype not in (str, None):
      for result in argtype.get_completion_list(param):
        yield result

  def _provide_all_flags_and_options(self, cmdargs):
    for argname, argtype in cmdargs.items():
      if argname.startswith('-'):
        yield argname
      else:
        for value in self._get_options_for_param(argtype, '?'):
          yield value

  def _handle_subargs(self, cmdargs, args):
    # dropped the command and binary so far
    if len(args) == 0:
      raise RuntimeError('cant parse 0 subargs')

    if len(args) == 1:
      if args[0] == '?': # Nothing provided, give args & opts.
        for value in self._provide_all_flags_and_options(cmdargs):
          yield value
      elif args[0].startswith('-'): # Attempting to type a flag.
        for flagname in cmdargs.keys():
          if flagname.startswith(args[0][:-1]):
            yield flagname
      else: # attempting to provide a value, query every non-flag argument.
        for argname, argtype in cmdargs.items():
          if not argname.startswith('-'):
            for value in self._get_options_for_param(argtype, args[0]):
              yield value

    if len(args) == 2:
      if args[0].startswith('--'): # Previous arg was a --flag
        argtype = cmdargs.get(args[0], None)
        if not argtype: # but the flag took no arguments!
          for value in self._handle_subargs(cmdargs, args[-1:]):
            yield value # Nothing else matters, just complete the last arg
        else: # the flag takes arguments, get them
          for value in self._get_options_for_param(argtype, args[1]):
            yield value
      else: # it wasn't a flag, so it doesn't matter
        for value in self._handle_subargs(cmdargs, args[-1:]):
          yield value

    if len(args) > 2:
      for value in self._handle_subargs(cmdargs, args[-2:]):
        yield value

  def _handle_completion(self, args, fn):
    assert(len(args) >= 1)
    # There will always be at least a '?'
    if len(args) == 1:
      command = args[0][:-1]
      for methodname in self._methods.keys():
        if methodname.startswith(command):
          fn(methodname)
      return

    # the command is now:
    # binary <command> {X} {Y} {Z}
    # where Z is either '?' or '{str}?'
    if args[0] not in self._methods:
      return # invalid command, do not complete

    cmdargs = self._methods[args[0]]['args']
    for value in self._handle_subargs(cmdargs, args[1:]):
      fn(value)

  def eval(self):
    if self._complete and len(sys.argv) >= 2 and sys.argv[1] == '--iacomplete':
      self._handle_completion(sys.argv[3:], print)
      return

    parsed = self._parser.parse_args()

    if 'task' in parsed:
      self._exec_func(self._methods[parsed.task]['func'], parsed)
    else:
      self._parser.print_help(sys.stderr)
