

class RenderableError(Exception):
  pass


class FatalError(RenderableError):
  pass


class FileHighlightError(RenderableError):
  @staticmethod
  def GetUnderlineHighlightTextInFile(file, text, start, end):
    text = str(text)
    with open(file, 'r') as f:
      for lno, line in enumerate(f.readlines()):
        lno += 1
        if lno < start:
          continue
        if lno > end:
          return f'`{text}` not found in {file} between {start}-{end}'
        if text in line:
          line = line.strip()
          start = line.find(text)
          spaces = (start+6) * ' '
          squigs = (len(text)-2) * '~'
          return f'{file}:\n...\n{lno:04}: {line}\n{spaces}^{squigs}^\n'

  def __init__(self, message, source, text, minline, maxline):
    super().__init__(f'{message}:\n{FileHighlightError.GetUnderlineHighlightTextInFile(source, text, minline, maxline)}')


class InvalidDependency(FileHighlightError):
  def __init__(self, targetname, targetfile, sourcefile, sourcerange):
    super().__init__(
      f'Failed to load target {targetname} (expected buildfile: {targetfile})',
      sourcefile,
      targetname,
      minline=sourcerange.lineno,
      maxline=sourcerange.end_lineno)


class InvalidSyntax(FileHighlightError):
  def __init__(self, message, search, frame):
    super().__init__(
      message, frame.filename, search, frame.positions.lineno, frame.positions.end_lineno)


class FileNotFoundError(FileHighlightError):
  def __init__(self, missing, source, sourcerange):
    super().__init__(
      f'File not found: {missing}',
      source, missing, sourcerange.lineno, sourcerange.end_lineno)