#!/bin/sh
set -eu
[ "$#" -eq 1 ] && [ "$1" = --version ] || { printf 'Use --version.\n' >&2; exit 64; }
printf '%s\n' 'lab-tool second 2.0'
