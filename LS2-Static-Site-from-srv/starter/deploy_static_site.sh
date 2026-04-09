#!/usr/bin/env bash
set -euo pipefail

SITE_ROOT="${1:-/srv/linux-systems-site}"

mkdir -p "$SITE_ROOT"
cp index.html "$SITE_ROOT/index.html"

cat <<EOF
Copied static site to $SITE_ROOT
Next steps:
1. Review linux-systems.conf
2. Place it in your Nginx sites-available directory
3. Test with nginx -t before reloading
EOF
