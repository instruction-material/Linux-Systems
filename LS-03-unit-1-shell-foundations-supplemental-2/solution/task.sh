#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
[[ $(uname -s) == Linux ]] || { printf 'Use an owned Linux lab.\n' >&2; exit 2; }
[[ $# -ge 2 && -n "$1" ]] || {
    printf 'Usage: bash task.sh literal-text file [file ...]\n' >&2; exit 2;
}
needle=$1
shift
for file in "$@"; do
    [[ "$file" != - ]] || { printf 'A file operand cannot be stdin (-).\n' >&2; exit 2; }
    if [[ -L "$file" || ( -e "$file" && ! -f "$file" ) ]]; then
        printf 'Use ordinary nonsymlink text files: %s\n' "$file" >&2; exit 2;
    fi
done
# Disable early exit only while collecting the two real pipeline statuses.
set +e
grep --color=never -F -l -Z -e "$needle" -- "$@" | sort -z -u
statuses=("${PIPESTATUS[@]}")
set -e
printf 'grep=%s sort=%s\n' "${statuses[0]}" "${statuses[1]}" >&2
if (( statuses[1] != 0 || statuses[0] > 1 )); then
    printf 'Search or sorting failed; discard any partial filename list.\n' >&2
    exit 2
fi
exit "${statuses[0]}"
