#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
command -v scdoc >/dev/null 2>&1 || {
    printf '%s\n' 'oud: scdoc is required to build man/oud.1' >&2
    exit 1
}
scdoc < "$project_dir/man/oud.1.scd" > "$project_dir/man/oud.1"
