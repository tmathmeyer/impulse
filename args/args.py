
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


class File(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    cmd = 'compgen -o bashdefault -o default -o nospace -F _ls {}'.format(stub)
    stdout =  subprocess.Popen(cmd, shell=True,
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in stdout.stdout.readlines():
      f = line.decode().replace('\n', '')
      if os.path.isdir(f):
        yield f + '/'
      else:
        yield f

class Directory(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    if os.path.isdir(stub):
      yield stub
      if not stub.endswith('/'):
        stub += '/'
    cmd = 'compgen -o bashdefault -o default -o nospace -F _ls {}'.format(stub)
    stdout =  subprocess.Popen(cmd, shell=True,
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in stdout.stdout.readlines():
      f = line.decode().replace('\n', '')
      if os.path.isdir(f):
        yield f
        yield f + '/'


class ArgumentParser(object):
  def __init__(self, complete=False):
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
        self._invalid_syntax(func, arg)
        return

      action = 'store'
      if argtype == bool:
        action = 'store_true'

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

  def _invalid_syntax(self, func, argname):
    decorator_call = inspect.stack()[2]
    msg = 'Argument {} requires type annotation.'.format(argname)
    filepath = decorator_call.filename
    lineno = decorator_call.lineno
    codeline = decorator_call.code_context
    raise SyntaxError(msg, (filepath, lineno, 0, codeline))




  def _get_values_for_type(self, argtype, stub):
    if argtype not in (str, None):
      for result in argtype.get_completion_list(stub):
        yield result

  def _provide_all_flags_and_options(self, cmdargs):
    for argname, argtype in cmdargs.items():
      if argname.startswith('-'):
        yield argname
      else:
        for value in self._get_values_for_type(argtype, ''):
          yield value

  def _when_last_arg_is_flag(self, cmdargs, stub):
    if stub in cmdargs: # this exact flag exists
      if cmdargs[stub]: # this flag has options
        for value in self._get_values_for_type(cmdargs[stub], ''):
          yield value
      else: # this flag has no options
        for value in self._provide_all_flags_and_options(cmdargs):
          yield value

    for flagname in cmdargs.keys():
      if flagname.startswith(stub) and flagname != stub:
        yield flagname

  def _last_arg_is_not_flag_but_last_was(self, cmdargs, stub, flag):
    if flag in cmdargs:
      if cmdargs[flag]: # previous flag takes args
        for value in self._get_values_for_type(cmdargs[flag], stub):
          yield value
      else: # previous flag takes no args
        for value in self._when_last_arg_is_not_flag(cmdargs, stub):
          yield value
    else:
      raise LookupError(flag)

  def _when_last_arg_is_not_flag(self, cmdargs, stub, flag=None):
    if flag and flag.startswith('-'):
      for value in self._last_arg_is_not_flag_but_last_was(cmdargs, stub, flag):
        yield value
    else:
      for argname, argtype in cmdargs.items():
        if not argname.startswith('-'):
          for value in self._get_values_for_type(argtype, stub):
            yield value

  def _handle_command(self, cmdargs, argv):
    if len(argv) == 0:
      for value in self._provide_all_flags_and_options(cmdargs):
        print(value)

    if len(argv) == 1:
      if argv[0] == '':
        self._handle_command(cmdargs, [])
      elif argv[0].startswith('-'):
        for value in self._when_last_arg_is_flag(cmdargs, argv[0]):
          print(value)
      else:
        for value in self._when_last_arg_is_not_flag(cmdargs, argv[0]):
          print(value)

    if len(argv) == 2:
      if argv[1].startswith('-'):
        self._handle_command(cmdargs, [argv[1]])
      else:
        for value in self._when_last_arg_is_not_flag(cmdargs, argv[1], argv[0]):
          print(value)

    if len(argv) > 2:
      self._handle_command(cmdargs, argv[-2:])

  def _print_completion_options(self, args):
    if len(args) == 0:
      for methodname in self._methods.keys():
        print(methodname)
      return

    if len(args) == 1:
      if args[0] in self._methods:
        args.append('')
      else:
        self._print_possible_commands(args[0])
        return

    if len(args) > 1 and args[0] in self._methods:
      self._handle_command(self._methods[args[0]]['args'], args[1:])
      return

  def _print_possible_commands(self, partial_cmd):
    for methodname in self._methods.keys():
      if methodname.startswith(partial_cmd):
        print(methodname)

  def eval(self):
    if self._complete and len(sys.argv) >= 2 and sys.argv[1] == '--iacomplete':
      self._print_completion_options(sys.argv[2:])
      return

    parsed = self._parser.parse_args()

    if 'task' in parsed:
      self._exec_func(self._methods[parsed.task]['func'], parsed)
    else:
      self._parser.print_help(sys.stderr)