#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
    printf 'usage: bash task.sh OWNED_SETTINGS_FILE [--message TEXT] [--watch]\n' >&2
    exit 64
fi
settings=$1
shift
if [[ ! -f "$settings" || -L "$settings" || ! -O "$settings" ]]; then
    printf 'use an owned regular settings file from this lab, not a symbolic link\n' >&2
    exit 73
fi
settings=$(realpath -- "$settings")
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
message_set=no
message=
watch=no
while (( $# )); do
    case "$1" in
        --message)
            if [[ $# -lt 2 ]]; then
                printf '%s\n' '--message requires a value' >&2
                exit 64
            fi
            message_set=yes
            message=$2
            shift 2
            ;;
        --watch) watch=yes; shift ;;
        *) printf 'unknown option: %s\n' "$1" >&2; exit 64 ;;
    esac
done
bash -n "$settings"
# The fresh Bash child expands its own positional arguments.
# shellcheck disable=SC2016
exec env -i PATH="$PATH" bash --noprofile --norc -c '
    set -euo pipefail
    # This is an owned, trusted Bash assignment file, not a generic dotenv parser.
    source "$1"
    # EXPORT_BEGIN
    export MESSAGE REPEAT
    # EXPORT_END
    if [[ "$3" == yes ]]; then
        export MESSAGE="$4"
    fi
    if [[ "$5" == yes ]]; then
        exec python3 "$2" --watch
    else
        exec python3 "$2"
    fi
' _ "$settings" "$here/environment_app.py" "$message_set" "$message" "$watch"
