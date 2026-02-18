
import abc

class UpdateGraphResponseData(object):
  def __init__(self):
    self.added_graph = set()
    self.rerun_more_deps = []

  def InjectMoreGraph(self, graph):
    self.added_graph |= graph

  def RerunWithDependency(self, nodes):
    self.added_graph |= (nodes)
    self.rerun_more_deps = nodes


class GraphNode[T]:
  def __init__(self, dependencies:set[GraphNode[T]], has_internal_access:bool):
    self.dependencies = dependencies
    # Make a copy of the set, but not the underlying objects
    self.remaining_dependencies = set(dependencies)
    self._has_internal_access = has_internal_access
    self.__in_thread__ = False

  def check_thread(self):
    assert self.__in_thread__

  def __call__(self, debug=False):
    self.__in_thread__ = True
    if self._has_internal_access:
      access = UpdateGraphResponseData()
      self.run_job(debug, access)
      return access
    else:
      return self.run_job(debug)

  @abc.abstractmethod
  def run_job(self, debug, internal_access=None):
    pass

  @abc.abstractmethod
  def __eq__(self, other):
    pass

  @abc.abstractmethod
  def __hash__(self):
    pass

  @abc.abstractmethod
  def get_name(self):
    pass

  @abc.abstractmethod
  def data(self) -> T:
    pass
