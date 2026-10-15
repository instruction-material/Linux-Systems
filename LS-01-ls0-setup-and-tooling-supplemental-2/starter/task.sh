#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -s) == Linux && $EUID -gt 0 ]] || { printf 'Use an ordinary account in an owned Linux lab.\n' >&2; exit 2; }
if (( $# != 1 )); then
    printf 'usage: bash task.sh ABSOLUTE_SEARCH_DIRECTORY[:DIRECTORY...]\n' >&2
    exit 2
fi
search_path=$1
[[ -n $search_path && $search_path != :* && $search_path != *: && $search_path != *::* && $search_path != *$'\n'* && $search_path != *$'\r'* ]] || { printf 'Use nonempty absolute directory entries without line breaks.\n' >&2; exit 2; }
IFS=: read -r -a search_directories <<< "$search_path"
for directory in "${search_directories[@]}"; do
    [[ $directory == /* && -d $directory && ! -L $directory && -O $directory ]] || { printf 'Use owned ordinary absolute search directories.\n' >&2; exit 2; }
done
readonly bash_bin=$BASH
if resolved=$(PATH="$search_path" BASH_ENV=/dev/null "$bash_bin" --noprofile --norc -c 'command -v lab-tool.sh'); then
    lookup_status=0
else
    lookup_status=$?
fi
printf 'lookup_status=%s\nresolved=%s\n' "$lookup_status" "$resolved"
if PATH="$search_path" BASH_ENV=/dev/null "$bash_bin" --noprofile --norc -c 'lab-tool.sh --version'; then
    run_status=0
else
    run_status=$?
fi
printf 'run_status=%s\n' "$run_status"
# TODO: a located command can still fail its actual version request.
if (( lookup_status == 0 )); then
    printf 'usable=yes\n'
    exit 0
fi
printf 'usable=no\n'
exit 1
