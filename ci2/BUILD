langs("Python")
load("//impulse/docker/build_defs.py")

py_library (
  name = "integration_base",
  srcs = [ "integration.py" ],
  deps = [
    "//impulse/hal:hal",
    "//impulse/util:temporal_dict",
  ],
)

py_library (
  name = "runner_lib",
  srcs = [
    "runnertype.py",
    "runner.py",
  ],
  deps = [
    ":run_integration_impl",
    "//impulse/host:libhost",
    "//impulse/rpc:rpc",
    "//impulse/util:interface",
  ],
)

py_library (
  name = "github_webhooks",
  srcs = [ "github.py" ],
  deps = [
    ":github_auth",
    ":integration_base",
    "//impulse/hal:hal",
  ]
)

py_library (
  name = "run_integration_impl",
  srcs = [ "run_integration_impl.py" ],
  deps = [
    ":integration_base",
    "//impulse/util:temp_dir",
  ],
)

py_library (
  name = "github_auth",
  srcs = [ "githubauth.py" ]
)

py_binary (
  name = "service",
  srcs = [ "service.py" ],
  deps = [
    ":github_webhooks",
    ":integration_base",
    ":runner_lib",
    "//impulse/hal:hal",
    "//impulse/host:libhost",
  ]
)

container (
  name = "ci-service",
  main_executable = "service",
  binaries = [
    "impulse",
  ],
  deps = [
    ":service",
    "//impulse:impulse",
  ],
  docker_args = {
    "pip_packages": [ "Flask" ],
    "alpine_packages": [
      "bash-completion",
      "fuse",
      "gcc",
      "g++",
      "git",
      "unzip",
      "zip",
    ],
    "environment": [ "FUSE_LIBRARY_PATH=/usr/lib/libfuse.so.2" ],
    "ports": [ 5566 ],
  }
)