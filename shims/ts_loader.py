
import os
import subprocess
import sys

from impulse.util import resources

def main():
  sysdir = resources.Resources.Dir()
  with open(os.path.join(sysdir, 'ts_bundle_entrypoint'), 'r') as f:
    entrypoint = os.path.join(sysdir, f.read())
    args = ['node', entrypoint, *sys.argv[1:]]
    subprocess.run(args=args)
                   #stdin=subprocess.PIPE, stdout=subprocess.PIPE,)