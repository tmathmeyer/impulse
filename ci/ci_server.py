
from impulse.ci import ci_pooling
from impulse.ci import logging
from impulse.ci import gogs
from impulse.ci import github
from impulse.hal import api
from impulse.host import libhost

def main():
  libhost.SetupContainerService('hosts.tedm.io')
  builders = ci_pooling.BuilderPool(4)

  app = api.GetFlask()
  app.Log('Starting')

  app.RegisterResourceProvider(gogs.BuildManager(builders))
  app.RegisterResourceProvider(github.BuildManager(builders))
  app.run(host='0.0.0.0', port=5566)
