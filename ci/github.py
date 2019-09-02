
import json
import re
import os
import subprocess
import sys
from urllib import request

from impulse.hal import api
from impulse.ci import githubauth
from impulse.util import temp_dir


GIT_URL = re.compile(
  r'^(http|https)\://[a-zA-Z\-\.\_0-9:]+/([a-zA-Z]+)/([a-zA-Z]+).git$')


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
  def __init__(self, comments_url:str, user:User, author_association:str,
                     head:Branch, base:Branch, **_):
    self.comments_url = comments_url
    self.user = user
    self.author_role = author_association
    self.head = head
    self.base = base


class ShellLog(api.ResourceTypeStruct()):
  def __init__(self):
    self.commands = []

  def format_error(self):
    errmsg = 'err'
    last_cmd = {'$?': 0}
    if self.commands:
      errmsg = self.commands[-1]
      if len(self.commands) > 1:
        last_cmd = self.commands[-2]
    return f'{errmsg}\n\t{last_cmd}'

  def CMD(self, cmd) -> bool:
    result = True
    try:
      output = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
      output = output.stdout.decode('utf-8').replace('\\n', '\n')
    except subprocess.CalledProcessError as e:
      output = str(e.output.decode('utf-8'))
      result = False
    self.commands.append({
      ' '.join(cmd): output
    })
    return result


class Build(api.Resource('github-pr')):
  def __init__(self, action:str, number:int, sender:User,
                     pull_request:PullRequest, repository:Repo, **_):
    super().__init__()
    self.user = sender
    self.action = action
    self.number = number
    self.pull_request = pull_request
    self.repository = repository
    self.log = ShellLog()

  def get_core_json(self):
    return { }

  def Run(self):
    if self._Run():
      write_this = list(self.log.commands[-1].values())[0]
      write_this = write_this.replace('\\n', '\n')
    else:
      write_this = self._log.format_error()

    message = (
"""
**Build URL**: <{}>
**Build Results**:
```
{}
```
""".format(self._HalURL, str(write_this)))
    data = str(json.dumps({'body': message})).encode('utf-8')
    req = request.Request(self.pull_request.comments_url, data=data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'token {}'.format(self._token))
    request.urlopen(req)

  def _Run(self):
    with temp_dir.ScopedTempDirectory(delete_non_empty=True):
      if not self.ensure_secure_branch_name(self.repository.name):
        return self.exit_msg('Invalid Branch Name')
      os.system('mkdir {}'.format(self.repository.name))
      with temp_dir.ScopedTempDirectory(self.repository.name):
        if not self.prepare_git_repo():
          return self.exit_msg('Unable to check out source files')
      if not os.path.exists('impulse'):
        self._log.CMD(['git', 'clone', 'https://github.com/tmathmeyer/impulse'])
      self._log.CMD(['ln', '-s', 'impulse/rules', 'rules'])
      return self._log.CMD(
        ['impulse', 'testsuite', '--debug', '--fakeroot', os.getcwd()])

  def exit_msg(self, msg):
    self.log.commands.append(msg)
    return False

  def ensure_secure_branch_name(self, branch_name:str) -> bool:
    match = re.match(r'^[a-zA-Z\-_]+$', branch_name)
    return match is not None

  def prepare_git_repo(self) -> bool:
    if not self.log.CMD(['git', 'init']):
      return False
    head_clone_url = self.pull_request.head.repo.clone_url
    base_clone_url = self.pull_request.base.repo.clone_url
    if not self.add_upstream_branch('head', head_clone_url):
      return False
    if not self.add_upstream_branch('base', base_clone_url):
      return False
    return self.checkout_and_merge(
      self.pull_request.head.branch,
      self.pull_request.base.branch)

  def add_upstream_branch(self, name:str, upstream:str) -> bool:
    if not self.ensure_secure_git_url(upstream):
      return False
    if not self.ensure_secure_branch_name(name):
      return False

    remote_cmd = 'git remote add {} {}'.format(name, upstream)
    pull_cmd = 'git fetch {}'.format(name)
    if not self._log.CMD(remote_cmd.split()):
      return False
    if not self.log.CMD(pull_cmd.split()):
      return False
    return True

  def ensure_secure_git_url(self, url):
    match = GIT_URL.match(url)
    if match is None:
      return False
    if not self.ensure_secure_branch_name(match.group(2)):
      return False
    if not self.ensure_secure_branch_name(match.group(3)):
      return False
    return True

  def checkout_and_merge(self, head_branch, base_branch):
    if not self.ensure_secure_branch_name(head_branch):
      return False
    if not self.ensure_secure_branch_name(base_branch):
      return False
    checkout_a = 'git checkout --track head/{}'.format(head_branch)
    checkout_b = 'git checkout --track base/{}'.format(base_branch)
    rebase = 'git rebase {}'.format(head_branch)
    if not self.log.CMD(checkout_a.split()):
      return False
    if not self.log.CMD(checkout_b.split()):
      return False
    if not self.log.CMD(rebase.split()):
      return False
    return True


class BuildManager(api.ProvidesResources(Build)):
  def __init__(self, builders):
    super().__init__(explorer=True)
    self.token = githubauth.token
    self._builds = {}
    self._builder_pool = builders

  @api.METHODS.post('/')
  def handle_webhook(self, build:Build):
    if build.action in ('opened', 'synchronize'):
      build._token = self.token
      if build.pull_request.author_role == 'OWNER':
        self._builder_pool.ingest(build)
    else:
      print

  @api.METHODS.get('/')
  def get_all_build(self) -> [Build]:
    self.get_updates()
    running_builds = self._builder_pool.running_build_ids()
    return [self._builds.get(i, None) for i in running_builds]

  @api.METHODS.get('/ALL')
  def get_all_build(self) -> [Build]:
    self.get_updates()
    return dict(self._builds.values().copy())

  @api.METHODS.get('/<build_id>')
  def get_build(self, build_id) -> Build:
    self.get_updates()
    build = self._builds.get(build_id, None)
    if build:
      return build
    raise api.ServiceError(404, 'Build not found')

  def get_updates(self):
    for build in self._builder_pool.updates():
      self._builds[build.get_id()] = build
