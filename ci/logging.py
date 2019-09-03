import sys

files = set()

def _do_trace(names):
  def __tracer__(frame, event, arg):
    if event == 'call':
      func_name = frame.f_code.co_name
      if func_name in ('write', 'add', 'split'):
        return
      filen = frame.f_code.co_filename.split('/')[-1][:-3]
      if filen in names:
        print(f'==> ({frame.f_code.co_filename}) {func_name}')
        sys.stdout.flush()
    
    if event == 'exception':
      print(arg)
  return __tracer__

def EnableTracing(*module_names):
  sys.settrace(_do_trace(module_names))
