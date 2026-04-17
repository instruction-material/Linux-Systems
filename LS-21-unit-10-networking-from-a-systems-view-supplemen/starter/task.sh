#!/usr/bin/env bash
set -euo pipefail

# TODO: summarize the log file more carefully.
grep -c "ERROR" sample.log
