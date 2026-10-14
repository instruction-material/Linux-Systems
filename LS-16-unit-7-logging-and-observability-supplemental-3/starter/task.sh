#!/usr/bin/env bash
set -euo pipefail
if (( $# != 1 )) || [[ ! -d "$1" || -L "$1" ]]; then
    printf 'Usage: bash task.sh OWNED_LAB_DIRECTORY\n' >&2
    exit 2
fi
lab=$(cd -- "$1" && pwd -P)
if [[ $(stat -c %u -- "$lab") != "$(id -u)" || $(stat -c %a -- "$lab") != '700' ]]; then
    printf 'The retention directory must belong to the active user and have mode 700.\n' >&2
    exit 2
fi
if [[ ! -f "$lab/.linux-log-lab" || -L "$lab/.linux-log-lab" ]] || [[ $(cat -- "$lab/.linux-log-lab") != 'linux-log-retention-v1' ]]; then
    printf 'The owned disposable log-lab marker is missing.\n' >&2
    exit 2
fi
for file in app.log rotation.conf rotation.state; do
    if [[ -L "$lab/$file" || ( -e "$lab/$file" && ! -f "$lab/$file" ) ]]; then
        printf 'A lab path is a symlink or a nonregular file: %s\n' "$file" >&2
        exit 2
    fi
done
if [[ ! -f "$lab/app.log" ]]; then
    printf 'Create the disposable app.log before rotating.\n' >&2
    exit 2
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
python3 - "$source_dir/logrotate.conf" "$lab" <<'PYTHON'
import sys
from pathlib import Path
source, directory = sys.argv[1:]
if any(char in directory for char in '\n\r"\\'):
    raise SystemExit("Use a lab path without quotes, backslashes or line breaks; spaces are supported.")
text = Path(source).read_text()
if text.count('__LAB__') != 1:
    raise SystemExit("The template must name exactly one owned application log.")
Path(directory, 'rotation.conf').write_text(text.replace('__LAB__', directory))
PYTHON
exec logrotate --state "$lab/rotation.state" --force "$lab/rotation.conf"
