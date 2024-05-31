
from impulse.core import exceptions

class MacroEnvironment():
  def __init__(self, loader:'RecursiveFileParser'):
    self._loader = loader

  def ImitateRule(self, rulefile, rulename, args, kwargs=None, tags=None):
    if tags is None:
      tags = []
    if kwargs is None:
      kwargs = {}
    self._loader.LoadFile(rulefile)
    rule = self._loader.GetRulenameFromLoader(rulename)
    if rule is None:
      raise exceptions.NoSuchRuleType('/dev/null', 0, rulename)
    buildfile = self._loader.GetMacroInvokerFile()
    args.update({'tags': tags, 'buildfile':buildfile})
    args.update(kwargs)
    self._loader.AddMetaTarget(rule(**args))

  def FilterDeps(self, deps:[str], rulenames:[str]) -> [str]:
    def itr():
      for dep in deps:
        rulename = self._loader.GetRulenameFromRawTarget(dep)
        if rulename in rulenames:
          yield dep
    return list(itr())

  def GetLocation(self) -> str:
    return self._loader._get_macro_expansion_directory()


def Buildmacro(loader: 'RecursiveFileParser', fn: 'function'):
  def replacement(**kwargs):
    macro_env = MacroEnvironment(loader)
    fn(macro_env, **kwargs)
  return replacement