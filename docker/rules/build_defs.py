

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




@depends_targets("//impulse/docker/templates:templates")
@using(populate_template)
@buildrule
def python_container(target, name, main_executable, **kwargs):
  import os
  binaries = kwargs.get('binaries', [])
  if binaries:
    binaries = [os.path.join('bin', b) for b in binaries]
    kwargs['binaries'] = binaries
  main_executable = os.path.join('bin', main_executable)

  with open('impulse/docker/templates/python.dockerfile.template', 'r') as inp:
    with open('Dockerfile', 'w+') as outp:
      for q in populate_template(inp.readlines(),
                                 main_executable=main_executable,
                                 **kwargs):
        outp.write(q)
  for binary in binaries:
    target.AddFile(binary)
  target.AddFile(main_executable)
  target.AddFile('Dockerfile')