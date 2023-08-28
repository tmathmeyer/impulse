from contextlib import contextmanager
import inspect
import re
import sys
import traceback

PASSED = '\033[38;5;2m'
FAILED = '\033[38;5;9m'
FAILED_ = '\033[38;5;88m'
ENDC = '\033[0m'

ANY = object()


class EarlyExitPassedError(Exception):
  pass


class FailedAssertError(Exception):
  def __init__(self, filename, casename, lineno, assertname, A, B):
    super().__init__()
    testbase = __file__[:-27]
    if filename.startswith(testbase):
      filename = filename[len(testbase):]
    self._file_location = '{}:{}'.format(filename, lineno)
    self._assertName = assertname
    self._expected = A
    self._actual = B
    self._casename = casename

  def print(self, string_len):
    fmt = '[ {}{}{} ] {} failed; expected {}, was {}'
    fileLocation = self._file_location
    if len(fileLocation) < string_len:
      fileLocation += ' ' * (string_len - len(fileLocation))
    print(
      fmt.format(
        FAILED_, fileLocation, ENDC, self._casename, self._expected,
        self._actual
      )
    )

  def FileLocationLength(self):
    return len(self._file_location)


class GenericCrashHandler(object):
  def __init__(self, isolator, exc):
    self.exc = exc
    self.isolator = isolator
    exc_type, exc, self.tb = sys.exc_info()

  def print(self):
    print('[ {}{}{} ]'.format(FAILED_, self.isolator.name, ENDC))
    print(self.exc)
    print(traceback.print_tb(self.tb))


def call_with_stack(method):
  def replacement(self, *args, **kwargs):
    return method(self, inspect.currentframe().f_back, *args, **kwargs)

  replacement._wrapped = method
  return replacement


def methods_on(cls):
  for entry in dir(cls):
    test = getattr(cls, entry)
    if callable(test):
      yield entry, test


def ExpectRaises(errtype):
  def decorator(fn):
    def replacement(*args, **kwargs):
      try:
        fn(*args, **kwargs)
      except errtype:
        raise EarlyExitPassedError()
      except AssertionError as e:
        raise EarlyExitPassedError()
      raise FailedAssertError(
        fn.__code__.co_filename, fn.__name__, fn.__code__.co_firstlineno,
        'ExpectFailed', errtype.__name__, 'Nothing Raised'
      )

    return replacement

  return decorator


def ExpectFailed(fn):
  return ExpectRaises(FailedAssertError)(fn)


@contextmanager
def ExpectException(tester, errtype):
  try:
    yield tester
  except FailedAssertError as e:
    raise e
  except Exception as e:
    tester.assertEqual._wrapped(
      tester,
      inspect.currentframe().f_back.f_back, type(e), errtype
    )
  else:
    tester.assertEqual._wrapped(
      tester, inspect.currentframe().f_back.f_back, errtype, 'Nothing Raised'
    )


def AssertRaiseError(assertname, casename, stack, A, B):
  case = stack.f_code.co_name
  file = stack.f_code.co_filename
  line = stack.f_lineno
  raise FailedAssertError(file, casename, line, assertname, A, B)


class TestIsolator():
  def __init__(self, cls, fnname, execute, setup=None, cleanup=None):
    self.setup = setup or self.setup
    self.cleanup = cleanup or self.cleanup
    self.execute = execute
    self.name = '{}.{}'.format(cls.__name__, fnname)
    self.cls = cls
    self.expectations = []

  def run(self):
    self.setup(self)
    self.execute(self)
    self.finish_expectations()
    self.cleanup(self)

  def setup(self, _):
    pass

  def cleanup(self, _):
    pass

  def finish_expectations(self):
    for expectation in self.expectations:
      expectation.assertExpectationsMet()

  def __getattr__(self, attr):
    clsEntry = getattr(self.cls, attr, None)
    if clsEntry and callable(clsEntry):
      return clsEntry.__get__(self, self.cls)
    return self.__getattribute__(attr)

  @call_with_stack
  def assertTrue(self, stack, expr):
    if not expr:
      AssertRaiseError('assertTrue', self.name, stack, True, False)

  @call_with_stack
  def assertFalse(self, stack, expr):
    if expr:
      AssertRaiseError('assertFalse', self.name, stack, False, True)

  @call_with_stack
  def assertEqual(self, stack, A, B):
    if A != B:
      AssertRaiseError('assertEqual', self.name, stack, B, A)

  @call_with_stack
  def assertNotEqual(self, stack, A, B):
    if A == B:
      AssertRaiseError('assertNotEqual', self.name, stack, B, A)

  @call_with_stack
  def assertNoDiff(self, stack, A, B):
    for a, b in zip(A.split('\n'), B.split('\n')):
      if a != b:
        AssertRaiseError('assertNoDiff', self.name, stack, b, a)

  @call_with_stack
  def assertIn(self, stack, A, B):
    if A not in B:
      AssertRaiseError("assertIn", self.name, stack, f'[..., {A}, ...]', B)

  @call_with_stack
  def assertCalledWithArgs(self, stack, *argsets):
    class CalledWithArgsExpector():
      def __init__(cwae):
        cwae.actual = []
        cwae.itr = iter(argsets)

      def assertExpectationsMet(cwae):
        sentinel = object()
        if next(cwae.itr, sentinel) is not sentinel:
          AssertRaiseError(
            'assertCalledWithArgs', self.name, stack, list(argsets), cwae.actual
          )

    cwae = CalledWithArgsExpector()

    def called(*args, **_):
      self.assertEqual._wrapped(
        self, stack, list(args), list(next(cwae.itr, ['NOT CALLED']))
      )
      cwae.actual.append(list(args))

    self.expectations.append(cwae)
    return called


