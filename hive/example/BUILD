load (
  "//rules/core/Python/build_defs.py",
  "//impulse/hive/rules/build_defs.py"
)

py_binary (
  name = "hive",
  srcs = [ "hive.py" ]
)

python_container (
  name = "hive-container",
  main_executable = "hive",
  deps = [":hive"],
  pip_packages = [ "Flask" ]
)