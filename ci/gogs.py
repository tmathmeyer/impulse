import re
import os
import subprocess

from impulse.hal import api
from impulse.ci import ci_pooling
from impulse.util import temp_dir

GIT_URL = re.compile(
  r'^(http|https)\://[a-zA-Z\-\.\_0-9:]+/([a-zA-Z]+)/([a-zA-Z]+).git$')


class RecursiveStepList(object):
  def __init__(self, parent=None):
    self.steps = []

  def add_step(self, step_name, step_value):
    self.steps.append({step_name: step_value})

  def add_subgroup(self, group_name):
    self.steps.append()


class User(api.ResourceTypeStruct()):
  def __init__(self, id:int, username:str, **kwargs):
    self.id = id
    self.username = username


class Repo(api.ResourceTypeStruct()):
  def __init__(self, owner:User, name:str, html_url:str, **kwargs):
    self.owner = owner
    self.name = name
    self.html_url = html_url
    self.__dict__.update(kwargs)


class PullRequest(api.ResourceTypeStruct()):
  def __init__(self, id:int, user:User, title:str,
               head_repo:Repo, head_branch:str,
               base_repo:Repo, base_branch:str,
               **kwargs):
    self.base_branch = base_branch
    self.base_repo = base_repo
    self.head_branch = head_branch
    self.head_repo = head_repo
    self.id = id
    self.user = user
    self.title = title


class ShellLog(object):
  def __init__(self, parent=None):
    self._parent = parent
    self.commands = []

  def __enter__(self, tag):
    child = ShellLog(self)
    self.commands.append({
      tag: child
    })
    return child

  def __exit__(self):
    return

  def __call__(self):
    pass

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

  def SerializeToJSON(self):
    return self.commands


class Build(api.Resource('gogs-pr')):
  def __init__(self, action:str, number:str, sender:User,
               pull_request:PullRequest, repository:Repo):
    super().__init__()
    self.action = action
    self.number = number
    self.sender = sender
    self.pull_request = pull_request
    self.repository = repository
    self.log = ShellLog()

  def get_core_json(self):
    return { }

  def get_id(self):
    return self.number

  def Run(self):
    print('STARTING RUN')
    with temp_dir.ScopedTempDirectory(delete_non_empty=True):
      if not self.ensure_secure_branch_name(self.repository.name):
        return self.exit_msg('Invalid Branch Name')
      os.system('mkdir {}'.format(self.repository.name))
      with temp_dir.ScopedTempDirectory(self.repository.name):
        if not self.prepare_git_repo():
          return self.exit_msg('Unable to check out source files')
      if not os.path.exists('impulse'):
        os.system('git clone http://192.168.0.100:10080/ted/impulse')
      os.system('ln -s impulse/rules rules')
      return self.log.CMD(
        ['impulse', 'testsuite', '--debug', '--fakeroot', os.getcwd()])


  def exit_msg(self, msg):
    self.log.commands.append(msg)
    return

  def ensure_secure_branch_name(self, branch_name:str) -> bool:
    match = re.match(r'^[a-zA-Z]+$', branch_name)
    return match is not None

  def prepare_git_repo(self) -> bool:
    if not self.log.CMD(['git', 'init']):
      return False
    head_clone_url = self.pull_request.head_repo.clone_url
    base_clone_url = self.pull_request.base_repo.clone_url
    if not self.add_upstream_branch('head', head_clone_url):
      return False
    if not self.add_upstream_branch('base', base_clone_url):
      return False
    return self.checkout_and_merge(
      self.pull_request.head_branch,
      self.pull_request.base_branch)

  def add_upstream_branch(self, name:str, upstream:str) -> bool:
    if not self.ensure_secure_git_url(upstream):
      return False
    if not self.ensure_secure_branch_name(name):
      return False

    remote_cmd = 'git remote add {} {}'.format(name, upstream)
    pull_cmd = 'git pull {}'.format(name)
    if not self.log.CMD(remote_cmd.split()):
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
  def __init__(self):
    super().__init__(explorer=True)
    self._builds = {}
    self._builder_pool = ci_pooling.BuilderPool(4)

  @api.METHODS.post('/')
  def handle_webhook(self, build:Build):
    self._builds[build.get_id()] = build
    if build.action == 'opened':
      self._builder_pool.ingest(build)
    if build.action == 'closed':
      self._builder_pool.expire(build)
    # Other operations not supported yet

  @api.METHODS.get('/')
  def get_all_build(self) -> [Build]:
    self.get_updates()
    running_builds = self._builder_pool.running_build_ids()
    print(running_builds)
    return [self._builds.get(i, None) for i in running_builds]

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
