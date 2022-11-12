def _compile(target, compiler, name, include, srcs, objs, flags, std, log=False):
  if std:
    command = f'{compiler} -o {name} {include} {srcs} {objs} {flags} -std={std}'
  else:
    command = f'{compiler} -o {name} {include} {srcs} {objs} {flags}'
  if log:
    print(command);
  try:
    target.Execute(command)
    if not os.path.exists(name):
      raise Exception(f'Compiler Command: |{command}|\nfailed to create output')
  except Exception as e:
    if target.IsDebug():
      os.system('tree')
    raise e
  return name


def _get_include_dirs(target, kwargs):
  includes = set(kwargs.get('include_dirs', []))
  includes.add(target.GetPackageDirectory())
  for deplib in target.Dependencies(tags='header'):
    includes.update(deplib.GetPropagatedData('includes'))
  includes = ' '.join(f'-I{d}' for d in includes)
  return f'-I. {includes}'


def _get_flags(target, kwargs):
  flags = set(kwargs.get('flags', []))
  for deplib in target.Dependencies(tags=Any('cpp_input')):
    flags.update(deplib.GetPropagatedData('buildflags'))
  for flag in flags:
    target.PropagateData('buildflags', flag)
  return flags


def _get_objects(target, tags:[str]) -> str:
  objects = set()
  for tag in tags:
    for deplib in target.Dependencies(tags=tag):
      for obj in deplib.IncludedFiles():
        objects.add(obj)
  return objects


def _get_src_files(target, srcs):
  for src in srcs:
    yield os.path.join(target.GetPackageDirectory(), src)


@using(_get_src_files)
@buildrule
def c_header(target, name, srcs, **kwargs):
  target.SetTags('header')
  for src in _get_src_files(target, srcs):
    target.AddFile(src)
  for deplib in target.Dependencies(tags='header'):
    for f in deplib.IncludedFiles():
      target.AddFile(f)


@using(_get_src_files)
@buildrule
def cpp_header(target, name, srcs, **kwargs):
  target.SetTags('header')
  for src in _get_src_files(target, srcs):
    target.AddFile(src)
  for deplib in target.Dependencies(tags='header'):
    for f in deplib.IncludedFiles():
      target.AddFile(f)
    for include in deplib.GetPropagatedData('includes'):
      target.PropagateData('includes', include)
  for include in kwargs.get('include_dirs', []):
    target.PropagateData('includes', include)


@using(_compile, _get_include_dirs, _get_flags)
@buildrule
def cc_compile(target, name, srcs, **kwargs):
  compiler = target.GetPlatform().cc_compiler
  cc_flags = target.GetPlatform().cc_flags
  language = kwargs.get('language', 'cpp')
  std_vers = kwargs.get('std', 'c++20')
  argflags = _get_flags(target, kwargs)
  includes = _get_include_dirs(target, kwargs)
  argflags.update(cc_flags)
  argflags.update(['-c', '-g'])

  if len(srcs) != 1:
    raise ValueError('cc_compile::srcs must have length 1')
  srcfile = os.path.join(target.GetPackageDirectory(), srcs[0])

  target.SetTags(f'{language}_input')
  target.AddFile(_compile(
    log=False,
    target=target,
    compiler=compiler,
    name=srcfile.replace('.cc', '.o').replace('.c', '.o'),
    include=includes,
    srcs=srcfile,
    objs='',
    flags=' '.join(argflags),
    std=std_vers))


@using(_compile, _get_objects, _get_flags)
@buildrule
def cc_combine(target, name, **kwargs):
  # force flag propagation, don't use result
  language = kwargs.get('language', 'cpp')
  target.SetTags(f'{language}_input')

  outname = os.path.join(target.GetPackageDirectory(), f'{name}_pkg.o')
  objects = _get_objects(target, [f'{language}_input'])
  objstrs = ' '.join(o for o in objects if 'FS_LOG' not in o)
  if objstrs == outname:
    target.AddFile(outname)
    return
  
  _get_flags(target, kwargs)
  ld_flags = set()
  ld_flags.update(target.GetPlatform().ld_flags)

  for export in kwargs.get('exports', []):
    ld_flags.add(f'-export={export}')

  target.AddFile(_compile(
    log=False,
    target=target,
    compiler=target.GetPlatform().cc_linker,
    name=outname,
    include='',
    srcs='',
    objs=objstrs,
    flags=' '.join(ld_flags),
    std=None))


@using(_compile, _get_objects, _get_flags, _get_include_dirs)
@buildrule
def cc_package_binary(target, name, **kwargs):
  target.SetTags('exe')
  compiler = target.GetPlatform().cc_compiler
  cc_flags = _get_flags(target, kwargs)
  language = kwargs.get('language', 'cpp')
  cc_flags.update(target.GetPlatform().cc_flags)
  cc_flags.update(['-g'])
  target.AddFile(_compile(
    log=False,
    target=target,
    compiler=compiler,
    name=os.path.join(target.GetPackageDirectory(), name),
    include=_get_include_dirs(target, kwargs),
    srcs='',
    objs=' '.join(_get_objects(target, [f'{language}_input'])),
    flags=' '.join(cc_flags),
    std=kwargs.get('std', 'c++20')))

  def export_binary(_, package_name, package_file, binary_location):
    package_exe = os.path.join(target.GetPackageDirectory(), package_name)
    binary_file = os.path.join(binary_location, package_name)
    os.system(f'cp {package_exe} {binary_file}')

  return export_binary


@buildmacro
def cc_object(macro_env, name, srcs, deps=None, includes=None, **kwargs):
  subtargets = []
  deps = deps or []
  includes = includes or []
  for cc_file in srcs:
    subtarget = cc_file.replace('.', '_') + '_o'
    macro_env.ImitateRule(
      rulefile = '//rules/core/C/build_defs.py',
      rulename = 'cc_compile',
      kwargs = kwargs,
      args = {
        'name': subtarget,
        'srcs': [ cc_file ],
        'deps': includes,
      })
    subtargets.append(f':{subtarget}')

  macro_env.ImitateRule(
    rulefile = '//rules/core/C/build_defs.py',
    rulename = 'cc_combine',
    kwargs = kwargs,
    args = {
      'name': name,
      'deps': subtargets + deps
    })


@buildmacro
def cc_binary(macro_env, name, srcs, deps=None, includes=None, **kwargs):
  subtargets = []
  deps = deps or []
  includes = includes or []
  for cc_file in srcs:
    subtarget = cc_file.replace('.', '_') + '_o'
    macro_env.ImitateRule(
      rulefile = '//rules/core/C/build_defs.py',
      rulename = 'cc_compile',
      kwargs = kwargs,
      args = {
        'name': subtarget,
        'srcs': [ cc_file ],
        'deps': includes,
      })
    subtargets.append(f':{subtarget}')

  macro_env.ImitateRule(
    rulefile = '//rules/core/C/build_defs.py',
    rulename = 'cc_combine',
    kwargs = kwargs,
    args = {
      'name': f'{name}_o',
      'deps': subtargets + deps
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/C/build_defs.py',
    rulename = 'cc_package_binary',
    kwargs = kwargs,
    args = {
      'name': name,
      'deps': [f':{name}_o']
    }
  )