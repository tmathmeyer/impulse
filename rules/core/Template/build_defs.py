
@buildrule
def raw_template(target, name, srcs, **kwargs):
  assert len(srcs) == 1
  target.SetTags('raw_template')
  target.AddFile(os.path.join(target.GetPackageDirectory(), srcs[0]))


@buildrule
def template(target, name, deps, template_data, **kwargs):
  """Template file syntax:
  # Load a variable by name
  load_variable_by_name = {variable}
  
  # iterate through a python list or generator
  {{list_name}}
  each_entry = {.}
  {{/list_name}}
  
  # Iterate through a list of lists recursively
  {{list_name}}
  foo = bar
  {{.}}
  nested_item={.}
  {{/.}}
  x = y
  {{/list_name}}

  # Iterate through a python dict or iterator of (key, value)
  {{dict_name}}
  {.key} = {.value}
  {{/dict_name}}
  """
  import re

  DNE = object()
  LOOPLINE = re.compile(r'{{([a-zA-Z_\.][a-zA-Z0-9_]+)}}')
  REPLACE = re.compile(r'{([a-zA-Z_][a-zA-Z0-9_]+)}')
  DOT = '{.}'
  KEY = '{.key}'
  VALUE = '{.value}'

  class TemplateLine(object):
    def __init__(self, line:str):
      self.line = line
    
    def Apply(self, items, dot=DNE, key=DNE, value=DNE):
      line = self.line
      if DOT in self.line:
        assert dot is not DNE
        line = line.replace(DOT, str(dot))
      if KEY in self.line:
        assert key is not DNE
        line = line.replace(KEY, str(key))
      if VALUE in self.line:
        assert value is not DNE
        line = line.replace(VALUE, str(value))
      search = REPLACE.search(line)
      if search:
        for m in search.groups():
          if m not in items:
            target.ExecutionFailed(
              'Template Key Error', f'Missing key {m} in {items}')
          line = line.replace('{' + m + '}', str(items[m]))
      yield line

  class TemplateLoop(object):
    def __init__(self, name:str):
      self.name = name
      self.subs = []
      self.current = None

    def Add(self, line:str) -> bool:
      if self.current is not None:
        if self.current.Add(line):
          self.current = None
        return False

      if line.strip() == '{{/' + self.name + '}}':
        assert self.current is None
        return True

      match = LOOPLINE.match(line.strip())
      if match:
        self.current = TemplateLoop(match.group(1))
        self.subs.append(self.current)
      else:
        self.subs.append(TemplateLine(line))

      return False

    def Apply(self, items, dot=DNE, key=DNE, value=DNE):
      iterator = None
      if self.name == '.':
        assert dot is not DNE
        iterator = dot
      elif self.name == '.key':
        assert key is not DNE
        iterator = key
      elif self.name == '.value':
        assert value is not DNE
        iterator = value
      else:
        iterator = items.get(self.name, [])

      if type(iterator) == dict:
        for key, value in iterator.items():
          for sub in self.subs:
            yield from sub.Apply(items, key=key, value=value, dot=dot)
      if type(iterator) == list:
        for dot in iterator:
          for sub in self.subs:
            yield from sub.Apply(items, dot=dot, value=value, key=key)
      else:
        raise ValueError('Bad type for iterator')

  def FileToTemplate(filename):
    tree = []
    current = None
    with open(filename, 'r') as f:
      for line in f.readlines():
        if current is not None:
          if current.Add(line):
            current = None
          continue
        match = LOOPLINE.match(line.strip())
        if match:
          current = TemplateLoop(match.group(1))
          tree.append(current)
        else:
          tree.append(TemplateLine(line))
    assert current is None
    return tree

  for deplib in target.Dependencies(tags=Any('raw_template')):
    with open(name, 'w+') as f:
      files = list(deplib.IncludedFiles())
      assert len(files) == 1
      for line in FileToTemplate(files[0]):
        for output in line.Apply(template_data):
          f.write(output)
    break
  target.AddFile(name)


@buildmacro
def template_expand(macro_env, name, template_file, tags, template_data):
  template_raw_target_ = name + '_raw_template'

  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'raw_template',
    args = {
      'name': template_raw_target_,
      'srcs': [ template_file ]
    })

  macro_env.ImitateRule(
    rulefile = '//rules/core/Template/build_defs.py',
    rulename = 'template',
    tags = tags,
    args = {
      'name': name,
      'deps': [ template_raw_target_.prepend(':') ],
      'template_data': template_data
    })