#!/bin/bash

# Keyboard Maestro helper for starting the V2 overworld tools viewer.
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

trap 'exit_code=$?; echo "[$(date "+%H:%M:%S")] Script exiting with status $exit_code" >> "$LOG_FILE"' EXIT

REPO_DIR="/Users/christofferandersen/Documents/2. Projects/23. App Devolopment/hg-engine.nosync"
PYTHON_BIN="$REPO_DIR/.venv/bin/python3"
SERVER_SCRIPT="$REPO_DIR/tools/overworld-viewer-v2/server.py"
HOST="127.0.0.1"
PORT="8766"
URL="http://${HOST}:${PORT}/"
HEALTH_URL="${URL}api/v2/health"
NDS_OPEN_COMMAND="/usr/bin/open -b net.kuribo64.melonDS {rom}"

# Set OPEN_PAGE=0, KMVAR_OPEN_PAGE=0, or KMVAR_OpenPage=0 in Keyboard Maestro
# if you only want to start the server.
OPEN_PAGE="${OPEN_PAGE:-${KMVAR_OPEN_PAGE:-${KMVAR_OpenPage:-1}}}"
LABEL="com.hgengine.overworld-viewer"
USER_ID="$(/usr/bin/id -u)"
DOMAIN="gui/$USER_ID"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/hg-engine"
OUT_LOG="$LOG_DIR/overworld-viewer-v2.out.log"
ERR_LOG="$LOG_DIR/overworld-viewer-v2.err.log"

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

is_v2_live() {
  local payload
  payload="$(/usr/bin/curl --silent --fail --max-time 2 "$HEALTH_URL" 2>/dev/null)" || return 1
  V2_HEALTH_JSON="$payload" "$PYTHON_BIN" -c '
import json
import os

health = json.loads(os.environ["V2_HEALTH_JSON"])
valid = (
    health.get("ok") is True
    and health.get("service") == "overworld-viewer-v2"
    and health.get("apiVersion") == 2
)
raise SystemExit(0 if valid else 1)
' >/dev/null 2>&1
}

is_managed_v2() {
  local job_state managed_pid listener_pids
  job_state="$(/bin/launchctl print "$DOMAIN/$LABEL" 2>/dev/null)" || return 1
  [[ "$job_state" == *"program = $PYTHON_BIN"* ]] || return 1
  [[ "$job_state" == *"$SERVER_SCRIPT"* ]] || return 1
  [[ "$job_state" == *"--port"* ]] || return 1
  [[ "$job_state" == *"$PORT"* ]] || return 1

  managed_pid="$(printf '%s\n' "$job_state" | /usr/bin/sed -n 's/^[[:space:]]*pid = \([0-9][0-9]*\)$/\1/p' | /usr/bin/head -1)"
  [[ -n "$managed_pid" ]] || return 1
  listener_pids="$(/usr/sbin/lsof -t -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | /usr/bin/sort -u)"
  [[ "$listener_pids" == "$managed_pid" ]]
}

is_managed_v2_config_current() {
  local job_state
  job_state="$(/bin/launchctl print "$DOMAIN/$LABEL" 2>/dev/null)" || return 1
  [[ "$job_state" == *"NDS_OPEN_COMMAND => $NDS_OPEN_COMMAND"* ]]
}

open_page() {
  if [[ "$OPEN_PAGE" == "1" ]]; then
    /usr/bin/open "$URL" >/dev/null 2>&1 || true
  fi
}

MANAGED_V2=0
if is_managed_v2; then
  MANAGED_V2=1
  if is_v2_live; then
    if is_managed_v2_config_current; then
      echo "V2 overworld viewer is already running: $URL"
      log_debug "Managed V2 viewer already live."
      open_page
      exit 0
    fi
    log_debug "Managed V2 configuration changed; reloading its LaunchAgent."
  else
    log_debug "Managed V2 listener is unhealthy; reloading its LaunchAgent."
  fi
fi

if [[ "$MANAGED_V2" != "1" ]] && /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is occupied by a process that is not the managed V2 viewer:"
  /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  log_debug "Port $PORT occupied by an unmanaged or incorrect process; refusing to terminate it."
  exit 1
fi

/bin/mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
log_debug "Writing LaunchAgent: $PLIST"

# launchd does not rotate these files. Keep an unexpectedly large stale log from
# growing forever while preserving the most recent copy for diagnostics.
for log_path in "$OUT_LOG" "$ERR_LOG"; do
  if [[ -f "$log_path" ]] && [[ "$(/usr/bin/stat -f%z "$log_path" 2>/dev/null || echo 0)" -gt 5242880 ]]; then
    /bin/mv -f "$log_path" "$log_path.previous"
  fi
done

PLIST_TMP="${PLIST}.tmp.$$"
trap 'exit_code=$?; /bin/rm -f "${PLIST_TMP:-}"; echo "[$(date "+%H:%M:%S")] Script exiting with status $exit_code" >> "$LOG_FILE"' EXIT

/bin/cat > "$PLIST_TMP" <<PLIST
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
    <string>--host</string>
    <string>$HOST</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>NDS_OPEN_COMMAND</key>
    <string>$NDS_OPEN_COMMAND</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$OUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG</string>
</dict>
</plist>
PLIST

if ! /usr/bin/plutil -lint "$PLIST_TMP" >/dev/null; then
  fail "Generated LaunchAgent plist is invalid: $PLIST_TMP"
fi
/bin/mv -f "$PLIST_TMP" "$PLIST"

if /bin/launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  log_debug "Existing LaunchAgent found; booting out before reload."
  /bin/launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
  for _ in {1..40}; do
    if ! /bin/launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      break
    fi
    /bin/sleep 0.25
  done
  if /bin/launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    fail "Existing LaunchAgent did not finish unloading: $DOMAIN/$LABEL"
  fi
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
  if is_managed_v2 && is_v2_live; then
    echo "Started persistent V2 overworld viewer: $URL"
    log_debug "Managed V2 viewer responded successfully."
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
