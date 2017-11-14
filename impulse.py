"""IdeMpotent Python bUiLd SystEm"""

import argparse
import inspect
import os
import sys


import threaded_dependence
import recursive_loader


PARSER = argparse.ArgumentParser()
TASKS = PARSER.add_subparsers(title='tasks')


def target(parser):
	def decorator(func):
		helpmsg = func.__doc__ or func.__name__
		task = parser.add_parser(
			func.__name__,
			help=helpmsg.splitlines()[0])
		task.set_defaults(task=func.__name__)

		args_name = inspect.getargspec(func)[0]
		for arg in args_name:
			task.add_argument(arg, metavar=arg[0].upper(), type=str)

		def __stub__(parsed):
			func(**dict((n, getattr(parsed, n)) for n in args_name))
		return __stub__

	return decorator



def _getroot():
	config = '%s/.config/impulse/config' % os.environ['HOME']
	if os.path.exists(config):
		with open(config, 'r') as f:
			return f.read()
	raise LookupError('Impulse has not been initialized.')


@target(TASKS)
def build(target):
	root = _getroot()
	cdir = os.environ['PWD']
	os.environ['impulse_root'] = root
	if not cdir.startswith(root):
		raise ValueError('Impulse can\'t be run from outside %s.' % root)

	if target.startswith(':'):
		target = '/%s%s' % (cdir[len(root):], target)
	
	graph = recursive_loader.generate_graph(target)
	pool = threaded_dependence.DependentPool(6)
	pool.input_job_graph(graph).start()


@target(TASKS)
def init():
	home = os.environ['HOME']
	if os.path.exists('%s/.config/impulse/config' % home):
		override = input(('A configuration file exists, '
						  'do you want to overwrite it? [y, N]'))
		if override not in ('y', 'yes', 'Y'):
			return

	os.makedirs('%s/.config/impulse/' % home, exist_ok=True)
	with open('%s/.config/impulse/config' % home, 'w') as config:
		config.write(os.environ['PWD'])




def main():
	a = PARSER.parse_args()
	try:
		getattr(sys.modules[__name__], a.task)(a)
	except AttributeError:
		if hasattr(a, 'task'):
			print('Command "%s" not found' % a.task)
		else:
			print('Command required')
	except KeyError as e:
		print(e)
		print('Task %s not found in %s' % (a.task, dir(sys.modules[__name__])))
	