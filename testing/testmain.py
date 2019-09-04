from impulse.args import args
from impulse.testing import unittest


arguments = args.ArgumentParser(complete=True)


@arguments
def run(notermcolor:bool=False):
  """Runs unit tests."""
  unittest.TestCase.RunAll(notermcolor, export_as='print')


def main():
  arguments.eval()
