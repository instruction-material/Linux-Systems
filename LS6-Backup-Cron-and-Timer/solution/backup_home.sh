#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { printf 'This backup lab requires Linux tools.\n' >&2; exit 2; }
[[ $# == 2 ]] || { printf 'Usage: bash backup_home.sh SOURCE_DIRECTORY BACKUP_DIRECTORY\n' >&2; exit 2; }
source_dir="$1"
dest_dir="$2"
retention_count="${RETENTION_COUNT:-5}"
[[ "$retention_count" =~ ^[1-9][0-9]{0,3}$ && "$retention_count" -le 1000 ]] || { printf 'RETENTION_COUNT must be an integer from 1 through 1000.\n' >&2; exit 2; }
[[ -d "$source_dir" ]] || { printf 'Missing source directory.\n' >&2; exit 2; }
source_dir="$(cd -- "$source_dir" && pwd -P)"
[[ "$source_dir" != / ]] || { printf 'Select an owned lab source, not the filesystem root.\n' >&2; exit 2; }
dest_dir="$(realpath -m -- "$dest_dir")"
case "$dest_dir/" in "$source_dir/"*) printf 'The backup directory must be outside the source tree.\n' >&2; exit 2 ;; esac
umask 077
mkdir -p -- "$dest_dir"
dest_dir="$(cd -- "$dest_dir" && pwd -P)"
case "$dest_dir/" in "$source_dir/"*) printf 'The backup directory must be outside the source tree.\n' >&2; exit 2 ;; esac
umask 077
exec 9> "$dest_dir/.linux-systems-backup.lock"
flock -x -w 30 9 || { printf 'Backup lock is busy.\n' >&2; exit 1; }
temporary="$(mktemp "$dest_dir/.backup-XXXXXX")"
inventory="$(mktemp "$dest_dir/.retention-XXXXXX")"
trap 'rm -f -- "$temporary" "$inventory"' EXIT
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
temporary_name="${temporary##*/}"
suffix="${temporary_name#.backup-}"
archive_name="linux-systems-backup-$stamp-$suffix.tar.gz"
# Relative archive members permit restoration into a separate owned directory.
tar -C "$source_dir" -czf "$temporary" .
# Hard-link publication refuses replacement of an existing archive name.
ln -- "$temporary" "$dest_dir/$archive_name"
rm -f -- "$temporary"
# Keep the archive just created, plus the newest retention_count - 1 older ones.
find "$dest_dir" -maxdepth 1 -type f -name 'linux-systems-backup-*.tar.gz' ! -name "$archive_name" -printf '%T@ %f\0' > "$inventory"
LC_ALL=C sort -z -nr -o "$inventory" "$inventory"
kept=0
while IFS= read -r -d '' record; do
    old_name="${record#* }"
    if (( kept >= retention_count - 1 )); then rm -f -- "$dest_dir/$old_name"; fi
    ((kept+=1))
done < "$inventory"
printf 'Created %s\n' "$dest_dir/$archive_name"
