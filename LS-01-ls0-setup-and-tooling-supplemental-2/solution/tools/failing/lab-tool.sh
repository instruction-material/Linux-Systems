#!/bin/sh
set -eu
[ "$#" -eq 1 ] && [ "$1" = --version ] || { printf 'Use --version.\n' >&2; exit 64; }
printf '%s\n' 'controlled version failure' >&2
exit 23
