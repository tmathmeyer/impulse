
class ImpulseBaseException(Exception):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)


class FileErrorException(ImpulseBaseException):
  @staticmethod
  def Render(filename, line, position, highlight_len):
    def ReadLineRange(start, end):
      with open(filename, 'r') as f:
        for i, line in enumerate(f.readlines()):
          if i < start:
            continue
          if i > end:
            break
          yield line
    content = ''.join(ReadLineRange(max(0, line-2), line-1))
    indent = ' ' * position
    squigly = '~' * max(0, highlight_len-2)
    return f'{content}{indent}^{squigly}^\n'

  def __init__(self, message, filename, line, pos, sq_len=0):
    super().__init__(
      f'{message}\n{filename}:{line}:'
      f'{FileErrorException.Render(filename, line, pos, sq_len)}')


class NoSuchRuleType(FileErrorException):
  """Raised when a build rule doesn't exist."""
  def __init__(self, filename, line, rulename):
    super().__init__(f'No such build rule type "{rulename}"',
      filename, line, 0, len(rulename))


class ListedSourceNotFound(Exception):
  def __init__(self, filename, targetname):
    super().__init__('[{}] used in [{}] not found on disk.'.format(
      filename, targetname))
    self.filename = filename
    self.targetname = targetname

class InvalidPathException(Exception):
  """Raised when a path is invalid for a provided reason."""
  def __init__(self, path, reason):
    super().__init__('[{}] invalid: {}'.format(path, reason))
    self.path = path
    self.reason = reason


class BuildDefsRaisesException(Exception):
  """Raised when a build_defs file raises an exception."""
  def __init__(self, target_name, buildrule_name, exception):
    fmt = '"{}" raised exception while building target "{}":\n{}'
    super().__init__(fmt.format(buildrule_name, target_name, exception))


class BuildRuleCompilationError(Exception):
  """Raised when a build rule fails to parse/compile correctly."""
  def __init__(self, ex2):
    super().__init__(ex2)


class ImpulseAssertWrapperError(Exception):
  """Raised when an impulse core library assert fails."""
  def __init__(self, ex3):
    super().__init__(ex3)


class BuildTargetCycle(Exception):
  """Raised when there is a dependency cycle."""
  @classmethod
  def Cycle(cls, pbt):
    return cls(cls._Message([pbt]), [pbt])

  @classmethod
  def _Message(cls, stack):
    msg = 'Build target cycle:\n{}'
    return msg.format(' => '.join(s.GetName() for s in stack))

  def __init__(self, message, pbts):
    self._parsed_target_stack = pbts
    super().__init__(message)

  def ChainException(self, pbt):
    newstack = [pbt] + self._parsed_target_stack
    return BuildTargetCycle(
      BuildTargetCycle._Message(newstack), newstack)


class BuildTargetMissing(ImpulseBaseException):
  """Raised when a build target is missing."""
  def __init__(self, ex6):
    super().__init__(ex6)


class FileImportException(Exception):
  """Raised when a file can't be recursively imported."""
  def __init__(self, ex, file):
    super().__init__('Exception occured importing {}:\n{}'.format(file, ex))


class BuildTargetMissingFrom(ImpulseBaseException):
  """Raised when a build target is missing."""
  def __init__(self, target, buildrule):
    super().__init__('Target "{}", used in "{}", is missing.'.format(
      target, buildrule))


class BuildTargetNoBuildNecessary(Exception):
  """Raised when a build target didn't actually need rebuilding."""
  def __init__(self):
    super().__init__('Build not necessary')



class FilesystemSyncException(Exception):
  """Raised when shit hits the fan."""
  def __init__(self):
    super().__init__('The filesystem is out of sync, please try rerunning.')


class FatalException(Exception):
  def __init__(self, s):
    super().__init__(s)


class MacroException(Exception):
  def __init__(self, macro, name, reason):
    super().__init__(f'{name}<{macro}> expansion failed: {reason}')


class PlatformKeyAbsentError(ImpulseBaseException):
  def __init__(self, platname, platkey):
    super().__init__(f'platform {platname} missing property {platkey}')