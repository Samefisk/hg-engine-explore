#!/bin/sh
set -eu

# This digest is deliberately duplicated in the compiled bootstrap. The
# committed inventory is publication input; production builds verify it before
# launching any host Python process.
inventory_sha256="efc8c257eea170b742590c74f14e12cee34a816eab7828f655219d4159eafea1"
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
source_path="$repo_root/scripts/summary_move_relearn_native_bootstrap.c"
inventory_path="$repo_root/scripts/summary_move_relearn_native_inventory.txt"
output_path="$repo_root/build/summary_move_relearn_native_bootstrap"
temporary_path="$output_path.tmp.$$"
compiler="/usr/bin/xcrun"

case "$inventory_sha256" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]* ) ;;
    * ) echo "native bootstrap inventory pin is malformed" >&2; exit 1 ;;
esac
test "${#inventory_sha256}" -eq 64
test -f "$source_path"
test -f "$inventory_path"
test -x "$compiler"
mkdir -p "$repo_root/build"

cleanup() {
    if test -e "$temporary_path"; then
        unlink "$temporary_path"
    fi
}
trap cleanup EXIT HUP INT TERM

"$compiler" --sdk macosx clang \
    -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
    -Wl,-no_uuid \
    "-DSMR_EXPECTED_INVENTORY_SHA256=\"$inventory_sha256\"" \
    "$source_path" -o "$temporary_path"
/usr/bin/codesign --force --sign - --timestamp=none \
    --identifier com.samefisk.hgengine.summary-relearn-bootstrap \
    "$temporary_path"
/usr/bin/codesign --verify --strict "$temporary_path"

dependencies=$(/usr/bin/otool -L "$temporary_path")
dependency_count=$(printf '%s\n' "$dependencies" | /usr/bin/awk 'NR > 1 && NF {count++} END {print count+0}')
test "$dependency_count" -eq 1
printf '%s\n' "$dependencies" | /usr/bin/grep -q '^[[:space:]]*/usr/lib/libSystem\.B\.dylib '

/bin/mv -f "$temporary_path" "$output_path"
trap - EXIT HUP INT TERM
self_record=$("$output_path" --print-self-record)
self_size=$(printf '%s\n' "$self_record" | /usr/bin/awk -F '\t' '{print $2}')
self_sha256=$(printf '%s\n' "$self_record" | /usr/bin/awk -F '\t' '{print $3}')
test -n "$self_size"
test "${#self_sha256}" -eq 64
printf '%s\t%s\t%s\n' "$self_size" "$self_sha256" "$inventory_sha256"
