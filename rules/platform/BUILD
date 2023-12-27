platform (
  name = "x64-linux-gnu",
  cc_compiler = "g++",
  cc_linker = "ld",
  cc_flags = [
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
    "-fdiagnostics-color=always",
  ],
  ld_flags = [
    "-z muldefs",
    "-r",
  ],
  c_compiler = "gcc",
)

platform (
  name = "x64-linux-clang",
  cc_compiler = "clang++",
  cc_linker = "ld",
  c_compiler = "clang",
  ld_flags = [
  ],
)

platform (
  name = "avr32-gnu",
  cc_compiler = "avr-gcc",
  cc_linker = "avr-ld",
)

platform (
  name = "wasm",
  cc_compiler = "clang++",
  cc_linker = "wasm-ld",
  cc_flags = [
    "-Ofast",
    "--target=wasm32",
    "-nostdinc",
    "-fno-rtti",
    "-fvisibility=hidden",
    "-fno-builtin",
    "-fno-exceptions",
    "-fno-threadsafe-statics",
  ],
  ld_flags = [
    "-no-entry",
    "-allow-undefined",
    "-export-all",
  ],
)