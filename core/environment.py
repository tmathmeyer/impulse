
import os


class Environ(object):
  """A helper class to access environment variables via attributes or keys."""
  def __getattr__(self, attr:str) -> str:
    return os.environ[attr]

  def __getitem__(self, item:str) -> str:
    return os.environ[item]


ENV=Environ()


def Root() -> str:
  """
  Returns the impulse root directory, initializing it from config if
  necessary.
  """
  if 'impulse_root' not in os.environ:
    config=f'{ENV.HOME}/.config/impulse/config'
    if os.path.exists(config):
      with open(config, 'r') as f:
        os.environ['impulse_root'] = f.read()
    else:
      raise LookupError('Impulse has not been initialized.')
  return os.environ['impulse_root']
