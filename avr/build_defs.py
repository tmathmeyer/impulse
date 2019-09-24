
def _get_objects(target):
  for deplib in target.Dependencies(package_ruletype='arduino_obj'):
    for obj in deplib.IncludedFiles():
      yield obj

def _get_src_files(target, srcs):
  for src in srcs:
    yield os.path.join(target.GetPackageDirectory(), src)


@using(_get_src_files)
@buildrule
def arduino_obj(target, name, srcs, **kwargs):
  chip = kwargs.get('chip', 'atmega328p')
  f_cpu = kwargs.get('F_CPU', '16000000UL')
  comp = kwargs.get('compiler', 'avr-gcc')
  out = os.path.join(target.GetPackageDirectory(), name+'.o')
  srcs = ' '.join(_get_src_files(target, srcs))

  command = f'{comp} -Os -DF_CPU={f_cpu} -mmcu={chip} -c -o {out} {srcs}'
  r = target.RunCommand(command)
  if r.returncode:
    target.ExecutionFailed(command, r.stderr)
  target.AddFile(out)


@using(_get_objects, _get_src_files)
@buildrule
def arduino_export(target, name, srcs, **kwargs):
  chip = kwargs.get('chip', 'atmega328p')
  comp = kwargs.get('compiler', 'avr-gcc')
  objects = list(_get_objects(target))
  objects = ' '.join(objects)
  out = os.path.join(target.GetPackageDirectory(), name)
  hexout = os.path.join(target.GetPackageDirectory(), name)
  command = f'{comp} -mmcu={chip} {objects} -o {out}'
  r = target.RunCommand(command)
  if r.returncode:
    target.ExecutionFailed(command, r.stderr)

  command = f'avr-objcopy -O ihex -R .eeprom {out} {hexout}.hex'
  r = target.RunCommand(command)
  if r.returncode:
    target.ExecutionFailed(command, r.stderr)

  target.AddFile(f'{hexout}.hex')