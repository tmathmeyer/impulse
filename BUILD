load(
    "//rules/core/Python/build_defs.py",
)

py_library(
    name = "impulse_lib",
    srcs = [
        "build_defs_runtime.py",
        "impulse.py",
        "impulse_paths.py",
        "recursive_loader.py",
        "status_out.py",
        "threaded_dependence.py",
    ],
)

py_binary(
	name = "impulse",
	deps = [
		":impulse_lib",
	],
	srcs = [
		"__main__.py",
	],
)