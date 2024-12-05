from impulse.types.stubs import buildrule
from impulse.types.stubs import depends_targets
from impulse.types.stubs import os
from impulse.types.interfaces import Package


@depends_targets("//impulse/util:bintools")
@buildrule
def npm_tool(target:Package, name, packages, **kwargs):
  for package in packages:
    target.Execute(f'npm install --save-dev {package}')
  target.AddDirectory('node_modules')

