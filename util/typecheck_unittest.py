from impulse.testing import unittest
from impulse.util import typecheck


class Foo():
  pass


class Example(unittest.TestCase):
  def test_TypeErrorThrown(self):
    @typecheck.Ensure
    def example(a:str, b:int, c=3, d=4):
      pass
    try:
      example(1, b=2)
    except TypeError as v:
      self.assertEqual(str(v),
        "Expected type <class 'str'> for \"a\", got <class 'int'>")

  def test_NoTypeError(self):
    @typecheck.Ensure
    def example(a:str, b:int, c:int):
      pass
    example('a', 1, 1)

  def test_CustomType(self):
    @typecheck.Ensure
    def example(a:Foo):
      return a
    self.assertEqual(type(example(Foo())), Foo)
    def ex(a:'Foo'):
      return a
    self.assertEqual(type(ex(Foo())), Foo)
    try:
      example(1)
    except TypeError as v:
      self.assertEqual(str(v),
        f"Expected type {Foo} for \"a\", got <class 'int'>")

  def test_TypeReturn(self):
    @typecheck.Ensure
    def example(a:int) -> int:
      return 1
    example(1)

    @typecheck.Ensure
    def example2(a:int) -> int:
      return ""
    try:
      example2(1)
    except TypeError as v:
      self.assertEqual(str(v),
        f"Expected type <class 'int'> for return, got <class 'str'>")
