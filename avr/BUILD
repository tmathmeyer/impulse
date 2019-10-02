load (
    "//impulse/avr/build_defs.py",
    "//rules/core/Python/build_defs.py"
)

arduino_obj (
  name = "blink_obj",
  srcs = [ "blink.c" ],
)

arduino_export (
  name = "blink",
  deps = [ ":blink_obj" ],
  srcs = [ "blink.c" ],
)

py_binary(
  name = "arduino",
  srcs = [ "arduino.py" ],
  deps = [
    "//impulse/args:args",
    git_repo("https://github.com/tmathmeyer/avrdude-src")
  ]
)