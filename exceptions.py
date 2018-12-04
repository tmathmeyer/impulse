


class BuildRuleRuntimeError(Exception):
  """Raised when a build_defs file raises an exception."""
  pass


class BuildRuleCompilationError(Exception):
  """Raised when a build rule fails to parse/compile correctly."""
  pass


class ImpulseAssertWrapperError(Exception):
  """Raised when an impulse core library assert fails."""
  pass


class BuildTargetNeedsNoUpdate(Exception):
  """Raised when a build target was built recently."""
  pass