@buildrule
def impulse_py_binary(name, srcs, **args):
  depends(inputs=srcs, outputs=[
    name,
    name+'.tmp.zip'
  ])

  inputs = [local_file(s) for s in srcs]
  binary, tmp_zip = build_outputs()
  command('zip -j {} {}'.format(tmp_zip, ' '.join(inputs)))
  write_file(binary, '#!/usr/bin/env python')
  append_file(binary, tmp_zip)
  command('chmod +x %s' % binary)