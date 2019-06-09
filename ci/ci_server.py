
from impulse.hal import api
from impulse.ci import build

def main():
  flask_app = api.GetFlask()
  flask_app.RegisterResourceProvider(build.BuildManager())
  flask_app.run(host='0.0.0.0', port=5566)