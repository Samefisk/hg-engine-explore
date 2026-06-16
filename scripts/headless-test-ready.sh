#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rom="$repo_root/test.nds"
dsv=""
image="${DESMUME_HEADLESS_IMAGE:-hg-engine-desmume-headless}"
screenshot="$repo_root/documentation/verification_screenshots/headless_test_ready_latest.png"
keep_running=false
build_image=true

initial_wait="${DESMUME_INITIAL_WAIT:-0.0}"
title_hold="${DESMUME_TITLE_HOLD:-0.45}"
title_gap="${DESMUME_TITLE_GAP:-0.45}"
a_taps="${DESMUME_A_TAPS:-6}"
tap_hold="${DESMUME_TAP_HOLD:-0.16}"
tap_gap="${DESMUME_TAP_GAP:-0.25}"
load_wait="${DESMUME_LOAD_WAIT:-1.0}"

usage() {
  cat <<'USAGE'
Usage: scripts/headless-test-ready.sh [options]

Boot test.nds headlessly and reach the loaded test.dsv overworld state quickly.
For memory reads, key-only actions, and JSON assertions, use
scripts/headless-overworld-test.py instead.

Options:
  --rom PATH             ROM to boot. Default: test.nds
  --dsv PATH             DeSmuME battery save to load. Default search order:
                         ./test.dsv, macOS DeSmuME 0.9.13, macOS DeSmuME 0.9.12,
                         ./.headless_desmume/.config/desmume/test.dsv
  --screenshot PATH      Ready screenshot path. Default:
                         documentation/verification_screenshots/headless_test_ready_latest.png
  --no-screenshot        Skip the ready screenshot.
  --keep-running         Leave the headless emulator running after ready state.
  --image NAME           Docker image to use. Default: hg-engine-desmume-headless
  --no-build-image       Fail if the headless emulator image is missing.
  --initial-wait SEC     Wait after emulator window appears before A sequence. Default: 0.0
  --a-taps COUNT         DS A taps after the title-screen A press. Default: 6
  -h, --help             Show this help.

Timing can also be tuned with DESMUME_TITLE_HOLD, DESMUME_TITLE_GAP,
DESMUME_TAP_HOLD, DESMUME_TAP_GAP, and DESMUME_LOAD_WAIT.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rom)
      rom="$2"
      shift 2
      ;;
    --dsv)
      dsv="$2"
      shift 2
      ;;
    --screenshot)
      screenshot="$2"
      shift 2
      ;;
    --no-screenshot)
      screenshot=""
      shift
      ;;
    --keep-running)
      keep_running=true
      shift
      ;;
    --image)
      image="$2"
      shift 2
      ;;
    --no-build-image)
      build_image=false
      shift
      ;;
    --initial-wait)
      initial_wait="$2"
      shift 2
      ;;
    --a-taps)
      a_taps="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

