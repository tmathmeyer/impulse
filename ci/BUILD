langs("Python")
load (
  "//impulse/docker/build_defs.py"
)

container (
  name = "ci-container",
  main_executable = "ci_server",
  binaries = [ "impulse" ],
  deps = [
    ":ci_server",
    "//impulse:impulse",
  ],
  docker_args = {
    "pip_packages": [ "Flask" ],
    "alpine_packages": [ "git", "fuse", "zip", "unzip", "bash-completion" ],
    "environment": [ "FUSE_LIBRARY_PATH=/usr/lib/libfuse.so.2" ],
    "ports": [ 5566 ],
  }
)

py_binary (
  name = "ci_server",
  srcs = [
    "github.py",
    "githubauth.py",
    "gogs.py",
    "logging.py",
    "ci_server.py",
    "ci_pooling.py"
  ],
  deps = [
    "//impulse/hal:hal",
    "//impulse/rpc:rpc",
    "//impulse/util:temp_dir",
    "//impulse/host:libhost",
  ],
)