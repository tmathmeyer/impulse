langs("Python")

py_library (
  name = "hal",
  srcs = [
    "api.py",
  ],
  data = [
    "frontend.html",
  ],
)

py_library (
  name = "logger",
  srcs = [
    "logger.py",
  ],
  deps = [
    ":hal",
    "//impulse/rpc:rpc",
  ],
)