abs_path() {
  local path="$1"
  if [[ "$path" != /* ]]; then
    path="$PWD/$path"
  fi

  local dir base
  dir="$(dirname "$path")"
  base="$(basename "$path")"
  (cd "$dir" && printf '%s/%s\n' "$PWD" "$base")
}

find_dsv() {
  if [[ -n "$dsv" ]]; then
    if [[ ! -f "$dsv" ]]; then
      echo "DSV not found: $dsv" >&2
      exit 1
    fi
    abs_path "$dsv"
    return
  fi

  local candidates=(
    "$repo_root/test.dsv"
    "$HOME/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv"
    "$HOME/Library/Application Support/DeSmuME/0.9.12/Battery/test.dsv"
    "$repo_root/.headless_desmume/.config/desmume/test.dsv"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      abs_path "$candidate"
      return
    fi
  done

  echo "No test.dsv found. Add ./test.dsv or pass --dsv PATH." >&2
  exit 1
}

if [[ ! -f "$rom" ]]; then
  echo "ROM not found: $rom" >&2
  exit 1
fi

rom_abs="$(abs_path "$rom")"
dsv_abs="$(find_dsv)"

headless_home="$repo_root/.headless_desmume"
headless_dsv="$headless_home/.config/desmume/test.dsv"
mkdir -p "$(dirname "$headless_dsv")"

if [[ "$(abs_path "$headless_dsv")" != "$dsv_abs" ]]; then
  cp -f "$dsv_abs" "$headless_dsv"
fi

if [[ "$rom_abs" == "$repo_root/"* ]]; then
  rom_container="/work/${rom_abs#"$repo_root/"}"
else
  mkdir -p "$headless_home/runtime"
  rom_copy="$headless_home/runtime/$(basename "$rom_abs")"
  cp -f "$rom_abs" "$rom_copy"
  rom_container="/work/.headless_desmume/runtime/$(basename "$rom_copy")"
fi

screenshot_container=""
if [[ -n "$screenshot" ]]; then
  if [[ "$screenshot" != /* ]]; then
    screenshot="$repo_root/$screenshot"
  fi
  mkdir -p "$(dirname "$screenshot")"
  screenshot_abs="$(abs_path "$screenshot")"

  if [[ "$screenshot_abs" == "$repo_root/"* ]]; then
    screenshot_container="/work/${screenshot_abs#"$repo_root/"}"
  else
    echo "Screenshot path must be inside the repository: $screenshot_abs" >&2
    exit 1
  fi
fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
  if [[ "$build_image" != true ]]; then
    echo "Docker image not found: $image" >&2
    exit 1
  fi

  echo "Building missing Docker image: $image" >&2
  docker build -t "$image" -f - "$repo_root" <<'DOCKERFILE'
FROM hg-engine:latest
USER root
RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    desmume \
    imagemagick \
    openbox \
    procps \
    x11-utils \
    xdotool \
    xvfb \
  && rm -rf /var/lib/apt/lists/*
DOCKERFILE
fi

docker run --rm --user "$(id -u):$(id -g)" \
  -v "$repo_root":/work -w /work \
  -e HOME=/work/.headless_desmume \
  -e SDL_AUDIODRIVER=dummy \
  -e ROM_PATH="$rom_container" \
  -e SCREENSHOT_PATH="$screenshot_container" \
  -e KEEP_RUNNING="$keep_running" \
  -e INITIAL_WAIT="$initial_wait" \
  -e TITLE_HOLD="$title_hold" \
  -e TITLE_GAP="$title_gap" \
  -e A_TAPS="$a_taps" \
  -e TAP_HOLD="$tap_hold" \
  -e TAP_GAP="$tap_gap" \
  -e LOAD_WAIT="$load_wait" \
  "$image" bash -lc '
set -euo pipefail

start_time="$SECONDS"
Xvfb :99 -screen 0 800x700x24 >/tmp/xvfb-test-ready.log 2>&1 &
xvfb_pid=$!

cleanup() {
  DISPLAY=:99 xdotool keyup x z Return Left Right Up Down 2>/dev/null || true
  if [[ -n "${emu_pid:-}" ]]; then kill "$emu_pid" 2>/dev/null || true; fi
  if [[ -n "${wm_pid:-}" ]]; then kill "$wm_pid" 2>/dev/null || true; fi
  kill "$xvfb_pid" 2>/dev/null || true
}
trap cleanup EXIT

export DISPLAY=:99
sleep 0.2
openbox >/tmp/openbox-test-ready.log 2>&1 &
wm_pid=$!
sleep 0.2

/usr/games/desmume-cli \
  --disable-sound \
  --disable-limiter \
  --load-type=1 \
  --nojoy=1 \
  "$ROM_PATH" >/tmp/desmume-test-ready.log 2>&1 &
emu_pid=$!

wid=""
for _ in $(seq 1 50); do
  wid="$(xdotool search --onlyvisible --name "Desmume" | head -n 1 || true)"
  [[ -n "$wid" ]] || wid="$(xdotool search --onlyvisible --name "DeSmuME" | head -n 1 || true)"
  [[ -n "$wid" ]] || wid="$(xdotool search --onlyvisible --class desmume | head -n 1 || true)"
  [[ -n "$wid" ]] && break
  sleep 0.08
done

if [[ -z "$wid" ]]; then
  echo "No visible DeSmuME window found" >&2
  tail -n 40 /tmp/desmume-test-ready.log >&2 || true
  exit 2
fi

focus_window() {
  xdotool windowfocus "$wid" 2>/dev/null || true
  sleep 0.04
}

press_a_for() {
  focus_window
  xdotool keydown --window "$wid" x
  sleep "$1"
  xdotool keyup --window "$wid" x
}

sleep "$INITIAL_WAIT"
press_a_for "$TITLE_HOLD"
sleep "$TITLE_GAP"

for _ in $(seq 1 "$A_TAPS"); do
  press_a_for "$TAP_HOLD"
  sleep "$TAP_GAP"
done

sleep "$LOAD_WAIT"

if [[ -n "$SCREENSHOT_PATH" ]]; then
  mkdir -p "$(dirname "$SCREENSHOT_PATH")"
  geom="$(xwininfo -id "$wid" \
    | awk "/Absolute upper-left X:/ {x=\$4} /Absolute upper-left Y:/ {y=\$4} /Width:/ {w=\$2} /Height:/ {h=\$2} END {printf \"%sx%s+%s+%s\", w, h, x, y}")"
  import -display :99 -window root /tmp/desmume-test-ready-root.png
  convert /tmp/desmume-test-ready-root.png -crop "$geom" +repage "$SCREENSHOT_PATH"
fi

elapsed=$((SECONDS - start_time))
echo "Ready: loaded test.dsv into overworld in ${elapsed}s"
if [[ -n "$SCREENSHOT_PATH" ]]; then
  echo "Screenshot: $SCREENSHOT_PATH"
fi

if [[ "$KEEP_RUNNING" == true ]]; then
  echo "Keeping headless emulator running. Press Ctrl-C to stop."
  wait "$emu_pid"
fi
'
