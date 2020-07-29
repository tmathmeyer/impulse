langs("C")

cpp_header (
  name = "languages_h",
  srcs = [ "python.h" ],
  deps = [
    "//impulse/base:status_h"
  ]
)

cpp_object (
  name = "python",
  srcs = [ "python.cc" ],
  deps = [
    ":languages_h",
    "//impulse/proto:protocompile_h"
  ]
)