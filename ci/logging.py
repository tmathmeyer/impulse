import sys

def _do_trace(frame, event, arg):
  if event == 'call':
    func_name = frame.f_code.co_name
    if func_name == 'write':
      return
    print(f'==> {func_name}')

  if event in ('return', 'exception'):
    print('ret / exc')

  return

def EnableTracing():
  sys.settrace(_do_trace)