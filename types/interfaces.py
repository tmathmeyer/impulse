
FileName = str
PackageName = str
DirectoryName = str
CommandLineString = str
Tag = str
EnvironmentVarName = str
EnvironmentVarValue = str


class Package():
  '''Buildrules always operate primarily on a `Package` object to track
  input and output files'''

  def AddFile(self, filename:FileName) -> None:
    '''Adds a file to the output package.'''
    raise NotImplementedError()

  def AddDirectory(self, directory:FileName) -> None:
    '''Adds all files in a directory'''
    raise NotImplementedError()

  def GetPackageName(self) -> PackageName:
    '''Gets the name of the package.'''
    raise NotImplementedError()

  def GetPackageDirectory(self) -> DirectoryName:
    '''Gets the package source directory.'''
    raise NotImplementedError()

  def ExecutionFailed(self, command:CommandLineString, stderr:str):
    '''Triggers an exception with given cmdline and stderr.'''
    raise NotImplementedError()

  def UseTempDir(self):
    '''Create a context manager for a temporary directory.'''
    raise NotImplementedError()

  def Dependencies(self, **filters) -> list['Package']:
    '''Gets all Packages which this Package depends on'''
    raise NotImplementedError()

  def SetTags(self, *tags:list[Tag]) -> None:
    '''Adds tags to this target.'''
    raise NotImplementedError()

  def Execute(self, *cmds:list[CommandLineString]) -> None:
    '''Executes |cmds| in order.'''
    raise NotImplementedError()

  def SetEnvVar(self, var:EnvironmentVarName, value:EnvironmentVarValue):
    '''Sets an environment variable for execution.'''
    raise NotImplementedError()

  def IsDebug(self) -> bool:
    '''Is this target being built in debug mode?'''
    raise NotImplementedError()

  def UnsetEnvVar(self, var:EnvironmentVarName):
    '''Unsets an environment variable for execution.'''
    raise NotImplementedError()

  def IncludedFiles(self) -> list[FileName]:
    '''Gets a list of all files included in this package.'''
    raise NotImplementedError()

  def Semaphor(self) -> None:
    '''Returns a semaphor context object which allows only one instance of
    this type of build rule to be run at a single time. This will slow down
    a build pipeline significantly'''
    raise NotImplementedError()
