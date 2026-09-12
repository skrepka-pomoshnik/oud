#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
"$script_dir/build_man.sh"
data_dir=${XDG_DATA_HOME:-${HOME:?HOME must be set}/.local/share}
target_dir="$data_dir/man/man1"
mkdir -p "$target_dir"
install -m 0644 "$project_dir/man/oud.1" "$target_dir/oud.1"
printf 'Installed %s\n' "$target_dir/oud.1"
