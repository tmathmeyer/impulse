

def Unit():
  def __init__(self):
    self._location = None
    self._asm_files = []


  def TakeLine(self, line):
    if line.startswith('cd'):
      self._location = line.split(' ')[1]
      return

    if line.startswith('/usr/lib/go/pkg/tool/linux_amd64/asm'):
      if 'gensymabis' not in line:
        asm_files.append(line.split(' ')[-1])
      return

    if line.startswith('/usr/lib/go/pkg/tool/linux_amd64/compile')


def read_file(filename):
  units = []
  unit = None
  with open(filename) as f:
    for line in f.readlines():
      if line.startswith('mkdir -p $WORK'): # new sub-unit
        if unit:
          units.append(unit)
        unit = Unit()
        continue
      if unit:
        unit.TakeLine(line)
  print(units)
