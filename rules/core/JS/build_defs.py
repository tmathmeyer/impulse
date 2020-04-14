
@buildrule
def js_module(target, name, srcs, **kwargs):
  target.SetTags('js_module', 'data')
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))

  for module in target.Dependencies(tags=Any('js_module', 'data')):
    for included in module.IncludedFiles():
      target.AddFile(included)