
import getpass
import grp
import os
import pwd
import re
import subprocess

from typing import Sequence, Dict

from impulse.args import args
from impulse.util import bintools


def _get_current_user_groups() -> Sequence[str]:
  user = getpass.getuser()
  for g in grp.getgrall():
    if user in g.gr_mem:
      yield g.gr_name
  yield grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name


def _prelaunch_checks() -> bool:
  if 'lock' not in _get_current_user_groups():
    print('User needs to be a member of the "lock" group.')
    return False
  return True


def _get_tty_device_drivers() -> Dict[str, str]:
  tty_sys_path = '/sys/class/tty'
  result = {}
  for ttydev in os.listdir(tty_sys_path):
    if 'device' in os.listdir(os.path.join(tty_sys_path, ttydev)):
      result[ttydev] = os.path.realpath(
        os.path.join(tty_sys_path, ttydev, 'device/driver'))
  return result


def _get_arduino_devices() -> Sequence[str]:
  for tty, driver in _get_tty_device_drivers().items():
    if driver.endswith('-uart'):
      yield os.path.join('/dev', tty)


class Device(object):
  def __init__(self, ttydevice):
    self._tty_device = ttydevice
    self._chipset = 'ATxmega32E5'  # just a guess!

  def RunCommand(self, command):
    return subprocess.run(command,
                          encoding='utf-8',
                          shell=True,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE)

  def Construct(self):
    cmd = '{} -C {} -c arduino -P {} -p {}'
    r = self.RunCommand(cmd.format(
      bintools.GetResourcePath('bin/avrdude', exe=True),
      bintools.GetResourcePath('impulse/avr/avrdude.conf'),
      self._tty_device,
      self._chipset));
    result = re.search(r'\(probably (\S+)\)', r.stderr)
    if result:
      self._chipset = result.group(1)
    else:
      self._chipset = 'unknown'

  def __str__(self):
    return f'''
IO device: {self._tty_device}
chipset: {self._chipset}
'''

  def __repr__(self):
    return str(self)


command = args.ArgumentParser(complete=True)


@command
def devices():
  """List the devices available"""
  if not _prelaunch_checks():
    return

  devices = [Device(dev) for dev in _get_arduino_devices()]
  completed_count_str = ''

  print('querying [', end='')
  for idx, device in enumerate(devices):
    print('\b'*len(completed_count_str), end='')
    completed_count_str = f'{idx}/{len(devices)}]'
    print(completed_count_str, end='', flush=True)
    device.Construct()

  print('\b'*len(completed_count_str), end='')
  print(f'{len(devices)}/{len(devices)}]')

  for device in devices:
    print(device)



def main():
  command.eval()