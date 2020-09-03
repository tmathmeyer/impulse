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
    "//impulse/host:libhost",
    "//impulse/rpc:rpc",
    "//impulse/host/frontend:frontend",

    git_repo(
      url = "https://github.com/tmathmeyer/nginx_config_parser",
      repo = "nginxweb",
      target = "//nginxweb:nginxio",
    ),
  ],
)

py_library (
  name = "libhost",
  srcs = [ "libhost.py" ],
  deps = [ "//impulse/hal:hal" ],
)

service_installer (
  name = "host_service_installer",
  description = "Service that manages docker and nginx",
  executable = "host_server",
  deps = [
    ":host_server",
  ],
)