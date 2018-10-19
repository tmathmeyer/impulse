#!/bin/bash

_impulseargs_complete_global() {
    local bin="$(which $1)"
    local query="impulse/args/__init__.py"
    if (strings "$bin" | grep --quiet "$query") >/dev/null 2>&1; then
        command="$bin --iacomplete $COMP_LINE?"
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