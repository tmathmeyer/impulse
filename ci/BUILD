load (
  "//rules/core/Python/build_defs.py",
  "//impulse/hive/rules/build_defs.py"
)

py_binary (
  name = "impulse_ci",
  srcs = [
    "build_task.py",
    "impulse_ci.py",
    "flask_api.py",
  ],
  deps = [
    "//impulse/util:temp_dir",
    "//impulse/rpc:rpc",
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
    "fusepy",
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