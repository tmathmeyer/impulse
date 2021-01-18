from impulse.testing import unittest
from impulse.util import typecheck


class Foo():
  pass

class TypeCheckTests(unittest.TestCase):
  def setup(self):
    from impulse.core import debug
    debug.EnableDebug('typing')

  def assertTypeCheckFail(self, expected, actual, variable=None):
    vrepr = 'return' if variable is None else f'arg "{variable}"'
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

  def test_TypeListOk(self):
    @typecheck.Ensure
    def example(a:int) -> [int]:
      return [1]
    example(1)

  def test_TypeListCanFail(self):
    with self.assertTypeCheckFail([int], int):
      @typecheck.Ensure
      def example(a:int) -> [int]:
        return 1
      example(1)

    with self.assertTypeCheckFail([int], [str]):
      @typecheck.Ensure
      def example(a:int) -> [int]:
        return [""]
      example(1)

  def test_Generics(self):
    from typing import TypeVar
    T = TypeVar('T')
    @typecheck.Ensure
    def example(a:T) -> [T]:
      return [a]

    example(1)
    example("a")

    with self.assertTypeCheckFail([int], [str]):
      @typecheck.Ensure
      def example(a:T) -> [T]:
        return [str(a)]
      example(1)

  def test_CustomListTypes(self):
    class Super():
      pass

    class Foo(Super):
      pass

    class Bar(Super):
      pass

    class Baz():
      def __init__(self, t):
        self._type = t
      @typecheck.Ensure
      def asSuper(self) -> Super:
        return self._type()

    @typecheck.Ensure
    def example(a:[Baz]) -> [Super]:
      return [x.asSuper() for x in a]

    example([Baz(Foo), Baz(Bar), Baz(Foo)])
