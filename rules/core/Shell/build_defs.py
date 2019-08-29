
@buildrule
def shell_script(target, name, cmds, output_files, **kwargs):
  for c in cmds:
    r = target.RunCommand(c)
    if r.returncode:
      target.ExecutionFailed(c, r.stderr)
  for file in output_files:
    target.AddFile(file)