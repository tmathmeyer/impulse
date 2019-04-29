
import os
import sys

from impulse.util import temp_dir

def main():
  assert len(sys.argv) == 2
  extractcmd = 'unzip {}'.format(os.path.join(os.getcwd(), sys.argv[1]))
  with temp_dir.ScopedTempDirectory():
    os.system(extractcmd)
    os.system('tree')
    os.system('docker build .')
    os.system('rm -rf ./*')
