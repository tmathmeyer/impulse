from impulse.testing import unittest

from alpha.only.packages.containing.periods import TypeName

class TestGeneratedCode(unittest.TestCase):
  def test_ContainsProperTypes(self):
    self.assertEqual(dir(TypeName), [
      'Enum', 'TypeName', '__builtins__',
      '__cached__', '__doc__', '__file__',
      '__loader__', '__name__', '__package__',
      '__spec__', 'auto', 'namedtuple'])

  def test_TypeNameProperties(self):
    fields = dir(TypeName.TypeName)
    self.assertTrue('NameOrId' in fields)
    self.assertTrue('NestedType' in fields)
    self.assertTrue('SomeEnumType' in fields)
    self.assertTrue('myBetterId' in fields)
    self.assertTrue('myId' in fields)
    self.assertTrue('subInstances' in fields)
    self.assertTrue('typeOfMyself' in fields)

  def test_CanCreateTypes(self):
    x = TypeName.TypeName(
      1234,
      [TypeName.TypeName.NestedType('a', 'c', 123)],
      TypeName.TypeName.SomeEnumType.firstValue,
      TypeName.TypeName.NameOrId(name = "abc"))

    self.assertEqual(x.myId, 1234)
    self.assertEqual(len(x.subInstances), 1)
    self.assertEqual(x.subInstances[0].foo, 'a')
    self.assertEqual(x.subInstances[0].bar, 'c')
    self.assertEqual(x.subInstances[0].baz, 123)
    self.assertEqual(x.typeOfMyself, TypeName.TypeName.SomeEnumType.firstValue)
    self.assertEqual(x.myBetterId.name, "abc")

  @unittest.ExpectFailed
  def test_CantAccessBadUnionType(self):
    name = TypeName.TypeName.NameOrId(name = "abc")
    fail_here = name.uniqueId

  def test_GetNameWorks(self):
    name = TypeName.TypeName.NameOrId(name = "abc")
    self.assertEqual(name.getUnionKey(), 'name')
    uniqueId = TypeName.TypeName.NameOrId(uniqueId = "abc")
    self.assertEqual(uniqueId.getUnionKey(), 'uniqueId')