# Impulse Export Packaging Spec

## package.json spec
```json
{
  "input_files": [
    "/path/relative/to/i_root",
    ...
  ],
  "output_files": [
    "/path/relative/to/i_root/packages",
    ....
  ],
  "depends": [
    "/path/relative/to/i_root/of_other_package.json",
    ...
  ],
  "build_timestamp": unixtime,
  "built_from": "py_library | py_binary | cpp_library | etc..."
}
```

```
$ROOT_DIRECTORY
 |--example
 |   |--nested
 |   |   |--BUILD
 |   |   \--foo.cpp
 |   |--BUILD
 |   |--bar.py
 |   \--baz.py
 \--PACKAGES
     \--example
         |--nested
         |   |--{rule}.package.json
         |   \--foo.o
         |--{rule}.package.json
         |--__init__.py
         |--bar.py
         \--baz.py
``` 
