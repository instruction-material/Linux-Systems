#!/bin/bash
set -eu
arguments=("$@")
printf 'argument_count=%s\n' "${#arguments[@]}"
for (( index=0; index<${#arguments[@]}; index++ )); do
    printf 'argument[%s]=<%s>\n' "$index" "${arguments[index]}"
done
