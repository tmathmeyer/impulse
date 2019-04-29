load(
    "//rules/core/Python/build_defs.py",
)

py_binary(
    name = "impulse",
    srcs = ["impulse.py"],
    deps = [
        ":impulse_libs",
        "//impulse/args:args"
    ],
)

py_library(
    name = "impulse_libs",
    srcs = [
        "impulse_paths.py",
        "recursive_loader.py",
        "status_out.py",
        "threaded_dependence.py",
        "build_target.py",
    ],
    deps = [
        "//impulse/args:args",
        "//impulse/pkg:packaging",
        "//impulse/exceptions:exceptions",
        "//impulse/util:temp_dir",
    ],
)
