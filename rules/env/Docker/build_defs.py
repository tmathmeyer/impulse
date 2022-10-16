@buildrule
def build_container(target, name, main_executable, **kwargs):
  target.PropagateData('docker_args', kwargs['docker_args'])
  target.SetTags('container')
  for binary in kwargs.get('binaries', []):
    target.AddFile(binary)
  target.Execute(f'cp bin/{main_executable} {main_executable}')
  target.AddFile(main_executable)
  for dockerfile in target.Dependencies(tags=Any('dockerfile')):
    for df in dockerfile.IncludedFiles():
      target.Execute(f'cp {df} Dockerfile')
      target.AddFile('Dockerfile')
      return


@buildmacro
def container(macro_env, name, binaries, main_executable, docker_args, deps):
  dockername = f'{name}_dockerfile'
  docker_args.update({
    'main_executable': main_executable,
    'binaries': binaries,
  })
  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template',
    tags = [ 'dockerfile' ],
    args = {
      'name': dockername,
      'deps': ['//impulse/rules/env/Docker:python-dockerfile-template'],
      'template_data': docker_args
    })

  macro_env.ImitateRule(
    rulefile = '//impulse/rules/env/Docker/build_defs.py',
    rulename = 'build_container',
    args = {
      'name': name,
      'deps': deps + [ f':{dockername}' ],
      'main_executable': main_executable,
      'binaries': binaries,
      'docker_args': docker_args,
    })