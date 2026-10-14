#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
input_dir="${1:-$SCRIPT_DIR/reports}"
[[ $# -le 1 ]] || { printf 'Usage: bash task.sh [log-directory]\n' >&2; exit 2; }
[[ -d "$input_dir" && -r "$input_dir" && -x "$input_dir" ]] || {
    printf 'Cannot inspect log directory: %s\n' "$input_dir" >&2; exit 1;
}
input_dir="$(cd -- "$input_dir" && pwd -P)"
manifest="$(mktemp)"
trap 'rm -f -- "$manifest"' EXIT
# Save enumeration first so a failed find cannot become a successful summary.
find "$input_dir" -maxdepth 1 -type f -name '*.log' -print0 > "$manifest"
file_count=0
error_total=0
warning_total=0
while IFS= read -r -d '' log_path; do
    # The second whitespace-separated field is the level, not a message word.
    counts="$(awk '$2 == "ERROR" {e++} $2 == "WARNING" {w++} END {print e+0, w+0}' "$log_path")"
    read -r error_count warning_count <<< "$counts"
    : # Both parsed level counts are retained.
    ((file_count+=1))
    ((error_total+=error_count)) || true
    ((warning_total+=warning_count)) || true
done < "$manifest"
printf 'files=%s errors=%s warnings=%s\n' "$file_count" "$error_total" "$warning_total"
