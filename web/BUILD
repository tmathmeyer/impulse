langs('Python', 'JS')
load("//impulse/web/build_defs.py")

py_binary(
  name = "demo",
  srcs = [ "demo.py" ],
  deps = [ ":demo_component" ],
  data = [ "demo.html" ],
)

js_module(
  name = "component_base",
  srcs = [ "component.js" ]
)

web_component(
  name = "demo_component",
  srcs = [ "demo_component.js" ],
)