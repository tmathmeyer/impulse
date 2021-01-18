
from impulse.format import format
from impulse.testing import unittest
from impulse.util import resources

class FormatTests(unittest.TestCase):
  def setup(self):
    pass

  def test_ReadBuildFile(self):
    reader = format.FormattingBuildFileReader()
    file = resources.Resources.Get('impulse/format/BUILD')
    reader.ReadFile(file)
    with open(file) as f:
      self.assertNoDiff(f.read().strip(), reader.PrintFormat().strip())