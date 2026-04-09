#!/usr/bin/env bash
set -euo pipefail

SITE_ROOT="${1:-/srv/linux-systems-site}"
OWNER="${2:-www-data:www-data}"

mkdir -p "$SITE_ROOT"
install -m 0644 index.html "$SITE_ROOT/index.html"

if command -v chown >/dev/null 2>&1; then
	chown -R "$OWNER" "$SITE_ROOT" 2>/dev/null || true
fi

if command -v chmod >/dev/null 2>&1; then
	chmod 0755 "$SITE_ROOT"
	chmod 0644 "$SITE_ROOT/index.html"
fi

cat <<EOF
Copied static site to $SITE_ROOT
Suggested verification:
- sudo nginx -t
- sudo systemctl reload nginx
- curl -I http://127.0.0.1/
EOF
