#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
    printf 'Use --version.\n' >&2
    exit 64
fi
if [ "$1" != --version ]; then
    printf 'Use --version.\n' >&2
    exit 64
fi
printf '%s\n' 'lab-tool second 2.0'
