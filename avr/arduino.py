
import getpass
import grp
import os
import pwd

from typing import Sequence, Dict

from impulse.args import args


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


command = args.ArgumentParser(complete=True)


@command
def devices():
  """List the devices available"""
  if not _prelaunch_checks():
    return
  print(list(_get_arduino_devices()))


def main():
  command.eval()