
import abc
import typing

from impulse.types import parsed_target


class MacroEnvironmentHost(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def GetBuildRule(self, buildrule_name:str) -> typing.Callable:
    '''Looks up a buildrule by name. Raises an error if it can't be found'''

  @abc.abstractmethod
  def LoadFile(self, filename:str) -> None:
    '''Loads a file'''


class RuleArchive(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def AddMetaTarget(self, target:None):
    '''Saves a meta target'''

  @abc.abstractmethod
  def AddParsedTarget(self, name:parsed_target.TargetReferenceName):
    '''Saves a parsed target'''


