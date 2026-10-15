#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
[[ $(uname -s) == Linux ]] || { printf 'Use an owned Linux lab.\n' >&2; exit 2; }
[[ $# -ge 1 ]] || { printf 'Usage: bash task.sh file [file ...]\n' >&2; exit 2; }
for file in "$@"; do
    [[ "$file" != - ]] || { printf 'A file operand cannot be stdin (-).\n' >&2; exit 2; }
    if [[ -L "$file" || ( -e "$file" && ! -f "$file" ) ]]; then
        printf 'Use ordinary nonsymlink text files: %s\n' "$file" >&2; exit 2;
    fi
done
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
set +e
cat -- "$@" | awk -f "$script_dir/count.awk"
statuses=("${PIPESTATUS[@]}")
set -e
printf 'producer=%s consumer=%s\n' "${statuses[0]}" "${statuses[1]}" >&2
if (( statuses[0] != 0 || statuses[1] != 0 )); then
    printf 'Pipeline failed; the printed summary is partial or unavailable.\n' >&2
    exit 2
fi
