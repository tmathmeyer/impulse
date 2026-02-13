
@buildrule
def shell_script(target, name, cmds, output_files, **kwargs):
  target.Execute(*cmds)
  for file in output_files:
    target.AddFile(file)