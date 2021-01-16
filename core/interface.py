
import inspect
import types
import typing

from impulse.util import typecheck


class _InterfaceMeta(type):
  """Checks signatures on instances of concrete classes that implement
     interface classes.
  """
  def __new__(mcls, name, bases, namespace, **kwargs):
    # Create the class so we can attach stuff to it
    cls = super().__new__(mcls, name, bases, namespace, **kwargs)

    # The internal sentinal boolean used by InterfaceParent in the decorator
    # we don't have to do anything with this at all, just continue.
    if namespace.get('_InterfaceParentSentinal', False):
      pass

    # Check whether this class is the 'interface'. Its possible to tell
    # because the base classes should include an 'InterfaceParent' internal
    # class which has the sentinal object.
    elif _InterfaceMeta.IsInterface(bases):
      # All methods defined are interface methods.
      cls._interface_methods = _InterfaceMeta.MethodSignatures(namespace)
    
    # This must then be a concrete class. Check all it's parents for any
    # interfaces and make sure all the methods match.
    else:
      required_methods = {}
      for base in bases:
        parent_methods = getattr(base, '_interface_methods', {})
        for method, signature in parent_methods.items():
          if method in required_methods:
            unexpected = required_methods[method]
            if unexpected != signature:
              raise TypeError(
                f'Conflicting interface methods for child class {name}: '
                f'{base.__name__} provides {method}::{signature}, '
                f'{base.__name__} provides {method}::{unexpected}')
          else:
            required_methods[method] = signature
      my_methods = _InterfaceMeta.MethodSignatures(namespace)
      for method, signature in required_methods.items():
        if my_methods.get(method, None) != signature:
          raise TypeError(f'Concrete class {name} missing required '
                          f'interface method {method}:[{signature}], '
                          f'found: {my_methods.get(method, None)}')

    return cls

  @classmethod
  def IsInterface(cls, bases) -> bool:
    return any(getattr(base, '_InterfaceParentSentinal') for base in bases)

  @classmethod
  def MethodSignatures(cls, namespace) -> typing.Dict[str, inspect.Signature]:
    methods = {}
    for name, method in namespace.items():
      if isinstance(method, types.FunctionType):
        methods[name] = inspect.signature(method)
    return methods


class _InterfaceParent(metaclass=_InterfaceMeta):
  """Parent class to get a metaclass into the |type()| call."""
  _InterfaceParentSentinal = True


@typecheck.Ensure
def IFace(class_def: type) -> '_InterfaceParent':
  """Decorator method to turn a class into an interface."""

  # Find all the local methods
  methods = {}
  for name, method in class_def.__dict__.items():
    if isinstance(method, types.FunctionType):
      methods[name] = method

  # Create the new type, adding _InterfaceParent to the other base classes
  created = typing.cast(_InterfaceParent, type(
    class_def.__name__,
    (_InterfaceParent, *class_def.__bases__),
    methods))

  # Mark it as _not_ an interface parent.
  created._InterfaceParentSentinal = False

  # Re-add the docstring
  created.__doc__ = class_def.__doc__
  return created
