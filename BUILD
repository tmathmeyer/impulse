py_binary (
  name = "impulse",
  srcs = [ "impulse.py" ],
  deps = [
    ":impulse_libs",
    "//impulse/args:args",
  ],
)

py_library (
  name = "impulse_libs",
  srcs = [
    "impulse_paths.py",
    "recursive_loader.py",
  ],
  deps = [
    "//impulse/args:args",
    "//impulse/core:debug",
    "//impulse/core:exceptions",
    "//impulse/core:job_printer",
    "//impulse/core:threading",
    "//impulse/format:format",
    "//impulse/lib:lib",
    "//impulse/loaders:loaders",
    "//impulse/pkg:packaging",
    "//impulse/rules:core_rules",
    "//impulse/util:bintools",
    "//impulse/util:temp_dir",
    "//impulse/util:tree_builder",
    "//impulse/util:typecheck",
    "//impulse/types:types",
    "//impulse/types:typecheck",
  ],
)