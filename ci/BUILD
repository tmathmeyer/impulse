load (
  "//rules/core/Python/build_defs.py",
  "//impulse/hive/rules/build_defs.py"
)

py_binary (
  name = "impulse_ci",
  srcs = [
    "build_task.py",
    "impulse_ci.py",
  ],
  deps = [
    "//impulse/util:temp_dir",
    "//impulse/rpc:rpc",
    "//impulse/hal:hal"
  ],
  data = [
    "frontend.html",
  ],
)

python_container (
  name = "ci-container",
  main_executable = "impulse_ci",
  deps = [
    ":impulse_ci",
    "//impulse:impulse",
  ],
  binaries = [
    "impulse",
  ],
  pip_packages = [
    "Flask",
  ],
  alpine_packages = [
    "git",
    "fuse",
    "zip",
    "unzip",
  ],
  environment = [
    "FUSE_LIBRARY_PATH=/usr/lib/libfuse.so.2",
  ],
)

py_binary (
  name = "ci_server",
  srcs = [
    "build.py",
    "ci_server.py",
    "ci_pooling.py"
  ],
  deps = [
    "//impulse/hal:hal",
    "//impulse/rpc:rpc",
  ],
)