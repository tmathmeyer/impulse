
import abc
import collections
import inspect
import enum
import types
import typing

from impulse.core import debug


def DEBUG(*args):
  pass


def _TypeErrorExpected(expected, actual, method, location):
  return TypeError(f'{method}[{location}]: expected: {expected}, was: `{actual}`')


def Assert(fn_wrap):
  if not debug.IsDebug():
    return fn_wrap
  def _replacement(*args, **kwargs):
    try:
      return _CheckTypes(fn_wrap, args, kwargs)
    except TypeError as e:
      raise TypeError(f'{fn_wrap.__name__}: {str(e)}')
  _replacement.__signature__ = inspect.signature(fn_wrap)
  return _replacement


def _CheckTypes(function, args:tuple, kwargs:dict):
  class Variable(typing.NamedTuple):
    name:str
    def Replace(self, name):
      return self

  class DeclType(typing.NamedTuple):
    impl:type|typing.TypeVar|types.GenericAlias
    def Replace(self, name):
      return self

  class InfType(typing.NamedTuple):
    impl:type|types.GenericAlias
    def Replace(self, name):
      return self

  class Constraint(typing.NamedTuple):
    lhs: Variable|DeclType|InfType
    rhs: Variable|DeclType|InfType
    note: str

    def Swap(self):
      return Constraint(self.rhs, self.lhs, self.note)

    def Replace(self, name):
      assert type(name.lhs) == Variable
      assert type(name.rhs) in (Variable, DeclType, InfType)
      if self.lhs == name.lhs:
        note = f'{name.note} | {self.note}'
        return Constraint(name.rhs, self.rhs.Replace(name), note)
      if self.rhs == name.lhs:
        note = f'{self.note} | {name.note}'
        return Constraint(self.lhs.Replace(name), name.rhs, note)
      return self

  class ConstraintOperation(enum.Enum):
    NOTHING = 'Nothing'
    REPLACE = 'Replace'
    TYPECHECK = 'Typecheck'
    BIND = 'Bind'
    EXPAND = 'Expand'

    @staticmethod
    def Determine(cons):
      if (cons.lhs == cons.rhs):
        return ConstraintOperation.NOTHING, None, None
      if type(cons.lhs) == Variable:
        return ConstraintOperation.REPLACE, cons, None
      if type(cons.lhs) == DeclType:
        assert type(cons.rhs) == InfType
        if type(cons.lhs.impl) in (type, abc.ABCMeta):
          return ConstraintOperation.TYPECHECK, cons.lhs, cons.rhs
        if type(cons.lhs.impl) == typing.TypeVar:
          return ConstraintOperation.BIND, cons.lhs, cons.rhs
        if type(cons.lhs.impl) in (typing._UnionGenericAlias, types.UnionType):
          return ConstraintOperation.EXPAND, cons.lhs, cons.rhs
        if type(cons.lhs.impl) == types.GenericAlias:
          return ConstraintOperation.BIND, cons.rhs, cons.lhs
        if type(cons.lhs.impl) == typing._AnyMeta:
          return ConstraintOperation.NOTHING, None, None
        raise TypeError(f'invalid type for {cons} left side ({cons.lhs.impl} - {type(cons.lhs.impl)})')
      if type(cons.lhs) == InfType:
        if type(cons.rhs) == InfType:
          raise TypeError('not implemented yet!')
        return ConstraintOperation.Determine(cons.Swap())

  def GenerateBindingsBranching(declared:types.UnionType, inferred:type|types.GenericAlias) -> dict[typing.TypeVar, set]:
    DEBUG('---XX', declared, '----', inferred)
    bindings = None
    for subtype in declared.__args__:
      if subtype == inferred:
        return {}
      if inferred == type(function) and type(subtype) == typing._CallableGenericAlias:
        #TODO: we need to extract the types from function and rebind them!
        return {}
      try:
        bindings = GenerateBindings(subtype, inferred)
      except:
        pass
    if bindings:
      return bindings
    raise TypeError(f'Cant convert {inferred} to {declared}')

  def GenerateBindings(declared:type|typing.TypeVar|types.GenericAlias, inferred:type|types.GenericAlias) -> dict[typing.TypeVar, set]:
    DEBUG('---YY', declared, '----', inferred)
    if type(declared) == type:
      return {}
    if type(declared) == typing.TypeVar:
      return {declared: set([inferred])}
    if type(inferred) != types.GenericAlias:
      raise TypeError(f'Cant convert {inferred} to {declared}')
    if inferred.__origin__ != declared.__origin__:
      raise TypeError(f'Cant convert {inferred} to {declared}')
    if len(inferred.__args__) != len(declared.__args__):
      raise TypeError(f'Cant convert {inferred} to {declared}')
    result = {}
    for dec,inf in zip(declared.__args__, inferred.__args__):
      for var,map in GenerateBindings(dec, inf).items():
        if var not in result:
          result[var] = map
        else:
          result[var].update(map)
    return result

  def CheckConstraintList(constraints):
    generic_bindings = {}
    while constraints:
      first = constraints.pop(0)
      DEBUG('')
      DEBUG(first)
      constraint, x, y = ConstraintOperation.Determine(first)
      DEBUG(constraint, x, y)

      if constraint == ConstraintOperation.NOTHING:
        continue
      elif constraint == ConstraintOperation.REPLACE:
        constraints = list(c.Replace(x) for c in constraints)
        for c in constraints:
          DEBUG('   ', c)
      elif constraint == ConstraintOperation.TYPECHECK:
        pass
      elif constraint == ConstraintOperation.BIND:
        for var,map in GenerateBindings(x.impl, y.impl).items():
          if var not in generic_bindings:
            generic_bindings[var] = map
          else:
            generic_bindings[var].update(map)
      elif constraint == ConstraintOperation.EXPAND:
        can_bind = GenerateBindingsBranching(x.impl, y.impl)
        if can_bind is None:
          raise TypeError(f'TypeError {first}')
        if len(can_bind):
          generic_bindings.update(can_bind)
      else:
        raise TypeError('Not Implemented')
    common_bindings = {}
    for key, values in generic_bindings.items():
      parent = CommonParent(values)
      if parent == object:
        raise TypeError(f'Cant find common parent for {key} among: {values}')
      common_bindings[key] = parent
    return common_bindings

  def CommonParent(classes):
    mros = [list(inspect.getmro(cls)) for cls in classes]
    track = collections.defaultdict(int)
    while mros:
      for mro in mros:
        cur = mro.pop(0)
        track[cur] += 1
        if track[cur] == len(classes):
          return cur
        if len(mro) == 0:
          mros.remove(mro)
    return None

  def DoesTypeQualify(actual:typing.Any, expected:type|typing.TypeVar, bindings:dict):
    DEBUG('\nQualify:')
    DEBUG(actual, expected, bindings)
    if actual == None and expected == None:
      return True

    if expected == typing.Any:
      return True

    if type(expected) in (type, abc.ABCMeta):
      DEBUG('isinstance')
      return isinstance(actual, expected)

    if type(expected) == typing.TypeVar:
      DEBUG('type lookup')
      return DoesTypeQualify(actual, bindings[expected], bindings)

    if type(expected) == typing.GenericAlias:
      DEBUG('generic')
      return DoesTypeQualify(actual, expected.__origin__, bindings)

    if type(expected) in (types.UnionType, typing._UnionGenericAlias):
      DEBUG('union')
      for arg in expected.__args__:
        if DoesTypeQualify(actual, arg, bindings):
          return True
      return False

    DEBUG(type(expected))
    return False

  def InferType(any):
    if type(any) == list:
      if len(any):
        return list[InferType(any[0])]
      return list[typing.Any]
    if type(any) == dict:
      if len(any):
        k,v = list(any.items())[0]
        return dict[InferType(k), InferType(v)]
      return dict[typing.Any, typing.Any]
    return type(any)

  try:
    type_constraint_list = []
    argspec = inspect.getfullargspec(function)

    # Ensure that all args are types. `self` and `cls` are optional, but only
    # if they are the first arg
    first = True
    for name in argspec.args:
      if name not in argspec.annotations:
        if first and name not in ('cls', 'self'):
          raise _TypeErrorExpected('type', 'missing', function, f'parameter `{name}`')
      first = False

    if 'return' not in argspec.annotations:
      if function.__name__ not in ('__init__', '__new__'):
        raise _TypeErrorExpected('type', 'missing', function, 'return')

    # Create constraints for all annotated types.
    for key, value in argspec.annotations.items():
      type_constraint_list.append(Constraint(Variable(key), DeclType(value),
                                            f'Annotation for {function.__name__}.{key}'))

    # Ensure all the defaults
    if argspec.defaults:
      for name, value in zip(argspec.args[0-len(argspec.defaults):], argspec.defaults):
        type_constraint_list.append(Constraint(Variable(name), InfType(InferType(value)),
                                            f'Default value for {name}'))

    # Deduce bindings and apply types accordingly
    for name,value in inspect.getcallargs(function, *args, **kwargs).items():
      type_constraint_list.append(Constraint(Variable(name), InfType(InferType(value)),
                                            f'Parameter value for {name} `value`'))

    DEBUG(f'\n\nConstraints ({function}):')
    for x in type_constraint_list:
      DEBUG(x)

    DEBUG('\nCheck Constraints:')
    bindings = CheckConstraintList(type_constraint_list)

    DEBUG('\nBindings:')
    DEBUG(bindings)
    evaluated = function(*args, **kwargs)
    if function.__name__ not in ('__init__', '__new__'):
      if not DoesTypeQualify(evaluated, argspec.annotations['return'], bindings):
        raise TypeError(f'Cant match return value `{evaluated}` to expected type: {argspec.annotations['return']}')
    return evaluated
  except TypeError as e:
    raise e
    #raise TypeError(f'{function}:\n  {str(e)}') from e

