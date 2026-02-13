from __future__ import annotations

import traceback
import typing

if typing.TYPE_CHECKING:
  from impulse.types import parsed_target


class ImpulseBaseException(Exception):
  """Base class for all impulse-specific exceptions."""
  def __init__(self, *args:object, **kwargs:object):
    super().__init__(*args, **kwargs)


class ImpulseFileChainException(ImpulseBaseException):
  """Exception that tracks a chain of imports leading to an error."""
  @staticmethod
  def Render(message:str, chain:list[str]) -> str:
    """Renders the exception message and its import chain."""
    indented=''.join([('  '*i + chain[i] + '\n') for i in range(len(chain))])
    return f'Error: {message}\nImported from:\n{indented}'

  def __init__(self, message:str, chain:list[str]):
    super().__init__(ImpulseFileChainException.Render(message, chain))
    self._message=message
    self._chain=chain

  def Chain(self, file:str) -> 'ImpulseFileChainException':
    """Adds a new file to the import chain."""
    return ImpulseFileChainException(self._message, [file]+self._chain)


class FileErrorException(ImpulseBaseException):
  """Exception providing line-level context for an error."""
  @staticmethod
  def Render(filename:str, line:int, position:int, highlight_len:int) -> str:
    """Renders a line of code with a caret/underline highlight."""
    def ReadLineRange(start:int, end:int) -> typing.Iterator[str]:
      try:
        with open(filename, 'r') as f:
          for i, line_content in enumerate(f.readlines()):
            if i < start:
              continue
            if i > end:
              break
            yield line_content
      except Exception:
        yield f'Unable to read {filename}\n'

    content=''.join(ReadLineRange(max(0, line-2), line-1))
    indent=' ' * position
    squigly='~' * max(0, highlight_len-2)
    return f'{content}{indent}^{squigly}^\n'

  def __init__(self, message:str, filename:str, line:int, pos:int, sq_len:int=0):
    super().__init__(
      f'{message}\n{filename}:{line}:'
      f'{FileErrorException.Render(filename, line, pos, sq_len)}')


class NoSuchRuleType(FileErrorException):
  """Raised when a build rule type doesn't exist."""
  def __init__(self, filename:str, line:int, rulename:str):
    super().__init__(f'No such build rule type "{rulename}"',
      filename, line, 0, len(rulename))


class ListedSourceNotFound(Exception):
  """Raised when a source file listed in a target is missing."""
  def __init__(self, filename:str, targetname:object):
    super().__init__('[{}] used in [{}] not found on disk.'.format(
      filename, targetname))
    self.filename=filename
    self.targetname=targetname


class InvalidPathException(Exception):
  """Raised when a path is invalid for a provided reason."""
  def __init__(self, path:str, reason:str):
    super().__init__('[{}] invalid: {}'.format(path, reason))
    self.path=path
    self.reason=reason


class BuildDefsRaisesException(Exception):
  """Raised when a build_defs file raises an exception."""
  def __init__(self, target_name:str, buildrule_name:str, exception:Exception):
    msg='"{}" raised exception while building target "{}":\n{}'
    super().__init__(msg.format(buildrule_name, target_name, exception))


class BuildRuleCompilationError(Exception):
  """Raised when a build rule fails to parse/compile correctly."""
  def __init__(self, ex2:Exception):
    super().__init__(str(ex2))


class ImpulseAssertWrapperError(Exception):
  """Raised when an impulse core library assert fails."""
  def __init__(self, ex3:Exception):
    super().__init__(str(ex3))


class BuildTargetCycle(Exception):
  """Raised when there is a dependency cycle between build targets."""
  @classmethod
  def Cycle(cls, pbt:'parsed_target.BuildTarget') -> 'BuildTargetCycle':
    """Creates a new BuildTargetCycle starting with the given target."""
    return cls(cls._Message([pbt]), [pbt])

  @classmethod
  def _Message(cls, stack:list['parsed_target.BuildTarget']) -> str:
    """Formats the cycle message from the stack of targets."""
    msg='Build target cycle:\n{}'
    return msg.format(' => '.join(s.GetName() for s in stack))

  def __init__(self, message:str, pbts:list['parsed_target.BuildTarget']):
    self._parsed_target_stack=pbts
    super().__init__(message)

  def ChainException(self, pbt:'parsed_target.BuildTarget') -> \
      'BuildTargetCycle':
    """Adds a target to the dependency stack and returns a new exception."""
    newstack=[pbt] + self._parsed_target_stack
    return BuildTargetCycle(
      BuildTargetCycle._Message(newstack), newstack)


class BuildTargetMissing(ImpulseBaseException):
  """Raised when a build target cannot be found."""
  def __init__(self, ex6:str):
    super().__init__(f'Target not found: {ex6}')


class FileLoadException(ImpulseFileChainException):
  """Raised when a file can't be loaded into the build environment."""
  pass


class BuildTargetMissingFrom(ImpulseBaseException):
  """Raised when a specific target is missing from a build rule."""
  def __init__(self, target:str, buildrule:str):
    super().__init__('Target "{}", used in "{}", is missing.'.format(
      target, buildrule))


class BuildTargetNoBuildNecessary(Exception):
  """Raised when a build target is already up to date."""
  def __init__(self) -> None:
    super().__init__('Build not necessary')


class FilesystemSyncException(Exception):
  """Raised when the filesystem state is inconsistent."""
  def __init__(self) -> None:
    msg='The filesystem is out of sync, please try rerunning.'
    super().__init__(msg)


class FatalException(Exception):
  """Exception for fatal, unrecoverable errors."""
  def __init__(self, s:str):
    super().__init__(s)


class MacroException(Exception):
  """Raised when a macro expansion fails."""
  def __init__(self, macro:str, name:str, reason:str):
    super().__init__(f'{name}<{macro}> expansion failed: {reason}')


class PlatformKeyAbsentError(ImpulseBaseException):
  """Raised when a property is missing from a platform definition."""
  def __init__(self, platname:str, platkey:str):
    super().__init__(f'platform {platname} missing property {platkey}')


class UncheckedException(Exception):
  """An exception that includes a full traceback in its rendering."""
  @staticmethod
  def Render(impl:'UncheckedException', kwargs:dict[str, object]) -> str:
    """Renders the exception with a full traceback."""
    stk='\n'.join(traceback.format_stack())
    return stk + '\n\n' + impl.__class__.__name__ + ': ' + str(kwargs)

  def __init__(self, **kwargs:object):
    super().__init__(UncheckedException.Render(self, kwargs))
    for k,v in kwargs.items():
      setattr(self, k, v)


class FileNotFoundException(UncheckedException):
  """Raised when a file is not found on disk."""
  filepath:str


class BuildFileNotFoundException(UncheckedException):
  """Raised when a BUILD file is missing."""
  pass


class BuildFileMissingTarget(UncheckedException):
  """Raised when a target is missing from a BUILD file."""
  pass


class TargetCannotBeMapped(UncheckedException):
  """Raised when a target cannot be mapped to a filesystem path."""
  target:str
  location:str
