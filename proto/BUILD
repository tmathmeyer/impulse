langs("C", "Python")

cpp_header (
  name = "protocompile_h",
  srcs = [ "protocompile.h" ],
)

cpp_header (
  name = "commandline_h",
  srcs = [ "commandline.h" ],
  deps = [ git_repo (
    url = "https://github.com/tmathmeyer/cppargs",
    repo = "cppargs",
    target = "//cppargs:argparse_h",
  ) ],
)

cpp_header (
  name = "proto_stream_parse_h",
  srcs = [ "proto_stream_parse.h" ],
  deps = [
    ":protocompile_h",
    ":protolex_h",
  ],
)

cpp_header (
  name = "protolex_h",
  srcs = [ "protolex.h" ],
  deps = [ "//impulse/lex:lex_h" ],
)

cpp_object (
  name = "protolex",
  srcs = [ "protolex.cc" ],
  deps = [
    ":protolex_h",
    "//impulse/lex:lex",
    "//impulse/lex:lex_h",
  ],
)

cpp_object (
  name = "proto_stream_parse",
  srcs = [ "proto_stream_parse.cc" ],
  deps = [
    ":proto_stream_parse_h",
    "//impulse/base:status_h",
  ],
)

cpp_binary (
  name = "protocompile",
  srcs = [ "protocompile.cc" ],
  deps = [
    "git://github.com/tmathmeyer/cppargs//:argparse_h",
    ":commandline_h",
    ":proto_stream_parse",
    ":proto_stream_parse_h",
    ":protocompile_h",
    ":protolex",
    ":protolex_h",
    "//impulse/base:status_h",
    "//impulse/lex:lex",
    "//impulse/lex:lex_h",
    "//impulse/proto/frontend:languages_h",
    "//impulse/proto/frontend:python",
  ],
)

py_proto (
  name = "example",
  srcs = [ "example.proto" ],
)

py_test (
  name = "python_gen_test",
  srcs = [ "python_gen_test.py" ],
  deps = [ ":example" ],
)