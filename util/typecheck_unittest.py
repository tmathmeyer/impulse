from impulse.testing import unittest
from impulse.util import typecheck


class Foo():
  pass

class Example(unittest.TestCase):
  def assertTypeCheckFail(self, expected, actual, variable=None):
    vrepr = 'return' if variable is None else f'"{variable}"'
    if str(expected.__module__) != 'builtins':
      expected = f'{expected.__name__} or {expected}'
    errstr = f'Expected type {expected} for {vrepr}, got {actual}'
    class FailContext():
      def __enter__(_):
        pass
      def __exit__(_, errcls, err, tb):
        self.assertEqual(str(err), errstr)
        return True
    return FailContext()

  def test_TypeErrorThrown(self):
    @typecheck.Ensure
    def example(a:str, b:int, c=3, d=4):
      return a,b,c,d
    with self.assertTypeCheckFail(str, int, 'a'):
      example(1, b=2)
    with self.assertTypeCheckFail(str, int, 'a'):
      example(1, 2)
    with self.assertTypeCheckFail(int, str, 'b'):
      example('a', '2')

  def test_NoTypeError(self):
    @typecheck.Ensure
    def example(a:str, b:int, c:int):
      return a,b,c
    self.assertEqual(example('a', 1, 1), ('a', 1, 1))

  def test_CustomTypeNoFail(self):
    @typecheck.Ensure
    def example(a:Foo):
      return a
    self.assertEqual(type(example(Foo())), Foo)

  def test_CustomTypeCanFail(self):
    with self.assertTypeCheckFail(Foo, int, 'a'):
      @typecheck.Ensure
      def ex(a:'Foo'):
        return a
      ex(1)

  def test_TypeReturnNoFail(self):
    @typecheck.Ensure
    def example(a:int) -> int:
      return 1
    example(1)

  def test_TypeReturnCanFail(self):
    with self.assertTypeCheckFail(int, str):
      @typecheck.Ensure
      def example(a:int) -> int:
        return ""
      example(1)

  def test_TypeListCanFail(self):
    with self.assertTypeCheckFail(int, str):
      @typecheck.Ensure
      def example(a:int) -> [int]:
        return [1]
      example(1)