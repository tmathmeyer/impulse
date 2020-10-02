
from impulse.ci2 import github
from impulse.ci2 import integration
from impulse.ci2 import runner
from impulse.hal import api
from impulse.host import libhost

class Mock(api.Resource('mock')):
  def __init__(self):
    super().__init__()

  def get_core_json(self):
    return { }


class MockJobHost(api.ProvidesResources(Mock)):
  def __init__(self, job_host):
    super().__init__(explorer=True)
    self._job_host = job_host

  @api.METHODS.get('/')
  def handle_webhook(self) -> str:
    self._job_host.EnqueueJob(integration.IntegrationJob(
      action='Mock',
      job_source='Mock',
      description='lorem ipsum something latin',
      diff_url='https://sptth.url',
      authenticated=False,
      repo_merge_into='INVALID MERGE INTO URL',
      branch_merge_into='INVALID MERGE INTO BRANCH',
      repo_merge_from='INVALID MERGE FROM URL',
      branch_merge_from='INVALID MERGE FROM BRANCH',
    ))
    return 'NICE'





def main():
  libhost.SetContainerServiceHostname('ci.tedm.io')
  app = api.GetFlaskInstance()

  jobHost = runner.JobHost()
  app.RegisterResourceProvider(github.WebhookListener(jobHost))
  app.RegisterResourceProvider(integration.IntegrationJobCache(jobHost))
  app.RegisterResourceProvider(MockJobHost(jobHost))


  app.Log('Starting')
  app.run(host='0.0.0.0', port=5566)
