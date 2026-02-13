
import inspect
import types
import typing


class _InterfaceMeta(type):
  """
  Checks signatures on instances of concrete classes that implement
  interface classes.
  """
  def __new__(mcls, name:str, bases:tuple[type, ...],
              namespace:dict[str, object], **kwargs:object) -> type:
    # Create the class so we can attach stuff to it
    cls=super().__new__(mcls, name, bases, namespace, **kwargs)

    # The internal sentinel boolean used by InterfaceParent in the decorator
    # we don't have to do anything with this at all, just continue.
    if namespace.get('_InterfaceParentSentinal', False):
      pass

    # Check whether this class is the 'interface'. Its possible to tell
    # because the base classes should include an '_InterfaceParent' internal
    # class which has the sentinel object.
    elif _InterfaceMeta.IsInterface(bases):
      # All methods defined are interface methods.
      cls._interface_methods=_InterfaceMeta.MethodSignatures(namespace) # type:ignore

    # This must then be a concrete class. Check all it's parents for any
    # interfaces and make sure all the methods match.
    else:
      required_methods:dict[str, inspect.Signature] = {}
      for base in bases:
        parent_methods=getattr(base, '_interface_methods', {})
        for method, signature in parent_methods.items():
          if method in required_methods:
            unexpected=required_methods[method]
            if unexpected != signature:
              raise TypeError(
                f'Conflicting interface methods for child class {name}: '
                f'{base.__name__} provides {method}::{signature}, '
                f'previously required {method}::{unexpected}')
          else:
            required_methods[method] = signature
      my_methods=_InterfaceMeta.MethodSignatures(namespace)
      for method, signature in required_methods.items():
        if my_methods.get(method, None) != signature:
          raise TypeError(f'Concrete class {name} missing required '
                          f'interface method {method}:[{signature}], '
                          f'found: {my_methods.get(method, None)}')

    return cls

  @classmethod
  def IsInterface(cls, bases:tuple[type, ...]) -> bool:
    """Returns True if any of the base classes is an interface parent."""
    return any(getattr(base, '_InterfaceParentSentinal', False) for base in bases)

  @classmethod
  def MethodSignatures(cls, namespace:dict[str, object]) -> dict[str, inspect.Signature]:
    """Returns a mapping of method names to their signatures."""
    methods = {}
    for name, method in namespace.items():
      if isinstance(method, types.FunctionType):
        methods[name] = inspect.signature(method)
    return methods


class _InterfaceParent(metaclass=_InterfaceMeta):
  """Parent class to get a metaclass into the type() call."""
  _InterfaceParentSentinal=True


def IFace(class_def:type) -> type:
  """Decorator method to turn a class into an interface."""

  # Find all the local methods
  methods:dict[str, object] = {}
  for name, method in class_def.__dict__.items():
    if isinstance(method, (types.FunctionType, property)):
      methods[name] = method

  # Create the new type, adding _InterfaceParent to the other base classes
  created=type(
    class_def.__name__,
    (_InterfaceParent, *class_def.__bases__),
    methods)

  # Mark it as _not_ an interface parent.
  setattr(created, '_InterfaceParentSentinal', False)

  # Re-add the docstring
  created.__doc__=class_def.__doc__
  return created
