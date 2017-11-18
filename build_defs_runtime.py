import os
import re
import subprocess
import shutil
import time
import random

import threaded_dependence

unpath = re.compile('//(.*):.*')

class RuleFinishedException(Exception):
	pass

def env(graph_object, name, ruletype, dependencies, debug):
	def directory():
		return unpath.match(name).group(1)

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
		return outputs

	def is_nodetype(dep, name):
		return dep.ruletype == name

	def copy(infile):
		try:
			os.makedirs(OUTPUT_DIR)
		except OSError as exc: # Guard against race condition
			pass
		shutil.copy(infile, OUTPUT_DIR)

	def depends(inputs, outputs):
		"""Breaks on all outputs being older than all inputs."""
		graph_object.outputs = [os.path.join(OUTPUT_DIR, out) for out in outputs]
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
			for out in graph_object.outputs:
				os.makedirs(os.path.dirname(out))
			if os.system(cmd) != 0:
				raise Exception()
		except:
			raise threaded_dependence.CommandError(cmd)

	def deptoken(dep):
		return os.environ['impulse_root'] + '/' + DEP + dep.name[1:]


	res = {}
	res.update(locals())
	res.update(globals())
	return res