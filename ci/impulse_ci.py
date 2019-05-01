
import flask
import uuid

from impulse.ci import flask_api

class WebhookBuildTask(flask_api.Resource):
  def __init__(self, head, head_branch, base, base_branch):
    self._head = head
    self._head_branch = head_branch
    self._base = base
    self._base_branch = base_branch
    self._id = uuid.uuid4()

  def get_full_json(self):
    return {
      'head': self._head,
      'head_branch': self._head_branch,
      'base': self._base,
      'base_branch': self._base_branch,
      'id': self._id
    }

  def get_core_json(self):
    return {
      'id': self._id
    }

  def get_id(self):
    return self._id



class WebHookResourceProvider(flask_api.ResourceProvider):
  def __init__(self, flask):
    super(WebHookResourceProvider, self).__init__('webhooks', flask)

    self._jobs = {}

  @flask_api.METHODS.post('/')
  def handle_post_request(self, data=None):
    pr = data.get('pull_request', None)
    if not pr:
      return 500, 'missing pull request'

    head = pr['head_repo']['clone_url']
    head_branch = pr['head_branch']
    base = pr['base_repo']['clone_url']
    base_branch = pr['base_branch']
    print('will now clone {} and {}, merge {} into {}, and build!'.format(
      head, base, head_branch, base_branch))
    job = WebhookBuildTask(head, head_branch, base, base_branch)
    self._jobs[job._id] = job    
    return self.HAL(job)

  @flask_api.METHODS.get('/')
  def handle_get_req(self):
    return self.HALList(self._jobs.values())

  @flask_api.METHODS.get('/<req_id>')
  def get_specific_req(self, req_id):
    return self._jobs.get(req_id, {})


def main():
  flask_app = flask.Flask(__name__)

  WebHookResourceProvider(flask_app)

  flask_app.run(host='0.0.0.0', port=5566)
