#  Impulse: A build tool based loosely on bazel, but without the bloat

Impulse differentiates itself by being much simpler, while still giving developers much more control. Macros/Rules in bazel use some vile offspring of bash and makefile syntax stored in raw strings, while Rules in impulse are simple python functions.

## Installing
see INSTALLING.md

## Running
Default help menu:
```
~~$ impulse

usage: impulse [-h] {build,test,init} ...

optional arguments:
  -h, --help         show this help message and exit

tasks:
  {build,test,init}
    build            Builds the given target.
    test             Builds a testcase and executes it.
    init             Initializes impulse in the current directory.
```

Initialize Impulse:
 - no args
 - uses current directory as root.
 - prompts before use.
```
~~$ impulse init
```

Build a target:
```
~~$ impulse build -h

usage: impulse build [-h] [--debug] [--fakeroot FAKEROOT] target

positional arguments:
  target

optional arguments:
  -h, --help           show this help message and exit
  --debug              Prints debug messages.
  --fakeroot           A directory to consider the fake root. useful for
                       bootstrapping.

```

Run tests:
```
~~$ impulse test -h

usage: impulse test [-h] [--export] [--fakeroot FAKEROOT] target

positional arguments:
  target

optional arguments:
  -h, --help           show this help message and exit
  --export             exports test results to a server [WIP].
  --fakeroot FAKEROOT  A directory to consider the fake root. useful for
                       bootstrapping.

```


## Directory Layout
Like the previously mentioned tools, impulse treats some directory as the ```$ROOT```, and all projects are contained somewhere within this directory. For the sake of example in this readme, we will assume that ```$ROOT = ~/src```.

#### IMPULSE targets
An impulse target is something that impulse can build. A target is either:
* relative -- the target name starts with a colon, ex: ```":local_rule"```. relative rules are rules located in the SAME ```BUILD``` file as the current rule.
* fixed -- the target name starts with TWO forward slashes, ex: ```"//project/lib_example:lib_example"```. This rule references a build rule defined in ```$ROOT/project/lib_example/BUILD``` and named ```lib_example```.

#### BUILD files
Projects have one or more ```BUILD``` files defined in them. These files use a subset of python syntax, however most builtin tools aren't present and can't be expected to work normally anyway. There is one core function availible -- ```load()```, which accepts comma seperated strings referencing build rule files. These references always exist as a fixed path starting with two slashes. The rule ```"//rules/core/C/build_defs.py"``` references the file ```$ROOT/rules/core/C/build_defs.py```. Once loaded, all rules defined in loaded rule files may be used.

## Writing a BUILD file
#### Two examples:
$ROOT/impulse/BUILD:
```python
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
        "exceptions.py"
    ],
    deps = [
        "//impulse/args:args",
        "//impulse/pkg:packaging"
    ],
)

```

$ROOT/example_unittests/BUILD:
```python
load (
    "//rules/core/C/build_defs.py",
)

c_header (
  name = 'argparse_h',
  srcs = [
    "argparse.h"
  ],
)

cpp_test (
  name = 'argparse_test2',
  srcs = ['test.cpp'],
  deps = [':argparse_h']
)
```


#### Rule files
In this directory live python-defined build rules (see [core_rules](CORE) for some examples). For rules used in many different projects, these rules _should_ live under ```$ROOT/rules/core/{lang}/build_defs.py``` however these rules may be placed anywhere located under ```$ROOT```.

## Writing a Rule file
A canonical example of a rule file is the included ```py_library``` rule:
```python
def _track_files(target, srcs):
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))
  for deplib in target.Dependencies(package_ruletype='py_library'):
    for f in deplib.IncludedFiles():
      target.AddFile(f)

def _write_file(target, name, contents):
  if not os.path.exists(name):
    with open(name, 'w+') as f:
      f.write(contents)
  target.AddFile(name)


@using(_track_files, _write_file)
@buildrule
def py_library(target, name, srcs, **kwargs):
  _track_files(target, srcs)

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)
```

The ```@using(...)``` decorator allows buildrules to include helper functions from the
build_defs.py file. This is because each method is actually parsed and compiled separately
from each other method in a build_defs.py file. Only buildrules can import helper
functions, they cannot import eachother.

To actually create a buildrule, the function must also be decorated with the 
```@buildrule``` decorator. A buildrule function must take at least two arguments,
```target: pkg.packaging.ExportablePackage``` and ```name: str```. All other arguments
that are passed to a buildrule function come from BUILD files directly, and are
should always be basic data types (int, str, list, etc). To force the requirement of any field, it can be added to the argument list as a non-default positional argument. A missing argument will cause building to fail and report the violating target.

By default, all operations take place in a read-only copy of the source directory
where the BUILD file exists. The location is a temporary copy-on-write filesystem
which allows the rule to use and modify source files without affecting the real
state of the original sources. A ```pkg.packaging.ExportablePackage``` has methods
and fields designed to help run code in the buildrule:
* ```pkg.packaging.ExportablePackage.Dependencies(**kwargs)```: A way to filter
  rule types based on their properties. A commonly used one would be filtering
  on ```package_ruletype```, as is shown in ```_get_objects``` above.
* ```pkg.packaging.ExportablePackage.GetPackageDirectory()```: A function which
  returns the package directory.
* ```pkg.packaging.ExportablePackage.AddFile(file)```: Adds a file as an output.

Finally, any buildrule which ends in ```_binary``` must return a function which
can be used to convert it's package into a binary. In python, for example:
```python
def py_make_binary(package_name, package_file, binary_location):
  binary_file = os.path.join(binary_location, package_name)
  os.system('echo "#!/usr/bin/env python3\n" >> {}'.format(binary_file))
  os.system('cat {} >> {}'.format(package_file, binary_file))
  os.system('chmod +x {}'.format(binary_file))
```
This task is simple, since the package files can just have a ```#!/usr/bin/env python```
prepended, and they become executable python archives. 

## Python Executables
The default build rules offer ```py_library``` and ```py_binary``` as two build rules. It should be noted that if these rules are used, they change the way imports handled. Any third party import will stay the same as before, but importing other code built with impulse will have to be done absolutly. For example, with the directory layout:
```
impulse_root/
  project/
    some_component/
      helper1.py
      helper2.py
    another_component/
      fancy_code.py
    run_this.py
```
for any of these files to import helper1.py, they should do it like:
```
from project.some_component import helper1
```
this holds EVEN FOR ```helper2.py```.
