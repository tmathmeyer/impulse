

def _propagate_modules(target, kwargs):
  modules = set(kwargs.get('modules', []))
  modules.add('@types/node')
  for dep in target.Dependencies(tags=Any('ts_library')):
    modules.update(set(dep.GetPropagatedData('modules')))
  return list(modules)


@using(_propagate_modules)
@buildrule
def ts_modules(target, name, srcs, **kwargs):
  target.SetTags('data')
  for module in _propagate_modules(target, kwargs):
    target.Execute(f'npm link --bin-links=false {module}')

  for directory, _, files in os.walk('node_modules', followlinks=True):
    for file in files:
      target.AddFile(os.path.join(directory, file))



@using(_propagate_modules)
@buildrule
def ts_library(target, name, srcs, **kwargs):
  target.SetTags('ts_library')
  for module in _propagate_modules(target, kwargs):
    target.PropagateData('modules', module)

  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))

  for module in target.Dependencies(tags=Any('ts_library', 'data')):
    for included in module.IncludedFiles():
      target.AddFile(included)


@using(_propagate_modules)
@buildrule
def ts_bundle(target, name, srcs, **kwargs):
  target.SetTags('ts_bundle', 'data')

  files = []
  def handle_file(file):
    if file.endswith('.ts'):
      files.append(file)
    else:
      target.AddFile(file)

  for src in srcs:
    handle_file(os.path.join(target.GetPackageDirectory(), src))

  for module in target.Dependencies(tags=Any('ts_library', 'data')):
    for included in module.IncludedFiles():
      handle_file(included)

  for module in _propagate_modules(target, kwargs):
    target.Execute(f'npm link --bin-links=false {module}')

  target.Execute(f'tsc {" ".join(files)}')

  for tsfile in files:
    jsfile = tsfile[:-2] + 'js'
    target.AddFile(jsfile)


@buildmacro
def ts_binary(macro_env, name, entrypoint, **kwargs):
  ts_bundle_rule = f'{name}_ts_bundle_intermediary'
  ts_entrypoint_rule = f'{name}_ts_bundle_entrypoint'
  ts_modules_rule = f'{name}_ts_bundle_modules'
  macro_env.ImitateRule(
    rulefile = '//rules/core/TS/build_defs.py',
    rulename = 'ts_bundle',
    args = {
      'name': ts_bundle_rule,
      'srcs': kwargs.get('srcs', []) + [entrypoint],
      'data': kwargs.get('data', []),
      'deps': kwargs.get('deps', []),
      'modules': kwargs.get('modules', []),
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/TS/build_defs.py',
    rulename = 'ts_modules',
    args = {
      'name': ts_modules_rule,
      'srcs': [],
      'modules': kwargs.get('modules', []),
    })

  macro_env.ImitateRule(
    rulefile = '//rules/builtins/builtins.py',
    rulename = 'file_reference',
    args = {
      'name': ts_entrypoint_rule,
      'file': 'ts_bundle_entrypoint',
      'content': entrypoint[:-2] + 'js',
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'py_binary',
    args = {
      'name': name,
      'deps': [
        f':{ts_bundle_rule}',
        f':{ts_entrypoint_rule}',
        f':{ts_modules_rule}',
        '//impulse/shims:typescript_shim',
      ],
      'mainfile': 'ts_loader.py',
      'mainpackage': 'impulse.shims',
    })