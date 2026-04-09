#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-$HOME/linux-systems-lab}"
DEST_DIR="${2:-$HOME/backups}"

mkdir -p "$DEST_DIR"

archive_name="linux-systems-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$DEST_DIR/$archive_name" "$SOURCE_DIR"

echo "Created $DEST_DIR/$archive_name"
