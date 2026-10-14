#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { printf 'This deployment lab requires Linux.\n' >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || { printf 'Usage: bash deploy_static_site.sh SITE_ROOT [OWNER:GROUP]\n' >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
site_root="$1"
site_owner="${2:-}"
[[ ! -L "$site_root" ]] || { printf 'The document root cannot be a symlink.\n' >&2; exit 2; }
mkdir -p -- "$site_root"
site_root="$(cd -- "$site_root" && pwd -P)"
temporary="$(mktemp "$site_root/.index-pending-XXXXXX")"
trap 'rm -f -- "$temporary"' EXIT
install_page() {
    install -m 0644 -- "$1" "$2"
}
install_page "$SCRIPT_DIR/index.html" "$temporary"
# Ownership failure is fatal and occurs before replacing an earlier page.
if [[ -n "$site_owner" ]]; then
    chown -- "$site_owner" "$temporary"
    chown -- "$site_owner" "$site_root"
fi
chmod 0755 -- "$site_root"
mv -f -- "$temporary" "$site_root/index.html"
printf 'Published %s/index.html\n' "$site_root"
stat -c 'mode=%a uid=%u gid=%g path=%n' -- "$site_root" "$site_root/index.html"
printf 'Set the Nginx root to that exact path, validate configuration, then request the lab listener at http://127.0.0.1:8080/.\n'
