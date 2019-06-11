from impulse.testing import unittest

class Example(unittest.TestCase):
  def test_TrueIsTrue(self):
    self.assertTrue(True)

  def test_FalseIsFale(self):
    self.assertFalse(False)

  @unittest.ExpectFailed
  def test_FalseIsntTrue(self):
    self.assertTrue(False)

  @unittest.ExpectFailed
  def test_TrueIsntFalse(self):
    self.assertFalse(True)

  def test_EqualIsEqual(self):
    self.assertEqual(1, 1)

  @unittest.ExpectFailed
  def test_DifferentIsntEqual(self):
    self.assertEqual(1, 8)
