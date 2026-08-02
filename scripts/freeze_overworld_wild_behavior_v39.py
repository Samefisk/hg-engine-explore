#!/usr/bin/env python3
"""Explicitly refresh the immutable v39 migration oracle.

Normal v40 generation and verification never import the live exporter.  This
command is intentionally separate so changing the frozen contract is a visible
review action.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "OverworldWildBehaviorV39.frozen.json.gz"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp_name:
        raw_path = Path(tmp_name) / "golden.json"
        subprocess.run([
            "python3", str(ROOT / "scripts" / "export_overworld_behavior_golden.py"),
            "--compact", "--output", str(raw_path),
        ], cwd=ROOT, check=True)
        artifact = json.loads(raw_path.read_text())
    if artifact["counts"]["contexts"] != 22272:
        raise SystemExit("refusing to freeze an incomplete production oracle")
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    canonical_hash = hashlib.sha256(canonical).hexdigest()
    manifest = json.loads((ROOT / "data" / "OverworldWildBehaviorV39.frozen.manifest.json").read_text())
    if args.output == DEFAULT_OUTPUT and canonical_hash != manifest["canonicalSha256"]:
        raise SystemExit("refusing to overwrite the pinned oracle; review the manifest and loader pin explicitly")
    args.output.write_bytes(gzip.compress(canonical, compresslevel=9, mtime=0))
    print(f"froze {args.output}: {len(canonical)} raw bytes, sha256={canonical_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
