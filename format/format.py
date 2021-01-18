
from collections import namedtuple

from impulse.core import exceptions
from impulse.format import readers


class FormattingError(exceptions.ImpulseBaseException):
  def __init__(self, msg):
    super().__init__(msg)
    self.msg = msg


class ProxyGitRepo(namedtuple('PGR', ['url', 'repo', 'target'])):
  def __lt__(self, t):
    if type(t) == str:
      return True
    if type(t) == ProxyGitRepo:
      return self.url < t.url


class ProxyPattern(namedtuple('PAT', ['pattern'])):
  pass


class FormattingBuildFileReader(readers.BuildFileReaderImpl):
  def __init__(self):
    super().__init__()
    self._langs_calls = []
    self._load_calls = []
    self._rules = []

  def call_langs(self, *langs):
    self._langs_calls += list(langs)

  def call_load(self, *loads):
    self._load_calls += list(loads)

  def call_git_repo(self, url, repo, target):
    return ProxyGitRepo(url, repo, target)

  def call_pattern(self, pattern):
    return ProxyPattern(pattern)

  def call(self, name, args, kwargs):
    if args:
      raise FormattingError('Unnamed arguments are disallowed in buildrules')
    self._rules.append({
      'name': name,
      'args': kwargs
    })

  def PrintFormat(self):
    try:
      return ''.join([self._print_langs(),
                      self._print_loads(),
                      self._print_rules()]).strip()
    except FormattingError as e:
      raise FormattingError(
        f'{e.msg}\nIn file: {self.GetFile()}') from None

  def _print_langs(self):
    if self._langs_calls:
      csl = ', '.join([f'"{l}"' for l in self._langs_calls])
      return f'langs({csl})\n'
    return ''

  def _print_loads(self):
    if self._load_calls:
      lsl = ',\n     '.join([f'"{l}"' for l in self._load_calls])
      return f'load({lsl})\n'
    return ''

  def _print_rules(self):
    result = '\n'
    for rule in self._rules:
      result += self._print_rule(rule)
      result += '\n\n'
    return result

  def _print_rule(self, rule):
    result = f'{rule["name"]} (\n'
    for name, value in rule['args'].items():
      try:
        formatted = self._print_data(value, 2, name in ('srcs', 'deps'))
        result += f'  {name} = {formatted},\n'
      except FormattingError as e:
        rulename = rule['args']['name']
        raise FormattingError(
          f'{e.msg}\nwhile formatting rule: {rulename}') from None
    result += ')'
    return result

  def _csorted(self, d):
    # Order: pattern, file, :target, git, //target
    if type(d) == ProxyGitRepo:
      return 'D' + d.url
    if type(d) == ProxyPattern:
      return 'A' + d.pattern
    elif type(d) == str:
      if d.startswith(':'):
        return 'C' + d
      elif d.startswith('//'):
        return 'E' + d
      else:
        return 'B' + d
    else:
      raise FormattingError(f'Unable to sort {d}')

  def _print_data(self, data, indent, sort=False):
    if type(data) == str:
      return f'"{data}"'

    if type(data) == int:
      return f'{data}'

    if type(data) == list:
      if len(data) == 1:
        return f'[ {self._print_data(data[0], indent)} ]'
      l = '[\n'
      for d in (sorted(data, key=self._csorted) if sort else data):
        l += ' ' * (indent + 2)
        l += self._print_data(d, indent+2)
        l += ',\n'
      l += ' ' * indent + ']'
      return l

    if type(data) == dict:
      l = '{\n'
      for k, v in data.items():
        l += ' ' * (indent + 2)
        l += f'"{k}": '
        l += self._print_data(v, indent+2)
        l += ',\n'
      l += ' ' * indent + '}'
      return l

    if type(data) == ProxyGitRepo:
      l = 'git_repo (\n'
      l += ' ' * (indent+2) + f'url = "{data.url}",\n'
      l += ' ' * (indent+2) + f'repo = "{data.repo}",\n'
      l += ' ' * (indent+2) + f'target = "{data.target}",\n'
      l += ' ' * indent + ')'
      return l

    if type(data) == ProxyPattern:
      return f'pattern("{data.pattern}")'

    raise FormattingError(f'unknown type of {data}')


