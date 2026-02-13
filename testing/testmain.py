import os
import sys

from impulse.args import args
from impulse.testing import unittest


arguments = args.ArgumentParser(complete=True)


@arguments
def run(notermcolor:bool=False, filter:str|None=None, github_actions:bool=False):
  """Runs unit tests."""
  export_as = 'print'
  if github_actions or os.environ.get('GITHUB_ACTIONS') == 'true':
    export_as = 'github_actions'

  if filter is not None:
    unittest.TestCase.RunFilter(notermcolor, filter, export_as=export_as)
    sys.exit(1)
  exit_code = unittest.TestCase.RunAll(notermcolor, export_as=export_as)
  sys.exit(exit_code)


def main():
  arguments.eval()
