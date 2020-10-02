
from impulse.ci2 import github
from impulse.ci2 import integration
from impulse.ci2 import runner
from impulse.hal import api
from impulse.host import libhost


def main():
  libhost.SetContainerServiceHostname('ci.tedm.io')
  app = api.GetFlaskInstance()

  jobHost = runner.JobHost()
  app.RegisterResourceProvider(github.WebhookListener(jobHost))
  app.RegisterResourceProvider(integration.IntegrationJobCache(jobHost))

  os.system('git config --global user.email "ci@impulse.ci"')
  os.system('git config --global user.name "impulse_ci"')

  app.Log('Starting')
  app.run(host='0.0.0.0', port=5566)
