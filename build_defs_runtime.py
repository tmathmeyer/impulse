
import marshal
import os
import random
import re
import subprocess
import sys
import shutil
import time
import types

from impulse import threaded_dependence

unpath = re.compile('//(.*):.*')

class RuleFinishedException(Exception):
  pass

def env(graph_object, __name, ruletype, dependencies, debug):
  def directory():
    return unpath.match(__name).group(1)

  DEP = '.deps'
  PWD = os.path.join(os.environ['impulse_root'], 'GENERATED')
  OUTPUT_DIR = os.path.join(PWD, directory())

  def local_file(f):
    return os.path.join(os.environ['impulse_root'], directory(), f)

  def build_outputs(dep=None):
    if not dep:
      outputs = graph_object.outputs
    else:
      outputs = []
      with open(deptoken(dep), 'r') as f:
        outputs += f.readlines()
    return [o.strip() for o in outputs]

  def is_nodetype(dep, name):
    return dep.ruletype == name

  def first(l):
    return l[0]

  def last(l):
    return l[-1]

  def compose(*F):
    def r(x):
      for f in F[::-1]:
        x = f(x)
      return x
    return r

  def dirname(f):
    return os.path.dirname(f)

  def copy(infile, outdir=''):
    outdir = os.path.join(OUTPUT_DIR, outdir)
    try:
      os.makedirs(outdir)
    except OSError as exc: # Guard against race condition
      pass
    shutil.copy(infile, outdir)

  def add_output(f):
    graph_object.outputs.append(f)

  def depends(inputs, outputs):
    """Breaks on all outputs being older than all inputs."""
    graph_object.outputs = [os.path.join(directory(), out) for out in outputs]
    def newest(things):
      time = None
      for x in things:
        if os.path.exists(x):
          mtime = os.path.getmtime(x)
          if time is None or mtime > time:
            time = mtime
      return time

    def oldest(things):
      time = None
      for x in things:
        if os.path.exists(x):
          mtime = os.path.getmtime(x)
          if time is None or mtime < time:
            time = mtime
      return time

    newest_input = newest(local_file(i) for i in inputs) or 0
    newest_dependency = newest(deptoken(d) for d in dependencies) or 0
    time_newest = max(newest_dependency, newest_input)

    time_oldest = oldest(
      os.path.join(OUTPUT_DIR, x) for x in outputs) or time_newest - 1

    if time_newest < time_oldest:
      raise RuleFinishedException()

  def command(cmd):
    try:
      os.makedirs(OUTPUT_DIR, exist_ok=True)
      for out in graph_object.outputs:
        os.makedirs(os.path.join(PWD, os.path.dirname(out)), exist_ok=True)

      process = subprocess.Popen(
        list(cmd.split()),
        cwd=PWD,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)
      _, stderr = process.communicate()
      if process.returncode != 0:
        raise threaded_dependence.CommandError(cmd + ' --> ' + stderr)
    except:
      raise

  def deptoken(dep):
    return os.environ['impulse_root'] + '/' + DEP + dep.name[1:]

  def write_file(filename, string):
    with open(os.path.join(PWD, filename), 'a') as f:
      f.write(string + '\n')

  def append_file(to_file, from_file):
    from_file = os.path.join(PWD, from_file)
    to_file = os.path.join(PWD, to_file)
    os.system('cat %s >> %s' % (from_file, to_file))


  res = {}
  res.update(locals())
  res.update(globals())

  for name, code in graph_object.access.items():
    code = marshal.loads(code)
    res[name] = types.FunctionType(code, res, name)

  return res
