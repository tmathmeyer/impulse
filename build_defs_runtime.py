import os
import re
import subprocess
import shutil
import time

import threaded_dependence

unpath = re.compile('//(.*):.*')

class RuleFinishedException(Exception):
	pass

def env(name, dependencies, debug):
	def directory():
		return unpath.match(name).group(1)

	def local_file(f):
		return os.path.join(os.environ['impulse_root'], directory(), f)

	def copy(infile, outdir):
		try:
			os.makedirs(outdir)
		except OSError as exc: # Guard against race condition
			pass

		shutil.copy(infile, outdir)

	def depends(inputs, outputs):
		"""Breaks on all outputs being older than all inputs."""
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

		newest_input = newest(flatten(local_file, inputs)) or 0
		newest_dependency = newest(flatten(deptoken, dependencies)) or 0

		time_newest = max(newest_dependency, newest_input)
		time_oldest = oldest(flatten(
			(lambda x: OUTPUT_DIR + '/' + x), outputs)) or time_newest - 1
		if time_newest < time_oldest:
			raise RuleFinishedException()

	def flatten(func, data):
		if isinstance(data, str):
			yield func(data)
		elif isinstance(data, threaded_dependence.DependentJob):
			yield func(data)
		else:
			for x in data:
				for y in flatten(func, x):
					yield y

	def command(cmd):
		try:
			if os.system(cmd) != 0:
				raise Exception()
		except:
			raise threaded_dependence.CommandError(cmd)

	def deptoken(dep):
		return PWD + '/' + DEP + dep.name[1:]

	
	GEN = 'GENERATED'
	DEP = '.deps'
	PWD = os.environ['impulse_root']
	OUTPUT_DIR = os.path.join(PWD, GEN, directory())

	res = {}
	res.update(locals())
	res.update(globals())
	return res