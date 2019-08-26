#!/bin/bash

_impulseargs_complete_global() {
    local bin="$(which $1)"
    local query="impulse/args/__init__.py"
    if (strings "$bin" | grep --quiet "$query") >/dev/null 2>&1; then
        export _LOCAL_COMP_LINE=$COMP_LINE
        readarray -t COMPREPLY <<<$("$bin" "--iacomplete")
        unset _LOCAL_COMP_LINE

        # if the command failed => unset completion
        if [[ $? != 0 ]]; then
          echo "failed cmd" > /tmp/impulse_complete_log
          unset COMPREPLY
          return

        # ensure that there are no spaces pasted if we end in a /
        elif [[ "$COMPREPLY" =~ [=/:]$ ]]; then
          echo "ends in /" > /tmp/impulse_complete_log
          compopt -o nospace

        # no results (?) => unset completion
        elif [ ${#COMPREPLY[@]} -eq 0 ]; then
          echo "no results" > /tmp/impulse_complete_log
          unset COMPREPLY
          return

        # first result is empty => unset completion
        elif [ -z "${COMPREPLY[0]}" ]; then
          echo "first empty" > /tmp/impulse_complete_log
          unset COMPREPLY
          return
        fi
    else
      type -t _completion_loader | grep -q 'function' && _completion_loader "$@"
    fi
}

complete -r -D -F _impulseargs_complete_global
complete -D -F _impulseargs_complete_global