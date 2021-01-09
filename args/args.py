
import abc
import argparse
import inspect
import os
import typing
import shlex
import subprocess
import sys

class ArgComplete(metaclass=abc.ABCMeta):
  def __init__(self, wrapped:typing.Optional[str]):
    self.wrapped = wrapped

  @classmethod
  @abc.abstractmethod
  def get_completion_list(self, stub):
    raise NotImplementedError()

  def value(self) -> typing.Optional[str]:
    return self.wrapped


class DefaultArgComplete(ArgComplete):
  @classmethod
  def get_completion_list(self, stub):
    raise NotImplementedError()


class Directory(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    dirs = list(cls._get_directories(stub=stub))
    if len(dirs) == 1:
      yield dirs[0]
      yield dirs[0] + '/'
    else:
      for d in dirs:
        yield d

  @classmethod
  def _get_directories(cls, stub):
    shell = '/bin/sh'
    if not os.path.exists(shell):
      return
    if not os.path.islink(shell):
      return

    cmd = 'compgen -o bashdefault -o default -o nospace -F _cd {}'.format(stub)
    stdout =  subprocess.Popen(cmd, shell=True,
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in stdout.stdout.readlines():
      f = line.decode().replace('\n', '').replace('//', '/')
      if os.path.isdir(f):
        yield f


class File(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub):
    yield from cls._get_directories(stub=stub)

  @classmethod
  def _get_directories(cls, stub):
    shell = '/bin/sh'
    if not os.path.exists(shell):
      return
    if not os.path.islink(shell):
      return

    cmd = 'compgen -o bashdefault -o default -o nospace -F _ls {}'.format(stub)
    stdout =  subprocess.Popen(cmd, shell=True,
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in stdout.stdout.readlines():
      f = line.decode().replace('\n', '').replace('//', '/')
      if os.path.exists(f):
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
    for arg, info in inspect.signature(func).parameters.items():
      if hasattr(args, arg):
        _args[arg] = getattr(args, arg)
      if issubclass(info.annotation, ArgComplete) and _args[arg] == None:
        _args[arg] = DefaultArgComplete(None)
    func(**_args)

  def _invalid_syntax(self, func, argname, missing):
    decorator_call = inspect.stack()[2]
    msg = 'Argument {} requires {}.'.format(argname, missing)
    filepath = decorator_call.filename
    lineno = decorator_call.lineno
    codeline = decorator_call.code_context
    raise SyntaxError(msg, (filepath, lineno, 0, codeline))

  def _get_sub_completion(self, needs_new_token, cmdargs, args):
    # dropped command and binary
    def filter_flags_opts_no_requirements(F):
      for argname, argtype in cmdargs.items():
        if argname.startswith('-') and argname.startswith(F):
          yield argname
        elif not argname.startswith('-') and not F.startswith('-') and argtype:
          yield from argtype.get_completion_list(F)

    # If we have no args at all, populate everything
    if not len(args):
      assert needs_new_token
      yield from filter_flags_opts_no_requirements('')

    elif len(args) == 1:
      if args[0].startswith('-'):
        if needs_new_token:
          assert args[0] in cmdargs
        flag_param_type = cmdargs.get(args[0], None)
        if flag_param_type:
          # this flag has a value, so we should try to populate it
          yield from flag_param_type.get_completion_list('')
          if not needs_new_token:
            # There could be substring flags too
            yield from filter_flags_opts_no_requirements(args[0])
        else:
          yield from filter_flags_opts_no_requirements('')
      else:
        yield from filter_flags_opts_no_requirements(
          '' if needs_new_token else args[0])

    elif len(args) == 2:
      (penultimate, last) = args
      if needs_new_token:
        yield from self._get_sub_completion(needs_new_token, cmdargs, [last])
      elif not penultimate.startswith('-'):
        # penultimate was not a flag, populate normally
        yield from filter_flags_opts_no_requirements(last)
      elif penultimate in cmdargs:
        flag_param_type = cmdargs.get(penultimate)
        if not flag_param_type:
          # The --flag takes no args, so populate normally
          yield from filter_flags_opts_no_requirements(last)
        else:
          yield from flag_param_type.get_completion_list(last)

    else: # more than two args, trim them
      yield from self._get_sub_completion(needs_new_token, cmdargs, args[-2:])

  def _print_commands_matching(self, stub, operation):
    for methodname in self._methods.keys():
      if methodname.startswith(stub):
        operation(methodname)

  def _print_completion_for_testing(self, args, tst):
    os.environ['_LOCAL_COMP_LINE'] = 'bin ' + ' '.join(args)
    return self._print_completion(tst)

  def _print_completion(self, operation=print):
    if '_LOCAL_COMP_LINE' not in os.environ:
      return

    COMP_LINE = os.environ.get('_LOCAL_COMP_LINE')
    binary, *args = shlex.split(COMP_LINE)
    needs_new_token = COMP_LINE.endswith(' ')

    # So far just the binary has been typed
    if len(args) == 0:
      if needs_new_token:
        self._print_commands_matching('', operation)
      return

    # The cursor has no space after the subcommand
    if len(args) == 1 and not needs_new_token:
      self._print_commands_matching(args[0], operation)
      return

    if needs_new_token:
      if args[0] not in self._methods:
        return # invalid subcommand, do not complete anything

    cmd_args = self._methods[args[0]]['args']
    for value in self._get_sub_completion(needs_new_token, cmd_args, args[1:]):
      operation(value)

  def eval(self):
    if self._complete and len(sys.argv) >= 2 and sys.argv[1] == '--iacomplete':
      self._print_completion()
      return

    parsed = self._parser.parse_args()

    if 'task' in parsed:
      self._exec_func(self._methods[parsed.task]['func'], parsed)
    else:
      self._parser.print_help(sys.stderr)
