#!/usr/bin/env bash
set -euo pipefail

#################
#   CONSTANTS   #
#################
readonly DEFAULT_SOURCE_DIR="$HOME/linux-systems-lab"
readonly DEFAULT_DEST_DIR="$HOME/backups"
readonly DEFAULT_RETENTION_COUNT="5"
readonly TIMESTAMP_FORMAT="+%Y%m%d-%H%M%S"
readonly ARCHIVE_PREFIX="linux-systems-backup"
readonly ARCHIVE_SUFFIX=".tar.gz"

#################
#   MAIN CODE   #
#################
# Read optional backup settings from arguments and the environment
source_dir="${1:-$DEFAULT_SOURCE_DIR}"
dest_dir="${2:-$DEFAULT_DEST_DIR}"
retention_count="${RETENTION_COUNT:-$DEFAULT_RETENTION_COUNT}"

# Create the destination directory before writing the archive
mkdir -p "$dest_dir"

# Build the archive name from a sortable timestamp
timestamp="$(date "$TIMESTAMP_FORMAT")"
archive_name="${ARCHIVE_PREFIX}-${timestamp}${ARCHIVE_SUFFIX}"

# Create the compressed backup archive
tar -czf "$dest_dir/$archive_name" "$source_dir"

# Remove older archives beyond the retention window
find "$dest_dir" -maxdepth 1 -type f -name "${ARCHIVE_PREFIX}-*${ARCHIVE_SUFFIX}" \
	| sort \
	| head -n "-${retention_count}" 2>/dev/null \
	| xargs -r rm -f

# Report the archive that was created
echo "Created $dest_dir/$archive_name"
