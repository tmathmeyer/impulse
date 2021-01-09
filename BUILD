langs("Python")

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
        "build_target.py",
    ],
    deps = [
        "//impulse/args:args",
        "//impulse/core:debug",
        "//impulse/core:exceptions",
        "//impulse/core:threading",
        "//impulse/core:job_printer",
        "//impulse/pkg:packaging",
        "//impulse/rules:core_rules",
        "//impulse/util:temp_dir",
        "//impulse/util:tree_builder",
        "//impulse/util:bintools",
    ],
)
