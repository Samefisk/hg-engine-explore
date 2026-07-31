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
  runtime_python=".venv/bin/python3"
  if [ ! -f "$runtime_python" ]; then
    echo "Missing host runtime Python: $runtime_python" >&2
    exit 1
  fi
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/dev/null \
    "$runtime_python" -S -B \
    scripts/pokemon_move_history_build_manifest.py \
    --bind-runtime build/pokemon_move_history_capture_build.json \
    --rom test.nds || exit $?
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/dev/null \
    "$runtime_python" -S -B \
    scripts/pokemon_move_history_build_manifest.py \
    --verify build/pokemon_move_history_capture_build.json \
    --rom test.nds --require-bound-runtime || exit $?
  ./scripts/copy-test-nds-to-delta.sh || exit $?
fi
exit "$build_status"

:WINDOWS

for /f "usebackq tokens=*" %%i in (`cd`) do docker run -it --rm --workdir /hg-engine --mount type=bind,source="%%i",destination=/hg-engine --mount type=volume,source=hg-engine-venv,destination=/tmp/hg-engine-venv --mount type=volume,source=hg-engine-pip-cache,destination=/tmp/pip-cache -e PIP_CACHE_DIR=/tmp/pip-cache hg-engine /usr/bin/env -i LC_ALL=C PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PIP_CACHE_DIR=/tmp/pip-cache PWD=/hg-engine /usr/bin/python3 scripts/verify_pokemon_move_history_capture.py --managed-build-clean
