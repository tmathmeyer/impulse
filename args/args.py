
import abc
import argparse
import inspect
import os
import types
import typing
import shlex
import subprocess
import sys

class ArgComplete(metaclass=abc.ABCMeta):
  def __init__(self, wrapped:str|None):
    self.wrapped=wrapped

  @classmethod
  @abc.abstractmethod
  def get_completion_list(cls, stub:str) -> typing.Iterator[str]:
    raise NotImplementedError()

  def value(self) -> str|None:
    return self.wrapped


class DefaultArgComplete(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub:str) -> typing.Iterator[str]:
    return iter([])


class Directory(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub:str) -> typing.Iterator[str]:
    dirs=list(cls._get_directories(stub=stub))
    if len(dirs) == 1:
      yield dirs[0]
      yield dirs[0] + '/'
    else:
      for d in dirs:
        yield d

  @classmethod
  def _get_directories(cls, stub:str) -> typing.Iterator[str]:
    shell='/bin/sh'
    if not os.path.exists(shell):
      return
    if not os.path.islink(shell):
      return

    cmd=f'compgen -o bashdefault -o default -o nospace -F _cd {stub}'
    stdout=subprocess.Popen(cmd,
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stream=stdout.stdout
    if stream is not None:
      for line in stream.readlines():
        f=line.decode().replace('\n', '').replace('//', '/')
        if os.path.isdir(f):
          yield f


class File(ArgComplete):
  @classmethod
  def get_completion_list(cls, stub:str) -> typing.Iterator[str]:
    yield from cls._get_directories(stub=stub)

  @classmethod
  def _get_directories(cls, stub:str) -> typing.Iterator[str]:
    shell='/bin/sh'
    if not os.path.exists(shell):
      return
    if not os.path.islink(shell):
      return

    cmd=f'compgen -o bashdefault -o default -o nospace -F _ls {stub}'
    stdout=subprocess.Popen(cmd,
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stream=stdout.stdout
    if stream is not None:
      for line in stream.readlines():
        f=line.decode().replace('\n', '').replace('//', '/')
        if os.path.exists(f):
          yield f


class ArgumentParser(object):
  def __init__(self, complete:bool=True):
    self._parser=argparse.ArgumentParser()
    self._subparser=self._parser.add_subparsers(title='tasks')
    self._methods:dict[str, dict[str, object]]={}
    self._complete=complete

  def __call__(self, func:typing.Callable) -> typing.Callable:
    methodname=func.__name__
    methodhelp=func.__doc__ or methodname

    self._methods[methodname]={
      'func': func,
      'args': {}
    }
    task=self._subparser.add_parser(
      methodname, help=methodhelp.splitlines()[0])

    task.set_defaults(task=methodname)

    try:
        # Pass globals to resolve string forward references
        type_hints = typing.get_type_hints(func, globalns=func.__globals__)
    except Exception:
        type_hints = {k: v.annotation for k, v in \
                      inspect.signature(func).parameters.items()}

    for arg, info in inspect.signature(func).parameters.items():
      argtype=type_hints.get(arg, info.annotation)
      default=info.default

      if argtype == inspect.Parameter.empty:
        self._invalid_syntax(func, arg, 'type annotation')
        return func

      if (type(argtype) == types.UnionType or
          getattr(argtype, '__origin__', None) is typing.Union):
        args_list = getattr(argtype, '__args__', [])
        if len(args_list) == 2 and type(None) in args_list:
           argtype = args_list[0] if args_list[1] == type(None) else args_list[1]

      action='store'
      if argtype == bool:
        action='store_true'
        if default == inspect.Parameter.empty:
          self._invalid_syntax(func, arg, 'a default value')

      if default == inspect.Parameter.empty:
        typing.cast(dict, self._methods[methodname]['args'])[arg]=argtype
        task.add_argument(arg, type=argtype, action=action)
      elif argtype == bool:
        typing.cast(dict, self._methods[methodname]['args'])['--'+arg]=None
        task.add_argument('--'+arg, default=default, action=action)
      else:
        typing.cast(dict, self._methods[methodname]['args'])['--'+arg]=argtype
        task.add_argument('--'+arg, type=argtype, default=default)
    return func

  def _exec_func(self, func:typing.Callable, args:argparse.Namespace) -> None:
    _args={}
    try:
        type_hints = typing.get_type_hints(func, globalns=func.__globals__)
    except Exception:
        type_hints = {k: v.annotation for k, v in \
                      inspect.signature(func).parameters.items()}

    for arg, info in inspect.signature(func).parameters.items():
      if hasattr(args, arg):
        _args[arg]=getattr(args, arg)
      annotation=type_hints.get(arg, info.annotation)
      if (type(annotation) == types.UnionType or
          getattr(annotation, '__origin__', None) is typing.Union):
        args_list = getattr(annotation, '__args__', [])
        if len(args_list) == 2 and type(None) in args_list:
           annotation = args_list[0] if args_list[1] == type(None) \
                        else args_list[1]

      if (inspect.isclass(annotation) and
          issubclass(annotation, ArgComplete) and _args.get(arg) is None):
        _args[arg]=DefaultArgComplete(None)
    func(**_args)

  def _invalid_syntax(self, func:typing.Callable, argname:str,
                      missing:str) -> None:
    decorator_call=inspect.stack()[2]
    msg=f'Argument {argname} requires {missing}.'
    filepath=decorator_call.filename
    lineno=decorator_call.lineno
    codeline=decorator_call.code_context
    raise SyntaxError(msg, (filepath, lineno, 0,
                            codeline[0] if codeline else ''))

  def _get_sub_completion(self, needs_new_token:bool,
                          cmdargs:dict[str, object],
                          args:list[str]) -> typing.Iterator[str]:
    def filter_flags_opts_no_requirements(F:str) -> typing.Iterator[str]:
      for argname, argtype in cmdargs.items():
        if argname.startswith('-') and argname.startswith(F):
          yield argname
        elif not argname.startswith('-') and not F.startswith('-') and argtype:
          if (inspect.isclass(argtype) and
              issubclass(argtype, ArgComplete)):
            # type:ignore
            yield from argtype.get_completion_list(F)

    if not len(args):
      assert needs_new_token
      yield from filter_flags_opts_no_requirements('')
    elif len(args) == 1:
      if args[0].startswith('-'):
        if needs_new_token:
          assert args[0] in cmdargs
        flag_param_type=cmdargs.get(args[0], None)
        if flag_param_type:
          # type:ignore
          yield from flag_param_type.get_completion_list('')
          if not needs_new_token:
            yield from filter_flags_opts_no_requirements(args[0])
        else:
          yield from filter_flags_opts_no_requirements('')
      else:
        yield from filter_flags_opts_no_requirements(
          '' if needs_new_token else args[0])
    elif len(args) == 2:
      (penultimate, last)=args
      if needs_new_token:
        yield from self._get_sub_completion(needs_new_token, cmdargs, [last])
      elif not penultimate.startswith('-'):
        yield from filter_flags_opts_no_requirements(last)
      elif penultimate in cmdargs:
        flag_param_type=cmdargs.get(penultimate)
        if not flag_param_type:
          yield from filter_flags_opts_no_requirements(last)
        else:
          # type:ignore
          yield from flag_param_type.get_completion_list(last)
    else:
      yield from self._get_sub_completion(needs_new_token, cmdargs, args[-2:])

  def _print_commands_matching(self, stub:str,
                               operation:typing.Callable[[str], None]) -> None:
    for methodname in self._methods.keys():
      if methodname.startswith(stub):
        operation(methodname)

  def _print_completion_for_testing(self, args:list[str],
                                    tst:typing.Callable[[str], None]) -> None:
    os.environ['_LOCAL_COMP_LINE']='bin ' + ' '.join(args)
    return self._print_completion(tst)

  def _print_completion(self,
                        operation:typing.Callable[[str], None]=print) -> None:
    if '_LOCAL_COMP_LINE' not in os.environ:
      return
    COMP_LINE=os.environ.get('_LOCAL_COMP_LINE') or ''
    args=shlex.split(COMP_LINE)
    if COMP_LINE.endswith(' '):
       args=args[1:]
    else:
       args=args[1:]
    needs_new_token=COMP_LINE.endswith(' ')
    if len(args) == 0:
      if needs_new_token:
        self._print_commands_matching('', operation)
      return
    if len(args) == 1 and not needs_new_token:
      self._print_commands_matching(args[0], operation)
      return
    if needs_new_token:
      if args[0] not in self._methods:
        return
    cmd_args=typing.cast(dict, self._methods[args[0]]['args'])
    for value in self._get_sub_completion(needs_new_token, cmd_args, args[1:]):
      operation(value)

  def eval(self) -> None:
    if self._complete and len(sys.argv) >= 2 and sys.argv[1] == '--iacomplete':
      self._print_completion()
      return
    if self._complete and len(sys.argv) >= 2 and sys.argv[1] == '--iacompdbg':
      self._print_completion_for_testing(sys.argv[2:], print)
      return
    parsed=self._parser.parse_args()
    if hasattr(parsed, 'task'):
      self._exec_func(self._methods[parsed.task]['func'], parsed)
    else:
      self._parser.print_help(sys.stderr)


def _GetForwardingWrapperFrame() -> tuple[types.FrameType, typing.Callable]:
  previous:types.FrameType|None=None
  for entry in inspect.stack():
    if entry.frame.f_code.co_name == '_exec_func':
      assert previous is not None
      module=inspect.getmodule(previous)
      return previous, getattr(module, previous.f_code.co_name)
    previous=entry.frame
  raise RuntimeError('Could not find forwarding wrapper frame')

def _GetDefaultValue(func:typing.Callable, name:str) -> object:
  for arg, info in inspect.signature(func).parameters.items():
    if arg == name:
      return info.default
  return None


def Forward(name:str) -> str:
  frame, func=_GetForwardingWrapperFrame()
  try:
      type_hints = typing.get_type_hints(func, globalns=func.__globals__)
  except Exception:
      type_hints = func.__annotations__

  if name not in type_hints:
    return ''
  argtype=type_hints[name]
  argvalue=frame.f_locals[name]
  argdefault=_GetDefaultValue(func, name)

  if argtype == bool:
    if argvalue is True:
      return f'--{name}'
    return ''

  if argdefault == inspect.Parameter.empty:
    return str(argvalue.wrapped)

  if argvalue is None:
    return ''

  if argtype in (str, bool, int):
    return f'--{name} {argvalue}'

  return f'--{name} {argvalue.wrapped}'
