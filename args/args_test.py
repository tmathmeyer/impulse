
from impulse.testing import unittest
from impulse.args import args
from impulse.util import temp_dir
import os


def CreateTemporaryDirectory():
  result = temp_dir.ScopedTempDirectory(delete_non_empty=True)
  result.__enter__()
  os.system('mkdir example')
  os.system('mkdir rapid')
  os.system('mkdir rasin')
  os.system('mkdir foobar')

  return result


class TestDirectoryCompletion(unittest.TestCase):

  def setup(self):
    self.deleteme = CreateTemporaryDirectory()

  def teardown(self):
    self.deleteme.__exit__()

  def test_get_directories(self):
    expanded_from_e = list(args.Directory._get_directories('e'))
    self.assertEqual(set(expanded_from_e), set(['example']))
    expanded_from_r = list(args.Directory._get_directories('r'))
    self.assertEqual(set(expanded_from_r), set(['rapid', 'rasin']))
    expanded_from_rpc = list(args.Directory._get_directories('rapid'))
    self.assertEqual(set(expanded_from_rpc), set(['rapid']))

  def test_get_completion(self):
    expanded_from_e = list(args.Directory.get_completion_list('e?'))
    self.assertEqual(set(expanded_from_e), set(['example', 'example/']))
    expanded_from_r = list(args.Directory.get_completion_list('r?'))
    self.assertEqual(set(expanded_from_r), set(['rapid', 'rasin']))
    expanded_from_rpc = list(args.Directory.get_completion_list('rapid?'))
    self.assertEqual(set(expanded_from_rpc), set(['rapid', 'rapid/']))


class TestArgumentParserDecorator(unittest.TestCase):

  def setup(self):
    self.deleteme = CreateTemporaryDirectory()

  def teardown(self):
    self.deleteme.__exit__()

  def test_zero_args(self):
    ap = args.ArgumentParser(False)
    self.assertEqual(ap._methods, {})
    self.assertEqual(ap._complete, False)

    @ap
    def _e1():
      pass

    self.assertEqual(ap._methods, {
      '_e1': {
        'func': _e1,
        'args': {}
      },
    })

  @unittest.ExpectRaises(SyntaxError)
  def test_requires_annotation(self):
    ap = args.ArgumentParser(False)
    @ap
    def _e1(A):
      pass

  def test_no_default_arg(self):
    ap = args.ArgumentParser(False)
    self.assertEqual(ap._methods, {})
    self.assertEqual(ap._complete, False)

    @ap
    def _e1(A:str):
      pass

    self.assertEqual(ap._methods, {
      '_e1': {
        'func': _e1,
        'args': {
          'A': str
        }
      },
    })

  def test_has_default_arg(self):
    ap = args.ArgumentParser(False)
    self.assertEqual(ap._methods, {})
    self.assertEqual(ap._complete, False)

    @ap
    def _e1(A:str='a'):
      pass

    self.assertEqual(ap._methods, {
      '_e1': {
        'func': _e1,
        'args': {
          '--A': str
        }
      },
    })


  @unittest.ExpectRaises(SyntaxError)
  def test_is_bool_needs_default(self):
    ap = args.ArgumentParser(False)
    self.assertEqual(ap._methods, {})
    self.assertEqual(ap._complete, False)

    @ap
    def _e1(A:bool):
      pass

    self.assertEqual(ap._methods, {
      '_e1': {
        'func': _e1,
        'args': {
          '--A': bool
        }
      },
    })

  def test_is_bool_has_default(self):
    ap = args.ArgumentParser(False)
    self.assertEqual(ap._methods, {})
    self.assertEqual(ap._complete, False)

    @ap
    def _e1(A:bool=False):
      pass

    self.assertEqual(ap._methods, {
      '_e1': {
        'func': _e1,
        'args': {
          '--A': None
        }
      },
    })


class TestArgumentParserComplete(unittest.TestCase):

  def setup(self):
    self.deleteme = CreateTemporaryDirectory()

  def teardown(self):
    self.deleteme.__exit__()

  def test_completion_method(self):
    ap = args.ArgumentParser()
    @ap
    def example():
      pass

    @ap
    def eat():
      pass

    ap._handle_completion(['e'], self.assertCalledWithArgs(
      ('example',), ('eat',)))


  def test_completion_directory_required(self):
    ap = args.ArgumentParser()
    @ap
    def example(foo:args.Directory):
      pass
    ap._handle_completion(['example', 'r?'], self.assertCalledWithArgs(
      ['rasin'], ['rapid']))

  def test_completion_directory_flag(self):
    ap = args.ArgumentParser()
    @ap
    def example(foo:args.Directory='rpc'):
      pass
    ap._handle_completion(['example', '--?'], self.assertCalledWithArgs(
      ['--foo']))
    ap._handle_completion(['example', '--foo', 'r?'], self.assertCalledWithArgs(
      ['rasin'], ['rapid']))