#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_rom="${1:-"$repo_root/test.nds"}"

if [[ ! -f "$source_rom" ]]; then
  echo "Delta sync skipped: ROM not found at $source_rom" >&2
  exit 1
fi

if [[ -n "${DELTA_NDS_SYNC_DIR:-}" ]]; then
  dest_dir="$DELTA_NDS_SYNC_DIR"
else
  icloud_root="$HOME/Library/Mobile Documents"
  candidates=(
    "$icloud_root/iCloud~com~rileytestut~Delta/Documents/Games"
    "$icloud_root/iCloud~com~rileytestut~Delta/Documents"
    "$icloud_root/com~apple~CloudDocs/Delta/Games"
    "$icloud_root/com~apple~CloudDocs/Delta/ROMs"
    "$icloud_root/com~apple~CloudDocs/Delta"
  )

  dest_dir=""
  for candidate in "${candidates[@]}"; do
    if [[ -d "$candidate" ]]; then
      dest_dir="$candidate"
      break
    fi
  done

  if [[ -z "$dest_dir" ]]; then
    dest_dir="$icloud_root/com~apple~CloudDocs/Delta/ROMs"
  fi
fi

mkdir -p "$dest_dir"

counter_file="$dest_dir/.test-nds-sync-counter"
last_number=0
if [[ -f "$counter_file" ]]; then
  last_number="$(tr -cd '0-9' < "$counter_file")"
  if [[ -z "$last_number" ]]; then
    last_number=0
  fi
fi
next_number=$((last_number + 1))

rm -f "$dest_dir/test.nds"
for old_rom in "$dest_dir"/test[0-9]*.nds; do
  if [[ -e "$old_rom" ]]; then
    rm -f "$old_rom"
  fi
done

dest_rom="$dest_dir/test${next_number}.nds"
cp -f "$source_rom" "$dest_rom"
printf '%s\n' "$next_number" > "$counter_file"
echo "Copied test.nds to $dest_rom"
