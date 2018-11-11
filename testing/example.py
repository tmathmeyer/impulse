from impulse.testing import unittest

class Example(unittest.TestCase):
  def test_TrueIsTrue(self):
    self.assertTrue(True)

  def test_FalseIsFale(self):
    self.assertFalse(False)

  def test_FalseIsntTrue(self):
    self.assertTrue(False)

  def test_TrueIsntFalse(self):
    self.assertFalse(True)

  def test_EqualIsEqual(self):
    self.assertEqual(1, 1)

  def test_DifferentIsntEqual(self):
    self.assertEqual(1, 8)
