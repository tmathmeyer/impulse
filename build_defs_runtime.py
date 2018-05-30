
import marshal
import os
import random
import re
import subprocess
import sys
import shutil
import time
import types

import threaded_dependence

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
				os.makedirs(os.path.dirname(out), exist_ok=True)

			process = subprocess.Popen(
				list(cmd.split()),
				stdout=subprocess.PIPE, stderr=subprocess.PIPE,
				universal_newlines=True)
			_, stderr = process.communicate()
			print(stderr)
			if process.returncode != 0:
				raise threaded_dependence.CommandError(stderr)
		except:
			raise

	def deptoken(dep):
		return os.environ['impulse_root'] + '/' + DEP + dep.name[1:]


	res = {}
	res.update(locals())
	res.update(globals())

	for name, code in graph_object.access.items():
		code = marshal.loads(code)
		res[name] = types.FunctionType(code, res, name)

	return res