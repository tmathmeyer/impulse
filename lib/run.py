import os
import subprocess


def RunCommand(command):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)


def OutputOrError(cmd):
  result = RunCommand(cmd)
  if result.returncode:
    raise ValueError(f'|{cmd}|:\n {result.stderr}')
  return result.stdout.strip()


class cd(object):
  def __init__(self, path):
    self._path = path
    self._oldpath = None

  def __enter__(self):
    self._oldpath = os.getcwd()
    os.chdir(self._path)

  def __exit__(self, *args, **kwargs):
    os.chdir(self._oldpath)
