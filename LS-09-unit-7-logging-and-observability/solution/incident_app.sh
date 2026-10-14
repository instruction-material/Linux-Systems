#!/usr/bin/env bash
set -euo pipefail
printf '<6>case: event=start\n'
if (( $# != 1 )) || [[ ! -f "$1" ]]; then
    printf '<3>case: event=config_missing\n' >&2
    exit 2
fi
setting=$(cat -- "$1")
if [[ "$setting" != 'enabled=yes' ]]; then
    printf '<3>case: event=config_invalid\n' >&2
    exit 2
fi
printf '<6>case: event=ready\n'
