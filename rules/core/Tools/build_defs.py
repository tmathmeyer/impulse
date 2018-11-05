import sys

@buildrule
def makezip(name, files, zipflags):
  depends(inputs=files, outputs=[name] + files)
  outfile, *zip_up = build_outputs()

  zipnames = []
  for I, O in zip(files, zip_up):
    command('cp {} {}'.format(local_file(I), O))
    zipnames.append(os.path.join(directory(), I))

  command('zip {} {} {}'.format(
    outfile, 
    ' '.join(zipflags), 
    ' '.join(zipnames)))