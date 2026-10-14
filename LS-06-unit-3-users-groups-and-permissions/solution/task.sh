#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { printf 'This access lab requires Linux.\n' >&2; exit 2; }
[[ $(id -u) -ne 0 ]] || { printf 'Use an unprivileged Linux account for access observations.\n' >&2; exit 2; }
[[ $# == 2 ]] || { printf 'Usage: bash task.sh setup|inspect|fix|verify WORKSPACE\n' >&2; exit 2; }
operation="$1"
lab_root="$2"
[[ -d "$lab_root" && ! -L "$lab_root" ]] || { printf 'Create an empty owned workspace first.\n' >&2; exit 2; }
lab_root="$(cd -- "$lab_root" && pwd -P)"
[[ "$(stat -c %u -- "$lab_root")" == "$(id -u)" ]] || { printf 'The workspace must belong to the active account.\n' >&2; exit 2; }
marker="$lab_root/.linux-permissions-lab"

check_layout() {
    [[ -f "$marker" && ! -L "$marker" ]] || { printf 'Missing lab marker.\n' >&2; return 2; }
    [[ "$(cat -- "$marker")" == "permissions-v1:$(id -u)" ]] || { printf 'Wrong lab identity.\n' >&2; return 2; }
    for path in "$lab_root/site" "$lab_root/site/private"; do
        [[ -d "$path" && ! -L "$path" ]] || { printf 'Unexpected lab path.\n' >&2; return 2; }
    done
}

inspect_access() {
    printf 'uid=%s groups=%s\n' "$(id -u)" "$(id -G)"
    stat -c 'mode=%a uid=%u gid=%g path=%n' -- "$lab_root" "$lab_root/site" "$lab_root/site/private"
    if [[ -r "$lab_root/site/private/index.html" ]]; then
        printf 'can_read=yes\n'
    else
        printf 'can_read=no\n'
    fi
}

fix_access() {
    chmod u+x -- "$lab_root/site/private"
}

case "$operation" in
    setup)
        [[ -z "$(find "$lab_root" -mindepth 1 -maxdepth 1 -print -quit)" ]] || { printf 'Setup requires an empty workspace.\n' >&2; exit 2; }
        mkdir -m 0700 -- "$lab_root/site" "$lab_root/site/private"
        printf 'owned lab page\n' > "$lab_root/site/private/index.html"
        chmod 0640 -- "$lab_root/site/private/index.html"
        printf 'permissions-v1:%s\n' "$(id -u)" > "$marker"
        chmod 0600 -- "$lab_root/site/private"
        inspect_access
        ;;
    inspect) check_layout; inspect_access ;;
    fix) check_layout; fix_access; inspect_access ;;
    verify)
        check_layout
        [[ -r "$lab_root/site/private/index.html" ]] || { printf 'Ancestor traversal is still blocked.\n' >&2; exit 1; }
        [[ "$(stat -c %a -- "$lab_root/site/private")" == 700 ]] || { printf 'Restore only owner traversal.\n' >&2; exit 1; }
        [[ "$(stat -c %a -- "$lab_root/site/private/index.html")" == 640 ]] || { printf 'File permissions changed unnecessarily.\n' >&2; exit 1; }
        printf 'verified owner traversal and unchanged file mode\n'
        ;;
    *) printf 'Unknown operation.\n' >&2; exit 2 ;;
esac
