#!/bin/sh
set -eu

LC_ALL=C
LANG=C
export LC_ALL LANG

# The caller owns the reviewed binary identity. Neither the candidate nor the
# published executable may supply either authority value itself.
if test "$#" -ne 2; then
    echo "usage: $0 EXPECTED-SHA256 EXPECTED-CDHASH" >&2
    exit 2
fi
expected_self_sha256=$1
expected_cdhash=$2
inventory_sha256="05928c73428c2876ec954aff477e74fb94b84c006f097d67f628596f7e181cda"
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
source_path="$repo_root/scripts/summary_move_relearn_native_bootstrap.c"
inventory_path="$repo_root/scripts/summary_move_relearn_native_inventory.txt"
output_path="$repo_root/build/summary_move_relearn_native_bootstrap"
temporary_path="$output_path.tmp.$$"
compiler="/usr/bin/xcrun"

case "$inventory_sha256" in
    *[!0-9a-f]* | "") echo "native bootstrap inventory pin is malformed" >&2; exit 1 ;;
esac
case "$expected_self_sha256" in
    *[!0-9a-f]* | "") echo "native bootstrap external SHA-256 pin is malformed" >&2; exit 1 ;;
esac
case "$expected_cdhash" in
    *[!0-9a-f]* | "") echo "native bootstrap external CDHash pin is malformed" >&2; exit 1 ;;
esac
test "${#inventory_sha256}" -eq 64
test "${#expected_self_sha256}" -eq 64
test "${#expected_cdhash}" -eq 40
test -f "$source_path"
test -f "$inventory_path"
test -x "$compiler"
mkdir -p "$repo_root/build"

cleanup() {
    if test -e "$temporary_path" || test -L "$temporary_path"; then
        unlink "$temporary_path"
    fi
}
trap cleanup EXIT HUP INT TERM

authenticate_binary() {
    candidate=$1
    label=$2
    test -f "$candidate"
    test ! -L "$candidate"
    actual_sha256=$(/usr/bin/shasum -a 256 "$candidate" | /usr/bin/awk '{print $1}')
    test "$actual_sha256" = "$expected_self_sha256" || {
        echo "native bootstrap $label SHA-256 differs" >&2
        return 1
    }
    /usr/bin/codesign --verify --strict "$candidate"
    signature=$(/usr/bin/codesign -d --verbose=4 "$candidate" 2>&1)
    printf '%s\n' "$signature" | /usr/bin/grep -q \
        'CodeDirectory .*flags=0x12b02(adhoc,hard,kill,restrict,library-validation,runtime)'
    printf '%s\n' "$signature" | /usr/bin/grep -q \
        '^Identifier=com.samefisk.hgengine.summary-relearn-bootstrap$'
    actual_cdhash=$(printf '%s\n' "$signature" | /usr/bin/awk -F= '/^CDHash=/{print $2}')
    test "$actual_cdhash" = "$expected_cdhash" || {
        echo "native bootstrap $label CDHash differs" >&2
        return 1
    }
    # No entitlement output is the exact empty entitlement set for this
    # deliberately entitlement-free ad-hoc signature. Any XML/DER-backed key
    # causes codesign to emit a plist and is rejected.
    entitlements=$(/usr/bin/codesign -d --entitlements - "$candidate" 2>/dev/null)
    test -z "$entitlements" || {
        echo "native bootstrap $label entitlement set is nonempty" >&2
        return 1
    }
    dependencies=$(/usr/bin/otool -L "$candidate")
    dependency_count=$(printf '%s\n' "$dependencies" | /usr/bin/awk \
        'NR > 1 && NF {count++} END {print count+0}')
    test "$dependency_count" -eq 1
    printf '%s\n' "$dependencies" | /usr/bin/grep -q \
        '^[[:space:]]*/usr/lib/libSystem\.B\.dylib '
    if /usr/bin/otool -l "$candidate" | /usr/bin/grep -q 'LC_UUID'; then
        echo "native bootstrap $label contains LC_UUID" >&2
        return 1
    fi
}

"$compiler" --sdk macosx clang \
    -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
    -Wl,-no_uuid \
    "-DSMR_EXPECTED_INVENTORY_SHA256=\"$inventory_sha256\"" \
    "$source_path" -o "$temporary_path"
/usr/bin/codesign --force --sign - --timestamp=none \
    --options runtime,restrict,library,hard,kill \
    --identifier com.samefisk.hgengine.summary-relearn-bootstrap \
    "$temporary_path"
authenticate_binary "$temporary_path" "temporary candidate"

/bin/mv -f "$temporary_path" "$output_path"

# Deterministic hostile tests may pause after atomic publication. The final
# authentication below is authoritative, so substitution can only fail the
# build and can never publish an attacker-reported identity.
published_fifo=${SUMMARY_MOVE_RELEARN_NATIVE_PUBLISHED_FIFO-}
continue_fifo=${SUMMARY_MOVE_RELEARN_NATIVE_CONTINUE_FIFO-}
if test -n "$published_fifo" || test -n "$continue_fifo"; then
    test -n "$published_fifo" && test -n "$continue_fifo"
    test "${published_fifo#/}" != "$published_fifo"
    test "${continue_fifo#/}" != "$continue_fifo"
    test -p "$published_fifo" && test -p "$continue_fifo"
    printf 'PUBLISHED\n' >"$published_fifo"
    IFS= read -r continuation <"$continue_fifo"
    test "$continuation" = "CONTINUE"
fi

authenticate_binary "$output_path" "published binary"
self_size=$(/usr/bin/stat -f '%z' "$output_path")
trap - EXIT HUP INT TERM
printf '%s\t%s\t%s\t%s\n' \
    "$self_size" "$expected_self_sha256" "$inventory_sha256" "$expected_cdhash"
