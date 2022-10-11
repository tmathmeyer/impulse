
BUILDVARS = {}

def Set(key, value):
  global BUILDVARS
  BUILDVARS[key] = value

def Get(key, default=None):
  global BUILDVARS
  return BUILDVARS.get(key, default)