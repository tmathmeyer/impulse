# IdeMpotent Python bUiLd SystEm (IMPULSE)

A mostly idempotent build system modeled after (bazel, buck, pants, etc), but without messy a messy setup process.

## Installing
```
git clone https://github.com/tmathmeyer/impulse
cd impulse
./build.sh
cp impulse {{DIRECTORY IN YOUR PATH}}

cd {{PROJECTS DIRECTORY}}
impulse init
```
You may then take any rules defined in the rules directory and bring them into your projects directory.

## Directory Layout
Like the previously mentioned tools, impulse treats some directory as the ```$ROOT```, and all projects are contained somewhere within this directory. For the sake of example in this readme, we will assume that ```$ROOT = ~/src```.

#### IMPULSE targets
An impulse target is something that impulse can build. A target is either:
* relative -- the target name starts with a colon, ex: ```":local_rule"```. relative rules are rules located in the SAME ```BUILD``` file as the current rule.
* fixed -- the target name starts with TWO forward slashes, ex: ```"//project/lib_example:lib_example"```. This rule references a build rule defined in ```$ROOT/project/lib_example/BUILD``` and named ```lib_example```.

#### BUILD files
Projects have one or more ```BUILD``` files defined in them. These files use a subset of python syntax, however most builtin tools aren't present and can't be expected to work normally anyway. There is one core function availible -- ```load()```, which accepts comma seperated strings referencing build rule files. These references always exist as a fixed path starting with two slashes. The rule ```"//rules/core/C/build_defs.py"``` references the file ```$ROOT/rules/core/C/build_defs.py```. Once loaded, all rules defined in loaded rule files may be used.


#### Rule files
In this directory live python-defined build rules (see [core_rules](CORE) for some examples). For rules used in many different projects, these rules _should_ live under ```$ROOT/rules/core/{lang}/build_defs.py``` however these rules may be placed anywhere located under ```$ROOT```.

## Writing a Rule File
A canonical example of a rule file is the included ```c_binary``` rule:
```python
@buildrule
def c_binary(name, **args):
	srcs = args.get('srcs', [])
	depends(inputs=srcs, outputs=[name])

	objects = ' '.join(' '.join(build_outputs(dep)) for dep in dependencies)
	sources = ' '.join(local_file(src) for src in srcs)

	cmd = 'gcc -o %s -I%s %s %s -std=c11 -pedantic -Wextra -Wall' % (
		build_outputs()[0], PWD, sources, objects)

	for flag in args.get('flags', []):
		cmd += (' ' + flag)

	command(cmd)
```

All build rules _MUST_ be tagged with the ```@buildrule``` decorator.

There are two special arguments when calling and writing a build rule:
* ```name```: must be positional, non-default, and is required to call a build rule. When defining a build rule, it is always the first argument.
* ```deps```: not required, but is used to list all rules which must be built prior to the current rule being built. the contents of ```deps``` is _not_ passed as an argument, but rather is available as a local variable called ```dependencies```, which is a list of ```DependencyGraph``` objects exposing the fields ```name (str)``` and ```dependencies ([DependencyGraph])```. 

In addition, there are a few functions present in the local scope when a build rule is executed:
* ```directory()```: the local directory of the target.
* ```local_file(str)```: gets the full path to a file defined relative to the build target.
* ```copy(str)```: copies the provided full file to a cache location.
* ```depends(inputs=[], outputs=[])```: The input files and output files that this rule produces.
* ```build_outputs(dep=None)```: Get the full paths for build outputs of a rule. If no rule is provided, get the build outputs of the current rule.
* ```command(str)```: run a shell command which outputs files.
* ```is_nodetype(dep, str)```: Tests whether a dependency is a given type.
