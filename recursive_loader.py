
import inspect
import marshal
import re
import os
import pathlib
import types


import build_defs_runtime
import threaded_dependence
import build_defs_runtime


rules = {}


class CreatedPreGraphNode(object):
	def __init__(self, full_name, args, func):
		self.full_name = full_name
		self.args = args
		self.func = func
		self.converted = None

	def __repr__(self):
		return str(self.args)

	def convert_to_graph(self, lookup):
		if not self.converted:
			elements = set()
			for d in flatten(self.args):
				if d.startswith('//'):
					elements.add(lookup[d].convert_to_graph(lookup))

			self.converted = DependencyGraph(self.full_name,
				elements, self.args, marshal.dumps(self.func.__code__))
		return self.converted


class DependencyGraph(threaded_dependence.DependentJob):
	def __init__(self, name, deps, args, decompiled_behavior):
		super().__init__(deps)
		self.name = name
		self.args = args
		self.decompiled_behavior = decompiled_behavior

	def __eq__(self, other):
		return other.name == self.name

	def __hash__(self):
		return hash(self.name)

	def __repr__(self):
		return self.name

	def run_job(self, debug):
		env = build_defs_runtime.env(self.name, self.dependencies, debug)
		try:
			code = marshal.loads(self.decompiled_behavior)
			types.FunctionType(code, env, self.name)(**self.args)
			module_finished_path = env['deptoken'](self)
			try:
				os.makedirs(os.path.dirname(module_finished_path))
			except:
				pass
			pathlib.Path(module_finished_path).touch(exist_ok=True)
		except build_defs_runtime.RuleFinishedException:
			pass





def flatten(item):
	if isinstance(item, str):
		yield item

	if isinstance(item, list):
		for i in item:
			for x in flatten(i):
				yield x

	if isinstance(item, dict):
		for i in item.values():
			for x in flatten(i):
				yield x


def _add_to_ruleset(pre_graph_node):
	rules[pre_graph_node.full_name] = pre_graph_node


def _load_recursive_dependencies(all_keys, build_path):
	return dict((key, _convert_load_vals(val, build_path))
		for key, val in all_keys.items())


def _convert_load_vals(value, build_path):
	if isinstance(value, str):
		if value.startswith(':'):
			return build_path + value
		elif value.startswith('//'):
			_load_build_file_with_rule(value)
			return value
		else:
			return value

	if isinstance(value, list):
		return [_convert_load_vals(v, build_path) for v in value]

	return value


def _get_build_file_dir(full_file_path):
	reg = re.compile(os.path.join(os.environ['impulse_root'], '(.*)/BUILD'))
	return '//' + reg.match(full_file_path).group(1)


def _load_full_rule_path(rule_full):
	full_path = '/'.join([os.environ['impulse_root'], rule_full[2:]])
	_load_all_in_file(full_path)


def _load_build_file_with_rule(rule_full):
	build_file_path = '/'.join([rule_full.split(':')[0], 'BUILD'])
	_load_full_rule_path(build_file_path)


already_loaded = set()
def _load_all_in_file(full_path):
	if full_path not in already_loaded:
		already_loaded.add(full_path)
		with open(full_path) as f:
			exec(compile(f.read(), full_path, 'exec'), _definition_env)


def buildrule(func):
	def __stub__(**kwargs):
		name = kwargs.get('name')
		build_path = _get_build_file_dir(inspect.stack()[1].filename)
		kwargs = _load_recursive_dependencies(kwargs, build_path)
		cpgn = CreatedPreGraphNode(build_path + ':' + name, kwargs, func)
		_add_to_ruleset(cpgn)
	return __stub__


def load_modules(*args):
	return [_load_full_rule_path(rule) for rule in args]


_definition_env = {
	'load': load_modules,
	'buildrule': buildrule
}


def generate_graph(rule):
	_load_build_file_with_rule(rule)
	rules[rule].convert_to_graph(rules)
	generated = set()
	for rule in rules.values():
		if rule.converted is not None:
			generated.add(rule.converted)
	return generated

