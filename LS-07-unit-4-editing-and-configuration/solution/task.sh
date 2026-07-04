#!/usr/bin/env bash
set -euo pipefail

#################
#   CONSTANTS   #
#################
readonly SAMPLE_LOG_PATH="sample.log"
readonly ERROR_PATTERN="ERROR"
readonly WARNING_PATTERN="WARNING"
readonly SUMMARY_FORMAT="errors=%s warnings=%s\n"

#################
#   MAIN CODE   #
#################
# Count matching log entries while allowing grep to report zero matches
error_count=$(grep -c "$ERROR_PATTERN" "$SAMPLE_LOG_PATH" || true)
warning_count=$(grep -c "$WARNING_PATTERN" "$SAMPLE_LOG_PATH" || true)

# Print the compact log summary for the lab check
printf "$SUMMARY_FORMAT" "$error_count" "$warning_count"
