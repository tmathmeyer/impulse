from impulse.args import args
from impulse.testing import unittest


arguments = args.ArgumentParser(complete=True)


@arguments
def run():
  """Runs unit tests."""
  unittest.TestCase.RunAll(export_as='print')


def main():
  arguments.eval()
