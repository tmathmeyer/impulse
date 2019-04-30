load (
  "//rules/core/Python/build_defs.py",
  "//impulse/hive/rules/build_defs.py"
)

py_binary (
  name = "impulse_ci",
  srcs = [ "impulse_ci.py" ]
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
  pip_packages = [ "Flask" ]
)