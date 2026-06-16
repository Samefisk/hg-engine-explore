#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync"
PYTHON_BIN="/Users/christofferandersen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
SERVER_SCRIPT="$REPO_DIR/scripts/overworld_behavior_profile_viewer.py"
HOST="127.0.0.1"
PORT="8765"
URL="http://${HOST}:${PORT}/"

# Set OPEN_PAGE=0 in Keyboard Maestro if you only want to start the server.
OPEN_PAGE="${OPEN_PAGE:-1}"

is_live() {
  /usr/bin/curl --silent --fail --max-time 2 "$URL" >/dev/null 2>&1
}

open_page() {
  if [[ "$OPEN_PAGE" == "1" ]]; then
    /usr/bin/open "$URL" >/dev/null 2>&1 || true
  fi
}

if is_live; then
  echo "Overworld viewer is already running: $URL"
  open_page
  exit 0
fi

if /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is in use, but $URL is not responding:"
  /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  exit 1
fi

quote() {
  printf "%q" "$1"
}

TERMINAL_COMMAND="cd $(quote "$REPO_DIR") && exec $(quote "$PYTHON_BIN") $(quote "$SERVER_SCRIPT") --serve --host $(quote "$HOST") --port $(quote "$PORT")"

/usr/bin/osascript - "$TERMINAL_COMMAND" <<'APPLESCRIPT'
on run argv
  tell application "Terminal"
    activate
    do script (item 1 of argv)
  end tell
end run
APPLESCRIPT

for _ in {1..30}; do
  if is_live; then
    echo "Started overworld viewer: $URL"
    open_page
    exit 0
  fi
  sleep 0.5
done

echo "Started Terminal command, but the viewer did not respond within 15 seconds: $URL"
exit 1
