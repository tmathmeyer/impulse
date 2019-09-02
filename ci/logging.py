import sys

def _do_trace(names):
  def __tracer__(frame, event, arg):
    if event == 'call':
      func_name = frame.f_code.co_name
      if func_name == 'write':
        return
      if f'{frame.f_code.co_filename}.py' in names:
        return
      print(f'==> {func_name}')

    if event in ('return', 'exception'):
      print('ret / exc')

    return
  return __tracer__

def EnableTracing(*module_names):
  sys.settrace(_do_trace(module_names))