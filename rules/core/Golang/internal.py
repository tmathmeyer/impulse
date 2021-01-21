
@buildrule
def igo_compile(T, name, pkg, go_src, asm_src, incl, goos, arch, **kwargs):
  comp = 'go tool compile'
  asm = 'go tool asm'
  pack = 'go tool pack r'
  asmhdr = 'go_asm.h'
  trim = '-trimpath .'
  flags = '-std -+ -pack'
  linksyms = ''
  linkasm = ''

  incls = ' '.join(f'-I {i}' for i in incl)
  goos = f'-D GOOS_{goos}'
  arch = f'-D GOARCH_{arch}'
  asms = ' '.join(asm_src)
  gos = ' '.join(go_src)
  cfg = ''

  if kwargs.get('complete', False):
    flags += ' -complete'

  T.Execute(f'touch {asmhdr}')
  if asm_src:
    T.Execute(f'{asm} {trim} {incls} {goos} {arch} -gensymabis -o symabis {asms}')
    linksyms = '-symabis symabis'
    linkasm = f'-asmhdr {asmhdr}'
  T.Execute(f'{comp} -o package.a {trim} -p {pkg} {flags} {linksyms} -D "" {cfg} {linkasm} {gos}')

  outfiles = []
  for asmfile in asm_src:
    output = os.path.basename(asmfile)
    output = os.path.splitext(output)[0] + '.o'
    T.Execute(
      f'{asm} {trim} {incls} {goos} {arch} -o {output} {asmfile}')
    outfiles.append(output)
  
  if outfiles:
    outfiles = ' '.join(outfiles)
    T.Execute(f'{pack} package.a {outfiles}')

  T.AddFile('package.a')

  with open('package.name', 'w+') as f:
    f.write(pkg)
  T.AddFile('package.name')