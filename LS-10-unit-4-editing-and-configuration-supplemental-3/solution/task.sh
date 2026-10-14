#!/usr/bin/env bash
set -euo pipefail
umask 077
if [[ $# -lt 2 || $# -gt 3 ]]; then
    printf 'usage: bash task.sh init LAB | preview|apply LAB TIMEOUT | rollback LAB BACKUP\n' >&2
    exit 64
fi
action=$1
lab=$2
value=${3-}
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
validator=$here/validate_config.py
names=(primary.conf secondary.conf)
if [[ ! -d "$lab" || -L "$lab" || ! -O "$lab" ]]; then
    printf 'use an existing owned directory, not a symbolic link\n' >&2
    exit 73
fi
lab=$(realpath -- "$lab")
if [[ "$lab" == / ]]; then
    printf 'the filesystem root is not a disposable lab\n' >&2
    exit 73
fi
if [[ "$action" == init ]]; then
    shopt -s nullglob dotglob
    entries=("$lab"/*)
    if (( ${#entries[@]} )); then
        printf 'initialization requires an empty directory\n' >&2
        exit 73
    fi
    for name in "${names[@]}"; do cp -- "$here/$name" "$lab/$name"; done
    printf 'unit4-replacement-owned-v1\n' > "$lab/.replacement-lab"
    printf 'initialized %s\n' "$lab"
    exit 0
fi
if [[ ! -f "$lab/.replacement-lab" || -L "$lab/.replacement-lab" ||
      $(<"$lab/.replacement-lab") != unit4-replacement-owned-v1 ]]; then
    printf 'initialize this disposable replacement lab first\n' >&2
    exit 73
fi
require_file() {
    if [[ ! -f "$1" || -L "$1" || ! -O "$1" ]]; then
        printf 'refusing a non-owned regular file: %s\n' "$1" >&2
        exit 73
    fi
}
for name in "${names[@]}"; do require_file "$lab/$name"; done
prepare_one() {
    local source=$1 destination=$2 new_value=$3
    # REPLACE_BEGIN
    sed -E -e "s|^([[:blank:]]*timeout[[:blank:]]*=[[:blank:]]*)[0-9]+([[:blank:]]*(#.*)?)$|\1${new_value}\2|" -- "$source" > "$destination"
    # REPLACE_END
}

case "$action" in
    preview|apply)
        if [[ ! "$value" =~ ^([1-9]|[1-5][0-9]|60)$ ]]; then
            printf 'TIMEOUT must be an integer from 1 through 60\n' >&2
            exit 64
        fi
        staged=$(mktemp -d "$lab/.edit.XXXXXX")
        trap 'rm -rf -- "$staged"' EXIT
        for name in "${names[@]}"; do
            python3 "$validator" "$lab/$name"
            prepare_one "$lab/$name" "$staged/$name" "$value"
            python3 "$validator" "$staged/$name" --expect-timeout "$value"
            chmod --reference="$lab/$name" "$staged/$name"
        done
        for name in "${names[@]}"; do
            if diff -u -- "$lab/$name" "$staged/$name"; then
                :
            else
                status=$?
                if [[ "$status" != 1 ]]; then exit "$status"; fi
            fi
        done
        if [[ "$action" == preview ]]; then exit 0; fi
        backup=$(mktemp -d "$lab/backup.XXXXXX")
        for name in "${names[@]}"; do cp -p -- "$lab/$name" "$backup/$name"; done
        printf 'unit4-replacement-backup-v1\n' > "$backup/.complete"
        printf 'backup=%s\n' "$backup"
        # The two renames are individually atomic, not a multi-file transaction.
        for name in "${names[@]}"; do mv -f -- "$staged/$name" "$lab/$name"; done
        printf 'applied both prepared files\n'
        ;;
    rollback)
        if [[ ! -d "$value" || -L "$value" || ! -O "$value" ]]; then
            printf 'use a retained complete backup from this lab\n' >&2
            exit 73
        fi
        backup=$(realpath -- "$value")
        if [[ "$backup" != "$lab"/backup.* || $(dirname -- "$backup") != "$lab" ||
              ! -f "$backup/.complete" || -L "$backup/.complete" ||
              $(<"$backup/.complete") != unit4-replacement-backup-v1 ]]; then
            printf 'backup must be a complete direct child of this lab\n' >&2
            exit 73
        fi
        staged=$(mktemp -d "$lab/.edit.XXXXXX")
        trap 'rm -rf -- "$staged"' EXIT
        for name in "${names[@]}"; do
            require_file "$backup/$name"
            python3 "$validator" "$backup/$name"
            cp -p -- "$backup/$name" "$staged/$name"
        done
        for name in "${names[@]}"; do mv -f -- "$staged/$name" "$lab/$name"; done
        printf 'restored both retained files\n'
        ;;
    *) printf 'unknown action: %s\n' "$action" >&2; exit 64 ;;
esac
