from impulse.types.stubs import buildrule
from impulse.types.interfaces import Package

@buildrule
def shell_script(target:Package, name:str, cmds:list[str],
                 output_files:list[str], **kwargs):
  target.Execute(*cmds)
  for file in output_files:
    target.AddFile(file)
