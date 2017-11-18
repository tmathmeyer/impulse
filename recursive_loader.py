
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
		self.parent = None

	def __repr__(self):
		return str(self.args)

	def convert_to_graph(self, lookup):
		if not self.converted:
			elements = set()
			for d in flatten(self.args):
				if d.startswith('//') or d.startswith(':'):
					elements.add(lookup[d].convert_to_graph(lookup))

			self.converted = DependencyGraph(self.full_name, self.func.__name__,
				elements, self.args, marshal.dumps(self.func.__code__),
				self.parent)
		return self.converted

	def set_parent(self, func):
		self.parent = marshal.dumps(func.__code__)


class DependencyGraph(threaded_dependence.DependentJob):
	def __init__(self, name, funcname, deps, args, decompiled_behavior, parent):
		super().__init__(deps)
		self.name = name
		self.outputs = []
		self.ruletype = funcname
		self.__args = args
		self.__decompiled_behavior = decompiled_behavior
		self.parent = parent

	def __eq__(self, other):
		return other.name == self.name

	def __hash__(self):
		return hash(self.name)

	def __repr__(self):
		return self.name

	def run_job(self, debug):
		env = build_defs_runtime.env(
			self, self.name, self.ruletype, self.dependencies, debug)
		try:
			code = marshal.loads(self.__decompiled_behavior)
			args = self.__args.copy()
			if self.parent:
				parent_code = marshal.loads(self.parent)
				args['parent'] = types.FunctionType(parent_code, env, 'parent')
			types.FunctionType(code, env, self.name)(**args)
			module_finished_path = env['deptoken'](self)
			try:
				os.makedirs(os.path.dirname(module_finished_path))
			except:
				pass
			with open(module_finished_path, 'w') as f:
				for output in self.outputs:
					f.write(output)
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


def makeCPGN(kwargs, build_path, func):
	name = kwargs.get('name')
	kwargs = _load_recursive_dependencies(kwargs, build_path)
	return CreatedPreGraphNode(build_path + ':' + name, kwargs, func)

def buildrule(func):
	def __stub__(*args, **kwargs):
		if len(args) == 1 and isinstance(args[0], types.FunctionType):
			def __inner__(**kwargs):
				name = kwargs.get('name')
				build_path = _get_build_file_dir(inspect.stack()[1].filename)
				cpgn = makeCPGN(kwargs, build_path, args[0])
				cpgn.set_parent(func.wraps)
				_add_to_ruleset(cpgn)
			return __inner__
		else:
			name = kwargs.get('name')
			build_path = _get_build_file_dir(inspect.stack()[1].filename)
			_add_to_ruleset(makeCPGN(kwargs, build_path, func))
	__stub__.wraps = func
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

