load(
    "//rules/core/Python/build_defs.py",
)

py_library(
  name = "unittest",
  srcs = [
    "unittest.py",
    "testmain.py"
  ],
  deps = [
    "//impulse/args:args"
  ]
)

py_test(
  name = "example_unittest",
  srcs = [
    "example.py"
  ]
)