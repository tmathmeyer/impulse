from impulse.core.interface import IFace
import typing

FileName = str
PackageName = str
DirectoryName = str
CommandLineString = str
Tag = str
EnvironmentVarName = str
EnvironmentVarValue = str


@IFace
class Package():
  """
  Buildrules always operate primarily on a `Package` object to track
  input and output files.
  """

  def AddFile(self, filename:FileName) -> None:
    """
    Adds a file to the output package.

    Args:
        filename:The path to the file to include in the package.
    """
    raise NotImplementedError()

  def AddDirectory(self, directory:FileName) -> None:
    """
    Adds all files in a directory to the output package.

    Args:
        directory:The path to the directory whose contents should be included.
    """
    raise NotImplementedError()

  def GetPackageName(self) -> PackageName:
    """
    Gets the name of the package.

    Returns:
        The name of the package.
    """
    raise NotImplementedError()

  def GetPackageDirectory(self) -> DirectoryName:
    """
    Gets the package source directory.

    Returns:
        The directory where the package's BUILD file is located.
    """
    raise NotImplementedError()

  def ExecutionFailed(self, command:CommandLineString, stderr:str):
    """
    Triggers an exception with given cmdline and stderr.

    Args:
        command:The command that failed.
        stderr:The error message from the failed command.
    """
    raise NotImplementedError()

  def UseTempDir(self):
    """
    Create a context manager for a temporary directory.

    Returns:
        A context manager providing a temporary directory.
    """
    raise NotImplementedError()

  def Dependencies(self, **filters) -> list['Package']:
    """
    Gets all Packages which this Package depends on.

    Args:
        **filters:Key-value pairs to filter the dependencies (e.g., tags).

    Returns:
        A list of Package objects representing the dependencies.
    """
    raise NotImplementedError()

  def SetTags(self, *tags:Tag) -> None:
    """
    Adds tags to this target.

    Args:
        *tags:Variable length argument list of tags to add.
    """
    raise NotImplementedError()

  def Execute(self, *cmds:CommandLineString) -> None:
    """
    Executes|cmds| in order.

    Args:
        *cmds:Variable length argument list of command lines to execute.
    """
    raise NotImplementedError()

  def SetEnvVar(self, var:EnvironmentVarName, value:EnvironmentVarValue):
    """
    Sets an environment variable for execution.

    Args:
        var:The name of the environment variable.
        value:The value to set.
    """
    raise NotImplementedError()

  def IsDebug(self) -> bool:
    """
    Is this target being built in debug mode?

    Returns:
        True if in debug mode, False otherwise.
    """
    raise NotImplementedError()

  def UnsetEnvVar(self, var:EnvironmentVarName):
    """
    Unsets an environment variable for execution.

    Args:
        var:The name of the environment variable to unset.
    """
    raise NotImplementedError()

  def IncludedFiles(self) -> list[FileName]:
    """
    Gets a list of all files included in this package.

    Returns:
        A list of file paths included in the package.
    """
    raise NotImplementedError()

  def Semaphor(self) -> None:
    """
    Returns a semaphor context object which allows only one instance of
    this type of build rule to be run at a single time. This will slow down
    a build pipeline significantly.
    """
    raise NotImplementedError()
