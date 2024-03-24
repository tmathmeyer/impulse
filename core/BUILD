py_library (
  name = "debug",
  srcs = [ "debug.py" ],
)

py_library (
  name = "exceptions",
  srcs = [ "exceptions.py" ],
)

py_library (
  name = "job_printer",
  srcs = [ "job_printer.py" ],
  deps = [ ":debug" ],
)

py_library (
  name = "threading",
  srcs = [ "threading.py" ],
  deps = [ ":job_printer" ],
)

py_library (
  name = "interface",
  srcs = [ "interface.py" ],
  deps = [ "//impulse/util:typecheck" ],
)

py_library (
  name = "environment",
  srcs = ["environment.py"],
)