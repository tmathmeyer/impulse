langs("Python", "C")

py_library (
  name = "temp_dir",
  srcs = ["temp_dir.py"]
)

py_library (
  name = "tree_builder",
  srcs = ["tree_builder.py"]
)

py_library (
  name = "interface",
  srcs = ["interface.py"]
)

py_library (
  name = "bintools",
  srcs = [ "resources.py" ],
  deps = [ ":temp_dir" ],
)

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
    ":location_h",
    ":bind_h"
  ],
)