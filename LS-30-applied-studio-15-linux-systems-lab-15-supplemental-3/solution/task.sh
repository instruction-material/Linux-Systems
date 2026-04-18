#!/usr/bin/env bash
set -euo pipefail

error_count=$(grep -c "ERROR" sample.log || true)
warning_count=$(grep -c "WARNING" sample.log || true)
printf 'errors=%s warnings=%s\n' "$error_count" "$warning_count"
