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
cp -f "$source_rom" "$dest_dir/test.nds"
echo "Copied test.nds to $dest_dir/test.nds"
