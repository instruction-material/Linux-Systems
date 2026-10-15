#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -s) == Linux && $EUID -gt 0 ]] || { printf 'Use an ordinary account in an owned Linux lab.\n' >&2; exit 2; }
if (( $# < 1 )); then
    printf 'usage: bash task.sh OWNED_BASH_SCRIPT [ARGUMENT...]\n' >&2
    exit 2
fi
target=$1
shift
[[ -f $target && ! -L $target && -O $target ]] || { printf 'Use an owned ordinary nonsymlink script.\n' >&2; exit 2; }
case $target in
    /*) ;;
    *) target=$PWD/$target ;;
esac
# The inspected program requires Bash; preserve each original argument.
BASH_ENV=/dev/null exec "$BASH" --noprofile --norc "$target" "$@"
