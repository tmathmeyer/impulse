langs("Python")

py_library (
  name = "readers",
  srcs = [ "readers.py" ],
  deps = [
    "//impulse/core:interface",
    "//impulse/util:typecheck",
  ],
)

py_library (
  name = "format",
  srcs = [ "format.py" ],
  deps = [
    ":readers",
    "//impulse/core:exceptions",
  ],
)

py_test (
  name = "format_unittest",
  srcs = [ "format_unittest.py" ],
  deps = [
    ":format",
    "//impulse/util:bintools",
  ],
  data = [ "BUILD" ],
)