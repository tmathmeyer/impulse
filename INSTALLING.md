# Installing Impulse
### requirements
 - python >= 3.7.0
 - linux >= 4.0
 - bash >= 4.4 (or knowledge of completion tools in other shells)

### Steps
First, select a directory in which all projects built by impulse will live.
Usually this is something like ```~/src```. This directory will be referenced
as ```$impulse-root``` throughout this document. ```$impulse-repository-path```
is the repository you're downloading impulse from.
 1. ```mkdir {$impulse-root} && cd {$impulse-root}```
 2. ```git clone {$impulse-repository-path} impulse```
 3. ```cd impulse && make && sudo make install``` (uses ```/usr/local/bin```)
 4. ```cd .. && impulse init```

### Completion
Source the file ```complete.sh``` from your shell (only bash supported for now)