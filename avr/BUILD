langs("Python")

load (
    "//impulse/avr/build_defs.py"
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
    "//impulse:impulse_libs",
  ],
  tools = [
    git_repo(
      url = "https://github.com/tmathmeyer/avrdude-src",
      repo = "avrdude-src",
      target = "//avrdude-src:avrdude",
    ),
    git_repo(
      url = "https://github.com/tmathmeyer/avrdude-src",
      repo = "avrdude-src",
      target = "//avrdude-src:avrdude_config",
    ),
  ],
  data = [
  ],
)