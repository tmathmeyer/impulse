
@depends_targets("//impulse/web:component_base")
@buildrule
def web_component(target, name, srcs, **kwargs):
  target.SetTags('data', 'webcomponent')
  
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))

  supported_dep_types = Any('js_module', 'webcomponent', 'data')
  for module in target.Dependencies(tags=supported_dep_types):
    for included in module.IncludedFiles():
      target.AddFile(included)