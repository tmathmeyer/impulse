
import os

from impulse.args import args
from impulse.util import resources

command = args.ArgumentParser(complete=True)

@command
def install(upgrade:bool=False):
  """Installs this package as a systemd target."""
  data = {}
  with resources.Resources.OpenGlob('*.metadata') as f:
    for line in f.readlines():
      k,v = line.strip().split('=', 1)
      data[k] = v
  
  binary = data['binary']
  destination = f'/usr/local/bin/{binary}'
  servicesrc = data['servicefile']
  servicedest = f'/etc/systemd/system/{binary}.service'
  if os.path.exists(destination) and not upgrade:
    print('Use --upgrade to overwrite an existing installation!')
    return

  if os.path.exists(servicedest) and not upgrade:
    print('Use --upgrade to overwrite an existing installation!')
    return

  if os.path.exists(servicedest):
    os.system(f'systemctl stop {binary}.service')

  os.system(f'cp bin/{binary} {destination}')
  os.system(f'cp {servicesrc} {servicedest}')
  os.system('systemctl daemon-reload')

  print('installation complete!')


def main():
  command.eval()