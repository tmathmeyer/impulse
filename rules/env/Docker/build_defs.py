@buildrule
def build_container(target, name, main_executable, **kwargs):
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
  dockername = name + '_dockerfile'
  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template',
    args = {
      'name': dockername,
      'deps': ['//rules/env/Docker:python-dockerfile-template'],
      'tags': [ 'dockerfile' ],
      'template_data': docker_args.update({
        'main_executable': main_executable,
        'binaries': binaries.prepend('bin/')
      })
    })

  macro_env.ImitateRule(
    rulefile = '//rules/env/Docker/build_defs.py',
    rulename = 'build_container',
    args = {
      'name': name,
      'deps': deps + [ dockername.prepend(':') ],
      'main_executable': main_executable,
      'binaries': binaries.prepend('bin/'),
    })