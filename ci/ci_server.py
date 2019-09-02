
from impulse.hal import api
from impulse.ci import ci_pooling
from impulse.ci import logging
from impulse.ci import gogs
from impulse.ci import github

def main():
  flask_app = api.GetFlask()
  builders = ci_pooling.BuilderPool(4)

  logging.EnableTracing()

  flask_app.RegisterResourceProvider(gogs.BuildManager(builders))
  flask_app.RegisterResourceProvider(github.BuildManager(builders))
  flask_app.run(host='0.0.0.0', port=5566)