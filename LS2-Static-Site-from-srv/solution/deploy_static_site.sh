#!/usr/bin/env bash
set -euo pipefail

#################
#   CONSTANTS   #
#################
readonly DEFAULT_SITE_ROOT="/srv/linux-systems-site"
readonly DEFAULT_OWNER="www-data:www-data"
readonly INDEX_FILE="index.html"
readonly SITE_DIR_MODE="0755"
readonly PAGE_FILE_MODE="0644"

#################
#   MAIN CODE   #
#################
# Read optional deployment settings from the command line
site_root="${1:-$DEFAULT_SITE_ROOT}"
site_owner="${2:-$DEFAULT_OWNER}"

# Create the destination directory and install the static homepage
mkdir -p "$site_root"
install -m "$PAGE_FILE_MODE" "$INDEX_FILE" "$site_root/$INDEX_FILE"

# Apply ownership when the host provides chown
if command -v chown >/dev/null 2>&1; then
	chown -R "$site_owner" "$site_root" 2>/dev/null || true
fi

# Apply permissions when the host provides chmod
if command -v chmod >/dev/null 2>&1; then
	chmod "$SITE_DIR_MODE" "$site_root"
	chmod "$PAGE_FILE_MODE" "$site_root/$INDEX_FILE"
fi

# Print follow-up checks the student can run after deployment
cat <<EOF
Copied static site to $site_root
Suggested verification:
- sudo nginx -t
- sudo systemctl reload nginx
- curl -I http://127.0.0.1/
EOF
