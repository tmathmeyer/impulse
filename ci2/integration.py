
from impulse.hal import api
from impulse.util import temporal_dict


class IntegrationJob(api.Resource('job')):
  def __init__(self, action:str,
                     job_source:str,
                     description:str,
                     repo_name:str,
                     diff_url:str,
                     writeback_url:str,
                     authenticated:bool,
                     repo_merge_into:str,
                     branch_merge_into:str,
                     repo_merge_from:str,
                     branch_merge_from:str):
    super().__init__()
    self.action = action
    self.job_source = job_source
    self.description = description
    self.repo_name = repo_name
    self.diff_url = diff_url
    self.writeback_url = writeback_url
    self.authenticated = authenticated
    self.repo_merge_into = repo_merge_into
    self.branch_merge_into = branch_merge_into
    self.repo_merge_from = repo_merge_from
    self.branch_merge_from = branch_merge_from
    self.status = 'pending'
    self.stdout = []

  def get_core_json(self):
    return {
      'job_source': self.job_source,
      'description': self.description,
      'authenticated': self.authenticated,
    }

  def type(self):
    return self.__class__


class IntegrationJobCache(api.ProvidesResources(IntegrationJob)):
  def __init__(self, runner_host):
    super().__init__(explorer=True)
    self._cache = temporal_dict.TemporalDict(hours=72)
    self._runner_host = runner_host

  @api.METHODS.get('/')
  def get_all_build(self) -> [IntegrationJob]:
    self._synchronize()
    return list(self._cache.values())

  @api.METHODS.get('/<uuid>')
  def get_id_build(self, uuid) -> IntegrationJob:
    self._synchronize()
    try:
      return self._cache[uuid]
    except:
      raise api.ServiceError(404, 'job not found')

  def _synchronize(self):
    for change in self._runner_host.QueryJobDeltas():
      self._apply(change)

  def _apply(self, change):
    op, key, *args = change

    if op == 'init':
      self._cache[key] = args[0]
      return

    if op == 'setattr':
      if key in self._cache:
        setattr(self._cache[key], args[0], args[1])
      return

    if op == 'append':
      if key in self._cache:
        getattr(self._cache[key], args[0]).append(args[1])
      return

    print(f'unhandeled change {op} for {key} (args: {args})') 