
@buildmacro
def service(macro_env, name, description, binary, deps):
  metadata_template = name + '_metadata'
  target_template = name + '_target'
  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template_expand',
    args = {
      'name': metadata_template,
      'template_file': 'systemd.metadata.template',
      'tags': [ 'data' ],
      'template_data': {
        'executable': binary,
        'servicefile': target_template
      }
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template_expand',
    args = {
      'name': target_template,
      'template_file': 'systemd.target.template',
      'tags': [ 'data' ],
      'template_data': {
        'executable': binary,
        'description': description,
        'after_target': 'network.target',
        'restart_status': 'always'
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
        '//impulse/systemd:installer',
        metadata_template.prepend('//impulse/systemd:'),
        target_template.prepend('//impulse/systemd:')
      ],
      'tools': deps
    })