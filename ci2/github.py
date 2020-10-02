
import json
from urllib import request

from impulse.hal import api
from impulse.ci2 import githubauth
from impulse.ci2 import integration


class User(api.ResourceTypeStruct()):
  def __init__(self, id:int, login:str, **_):
    self.id = id
    self.username = login


class Repo(api.ResourceTypeStruct()):
  def __init__(self, owner:User, name:str, clone_url:str, **_):
    self.owner = owner
    self.name = name
    self.clone_url = clone_url


class Branch(api.ResourceTypeStruct()):
  def __init__(self, label:str, ref:str, user:User, repo:Repo, **_):
    self.label = label
    self.branch = ref
    self.user = user
    self.repo = repo


class PullRequest(api.ResourceTypeStruct()):
  def __init__(self, comments_url:str, title:str, author_association:str,
                     diff_url:str, updated_at:str, locked:bool,
                     statuses_url:str,
                     user:User, head:Branch, base:Branch,
                     **_):
    self.comments_url = comments_url
    self.statuses_url = statuses_url
    self.user = user
    self.author_role = author_association
    self.head = head
    self.base = base
    self.title = title
    self.diff_url = diff_url
    self.updated_at = updated_at
    self.locked = locked


class Build(api.Resource('github-pr')):
  def __init__(self, action:str, number:int, pull_request:PullRequest,
                     sender:User, repository:Repo,
                     **_):
    super().__init__()
    self.action = action
    self.number = number
    self.pull_request = pull_request
    self.user = sender
    self.repository = repository

  def get_core_json(self):
    return { }


class WebhookListener(api.ProvidesResources(Build)):
  def __init__(self, job_host):
    super().__init__(explorer=True)
    self._job_host = job_host

  @api.METHODS.post('/')
  def handle_webhook(self, build:Build):
    self._job_host.EnqueueJob(integration.IntegrationJob(
      action=build.action,
      job_source='github',
      description=build.pull_request.title,
      repo_name=build.repository.name,
      diff_url=build.pull_request.diff_url,
      writeback_url=build.pull_request.statuses_url,
      authenticated=(build.pull_request.author_role=='OWNER'),
      repo_merge_into=build.pull_request.base.repo.clone_url,
      branch_merge_into=build.pull_request.base.branch,
      repo_merge_from=build.pull_request.head.repo.clone_url,
      branch_merge_from=build.pull_request.head.branch))


def UpdatePRStatus(pr_statuses_url, state, details_url, desc, context):
  data = str(json.dumps({
    'state': state,
    'target_url': details_url,
    'description': desc,
    'context': context
  })).encode('utf-8')
  req = request.Request(pr_statuses_url, data=data)
  req.add_header('Content-Type', 'application/json')
  req.add_header('Authorization', f'token {githubauth.token}')
  request.urlopen(req)
