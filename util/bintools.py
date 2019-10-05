
import os
import pkgutil

def LoadExecutables():
  import sys
  for k,v in sys.modules.items():
    print(k,v)

  return 'fucl'

  for file in eval(pkgutil.get_data('bin', '__tools__')):
    package = '.'.join(os.path.dirname(file).split('/'))
    name = os.path.basename(file)
    return type(pkgutil.get_data(package, name))