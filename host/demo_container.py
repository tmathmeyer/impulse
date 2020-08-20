
from impulse.hal import api
from impulse.host import libhost

def main():
  flask_app = api.GetFlask()
  libhost.SetupContainerService(flask_app, 'demo.tedm.io')
  flask_app.run(host='0.0.0.0', port=5566)