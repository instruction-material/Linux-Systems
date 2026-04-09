#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-$HOME/linux-systems-lab}"
DEST_DIR="${2:-$HOME/backups}"
RETENTION_COUNT="${RETENTION_COUNT:-5}"

mkdir -p "$DEST_DIR"

timestamp="$(date +%Y%m%d-%H%M%S)"
archive_name="linux-systems-backup-${timestamp}.tar.gz"
tar -czf "$DEST_DIR/$archive_name" "$SOURCE_DIR"

find "$DEST_DIR" -maxdepth 1 -type f -name 'linux-systems-backup-*.tar.gz' \
	| sort \
	| head -n "-${RETENTION_COUNT}" 2>/dev/null \
	| xargs -r rm -f

echo "Created $DEST_DIR/$archive_name"
