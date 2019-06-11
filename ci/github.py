
import sys
from impulse.hal import api



class User(api.ResourceTypeStruct()):
  def __init__(self, id:int, login:str, **kwargs):
    self.id = id
    self.username = login


class Build(api.Resource('github-pr')):
  def __init__(self, sender:User, **kwargs):
    super().__init__()
    self.__dict__.update(kwargs)

  def get_core_json(self):
    return { }

  def Run(self):
    print(str(self.__dict__), file=sys.stderr)






class BuildManager(api.ProvidesResources(Build)):
  def __init__(self):
    super().__init__(explorer=True)

  @api.METHODS.post('/')
  def handle_webhook(self, build:Build):
    build.Run()
