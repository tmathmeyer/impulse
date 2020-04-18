langs("C", "Python")

cpp_header (
  name = "protocompile_h",
  srcs = [ "protocompile.h" ],
)

cpp_header (
  name = "protoparse_h",
  srcs = [ "protoparse.h" ],
  deps = [
    ":protocompile_h",
    "//impulse/util:status_h",
  ],
)

cpp_header (
  name = "commandline_h",
  srcs = [ "commandline.h" ],
  deps = [
    "//cppargs:argparse_h",
  ],
)

cpp_object (
  name = "protoparse",
  srcs = [ "protoparse.cc" ],
  deps = [
    ":protocompile_h",
    ":protoparse_h",
  ]
)

cpp_binary (
  name = "protocompile",
  srcs = [ "protocompile.cc", ],
  deps = [
    ":commandline_h",
    ":protocompile_h",
    ":protoparse_h",
    ":protoparse",
    "//impulse/proto/frontend:languages_h",
    "//impulse/proto/frontend:python",
    "//impulse/util:status_h",
    "//cppargs:argparse_h",
  ],
)

py_proto (
  name = "example",
  srcs = [ "example.proto", ],
)

py_test(
  name = "python_gen_test",
  srcs = [
    "python_gen_test.py"
  ],
  deps = [
    ":example",
  ]
)