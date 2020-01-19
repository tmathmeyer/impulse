langs("Python")

py_library(
  name = "args",
  srcs = [
    "args.py",
  ],
)

py_test(
  name = "args_unittest",
  srcs = [
    "args_test.py",
  ],
  deps = [
    ":args",
    "//impulse/util:temp_dir",
  ],
)