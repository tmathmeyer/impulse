langs("C")


cpp_header (
  name = "regex_h",
  srcs = [ "regex.h" ]
)

cpp_object (
  name = "regex",
  srcs = [ "regex.cc" ],
  deps = [
    ":regex_h",
  ]
)

cpp_header (
  name = "lex_h",
  srcs = [ "lex.h" ],
  deps = [
    ":regex_h",
  ]
)

cpp_binary (
  name = "lex",
  srcs = [ "lex.cc" ],
  deps = [
    ":lex_h",
    ":regex",
  ]
)