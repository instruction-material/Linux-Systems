#!/usr/bin/env bash
set -euo pipefail
role_root=$(CDPATH="" cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if (( $# == 0 )); then
    printf 'usage: bash task.sh {check|app|backup|render} [arguments...]\n' >&2
    exit 2
fi
command=$1
shift
case "$command" in
    check) exec python3 "$role_root/app.py" --check "$@" ;;
    app) exec python3 "$role_root/app.py" "$@" ;;
    backup) exec python3 "$role_root/backup.py" "$@" ;;
    render) exec python3 "$role_root/render_lab.py" "$@" ;;
    *) printf 'unknown project action\n' >&2; exit 2 ;;
esac
