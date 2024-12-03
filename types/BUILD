py_library (
  name = "types",
  srcs = [
    "builtins.py",
    "parsed_target.py",
    "parser_host.py",
    "paths.py",
    "references.py",
  ],
  deps = [
    ":typecheck",
    "//impulse/core:environment",
  ],
)

py_library (
  name = "typecheck",
  srcs = [ "typecheck.py" ],
)