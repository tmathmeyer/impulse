langs("Python", "Template")

py_library (
  name = "installer",
  srcs = [ "installer.py" ],
  deps = [
    "//impulse/args:args",
    "//impulse/util:bintools",
  ],
)

raw_template (
  name = "metadata-template",
  srcs = [ "systemd.metadata.template" ],
)

raw_template (
  name = "target-template",
  srcs = [ "systemd.target.template" ],
)