
import os
import sys
from pathlib import Path


from impulse.util import temp_dir

def main():
  assert len(sys.argv) == 2
  extractcmd = 'unzip {}'.format(os.path.join(os.getcwd(), sys.argv[1]))
  with temp_dir.ScopedTempDirectory():
    os.system(extractcmd)
    os.system('tree')
    dockercmd = 'docker build -t {} .'.format(Path(sys.argv[1]).stem)
    print(dockercmd)
    os.system(dockercmd)
    os.system('rm -rf ./*')
