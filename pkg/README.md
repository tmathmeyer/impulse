# The .ipkg file format
Really just a zip file underneath, except that it contains a file called
pkg_contents.json

## pkg_contents.json
This json file contains a dict with the following fields:
```
{
  "included_files": [
    ["Example.file.name", "example.file.sha256"],
    [...]
  ],
  "depends_on_targets": [
    //fully/qualified/example:target
  ],
  "package_name": "//impulse:impulse_libs",
  "package_ruletype": "py_library",
  "build_timestamp": 1550904457,
  "is_binary_target": true
}
```