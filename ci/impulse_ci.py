
import flask
from flask import request

from impulse.ci import flask_api
from impulse.ci import build_task
from impulse.rpc import rpc

class WebHookResourceProvider(flask_api.ResourceProvider):
  def __init__(self, flask):
    super(WebHookResourceProvider, self).__init__('webhooks', flask)
    self._CIProcessPool = rpc.RPC(build_task.ProcessPool, 3)

  @flask_api.METHODS.post('/')
  def handle_post_request(self, data=None):
    pr = data.get('pull_request', None)
    if not pr:
      raise flask_api.ServiceError(500, 'Only supports pull request')

    if data.get('action', None) == 'opened':
      return self.HAL(self._CIProcessPool.StartJob(pr))

    raise flask_api.ServiceError(500, 'Only supports opened issues')

  @flask_api.METHODS.get('/')
  def handle_get_req(self):
    query_index = request.args.get('index', 0)
    return self.HALList(self._CIProcessPool.GetNJobs(query_index, 10))

  @flask_api.METHODS.get('/<req_id>')
  def get_specific_req(self, req_id):
    job = self._CIProcessPool.GetJob(req_id)
    if job is None:
      raise flask_api.ServiceError(404, 'Not Found')
    return self.HAL(job, full=True)


def main():
  flask_app = flask.Flask(__name__)

  WebHookResourceProvider(flask_app)

  flask_app.run(host='0.0.0.0', port=5566)
