:; if [ -z 0 ]; then
  @echo off
  goto :WINDOWS
fi

docker run -it --rm \
  --workdir /hg-engine \
  --mount type=bind,source="$(pwd)",destination=/hg-engine \
  --mount type=volume,source=hg-engine-venv,destination=/tmp/hg-engine-venv \
  --mount type=volume,source=hg-engine-pip-cache,destination=/tmp/pip-cache \
  -e PIP_CACHE_DIR=/tmp/pip-cache \
  hg-engine /usr/bin/env -i LC_ALL=C PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PIP_CACHE_DIR=/tmp/pip-cache PWD=/hg-engine /usr/bin/python3 scripts/verify_pokemon_move_history_capture.py --managed-build-clean
build_status=$?
if [ "$build_status" -eq 0 ]; then
  runtime_python="$PWD/.venv/bin/python3"
  if [ ! -f "$runtime_python" ]; then
    echo "Missing host runtime Python: $runtime_python" >&2
    exit 1
  fi
  native_bootstrap_expected_sha256="8288d2522a1d9c4dc6f63f43dcdd09b81079c5b3c13f4e1517942c1e56158b9d"
  native_bootstrap_expected_cdhash="98782a6d415471aced75ef90b292b4b9a447c0ab"
  native_record=$(./scripts/build_summary_move_relearn_native_bootstrap.sh \
    "$native_bootstrap_expected_sha256" \
    "$native_bootstrap_expected_cdhash") || exit $?
  set -- $native_record
  if [ "$#" -ne 4 ]; then
    echo "Malformed native bootstrap build record" >&2
    exit 1
  fi
  native_bootstrap="$PWD/build/summary_move_relearn_native_bootstrap"
  native_bootstrap_sha256="$2"
  native_inventory_sha256="$3"
  native_bootstrap_cdhash="$4"
  if [ "$native_bootstrap_sha256" != "$native_bootstrap_expected_sha256" ] \
    || [ "$native_bootstrap_cdhash" != "$native_bootstrap_expected_cdhash" ]; then
    echo "Native bootstrap differs from external publication seal" >&2
    exit 1
  fi
  native_inventory="$PWD/scripts/summary_move_relearn_native_inventory.txt"
  authenticate_native_bootstrap() {
    actual_sha256=$(/usr/bin/shasum -a 256 "$native_bootstrap" | /usr/bin/awk '{print $1}') || return 1
    [ "$actual_sha256" = "$native_bootstrap_expected_sha256" ] || return 1
    /usr/bin/codesign --verify --strict "$native_bootstrap" || return 1
    signature=$(/usr/bin/codesign -d --verbose=4 "$native_bootstrap" 2>&1) || return 1
    actual_cdhash=$(printf '%s\n' "$signature" | /usr/bin/awk -F= '/^CDHash=/{print $2}')
    [ "$actual_cdhash" = "$native_bootstrap_expected_cdhash" ] || return 1
    printf '%s\n' "$signature" | /usr/bin/grep -q \
      'CodeDirectory .*flags=0x12b02(adhoc,hard,kill,restrict,library-validation,runtime)' || return 1
    entitlements=$(/usr/bin/codesign -d --entitlements - "$native_bootstrap" 2>/dev/null) || return 1
    [ -z "$entitlements" ] || return 1
    dependencies=$(/usr/bin/otool -L "$native_bootstrap") || return 1
    [ "$(printf '%s\n' "$dependencies" | /usr/bin/awk 'NR > 1 && NF {count++} END {print count+0}')" -eq 1 ] || return 1
    printf '%s\n' "$dependencies" | /usr/bin/grep -q \
      '^[[:space:]]*/usr/lib/libSystem\.B\.dylib ' || return 1
    ! /usr/bin/otool -l "$native_bootstrap" | /usr/bin/grep -q 'LC_UUID'
  }
  authenticate_native_bootstrap || exit $?
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C \
    "$native_bootstrap" \
    --inventory "$native_inventory" \
    --expected-inventory-sha256 "$native_inventory_sha256" \
    --expected-self-sha256 "$native_bootstrap_sha256" -- \
    "$runtime_python" -I -S -B -X pycache_prefix=/dev/null \
    "$PWD/scripts/pokemon_move_history_build_manifest.py" \
    --bind-runtime build/pokemon_move_history_capture_build.json \
    --rom test.nds || exit $?
  authenticate_native_bootstrap || exit $?
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C \
    "$native_bootstrap" \
    --inventory "$native_inventory" \
    --expected-inventory-sha256 "$native_inventory_sha256" \
    --expected-self-sha256 "$native_bootstrap_sha256" -- \
    "$runtime_python" -I -S -B -X pycache_prefix=/dev/null \
    "$PWD/scripts/pokemon_move_history_build_manifest.py" \
    --verify build/pokemon_move_history_capture_build.json \
    --rom test.nds --require-bound-runtime || exit $?
  ./scripts/copy-test-nds-to-delta.sh || exit $?
fi
exit "$build_status"

:WINDOWS

for /f "usebackq tokens=*" %%i in (`cd`) do docker run -it --rm --workdir /hg-engine --mount type=bind,source="%%i",destination=/hg-engine --mount type=volume,source=hg-engine-venv,destination=/tmp/hg-engine-venv --mount type=volume,source=hg-engine-pip-cache,destination=/tmp/pip-cache -e PIP_CACHE_DIR=/tmp/pip-cache hg-engine /usr/bin/env -i LC_ALL=C PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PIP_CACHE_DIR=/tmp/pip-cache PWD=/hg-engine /usr/bin/python3 scripts/verify_pokemon_move_history_capture.py --managed-build-clean
