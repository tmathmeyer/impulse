#  Impulse: A binary packager / build system for personal projects

I got the idea for this because I was trying to write bzl files for work one day
and realized how insane the bash/makefile nonsense syntax was. Of course, this
also triggered my NIH syndrome and I decided to make my own declarative build
system, where the rule definitions are written in plain python.

## Installing
### requirements
 - python >= 3.8.0
 - linux >= 5.0
 - bash >= 4.4 (or knowledge of completion tools in other shells)

### Setup
You first need to setup your project root - this is kind of like a mono-repo,
and ```impulse``` will use this directory if it needs to fetch things from git
or look up build targets. This is generally something like ```~/git``` or
```~/src```, but really any user-writable directory works fine. Lets call this
directory ```$impulse-root```.
 1. ```cd {$impulse-root}```
 2. ```git clone https://github.com/tmathmeyer/impulse.git impulse```
 3. ```cd impulse && make && sudo make install``` (installed to ```/usr/local/bin```)
 4. ```cd .. && impulse init```

### Shell Completion for ```/bin/bash```
Source the file ```complete.sh``` from your shell. You can copy this somewhere
else and source it from your ```~/.bashrc``` as well.

## Running
Default help menu:
```
~~$ impulse

usage: impulse [-h] {build,print_tree,run,docker,test,init,testsuite} ...

optional arguments:
  -h, --help            show this help message and exit

tasks:
  {build,print_tree,run,docker,test,init,testsuite}
    build               Builds the given target.
    print_tree          Builds the given target.
    run                 Builds a testcase and executes it.
    docker              Builds a docker container from the target.
    test                Builds a testcase and executes it.
    init                Initializes impulse in the current directory.
    testsuite           testsuite
```

You can get more help for each individual command by running
```impulse {command} --help```. for example:
```
$ impulse init --help
usage: impulse init [-h]

optional arguments:
  -h, --help  show this help message and exit
```
or
```
$ impulse testsuite --help
usage: impulse testsuite [-h] [--project PROJECT] [--debug] [--notermcolor] [--fakeroot FAKEROOT]

optional arguments:
  -h, --help           show this help message and exit
  --project PROJECT
  --debug
  --notermcolor
  --fakeroot FAKEROOT
```

#### Targets
An impulse target is something that impulse can build. A target is either:
* relative -- the target name starts with a colon, ex: ```":local_rule"```. relative rules are rules located in the SAME ```BUILD``` file as the current rule.
* fixed -- the target name starts with TWO forward slashes, ex: ```"//project/lib_example:lib_example"```. This rule references a build rule defined in ```$ROOT/project/lib_example/BUILD``` and named ```lib_example```.

#### BUILD files
Projects have one or more ```BUILD``` files defined in them. These files use a subset of python syntax, however most builtin tools aren't present and can't be expected to work normally anyway. There is one core function availible -- ```load()```, which accepts comma seperated strings referencing build rule files. These references always exist as a fixed path starting with two slashes. The rule ```"//rules/core/C/build_defs.py"``` references the file ```$ROOT/rules/core/C/build_defs.py```. Once loaded, all rules defined in loaded rule files may be used.

## Writing a BUILD file
#### Two examples:
$ROOT/impulse/BUILD:
```python
langs("Python")

py_library(
    name = "debug",
    srcs = [ "debug.py" ],
)

py_library(
  name = "exceptions",
  srcs = [ "exceptions.py" ],
)

py_library(
  name = "job_printer",
  srcs = [ "job_printer.py" ],
  deps = [ ":debug" ],
)
```

$ROOT/example_unittests/BUILD:
```python
langs("C")

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

entries in deps can also be some internal builtin functions. Currently supported is ```git_repo```
which takes url, repo, commit, target as arguments. A git repo dependency will attempt to checkout
the repository into $IMPULSE_ROOT, make a sub-working tree checked out at |commit| and then
build |target| as a dependency.

#### Rule files
In this directory live python-defined build rules (see [core_rules](CORE) for some examples). For rules used in many different projects, these rules _should_ live under ```$ROOT/rules/core/{lang}/build_defs.py``` however these rules may be placed anywhere located under ```$ROOT```.

## Writing a Rule file
A canonical example of a rule file is the included ```py_library``` rule:
```python
def _add_files(target, srcs):
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))
  for deplib in target.Dependencies(tags=Any('py_library')):
    for f in deplib.IncludedFiles():
      target.AddFile(f)
  for deplib in target.Dependencies(tags=Any('data')):
    for f in deplib.IncludedFiles():
      target.AddFile(f)
      d = os.path.dirname(f)
      while d:
        _write_file(target, os.path.join(d, '__init__.py'), '#generated')
        d = os.path.dirname(d)


def _write_file(target, name, contents):
  if not os.path.exists(name):
    with open(name, 'w+') as f:
      f.write(contents)
  target.AddFile(name)


@using(_add_files, _write_file)
@buildrule
def py_library(target, name, srcs, **kwargs):
  target.SetTags('py_library')
  _add_files(target, srcs + kwargs.get('data', []))

  # Create the init files
  directory = target.GetPackageDirectory()
  while directory:
    _write_file(target, os.path.join(directory, '__init__.py'), '#generated')
    directory = os.path.dirname(directory)
```

More to come.
