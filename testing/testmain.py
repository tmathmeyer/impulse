from impulse.args import args
from impulse.testing import unittest


arguments = args.ArgumentParser(complete=True)


@arguments
def run(notermcolor:bool=False, filter:str=None):
  """Runs unit tests."""
  if filter is not None:
    unittest.TestCase.RunFilter(notermcolor, filter, export_as='print')
    return
  unittest.TestCase.RunAll(notermcolor, export_as='print')


def main():
  arguments.eval()
