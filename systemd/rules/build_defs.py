

def populate_template(template_contents, **kwargs):
  import re
  loopline = re.compile(r'{{([a-zA-Z_]+)}}')
  endloopline = re.compile(r'{{/([a-zA-Z_]+)}}')
  templateline = re.compile(r'{([a-zA-Z_]+)}')
  dotline = re.compile(r'{\.}')

  def _format_fn(line, _dotval=None, **kwargs):
    if dotline.search(line):
      if not _dotval:
        raise ValueError('Cant use {{.}} outside of a loop')
      line = line.replace('{.}', str(_dotval))

    line = line.format(**kwargs)
    return line

  loop_contents = []
  loop_variable = None
  replace_contents = []
  for line in template_contents:
    loop = loopline.search(line)
    if loop:
      if loop_variable:
        raise ValueError('Nested loops evil! (for: {})'.format(loop_variable))
      loop_variable = loop.group(1)
      if loop_variable not in kwargs:
        raise ValueError('Missing template parameter: {}'.format(loop_variable))
    else:
      endloop = endloopline.search(line)
      if endloop:
        if endloop.group(1) != loop_variable:
          raise ValueError('Mismatched open/close: {} {}'.format(
            loopline, endloop.group(0)))
        for e in kwargs[loop_variable]:
          for line in loop_contents:
            yield _format_fn(line, _dotval=e)
        loop_variable = None
        loop_contents = []
      else:
        if loop_variable:
          loop_contents.append(line)
        else:
          yield _format_fn(line, **kwargs)

@depends_targets("//impulse/systemd/templates:templates")
@using(populate_template)
@buildrule
def python_service(target, name, description, executable, **kwargs):
  target.SetTags('service')
  #fields = ['description', 'after_target', 'restart_status', 'executable']
  with open('impulse/systemd/templates/systemd.target.template', 'r') as inp:
    with open(f'{name}.service', 'w+') as outp:
      for line in populate_template(inp.readlines(),
          description=description, executable=executable,
          after_target=kwargs.get('after_target', 'network.target'),
          restart_status=kwargs.get('restart_status', 'always')):
        outp.write(line)

  #fields = ['executable', 'service_file']
  with open('impulse/systemd/templates/install_script.sh.template', 'r') as inp:
    with open('install.sh', 'w+') as outp:
      for line in populate_template(inp.readlines(),
          executable=executable, service_file=f'{name}.service'):
        outp.write(line)

  import os
  os.system('chmod +x install.sh')

  target.AddFile(f'bin/{executable}')
  target.AddFile(f'{name}.service')
  target.AddFile('install.sh')