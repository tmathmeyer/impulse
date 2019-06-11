
from impulse.hal import api
from impulse.ci import gogs
from impulse.ci import github

def main():
  flask_app = api.GetFlask()
  flask_app.RegisterResourceProvider(gogs.BuildManager())
  flask_app.RegisterResourceProvider(github.BuildManager())
  flask_app.run(host='0.0.0.0', port=5566)