
import multiprocessing
import os
import re
import subprocess
import threading
import uuid


from impulse.ci import flask_api
from impulse.util import temp_dir
from impulse.rpc import rpc



class ProcessPool(object):
  def __init__(self, proc_count):
    self.CIBuilders = []

    self.BuildMap = {}
    self.BuildsInOrder = []
    self.BuildQueue = multiprocessing.Queue()

    for _ in range(proc_count):
      self.CIBuilders.append(rpc.RPC(CIBuilder))

  def StartJob(self, json):
    build = WebhookBuildTask(json)
    self.BuildMap[build.get_id()] = build
    self.BuildsInOrder.append(build)
    self.BuildQueue.put(build)
    self.MessageLoop()
    return build

  def GetNJobs(self, start, count):
    self.MessageLoop()
    build_ids = self.BuildsInOrder[0-start-count:0-start]
    return [self.BuildMap[b_id] for b_id in build_ids]

  def GetJob(self, b_id):
    self.MessageLoop()
    return self.BuildMap.get(b_id, None)

  def MessageLoop(self):
    def FillReadyBuilders():
      for builder in self.CIBuilders:
        if builder.status == CIBuilder.READY and self.BuildQueue.qsize():
          builder.AddJob(self.BuildQueue.get())
          return FillReadyBuilders()
    FillReadyBuilders()
    def UpdateBuildChanges():
      for builder in self.CIBuilders:
        if builder.status != CIBuilder.READY:
          job = builder.GetJob()
          self.BuildMap[job.get_id()].TakeUpdates(job)
        if builder.status == CIBuilder.FINISHED:
          builder.RemoveJob()
    UpdateBuildChanges()



class CIBuilder(object):
  READY = str(uuid.uuid4())
  FINISHED = str(uuid.uuid4())
  RUNNING = str(uuid.uuid4())

  def __init__(self):
    self.status = CIBuilder.READY
    self.job = None
    self.thread = None

  def _run(self):
    self.job.enter_thread()
    self.status = CIBuilder.FINISHED

  def AddJob(self, job):
    assert self.status == CIBuilder.READY
    self.status = CIBuilder.RUNNING
    self.job = job
    self.thread = threading.Thread(target=self._run)
    self.thread.start()

  def GetJob(self):
    assert self.status != CIBuilder.READY
    return self.job

  def RemoveJob(self):
    assert self.status == CIBuilder.FINISHED
    self.status = CIBuilder.READY
    self.job = None


class JSONWrapper(object):
  def __init__(self, jsondict):
    self._json_dict = jsondict

  def __getattr__(self, attr):
    def convert(ent):
      if type(ent) == dict:
        return JSONWrapper(ent)
      if type(ent) == list:
        return [convert(e) for e in ent]
      return ent

    if attr in self._json_dict:
      return convert(self._json_dict[attr])


def CO(*args, **kwargs):
  kwargs.update({'stderr': subprocess.STDOUT})
  try:
    return str(subprocess.check_output(*args, **kwargs).decode('utf-8'))
  except subprocess.CalledProcessError as e:
    return str(e.output.decode('utf-8'))


GIT_URL = re.compile(
  r'^(http|https)\://[a-zA-Z\-\.\_0-9:]+/([a-zA-Z]+)/([a-zA-Z]+).git$')

class WebhookBuildTask(flask_api.Resource):
  def __init__(self, json):
    json = JSONWrapper(json)
    self.hal_dict = {}
    self.hal_dict['head_repo'] = json.head_repo.clone_url
    self.hal_dict['base_repo'] = json.base_repo.clone_url
    self.hal_dict['head_branch'] = json.head_branch
    self.hal_dict['base_branch'] = json.base_branch
    self.hal_dict['project'] = json.base_repo.name
    self.hal_dict['steps'] = []

    self.id = uuid.uuid4()
    self.hal_dict['id'] = self.get_id()

  def get_full_json(self):
    return self.hal_dict

  def get_core_json(self):
    return { 'id': self.get_id() }

  def get_id(self):
    return str(self.id)

  def TakeUpdates(self, job):
    self.__dict__.update(job.__dict__)

  def __repr__(self):
    return str(self.get_full_json())

  def _enter_new_step(self, name):
    self.hal_dict['steps'].append({'name': name})

  def _add_step_entry(self, k, v):
    self.hal_dict['steps'][-1][k] = v

  def _get_entry_in_step(self, k):
    return self.hal_dict['steps'][-1][k]

  def enter_thread(self):
    self._enter_new_step('Preparation')
    print(os.getcwd())
    with temp_dir.ScopedTempDirectory(delete_non_empty=True):
      project = self._get('project')
      self.ensure_secure_branch_name(project)
      os.system('mkdir {}'.format(project))
      with temp_dir.ScopedTempDirectory(project):
        self._add_step_entry('workdir', os.getcwd())
        self.prepare_git_repo()
      if not os.path.exists('impulse'):
        os.system('git clone http://192.168.0.100:10080/ted/impulse')
      os.system('ln -s impulse/rules rules')
      self._enter_new_step('Running Tests')
      os.system('/bin/impulse testsuite --debug --fakeroot {} 1>&2'.format(os.getcwd()))
      self._add_step_entry('stdout',
        CO('/bin/impulse testsuite --debug --fakeroot {}'.format(os.getcwd())))


  def ensure_secure_branch_name(self, branch_name):
    match = re.match(r'^[a-zA-Z]+$', branch_name)
    assert match is not None

  def ensure_secure_git_url(self, url):
    match = GIT_URL.match(url)
    assert match is not None
    self.ensure_secure_branch_name(match.group(2))
    self.ensure_secure_branch_name(match.group(3))

  def _get(self, attr):
    return self.hal_dict.get(attr, None)

  def add_upstream_branch(self, name, upstream):
    self.ensure_secure_git_url(upstream)
    self.ensure_secure_branch_name(name)
    remote_cmd = 'git remote add {} {}'.format(name, upstream)
    self._get_entry_in_step('steps').append({
      remote_cmd: CO(remote_cmd, shell=True)
    })
    pull_cmd = 'git pull {}'.format(name)
    self._get_entry_in_step('steps').append({
      pull_cmd: CO(pull_cmd, shell=True)
    })

  def checkout_and_merge(self, head_branch, base_branch):
    self.ensure_secure_branch_name(head_branch)
    self.ensure_secure_branch_name(base_branch)
    checkout_a = 'git checkout --track head/{}'.format(head_branch)
    checkout_b = 'git checkout --track base/{}'.format(base_branch)
    rebase = 'git rebase {}'.format(head_branch)
    self._get_entry_in_step('steps').append({
      checkout_a: CO(checkout_a, shell=True)
    })
    self._get_entry_in_step('steps').append({
      checkout_b: CO(checkout_b, shell=True)
    })
    self._get_entry_in_step('steps').append({
      rebase: CO(rebase, shell=True)
    })

  def prepare_git_repo(self):
    self._enter_new_step('Git')
    self._add_step_entry('steps', [])
    self._get_entry_in_step('steps').append({
      'git init': CO('git init', shell=True)
    })
    self.add_upstream_branch('head', self._get('head_repo'))
    self.add_upstream_branch('base', self._get('base_repo'))
    self.checkout_and_merge(self._get('head_branch'), self._get('base_branch'))