load(
    "//rules/core/Python/build_defs.py",
)


py_binary(
    name = "impulse",
    srcs = ["impulse.py"],
    deps = [":impulse_libs"],
)

py_library(
    name = "impulse_libs",
    srcs = [
        "build_defs_runtime.py",
        "impulse_paths.py",
        "recursive_loader.py",
        "status_out.py",
        "threaded_dependence.py",
    ],
)
