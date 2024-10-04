
@buildrule
def js_bundle(target, name, srcs, **kwargs):
  target.SetTags('js_bundle', 'data')
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))

  for module in target.Dependencies(tags=Any('js_bundle', 'data')):
    for included in module.IncludedFiles():
      target.AddFile(included)