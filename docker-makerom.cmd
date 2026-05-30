:; if [ -z 0 ]; then
  @echo off
  goto :WINDOWS
fi

docker run -it --rm --mount type=bind,source="$(pwd)",destination=/hg-engine hg-engine /bin/bash -lc 'cd /hg-engine && make -j$(nproc) VENV=/tmp/hg-engine-venv'
build_status=$?
if [ "$build_status" -eq 0 ]; then
  ./scripts/copy-test-nds-to-delta.sh || exit $?
fi
exit "$build_status"

:WINDOWS

for /f "usebackq tokens=*" %%i in (`cd`) do docker run -it --rm --mount type=bind,source="%%i",destination=/hg-engine hg-engine /bin/bash -lc "cd /hg-engine && make -j$(nproc) VENV=/tmp/hg-engine-venv"
