#!/bin/bash

# Keyboard Maestro helper for starting the overworld behavior/encounter viewer.
# This intentionally follows the same defensive shell setup as km_codex_exec.sh:
# KM may run script text through a sparse non-interactive shell with a tiny PATH.

LOG_FILE="/tmp/km_overworld_viewer_debug.log"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [ -z "${BASH_VERSION:-}" ]; then
  echo "==== KM OVERWORLD VIEWER ENTRY $(date '+%Y-%m-%d %H:%M:%S %Z') via non-bash shell; re-execing with /bin/bash ====" >> "$LOG_FILE"
  exec /bin/bash "$0" "$@"
fi

set -euo pipefail

{
  echo "==== KM OVERWORLD VIEWER ENTRY $(date '+%Y-%m-%d %H:%M:%S %Z') ===="
  echo "script: $0"
  echo "pid: $$ ppid: $PPID"
  echo "user: $(id -un 2>/dev/null || echo '<unknown>')"
  echo "shell: ${SHELL:-<unset>}"
  echo "bash: ${BASH_VERSION:-<unset>}"
  echo "pwd: $(pwd)"
  echo "PATH: $PATH"
} >> "$LOG_FILE" 2>&1

trap 'status=$?; echo "[$(date "+%H:%M:%S")] Script exiting with status $status" >> "$LOG_FILE"' EXIT

REPO_DIR="/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync"
PYTHON_BIN="/Users/christofferandersen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
SERVER_SCRIPT="$REPO_DIR/scripts/overworld_behavior_profile_viewer.py"
HOST="127.0.0.1"
PORT="8765"
URL="http://${HOST}:${PORT}/"

# Set OPEN_PAGE=0, KMVAR_OPEN_PAGE=0, or KMVAR_OpenPage=0 in Keyboard Maestro
# if you only want to start the server.
OPEN_PAGE="${OPEN_PAGE:-${KMVAR_OPEN_PAGE:-${KMVAR_OpenPage:-1}}}"
LABEL="com.hgengine.overworld-viewer"
USER_ID="$(/usr/bin/id -u)"
DOMAIN="gui/$USER_ID"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/hg-engine"
OUT_LOG="$LOG_DIR/overworld-viewer.out.log"
ERR_LOG="$LOG_DIR/overworld-viewer.err.log"

log_debug() {
  echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"
}

fail() {
  echo "Error: $1"
  log_debug "ERROR: $1"
  exit 1
}

log_debug "Repo: $REPO_DIR"
log_debug "Python: $PYTHON_BIN"
log_debug "URL: $URL"

[[ -d "$REPO_DIR" ]] || fail "Repo directory not found: $REPO_DIR"
[[ -x "$PYTHON_BIN" ]] || fail "Python runtime not executable: $PYTHON_BIN"
[[ -f "$SERVER_SCRIPT" ]] || fail "Server script not found: $SERVER_SCRIPT"

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
  log_debug "Viewer already live."
  open_page
  exit 0
fi

if /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is in use, but $URL is not responding:"
  /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  log_debug "Port $PORT occupied by a non-responsive process."
  exit 1
fi

/bin/mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
log_debug "Writing LaunchAgent: $PLIST"

/bin/cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>WorkingDirectory</key>
  <string>$REPO_DIR</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$SERVER_SCRIPT</string>
    <string>--serve</string>
    <string>--host</string>
    <string>$HOST</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$OUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG</string>
</dict>
</plist>
PLIST

if /bin/launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  log_debug "Existing LaunchAgent found; booting out before reload."
  /bin/launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
fi

if ! /bin/launchctl bootstrap "$DOMAIN" "$PLIST"; then
  echo "Could not start the LaunchAgent:"
  /bin/launchctl print "$DOMAIN/$LABEL" 2>&1 || true
  echo
  echo "Error log:"
  /usr/bin/tail -40 "$ERR_LOG" 2>/dev/null || true
  log_debug "launchctl bootstrap failed. See $ERR_LOG"
  exit 1
fi

log_debug "LaunchAgent bootstrapped."
/bin/launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true

for _ in {1..30}; do
  if is_live; then
    echo "Started overworld viewer: $URL"
    log_debug "Viewer responded successfully."
    open_page
    exit 0
  fi
  sleep 0.5
done

echo "Started LaunchAgent, but the viewer did not respond within 15 seconds: $URL"
echo "Output log: $OUT_LOG"
echo "Error log: $ERR_LOG"
echo "Keyboard Maestro debug log: $LOG_FILE"
log_debug "Viewer did not respond in time."
exit 1
