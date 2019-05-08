
import multiprocessing
import os
import uuid

from impulse.ci import flask_api
from impulse.util import temp_dir
from impulse.rpc import rpc



class ProcessPool(object):
  def __init__(self, proc_count):
    print('ProcessPool pid = {}'.format(os.getpid()))
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
    print('started build: {}'.format(build))
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

  def AddJob(self, job):
    assert self.status == CIBuilder.READY
    print('Starting job: {}'.format(job))
    self.status = CIBuilder.RUNNING
    self.job = job

  def GetJob(self):
    assert self.status != CIBuilder.READY
    return self.job

  def RemoveJob():
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

class WebhookBuildTask(flask_api.Resource):
  def __init__(self, json):
    json = JSONWrapper(json)
    self.hal_dict = {}
    self.hal_dict['head_repo'] = json.head_repo.clone_url
    self.hal_dict['base_repo'] = json.base_repo.clone_url
    self.hal_dict['head_branch'] = json.head_branch
    self.hal_dict['base_branch'] = json.base_branch

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

  def _enter_thread(self):
    with temp_dir.ScopedTempDirectory():
      self.prepare_git_repo()
      os.system('tree')

  def __repr__(self):
    return str(self.get_full_json())

  def _get(self, attr):
    return self.hal_dict.get(attr, None)

  def add_upstream_branch(self, name, upstream):
    os.system('git remote add {} {}'.format(name, upstream))
    os.system('git pull {}'.format(name))

  def checkout_and_merge(self, head_branch, base_branch):
    os.system('git checkout --track head/{}'.format(head_branch))
    os.system('git checkout --track base/{}'.format(base_branch))
    os.system('git rebase {}'.format(head_branch))

  def prepare_git_repo(self):
    os.system('git init')
    add_upstream_branch('head', self._get('head_repo'))
    add_upstream_branch('base', self._get('base_repo'))
    checkout_and_merge(self._get('head_branch'), self._get('base_branch'))