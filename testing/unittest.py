
import inspect


STRING_SIZE = 29


class FailedExpectationException(Exception):
  def __init__(self, filename, casename, lineno, assertName, expected, actual):
    self._filename = filename
    self._lineno = lineno
    self._assertName = assertName
    self._expected = expected
    self._actual = actual
    self._casename = casename

  def print(self, exporter, _):
    fmt = '[ {} ] {} failed; expected {}, was {}'
    fileLocation = '{}:{}'.format(self._filename, self._lineno)
    if len(fileLocation) < STRING_SIZE:
      fileLocation += ' ' * (STRING_SIZE - len(fileLocation))
    if len(fileLocation) > STRING_SIZE -3:
      fileLocation = '...' + fileLocation[-STRING_SIZE+3:]
    print(fmt.format(
      fileLocation, self._assertName, self._expected, self._actual))
    if not hasattr(exporter, 'failures'):
      exporter.failures = 1
    else:
      exporter.failures += 1

  def json(self, exporter, clazz):
    if not hasattr(exporter, 'failures'):
      exporter.failures = []
    exporter.failures.append({
      'filename': self._filename,
      'testcase': self._casename,
      'line_number': self._lineno,
      'actual_value': self._actual,
      'assert_type': self._assertName,
      'expected_value': self._expected,
      'classname': clazz.__name__,
    })


class ReportSuccess():
  def __init__(self, clazz, testmethod):
    self._clazz = clazz
    self._testmethod = testmethod

  def print(self, exporter):
    fmt = '[ {} ] Success'
    funcname = '{}.{}'.format(self._clazz.__name__, self._testmethod.__name__)
    if len(funcname) < STRING_SIZE:
      funcname += ' ' * (STRING_SIZE - len(funcname))
    if len(funcname) > STRING_SIZE:
      funcname = funcname[-STRING_SIZE:]
    print(fmt.format(funcname))

  def json(self, exporter):
    if not hasattr(exporter, 'successes'):
      exporter.successes = []
    exporter.successes.append({
      'testcase': self._testmethod.__name__,
      'classname': self._clazz.__name__
    })


class TestCaseDataExporter(object):
  def markFailed(self, stack, expected, actual):
    assertName = inspect.currentframe().f_back.f_code.co_name
    testcaseName = stack.f_code.co_name
    testcaseFile = stack.f_code.co_filename
    raise FailedExpectationException(
      testcaseFile, testcaseName, stack.f_lineno,
      assertName, expected, actual)

  def print(self):
    return getattr(self, 'failures', 0)

  def json(self):
    return  {
      'successes': getattr(self, 'successes', []),
      'failures': getattr(self, 'failures', [])
    }

  def run(self, export_as='print'):
    for clazz in TestCase.__subclasses__():
      methods = dir(clazz)
      for testmethod in filter(lambda f: f.startswith('test_'), methods):
        if callable(getattr(clazz, testmethod)):
          inst = clazz(self)
          if 'setup' in methods:
            inst.setup()

          success = False
          fn = getattr(inst, testmethod)
          exc = None
          f_bad = False
          try:
            fn()
            if fn.__name__ == 'INVERSION':
              f_bad = True
              raise FailedExpectationException(
                fn._fileline[0], testmethod, fn._fileline[1],
                'ExpectFailed', 'method to fai', 'passed instead')
            success = True
          except FailedExpectationException as e:
            exc = e
            if fn.__name__ == 'INVERSION':
              success = True
            if f_bad:
              success = False
            exc = e

          if success:
            getattr(ReportSuccess(clazz, fn), export_as)(self)
          else:
            getattr(exc, export_as)(self, clazz)


          if 'teardown' in methods:
            inst.teardown()
    return getattr(self, export_as)()


def ExpectFailed(func):
  def INVERSION(*a, **k):
    return func(*a, **k)
  INVERSION._fileline = (
    func.__code__.co_filename, func.__code__.co_firstlineno)
  return INVERSION


def initializedWithStack(classmethod):
  def replacement(self, *args):
    return classmethod(self, inspect.currentframe().f_back, *args)
  return replacement


tests = TestCaseDataExporter()


class TestCase(object):
  def __init__(self, exporter):
    self._exporter = exporter

  @initializedWithStack
  def assertTrue(self, stack, expression):
    if not expression:
      self._exporter.markFailed(stack, True, False)

  @initializedWithStack
  def assertFalse(self, stack, expression):
    if expression:
      self._exporter.markFailed(stack, False, True)

  @initializedWithStack
  def assertEqual(self, stack, A, B):
    if A != B:
      self._exporter.markFailed(stack, A, B)