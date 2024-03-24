py_library (
  name = "temp_dir",
  srcs = [ "temp_dir.py" ],
)

py_library (
  name = "tree_builder",
  srcs = [ "tree_builder.py" ],
)

py_library (
  name = "bintools",
  srcs = [ "resources.py" ],
  deps = [ ":temp_dir" ],
)

py_library (
  name = "temporal_dict",
  srcs = [ "temporal_dict.py" ],
)

py_library (
  name = "typecheck",
  srcs = [ "typecheck.py" ],
  deps = [ "//impulse/core:debug" ],
)

py_test (
  name = "typecheck_unittest",
  srcs = [ "typecheck_unittest.py" ],
  deps = [ ":typecheck" ],
)

py_library (
  name = "rpc",
  srcs = [ "rpc.py" ],
)

py_library (
  name = "buildvars",
  srcs = [ "buildvars.py" ],
)