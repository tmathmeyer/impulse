


class BuildRuleRuntimeError(Exception):
  """Raised when a build_defs file raises an exception."""
  pass


class BuildRuleCompilationError(Exception):
  """Raised when a build rule fails to parse/compile correctly."""
  def __init__(self, ex):
    super(ex)
    print(ex.__class__)


class ImpulseAssertWrapperError(Exception):
  """Raised when an impulse core library assert fails."""
  pass


class BuildTargetNeedsNoUpdate(Exception):
  """Raised when a build target was built recently."""
  pass


class BuildTargetCycle(Exception):
  """Raised when there is a dependency cycle."""
  pass


class BuildTargetMissing(Exception):
  """Raised when a build target is missing."""
  pass


class FileImportException(Exception):
  """Raised when a file can't be recursively imported."""
  def __init__(self, exc, file):
    super(exc)


class BuildTargetMissingFrom(Exception):
  """Raised when a build target is missing."""
  def __init__(self, target, buildrule):
    super().__init__('Target "{}", used in "{}", is missing.'.format(
      target, buildrule))


class NoSuchRuleType(Exception):
  """Raised when a build rule doesn't exist."""
  def __init__(self, missing_type):
    super().__init__('No such build rule type "{}"'.format(missing_type))