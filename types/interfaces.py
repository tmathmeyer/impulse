
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

  def AddFile(self, filename:FileName):
    '''Adds a file to the output package.'''
    pass

  def AddDirectory(self, directory:FileName):
    '''Adds all files in a directory'''
    pass

  def GetPackageName(self) -> PackageName:
    '''Gets the name of the package.'''
    pass

  def GetPackageDirectory(self) -> DirectoryName:
    '''Gets the package source directory.'''
    pass

  def ExecutionFailed(self, command:CommandLineString, stderr:str):
    '''Triggers an exception with given cmdline and stderr.'''
    pass

  def UseTempDir(self):
    '''Create a context manager for a temporary directory.'''
    pass

  def Dependencies(self, **filters) -> ['Package']:
    '''Gets all Packages which this Package depends on'''
    pass

  def SetTags(self, *tags:list[Tag]) -> None:
    '''Adds tags to this target.'''
    pass

  def Execute(self, *cmds:list[CommandLineString]) -> None:
    '''Executes |cmds| in order.'''
    pass

  def SetEnvVar(self, var:EnvironmentVarName, value:EnvironmentVarValue):
    '''Sets an environment variable for execution.'''
    pass

  def IsDebug(self) -> bool:
    '''Is this target being built in debug mode?'''

  def UnsetEnvVar(self, var:EnvironmentVarName):
    '''Unsets an environment variable for execution.'''
    pass

  def IncludedFiles(self) -> list[FileName]:
    '''Gets a list of all files included in this package.'''
    pass

  def Semaphor(self) -> None:
    '''Returns a semaphor context object which allows only one instance of
    this type of build rule to be run at a single time. This will slow down
    a build pipeline significantly'''
    pass
