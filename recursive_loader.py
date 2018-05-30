
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

class FilterableSet(object):
	def __init__(self, *args, **kwargs):
		self.wrapped = set(*args, **kwargs)

	def __iter__(self):
		return self.wrapped.__iter__()

	def __getattr__(self, attr):
		if attr == 'wrapped':
			return set()
		return getattr(self.wrapped, attr)

	def filter(self, **kwargs):
		matching = [x for x in self.wrapped if self._matches(x, kwargs)]
		return FilterableSet(*matching)

	def _matches(self, x, props):
		for k,v in props.items():
			if not hasattr(x, k):
				return False
			if getattr(x, k) != v:
				return False
		return True


class CreatedPreGraphNode(object):
	def __init__(self, full_name, args, func):
		self.full_name = full_name
		self.args = args
		self.func = func
		self.converted = None
		self.access = {}

	def __repr__(self):
		return str(self.args)

	def convert_to_graph(self, lookup):
		if not self.converted:
			dependencies = FilterableSet()
			for d in flatten(self.args):
				if d.startswith('//') or d.startswith(':'):
					dependencies.add(lookup[d].convert_to_graph(lookup))

			self.converted = DependencyGraph(self.full_name, self.func.__name__,
				dependencies, self.args, marshal.dumps(self.func.__code__),
				self.access)
		return self.converted

	def set_access(self, name, func):
		self.access[name] = marshal.dumps(func.__code__)


class DependencyGraph(threaded_dependence.DependentJob):
	def __init__(self, name, funcname, deps, args, decompiled_behavior, access):
		super().__init__(deps)
		self.name = name
		self.outputs = []
		self.ruletype = funcname
		self.__args = args
		self.__decompiled_behavior = decompiled_behavior
		self.access = access

		self.printed = False

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
			types.FunctionType(code, env, self.name)(**self.__args)
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
		except TypeError:
			#TODO maybe make this check more robust instead of catching.
			err_template = 'target "%s" missing required argument(s) "%s"'
			function_object = types.FunctionType(code, env, self.name)
			all_args = inspect.getargspec(function_object).args
			missing_args = filter(lambda arg: arg not in self.__args.keys(), all_args)
			missing = ', '.join(missing_args)
			raise threaded_dependence.CommandError(err_template % (self.name, missing))

	def d_print(self, indent):
		if not self.printed:
			self.printed = True
			print(' ' * indent + str(self))
			for d in self.dependencies:
				d.d_print(indent+1)
	def q_print(self):
		self.printed = False
		for d in self.dependencies:
			d.q_print()

	def print(self):
		self.d_print(0)
		self.q_print()


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

def buildrule(*funcs):
	def __stub__(*args, **kwargs):
		if len(args) > 0 and isinstance(args[0], types.FunctionType):
			def __inner__(**kwargs):
				name = kwargs.get('name')
				build_path = _get_build_file_dir(inspect.stack()[1].filename)
				cpgn = makeCPGN(kwargs, build_path, args[0])
				for func in funcs:
					cpgn.set_access(func.wraps.__name__, func.wraps)
				_add_to_ruleset(cpgn)
			return __inner__
		else:
			name = kwargs.get('name')
			build_path = _get_build_file_dir(inspect.stack()[1].filename)
			_add_to_ruleset(makeCPGN(kwargs, build_path, funcs[0]))
	__stub__.wraps = funcs[0]
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

