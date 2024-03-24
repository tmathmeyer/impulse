import os


class Environ():
  def __getattr__(self, attr):
    return os.environ[attr]
  def __getitem__(self, item):
    return os.environ[item]
ENV = Environ()


def Root():
  if 'impulse_root' not in os.environ:
    config = f'{ENV.HOME}/.config/impulse/config'
    if os.path.exists(config):
      with open(config, 'r') as f:
        os.environ['impulse_root'] = f.read()
    else:
      raise LookupError('Impulse has not been initialized.')
  return os.environ['impulse_root']