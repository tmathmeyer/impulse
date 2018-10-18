#!/bin/bash

_impulseargs_complete_global() {
    local executable="$(which $1)"
    if (strings "$executable" | grep --quiet "impulse/args/__init__.py") >/dev/null 2>&1; then
        command="$executable --iacomplete ${COMP_WORDS[@]:1}"
        cmdout=$(eval "$command")
        readarray -t COMPREPLY <<<"$cmdout"
        if [[ $? != 0 ]]; then
            unset COMPREPLY
        elif [[ "$COMPREPLY" =~ [=/:]$ ]]; then
            compopt -o nospace
        fi
    else
        type -t _completion_loader | grep -q 'function' && _completion_loader "$@"
    fi
}

complete -D -F _impulseargs_complete_global