class TestCase(object):
  @classmethod
  def RunAll(cls, notermcolor, export_as='print'):
    cls.RunTests(notermcolor, (lambda x: True), export_as)

  @classmethod
  def RunFilter(cls, notermcolor, filter, export_as='print'):
    cls.RunTests(notermcolor, cls._Matches(filter), export_as)

  @classmethod
  def ListTests(cls):
    pass

  @classmethod
  def RunTests(cls, notermcolor, filtrfn, export_fn):
    if notermcolor:
      global PASSED
      global FAILED
      global FAILED_
      global ENDC
      PASSED = ''
      FAILED = ''
      FAILED_ = ''
      ENDC = ''
    out = {'passes': [], 'failures': [], 'crashes': []}
    for clazz in TestCase.__subclasses__():
      test_methods = []
      setup_method = None
      cleanup_method = None
      for name, method in methods_on(clazz):
        if name == 'setup':
          setup_method = method
        elif name == 'cleanup':
          cleanup_method = method
        elif name.startswith('test_'):
          test_methods.append((method, name))

      for method, name in test_methods:
        full_name = f'{clazz.__name__}.{name[5:]}'
        if not filtrfn(full_name):
          continue
        cls.RunIsolated(
          out, TestIsolator(clazz, name, method, setup_method, cleanup_method)
        )
    return getattr(cls, export_fn)(out)

  @classmethod
  def _Matches(cls, regex):
    matcher = re.compile(regex)

    def filterer(name):
      return matcher.match(name)

    return filterer

  @classmethod
  def RunIsolated(cls, out, isolator):
    try:
      isolator.run()
    except FailedAssertError as e:
      out['failures'].append(e)
    except EarlyExitPassedError as e:
      pass
    except Exception as e:
      out['crashes'].append(GenericCrashHandler(isolator, e))
      return
    out['passes'].append(isolator)

  @classmethod
  def print(cls, out):
    p_len = len(out['passes'])
    f_len = len(out['failures'])
    c_len = len(out['crashes'])
    print(
      '{}{} test{} passed.{}'.format(
        PASSED, p_len, '' if p_len == 1 else 's', ENDC
      )
    )

    if (f_len):
      print(
        '{}{} test{} failed:{}'.format(
          FAILED, f_len, '' if f_len == 1 else 's', ENDC
        )
      )
      max_len = max(f.FileLocationLength() for f in out['failures'])
      for f in out['failures']:
        cls.PrintFailure(f, max_len)

    if (c_len):
      print(
        '{}{} test{} crashed:{}'.format(
          FAILED, c_len, '' if c_len == 1 else 's', ENDC
        )
      )
      for f in out['crashes']:
        cls.PrintCrashed(f)

  @classmethod
  def PrintFailure(cls, failure:FailedAssertError, max_len:int):
    failure.print(max_len)

  @classmethod
  def PrintCrashed(cls, crash:GenericCrashHandler):
    crash.print()


class MockMethod():
  __slots__ = ('_calls', '_name', '_returns')

  def __init__(self, name):
    self._calls = []
    self._returns = []
    self._name = name

  def __call__(self, *args, **kwargs):
    self._calls.append((args, kwargs))
    for a, k, v in self._returns:
      if self._deepcomp(a, args) and self._deepcomp(k, kwargs):
        return v

  def _deepcomp(self, X, Y):
    if (X is ANY) or (Y is ANY):
      return True
    if type(X) != type(Y):
      return False
    if type(X) == list:
      return self._listcompare(X, Y)
    if type(X) == dict:
      return self._dictcompare(X, Y)
    return X == Y

  def _listcompare(self, X, Y):
    if len(X) != len(Y):
      return False
    for x, y in zip(X, Y):
      if not self._deepcomp(x, y):
        return False
    return True

  def _dictcompare(self, X, Y):
    if len(X) != len(Y):
      return False
    for k, v in X.items():
      if k not in Y:
        return False
      if not self._deepcomp(v, Y[k]):
        return False
    return True

  def ReturnWhenCalled(self, retval, *args, **kwargs):
    for ent in self._returns:
      if self._deepcomp(args, ent[0]) and self._deepcomp(kwargs, ent[1]):
        ent[2] = retval
        return
    self._returns.append([args, kwargs, retval])

  @call_with_stack
  def AssertCalled(self, stack, *args, **kwargs):
    if not self._calls:
      AssertRaiseError(
        'assertCall', self._name, stack, f'{self._name} to be called',
        'not called'
      )
    sargs, skwargs = self._calls.pop()
    if not self._listcompare(sargs, args):
      AssertRaiseError('assertCall', self._name, stack, sargs, args)
    if not self._dictcompare(skwargs, kwargs):
      AssertRaiseError('assertCall', self._name, stack, skwargs, kwargs)

  @call_with_stack
  def AssertCallsChecked(self, stack):
    if self._calls:
      AssertRaiseError(
        'assertCallsChecked', self._name, stack,
        f'No unchecked calls to {self._name}',
        f'called with args: {self._calls}'
      )


def MockAllModuleMethods(module):
  for name in dir(module):
    entry = getattr(module, name)
    if type(entry) == type(MockAllModuleMethods):
      setattr(module, name, MockMethod(name))
    if type(entry) == MockMethod:
      setattr(module, name, MockMethod(name))
