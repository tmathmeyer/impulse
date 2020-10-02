
from impulse.hal import api


HOSTNAME = None


class Impulse(api.Resource('impulse')):
  def __init__(self):
    super().__init__()

  def get_core_json(self):
    return { }

  def type(self):
    return self.__class__


class ImpulseManager(api.ProvidesResources(Impulse)):
  def __init__(self, hostname):
    super().__init__(explorer=True)
    self._hostname = hostname

  @api.METHODS.get('/identify')
  def byHostname(self) -> str:
    return self._hostname


def SetupContainerService(hostname):
  global HOSTNAME
  HOSTNAME = hostname
  api.GetFlaskInstance().RegisterResourceProvider(ImpulseManager(hostname))


def SetContainerServiceHostname(hostname):
  SetupContainerService(hostname)


def GetHostname():
  global HOSTNAME
  return HOSTNAME