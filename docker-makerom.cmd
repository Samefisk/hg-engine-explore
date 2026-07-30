:; if [ -z 0 ]; then
  @echo off
  goto :WINDOWS
fi

docker run -it --rm \
  --mount type=bind,source="$(pwd)",destination=/hg-engine \
  --mount type=volume,source=hg-engine-venv,destination=/tmp/hg-engine-venv \
  --mount type=volume,source=hg-engine-pip-cache,destination=/tmp/pip-cache \
  -e PIP_CACHE_DIR=/tmp/pip-cache \
  hg-engine /bin/bash -lc 'cd /hg-engine && python3 scripts/verify_pokemon_move_history_capture.py --pre-make && make -j$(nproc) VENV=/tmp/hg-engine-venv'
build_status=$?
if [ "$build_status" -eq 0 ]; then
  ./scripts/copy-test-nds-to-delta.sh || exit $?
fi
exit "$build_status"

:WINDOWS

for /f "usebackq tokens=*" %%i in (`cd`) do docker run -it --rm --mount type=bind,source="%%i",destination=/hg-engine --mount type=volume,source=hg-engine-venv,destination=/tmp/hg-engine-venv --mount type=volume,source=hg-engine-pip-cache,destination=/tmp/pip-cache -e PIP_CACHE_DIR=/tmp/pip-cache hg-engine /bin/bash -lc "cd /hg-engine && python3 scripts/verify_pokemon_move_history_capture.py --pre-make && make -j$(nproc) VENV=/tmp/hg-engine-venv"
