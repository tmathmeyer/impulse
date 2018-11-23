
from impulse.testing import unittest
from impulse.args import args

class TestArgs(unittest.TestCase):

  def setup(self):
    self._parser = args.ArgumentParser()

  def test_extracts_docstring(self):
    def documented_fn():
      """Example Docstring."""
      pass
    self._parser(documented_fn)

  def test_needs_types_on_args(self):
    def typelessarg(_arg):
      pass
    def typelesskwarg(_kwarg=1):
      pass