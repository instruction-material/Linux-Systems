#!/usr/bin/env bash
set -euo pipefail
unset CDPATH
[[ $(uname -s) == Linux && $EUID -gt 0 ]] || { printf 'Use an ordinary account in an owned Linux lab.\n' >&2; exit 2; }
[[ $# -eq 1 && -d "$1" ]] || { printf 'Usage: bash task.sh existing-directory\n' >&2; exit 2; }
builtin cd -L -- "$1"
printf 'logical\0%s\0' "$PWD"
(
    builtin cd -P -- .
    printf 'physical\0%s\0' "$PWD"
)
(
    builtin cd -L -- ..
    printf 'logical_parent\0%s\0' "$PWD"
)
(
    builtin cd -P -- ..
    printf 'physical_parent\0%s\0' "$PWD"
)
