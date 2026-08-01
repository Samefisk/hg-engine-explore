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
  native_record=$(./scripts/build_summary_move_relearn_native_bootstrap.sh) || exit $?
  set -- $native_record
  if [ "$#" -ne 3 ]; then
    echo "Malformed native bootstrap build record" >&2
    exit 1
  fi
  native_bootstrap="$PWD/build/summary_move_relearn_native_bootstrap"
  native_bootstrap_sha256="$2"
  native_inventory_sha256="$3"
  native_inventory="$PWD/scripts/summary_move_relearn_native_inventory.txt"
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C \
    "$native_bootstrap" \
    --inventory "$native_inventory" \
    --expected-inventory-sha256 "$native_inventory_sha256" \
    --expected-self-sha256 "$native_bootstrap_sha256" -- \
    "$runtime_python" -I -S -B -X pycache_prefix=/dev/null \
    "$PWD/scripts/pokemon_move_history_build_manifest.py" \
    --bind-runtime build/pokemon_move_history_capture_build.json \
    --rom test.nds || exit $?
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
