langs("C")

cpp_header (
  name = "location_h",
  srcs = [ "location.h" ],
)

cpp_header (
  name = "bind_h",
  srcs = [ "bind.h" ],
  deps = [ ":location_h" ],
)

cpp_header (
  name = "status_h",
  srcs = [ "status.h" ],
  deps = [
    ":bind_h",
    ":location_h",
  ],
)