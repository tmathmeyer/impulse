import sys

from impulse.args import args
from impulse.testing import unittest


arguments = args.ArgumentParser(complete=True)


@arguments
def run(notermcolor:bool=False, filter:str|None=None):
  """Runs unit tests."""
  if filter is not None:
    unittest.TestCase.RunFilter(notermcolor, filter, export_as='print')
    sys.exit(1)
  exit_code = unittest.TestCase.RunAll(notermcolor, export_as='print')
  sys.exit(exit_code)


def main():
  arguments.eval()
