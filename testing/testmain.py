from impulse.args import args
from impulse.testing import unittest


arguments = args.ArgumentParser(complete=True)


@arguments
def run():
  """Runs unit tests."""
  failure_count = unittest.tests.run(export_as='print')
  print('{} test{} failed'.format(
    failure_count,
    's' if failure_count != 1 else ''))


def upload_results(results):
  #TODO actually upload something somewhere
  return 'https://localhost:8080/CI/1c592d73657aa9c8a8fd04dbd66f086ce7bb1274'

@arguments
def export_results():
  """Runs unit tests and uploads them to a service."""
  as_dict = unittest.tests.run(export_as='json')
  url = upload_results(as_dict)
  print('{} test{} failed. See results at {}'.format(
    len(as_dict.get('failures', [])),
    's' if len(as_dict.get('failures', [])) != 1 else '',
    url))


def main():
  arguments.eval()
