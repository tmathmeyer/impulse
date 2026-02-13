
import typing

class RenderableError(Exception):
  """Base class for errors that can be rendered to the user."""
  pass


class FatalError(RenderableError):
  """Exception raised for unrecoverable errors."""
  pass


class PositionInfo(typing.Protocol):
  """Protocol for objects providing line number information."""
  lineno:int
  end_lineno:int


class FrameInfo(typing.Protocol):
  """Protocol for objects providing frame context information."""
  filename:str
  positions:PositionInfo


class FileHighlightError(RenderableError):
  """Exception that provides a highlighted snippet of the source file."""
  @staticmethod
  def GetUnderlineHighlightTextInFile(file:str, text:str, start:int,
                                       end:int) -> str:
    """Extracts a line from a file and adds an underline highlight to it."""
    text=str(text)
    try:
      with open(file, 'r') as f:
        for lno, line in enumerate(f.readlines()):
          lno+=1
          if lno < start:
            continue
          if lno > end:
            return f'`{text}` not found in {file} between {start}-{end}'
          if text in line:
            line_content=line.strip()
            pos=line_content.find(text)
            spaces=(pos) * ' '
            if len(text) >= 2:
              squigs=(len(text) - 2) * '~'
              hl=f'^{squigs}^'
            else:
              hl='^'
            res=f'{file}:\n...\n{lno:04}: {line_content}\n{spaces}{hl}\n'
            return res
    except Exception as e:
      return f'Unable to read {file}: {str(e)}'
    return f'`{text}` not found in {file}'

  def __init__(self, message:str, source:str, text:str, minline:int,
               maxline:int):
    highlight=FileHighlightError.GetUnderlineHighlightTextInFile(
        source, text, minline, maxline)
    super().__init__(f'{message}:\n{highlight}')


class InvalidDependency(FileHighlightError):
  """Exception raised when a dependency cannot be resolved."""
  def __init__(self, targetname:str, targetfile:str, sourcefile:str,
               sourcerange:PositionInfo):
    super().__init__(
      f'Failed to load target {targetname} (expected buildfile: {targetfile})',
      sourcefile,
      targetname,
      minline=sourcerange.lineno,
      maxline=sourcerange.end_lineno)


class InvalidSyntax(FileHighlightError):
  """Exception raised for syntax errors in build files."""
  def __init__(self, message:str, search:str, frame:FrameInfo):
    super().__init__(
      message, frame.filename, search, frame.positions.lineno,
      frame.positions.end_lineno)


class FileNotFoundError(FileHighlightError):
  """Exception raised when a required file is missing."""
  def __init__(self, missing:str, source:str, sourcerange:PositionInfo):
    super().__init__(
      f'File not found: {missing}',
      source, missing, sourcerange.lineno, sourcerange.end_lineno)
