from __future__ import annotations
from impulse.types.stubs import buildrule
from impulse.types.interfaces import Package
import typing

@buildrule
def shell_script(target:Package, name:str, cmds:list[str],
                 output_files:list[str], **kwargs:typing.Any):
  target.Execute(*cmds)
  for file in output_files:
    target.AddFile(file)
