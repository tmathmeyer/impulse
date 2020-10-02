
import os

from impulse.args import args
from impulse.util import resources

command = args.ArgumentParser(complete=True)
DRY = False

def run(cmd):
  if DRY:
    print(cmd)
  else:
    os.system(cmd)

@command
def install(upgrade:bool=False, dryrun:bool=False):
  """Installs this package as a systemd target."""
  global DRY
  DRY = dryrun
  data = {}
  with resources.Resources.OpenGlob('*_metadata') as f:
    for line in f.readlines():
      k,v = line.strip().split('=', 1)
      data[k] = v
  
  binary = data['binary']
  destination = f'/usr/local/bin/{binary}'
  servicesrc = os.path.join(resources.Resources.Dir(), data['servicefile'])
  servicedest = f'/etc/systemd/system/{binary}.service'
  if os.path.exists(destination) and not upgrade:
    print('Use --upgrade to overwrite an existing installation!')
    return

  if os.path.exists(servicedest) and not upgrade:
    print('Use --upgrade to overwrite an existing installation!')
    return

  if os.path.exists(servicedest):
    run(f'systemctl stop {binary}.service')

  binary_src = os.path.join(resources.Resources.Dir(), 'bin', binary)
  run(f'chmod +x {binary_src}')
  run(f'cp {binary_src} {destination}')
  run(f'cp {servicesrc} {servicedest}')
  run('systemctl daemon-reload')

  print('installation complete!')

@command
def uninstall(dryrun:bool=False):
  """Installs this package as a systemd target."""
  global DRY
  DRY = dryrun
  data = {}
  with resources.Resources.OpenGlob('*.metadata') as f:
    for line in f.readlines():
      k,v = line.strip().split('=', 1)
      data[k] = v

  binary = data['binary']
  destination = f'/usr/local/bin/{binary}'
  servicedest = f'/etc/systemd/system/{binary}.service'
  if not os.path.exists(destination) or not os.path.exists(servicedest):
    print('Already uninstalled')
    return

  run(f'systemctl stop {binary}.service')
  run(f'systemctl disable {binary}.service')
  run(f'rm {destination}')
  run(f'rm {servicedest}')

  run('systemctl daemon-reload')
  print('uninstallation complete!')


def main():
  command.eval()