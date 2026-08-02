#!/usr/bin/env python3
"""Authenticate and load the immutable v39 migration oracle."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "OverworldWildBehaviorV39.frozen.json.gz"
MANIFEST = ROOT / "data" / "OverworldWildBehaviorV39.frozen.manifest.json"
PINNED_MANIFEST_SHA256 = "66a076518e62e311fb9194a328be986e6e85a9ff653ea0b06cd32c2608b9151d"


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def load_frozen(path: Path = FROZEN):
    manifest_raw = MANIFEST.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != PINNED_MANIFEST_SHA256:
        raise ValueError("v39 frozen-oracle manifest is not the pinned reviewed manifest")
    manifest = json.loads(manifest_raw)
    raw = gzip.decompress(path.read_bytes())
    if hashlib.sha256(raw).hexdigest() != manifest["canonicalSha256"]:
        raise ValueError("v39 frozen oracle canonical hash mismatch")
    artifact = json.loads(raw)
    if canonical_bytes(artifact) != raw:
        raise ValueError("v39 frozen oracle is not canonical JSON")
    if artifact["sourceRevision"] != manifest["sourceRevision"]:
        raise ValueError("v39 frozen oracle source revision mismatch")
    artifact_sources = {item["path"]: item["sha256"] for item in artifact["sources"]}
    if artifact_sources != manifest["sources"]:
        raise ValueError("v39 frozen oracle source manifest mismatch")
    expected = manifest["counts"]
    actual = {
        "classAssignments": len(artifact["classRules"]),
        "contexts": len(artifact["contexts"]),
        "contextualFollowerProbes": len(artifact["contextualForcedProbes"]),
        "dormantForcedAsleepProbes": len(artifact["dormantContextProbes"]),
        "isolatedOverrideProbes": len(artifact["isolatedOverrideProbes"]),
        "orderedOverrides": len(artifact["overrides"]),
    }
    if actual != expected:
        raise ValueError(f"v39 frozen oracle domain mismatch: {actual}")
    return artifact


__all__ = ["FROZEN", "MANIFEST", "load_frozen"]
