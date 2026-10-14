#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# != 2 ]]; then
    printf 'usage: bash task.sh init|apply|rollback LAB_DIRECTORY\n' >&2
    exit 64
fi
action=$1
lab=$2
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
app=$here/config_app.py
if [[ ! -d "$lab" || -L "$lab" || ! -O "$lab" ]]; then
    printf 'use an existing owned directory, not a symbolic link\n' >&2
    exit 73
fi
lab=$(realpath -- "$lab")
if [[ "$lab" == / ]]; then
    printf 'the filesystem root is not a lab directory\n' >&2
    exit 73
fi

if [[ "$action" == init ]]; then
    shopt -s nullglob dotglob
    entries=("$lab"/*)
    if (( ${#entries[@]} )); then
        printf 'initialization requires an empty lab directory\n' >&2
        exit 73
    fi
    cp -- "$here/config.json" "$lab/config.json"
    cp -- "$here/candidate.json" "$lab/candidate.json"
    printf 'unit4-editing-owned-v1\n' > "$lab/.editing-lab"
    printf 'initialized %s\n' "$lab"
    exit 0
fi

if [[ ! -f "$lab/.editing-lab" || -L "$lab/.editing-lab" ||
      $(<"$lab/.editing-lab") != unit4-editing-owned-v1 ]]; then
    printf 'initialize this disposable directory before changing it\n' >&2
    exit 73
fi
for name in config.json candidate.json config.before.json; do
    if [[ -L "$lab/$name" || ( -e "$lab/$name" && ( ! -f "$lab/$name" || ! -O "$lab/$name" ) ) ]]; then
        printf 'refusing a non-owned regular file: %s\n' "$name" >&2
        exit 73
    fi
done

case "$action" in
    apply)
        # APPLY_BEGIN
        # TODO: validate current and candidate, retain a backup, and stage the replacement.
        printf 'unfinished: implement the validated apply step\n' >&2
        exit 78
        # APPLY_END
        ;;
    rollback)
        python3 "$app" validate "$lab/config.before.json"
        staged=$(mktemp "$lab/.config.XXXXXX")
        trap 'rm -f -- "$staged"' EXIT
        cp -p -- "$lab/config.before.json" "$staged"
        mv -f -- "$staged" "$lab/config.json"
        printf 'restored; explicitly reload the owned lab process next\n'
        ;;
    *)
        printf 'unknown action: %s\n' "$action" >&2
        exit 64
        ;;
esac
