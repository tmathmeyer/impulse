@buildrule
def py_library(name, srcs, **args):
  depends(inputs=srcs, outputs=[name+'.pylib'])

  sources = ' '.join(local_file(src) for src in srcs)
  tmp_output = build_outputs()[0]+'.part'
  zipcmd = 'zip -j %s %s' % (tmp_output, sources)
  command(zipcmd)

  deplibs_dependencies = dependencies.filter(ruletype='py_library')
  deplibs = ' '.join(sum(map(build_outputs, deplibs_dependencies), []))
  zipmergecmd = 'zipmerge %s %s %s' % (build_outputs()[0], tmp_output, deplibs)
  command(zipmergecmd)


@buildrule
def py_binary(name, srcs, **args):
  depends(inputs=srcs, outputs=[name])

  binary = build_outputs()[0]

  sources = ' '.join(local_file(src) for src in srcs)
  tmp_output = binary+'.part'
  zipcmd = 'zip -j %s %s' % (tmp_output, sources)
  command(zipcmd)

  deplibs_dependencies = dependencies.filter(ruletype='py_library')
  deplibs = ' '.join(sum(map(build_outputs, deplibs_dependencies), []))
  tmp_zip = binary+'.zip'
  zipmergecmd = 'zipmerge %s %s %s' % (tmp_zip, tmp_output, deplibs)
  command(zipmergecmd)

  write_file(binary, '#!/usr/bin/env python')
  append_file(binary, tmp_zip)
  command('chmod +x %s' % binary)