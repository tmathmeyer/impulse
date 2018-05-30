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

## Writing a Rule file
A canonical example of a rule file is the included ```c_object``` rule:
```python
@buildrule
def c_object(name, srcs, **args):
	depends(inputs=srcs, outputs=[name+'.o'])

	object_dependencies = dependencies.filter(ruletype='c_object')
	objects = ' '.join(sum(map(build_outputs, object_dependencies), []))

	sources = ' '.join(local_file(src) for src in srcs)

	cmd = 'gcc -o %s -I%s -c %s %s -std=c11 -Wextra -Wall' % (
		build_outputs()[0], PWD, sources, objects)

	for flag in args.get('flags', []):
		cmd += (' ' + flag)
	command(cmd)
```

All build rules _MUST_ be tagged with the ```@buildrule``` decorator.

The ```@buildrule``` decorator can either be used with no arguments, or can be given another buildrule to use in scope. An example is the ```c_object_nostd``` rule:
```python
@buildrule(c_object)
def c_object_nostd(name, srcs, **args):
	flags = args.setdefault('flags', [])
	flags += [
		'-nostdinc', '-fno-stack-protector', '-m64', '-g'
	]
	c_object(name, srcs, **args)
```
which simply adds some flags and lets ```c_object``` do the heavy lifting. It is important to pass any needed build rules in the decorator, as the function bodies are evaluated as independant compilation units and will not have file local access at runtime.

There are two special arguments when calling a build rule:
* ```name```: A string which MUST be provided.
* ```deps```: Although not required, it is used to build the dependency graph of targets. The build rule code will have access to both the list of strings provided here, as well as the graph node objects.

When writing a build rule:
* It is acceptable to place ```name``` as a required positional argument, since it is required anyway.
* To force the requirement of any other field, it can be added to the argument list as a non-default positional argument. A missing argument will cause building to fail and report the violating target.
* A magic variable ```dependencies``` is availible, and it references a special ```FilterableSet``` type containing the direct dependencies for the current target, represented in their raw node form.

In addition, there are a few magic functions present in the local scope when a build rule is executed:
* ```directory()```: the local directory of the target.
* ```local_file(str)```: gets the full path to a file defined relative to the build target.
* ```copy(str)```: copies the provided full file to a cache location.
* ```depends(inputs=[], outputs=[])```: The input files and output files that this rule produces.
* ```build_outputs(dep=None)```: Get the full paths for build outputs of a rule. If no rule is provided, get the build outputs of the current rule.
* ```command(str)```: run a shell command which outputs files.
* ```is_nodetype(dep, str)```: Tests whether a dependency is a given type.

## Writing a BUILD file
#### Two examples:
$ROOT/json/BUILD:
```python
load(
    "//rules/core/C/build_defs.py",
)

c_headers(
    name = "map_h",
    srcs = [
        "map.h",
    ],
)

c_object(
    srcs = [
        "map.c",
    ],
    name = "map",
    deps = [
        ":map_h"
    ],
)
```

$ROOT/weather/BUILD:
```python
load(
    "//rules/core/C/build_defs.py",
)

c_headers(
    name = "exif_tags_h",
    srcs = [
        "exif_tags.h",
    ],
)

c_headers(
    name = "exif_h",
    srcs = [
        "exif.h",
    ],
    deps = [
        "//map:map_h",
    ],
)

c_object(
    name = "exif_tags",
    srcs = [
        "exif_tags.c",
    ],
    deps = [
        ":exif_tags_h"
    ],
)

c_object(
    name = "exif",
    srcs = [
        "exif.c",
    ],
    deps = [
        ":exif_tags_h",
        ":exif_h",
        "//map:map_h",
    ],
)

c_binary(
    name = "identify_photosphere",
    srcs = [
        "photosphere.c",
    ],
    deps = [
        ":exif",
        "//map:map",
        ":exif_tags",
    ]
)
```