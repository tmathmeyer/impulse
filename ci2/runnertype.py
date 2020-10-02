
from impulse.util import interface

@interface.IFace
class RunnerType(object):
  
  def EnqueueJob(self, instance):
    pass

  def QueryJobDeltas(self):
    pass