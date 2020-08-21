langs("Python")
load (
  "//impulse/docker/rules/build_defs.py",
  "//impulse/systemd/rules/build_defs.py"
)

py_binary (
  name = "host_server",
  srcs = [
    "host_server.py",
  ],
  deps = [
    "//impulse/hal:hal",
    "//impulse/hal:logger",
    "//impulse/host:libhost",
    "//impulse/rpc:rpc",

    git_repo(
      url = "https://github.com/tmathmeyer/nginx_config_parser",
      repo = "nginxweb",
      target = "//nginxweb:nginxio",
    ),
  ],
)

python_service (
  name = "host_service",
  description = "Service that manages docker and nginx",
  executable = "host_server",
  deps = [
    ":host_server",
  ],
)

py_library (
  name = "libhost",
  srcs = [ "libhost.py" ],
  deps = [ "//impulse/hal:hal" ],
)

py_binary (
  name = "demo_container",
  srcs = [
    "demo_container.py",
  ],
  deps = [
    "//impulse/hal:hal",
    "//impulse/host:libhost",
  ],
)

python_container (
  name = "demo-container",
  main_executable = "demo_container",
  binaries = [ ],
  environment = [ ],
  alpine_packages = [ ],
  ports = [ 5566 ],
  deps = [
    ":demo_container",
  ],
  pip_packages = [
    "Flask",
  ],
)