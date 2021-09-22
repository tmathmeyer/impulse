
@buildmacro
def service(macro_env, name, description, binary, deps):
  import getpass
  metadata_template = name + '_metadata'
  target_template = name + '_target'
  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template',
    args = {
      'name': metadata_template,
      'deps': [ '//rules/env/SystemD:metadata-template' ],
      'tags': [ 'data' ],
      'template_data': {
        'executable': binary,
        'servicefile': target_template
      }
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template',
    args = {
      'name': target_template,
      'deps': [ '//rules/env/SystemD:target-template' ],
      'tags': [ 'data' ],
      'template_data': {
        'executable': binary,
        'description': description,
        'after_target': 'network.target',
        'restart_status': 'always',
        'user': getpass.getuser(),
      }
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Python/build_defs.py',
    rulename = 'py_binary',
    args = {
      'name': name,
      'mainfile': 'installer',
      'mainpackage': 'impulse.systemd',
      'deps': deps + [
        '//impulse/tools/SystemDInstaller:installer',
        metadata_template.prepend(':'),
        target_template.prepend(':')
      ],
      'tools': deps
    })