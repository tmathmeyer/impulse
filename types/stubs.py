'''Essentially a header file which matches the function signatures
   of the functions declared in builtins.py, so that static analysis
   tools decide to play nice.'''

import os
import typing


# Rebind `os` so the typechecker doesn't freak!
os = os


SourceList = list[str]
TargetName = str
Any = set
BuildTargetName = str
BuildTarget = None
TargetKwargs = dict[str, object]
HelperFunction = typing.Callable[[object], object]
BuildRuleFunction = typing.Callable[[BuildTarget, TargetName, SourceList,
                                     TargetKwargs], None]
BuildRuleDecorator = typing.Callable[[BuildRuleFunction], BuildRuleFunction]


def using(*includes:list[HelperFunction]) -> BuildRuleDecorator:
  ''' A decorator which declares that the buildrule requires linkage
      to a set of helper functions declared elsewhere in the file. It must be
      applied to the buildrule function syntactically before the @buildrule
      decorator. Example:

      def helper_method(...):
        ...

      @using(helper_method)
      @buildrule
      def py_binary(...):
        ...
  '''


def buildrule(fn:BuildRuleFunction) -> BuildRuleFunction:
  '''A decorator which tags this function as one which may be used as a rule
  in a BUILD file target declaration'''


def depends_targets(*targets:list[BuildTargetName]) -> BuildRuleDecorator:
  '''A decorator which adds all named targets to the dependency list for
     all targets of this type'''
