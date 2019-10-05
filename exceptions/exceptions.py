
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
  def Cycle(cls, pbt: 'ParsedBuildTarget'):
    return cls(cls._Message([pbt]), [pbt])

  @classmethod
  def _Message(cls, stack):
    msg = 'Build target cycle:\n{}'
    return msg.format(' => '.join(s.GetName() for s in stack))

  def __init__(self, message, pbts):
    self._parsed_target_stack = pbts
    super().__init__(message)

  def ChainException(self, pbt: 'ParsedBuildTarget'):
    newstack = [pbt] + self._parsed_target_stack
    return BuildTargetCycle(
      BuildTargetCycle._Message(newstack), newstack)


class BuildTargetMissing(Exception):
  """Raised when a build target is missing."""
  def __init__(self, ex6):
    super().__init__(ex6)


class FileImportException(Exception):
  """Raised when a file can't be recursively imported."""
  def __init__(self, ex, file):
    super().__init__('Exception occured importing {}:\n{}'.format(file, ex))


class BuildTargetMissingFrom(Exception):
  """Raised when a build target is missing."""
  def __init__(self, target, buildrule):
    super().__init__('Target "{}", used in "{}", is missing.'.format(
      target, buildrule))


class NoSuchRuleType(Exception):
  """Raised when a build rule doesn't exist."""
  def __init__(self, missing_type):
    super().__init__('No such build rule type "{}"'.format(missing_type))


class FilesystemSyncException(Exception):
  """Raised when shit hits the fan."""
  def __init__(self):
    super().__init__('The filesystem is out of sync, please try rerunning.')


class FatalException(Exception):
  def __init__(self, s):
    super().__init__(s)


class RerunRuleException(Exception):
  def __init__(self, new_dependencies):
    super().__init__('')
    self.new_dependencies = new_dependencies