load (
  "//rules/core/Python/build_defs.py",
  "//impulse/docker/rules/build_defs.py"
)

python_container (
  name = "ci-container",
  main_executable = "ci_server",
  deps = [
    ":ci_server",
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
    "github.py",
    "githubauth.py",
    "gogs.py",
    "ci_server.py",
    "ci_pooling.py"
  ],
  deps = [
    "//impulse/hal:hal",
    "//impulse/rpc:rpc",
    "//impulse/util:temp_dir",
  ],
)