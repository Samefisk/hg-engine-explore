:; if [ -z 0 ]; then
  @echo off
  goto :WINDOWS
fi

LC_ALL=C
LANG=C
export LC_ALL LANG

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
  native_bootstrap_expected_sha256="0dab24cea974aaca1dacf2968a9d4a974aed8a01c92d16cb705a3ae16fc62fea"
  native_bootstrap_expected_cdhash="28821e50a5fe44926752cf2630eeafe5a5d2ce5e"
  native_record=$(./scripts/build_summary_move_relearn_native_bootstrap.sh \
    "$native_bootstrap_expected_sha256" \
    "$native_bootstrap_expected_cdhash") || exit $?
  set -- $native_record
  if [ "$#" -ne 4 ]; then
    echo "Malformed native bootstrap build record" >&2
    exit 1
  fi
  native_bootstrap="$PWD/build/summary_move_relearn_native/summary_move_relearn_native_bootstrap"
  native_bootstrap_sha256="$2"
  native_inventory_sha256="$3"
  native_bootstrap_cdhash="$4"
  if [ "$native_bootstrap_sha256" != "$native_bootstrap_expected_sha256" ] \
    || [ "$native_bootstrap_cdhash" != "$native_bootstrap_expected_cdhash" ]; then
    echo "Native bootstrap differs from external publication seal" >&2
    exit 1
  fi
  native_inventory="$PWD/scripts/summary_move_relearn_native_inventory.txt"
  protected_spawn_source="$PWD/scripts/summary_move_relearn_protected_spawn.swift"
  protected_spawn_source_sha256="87a2891706046f4ebf074240428312e1b434229921be8ec1c1e6c2773c51d941"
  protected_spawn_swift_cdhash="100b213164b4fd6521129ccd725d35cb674cef15"
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
  protected_native_bootstrap() {
    separator=$(printf '\037') || return 1
    serialized_argv=
    for protected_argument in "$@"; do
      [ -n "$protected_argument" ] || return 1
      case "$protected_argument" in *"$separator"*) return 1;; esac
      if [ -z "$serialized_argv" ]; then
        serialized_argv=$protected_argument
      else
        serialized_argv="$serialized_argv$separator$protected_argument"
      fi
    done
    [ -n "$serialized_argv" ] || return 1
    [ -f "$protected_spawn_source" ] && [ ! -L "$protected_spawn_source" ] || return 1
    exec 9<"$protected_spawn_source" || return 1
    protected_source_with_sentinel=$(/bin/cat <&9; printf '.') || return 1
    exec 9<&-
    protected_source=${protected_source_with_sentinel%.}
    actual_source_sha256=$(printf '%s' "$protected_source" \
      | /usr/bin/shasum -a 256 | /usr/bin/awk '{print $1}') || return 1
    [ "$actual_source_sha256" = "$protected_spawn_source_sha256" ] || return 1
    /usr/bin/codesign --verify --strict \
      -R '=identifier "com.apple.dt.xcode_select.tool-shim" and anchor apple' \
      /usr/bin/swift || return 1
    swift_signature=$(/usr/bin/codesign -d --verbose=4 /usr/bin/swift 2>&1) \
      || return 1
    [ "$(printf '%s\n' "$swift_signature" \
      | /usr/bin/awk -F= '/^CDHash=/{print $2}')" \
      = "$protected_spawn_swift_cdhash" ] || return 1
    protected_child_environment="LC_ALL=C${separator}PATH=/usr/bin:/bin"
    if [ -n "${SUMMARY_MOVE_RELEARN_PROTECTED_SPAWNED_FIFO-}" ] \
      || [ -n "${SUMMARY_MOVE_RELEARN_PROTECTED_CONTINUE_FIFO-}" ]; then
      [ -n "${SUMMARY_MOVE_RELEARN_PROTECTED_SPAWNED_FIFO-}" ] \
        && [ -n "${SUMMARY_MOVE_RELEARN_PROTECTED_CONTINUE_FIFO-}" ] || return 1
      printf '%s' "$protected_source" | /usr/bin/env -i \
        PATH=/usr/bin:/bin LC_ALL=C \
        SMR_PROTECTED_ARGV="$serialized_argv" \
        SMR_PROTECTED_ENV="$protected_child_environment" \
        SMR_PROTECTED_EXPECTED_PATH="$native_bootstrap" \
        SMR_PROTECTED_EXPECTED_CDHASH="$native_bootstrap_expected_cdhash" \
        SMR_PROTECTED_EXPECTED_FLAGS=22012b01 \
        SMR_PROTECTED_SPAWNED_FIFO="$SUMMARY_MOVE_RELEARN_PROTECTED_SPAWNED_FIFO" \
        SMR_PROTECTED_CONTINUE_FIFO="$SUMMARY_MOVE_RELEARN_PROTECTED_CONTINUE_FIFO" \
        /usr/bin/swift -
    else
      printf '%s' "$protected_source" | /usr/bin/env -i \
        PATH=/usr/bin:/bin LC_ALL=C \
        SMR_PROTECTED_ARGV="$serialized_argv" \
        SMR_PROTECTED_ENV="$protected_child_environment" \
        SMR_PROTECTED_EXPECTED_PATH="$native_bootstrap" \
        SMR_PROTECTED_EXPECTED_CDHASH="$native_bootstrap_expected_cdhash" \
        SMR_PROTECTED_EXPECTED_FLAGS=22012b01 \
        /usr/bin/swift -
    fi
  }
  authenticate_native_bootstrap || exit $?
  if [ -n "${SUMMARY_MOVE_RELEARN_BIND_AUTHENTICATED_FIFO-}" ] \
    || [ -n "${SUMMARY_MOVE_RELEARN_BIND_CONTINUE_FIFO-}" ]; then
    [ -n "${SUMMARY_MOVE_RELEARN_BIND_AUTHENTICATED_FIFO-}" ] \
      && [ -n "${SUMMARY_MOVE_RELEARN_BIND_CONTINUE_FIFO-}" ] || exit 1
    [ -p "$SUMMARY_MOVE_RELEARN_BIND_AUTHENTICATED_FIFO" ] \
      && [ -p "$SUMMARY_MOVE_RELEARN_BIND_CONTINUE_FIFO" ] || exit 1
    printf 'AUTHENTICATED\n' >"$SUMMARY_MOVE_RELEARN_BIND_AUTHENTICATED_FIFO"
    IFS= read -r bind_continuation \
      <"$SUMMARY_MOVE_RELEARN_BIND_CONTINUE_FIFO"
    [ "$bind_continuation" = "CONTINUE" ] || exit 1
  fi
  protected_native_bootstrap \
    "$native_bootstrap" \
    --inventory "$native_inventory" \
    --expected-inventory-sha256 "$native_inventory_sha256" \
    --expected-self-sha256 "$native_bootstrap_sha256" -- \
    "$runtime_python" -I -S -B -X pycache_prefix=/dev/null \
    "$PWD/scripts/pokemon_move_history_build_manifest.py" \
    --bind-runtime build/pokemon_move_history_capture_build.json \
    --rom test.nds || exit $?
  authenticate_native_bootstrap || exit $?
  protected_native_bootstrap \
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
