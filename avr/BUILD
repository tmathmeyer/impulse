load (
    "//impulse/avr/build_defs.py",
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