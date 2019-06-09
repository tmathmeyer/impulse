from impulse.hal import api
from impulse.ci import ci_pooling

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

  def CMD(self, cmd):
    co_args = {'stderr': subprocess.STDOUT}
    try:
      output = str(subprocess.check_output(
        cmd, stderr=subprocess.STDOUT, shell=True)).decode('utf-8')
    except subprocess.CalledProcessError as e:
      output = str(e.output.decode('utf-8'))
    self.commands.append({
      cmd: output
    })



class Build(api.Resource('builds')):
  def __init__(self, action:str, number:str, sender:User,
               pull_request:PullRequest, repository:Repo):
    super().__init__()
    self.action = action
    self.number = number
    self.sender = sender
    self.pull_request = pull_request
    self.repository = repository
    self.log = ShellLog()

  def get_full_json(self):
    return self.hal_dict

  def get_core_json(self):
    return { }

  def get_id(self):
    return self.number

  def Run(self):
    with self.log('Preparation') as 


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
    return [self._builds.get(i, None) for i in 
            self._builder_pool.running_build_ids()]

  @api.METHODS.get('/<build_id>')
  def get_build(self, build_id) -> Build:
    return self._builds.get(build_id, None)