#!/usr/bin/env python3
"""Verify that normal Walk tile timing is profile data, not lifecycle policy."""

from __future__ import annotations

import re
import sys
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.verify_overworld_role_controller import function_bodies


def function_body(source: str, name: str) -> str:
    # Declarations and earlier calls are not the completion owner. The shared
    # C scanner also ignores braces in comments and string literals.
    body = function_bodies(source).get(name)
    if body is None:
        raise SystemExit(f"missing function: {name}")
    return body


def verify_walk_pause_routing(spawns: str) -> None:
    completion = function_body(
        spawns,
        "OverworldWildSpawns_HandleFinishedMovementCommand",
    )
    if "lane->walkPause" not in completion:
        raise SystemExit("Walk completion does not read the lane Walk pause")
    if completion.count("== OW_WILD_BEHAVIOR_LOCOMOTION_WANDER") < 2:
        raise SystemExit("Walk pause is not routed through both controller lanes")
    if completion.count("lane->walkPause") != 2:
        raise SystemExit("Each controller lane must use its resolved tile wait")
    if "slot == OW_WILD_FOLLOWER_SLOT" in completion:
        raise SystemExit("Follower Walk timing is still hard-coded in the engine")


def profile_slice(source: str, name: str) -> str:
    start = source.find(f"/* profile: {name} */")
    end = source.find("/* profile: ", start + 1)
    if start < 0:
        raise SystemExit(f"missing profile range: {name}")
    return source[start:] if end < 0 else source[start:end]


def main() -> int:
    header = (REPO / "include/overworld_wild_behavior_data.h").read_text()
    generated_schema = (
        REPO / "include/generated/overworld_behavior_schema.h"
    ).read_text()
    runtime = (
        REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    ).read_text()
    pause_resolver = (
        REPO / "src/overworld_walk_pause_variance.c"
    ).read_text()
    spawns = (
        REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    data = (REPO / "data/OverworldWildBehaviorData.c").read_text()
    catalog = json.loads(
        (REPO / "data/overworld_behavior_profiles.json").read_text()
    )
    backend = (REPO / "scripts/overworld_behavior_profile_viewer.py").read_text()
    viewer = (REPO / "tools/overworld-viewer-v2/static/profiles.js").read_text()
    validator = (REPO / "scripts/validate_overworld_wild_blobs.py").read_text()
    schema = json.loads(
        (REPO / "tools/overworld/behavior_schema.json").read_text()
    )

    for required in (
        "#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 79",
        "u8 walkPause;",
        "#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE (1u << 22)",
        "#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE_VARIANCE (1u << 27)",
        "OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE",
        "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_CARDINAL_OPTIONS",
        "OverworldWildBehaviorProfileDataSizeMustRemain72Bytes",
        "OverworldWildBehaviorOverrideProfileSizeMustRemain212Bytes",
    ):
        if required not in header:
            raise SystemExit(f"Walk pause schema is incomplete: {required}")

    verify_walk_pause_routing(spawns)
    if "OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE(" not in pause_resolver \
            or "OverworldMotion_ApplyWalkPauseVariance" not in pause_resolver:
        raise SystemExit("Walk pause variance is not resolved by its fixed helper")
    if "OverworldWildSpawns_ResolveWalkPause" not in runtime \
            or "intent.pauseFrames" not in runtime:
        raise SystemExit("Walk requests do not carry the resolved pause variance")

    pause_variance = next(
        (field for field in schema["fields"] if field["key"] == "walkPauseVariance"),
        None,
    )
    if pause_variance is None or any((
        pause_variance["id"] != 69,
        pause_variance["offset"] != 63,
        pause_variance.get("bitOffset") != 1,
        pause_variance.get("bitWidth") != 7,
        pause_variance["bounds"] != {"min": 0, "max": 32},
        pause_variance["introducedIn"] != 75,
    )):
        raise SystemExit("Walk pause variance does not use the compact v75 packed field")

    nervous = profile_slice(data, "Scavenger")
    for required in (
        "OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE",
        "OW_WILD_BEHAVIOR_OVERRIDE3_TILES_BEFORE_TURN_SKID",
    ):
        if required not in nervous:
            raise SystemExit(f"Scavenger Walk pause is incomplete: {required}")
    scavenger_fields = next(
        profile["fields"]
        for profile in catalog["profiles"]
        if profile["id"] == "nervous-scavenger"
    )
    if scavenger_fields["tiredProfile"]["value"] != "apply-nervous-scavenger":
        raise SystemExit("Scavenger does not retain its Tired lane")
    if "OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(3, 0, 0)" not in nervous \
            or not re.search(r"OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS\(3, 0, 0\),\s*0,\s*1,", nervous):
        raise SystemExit(
            "Scavenger does not retain its zero tile wait, three-tile skid buildup, and one-frame acceleration"
        )

    grazer_fields = next(
        profile["fields"]
        for profile in catalog["profiles"]
        if profile["id"] == "gentle-grazer"
    )
    if grazer_fields.get("walkPauseVariance") != {
        "operator": "replace",
        "value": 6,
    }:
        raise SystemExit("Gentle grazer does not use the authored Walk pause variance")
    if grazer_fields.get("walkPause") != {
        "operator": "replace",
        "value": 0,
    }:
        raise SystemExit("Gentle grazer Walk pause does not start at zero")

    follower = profile_slice(data, "Follower Pokemon")
    if "OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE" not in follower:
        raise SystemExit("Follower Pokemon does not preserve its zero Walk wait")

    for source, required in (
        (header, "OverworldWildBehaviorProfileDataSizeMustRemain72Bytes"),
        (generated_schema, "#define OW_BEHAVIOR_SCHEMA_FIELD_COUNT 72"),
        (backend, '"walkPause"'),
        (backend, '"walkPauseVariance"'),
        (viewer, "walkPause"),
        (viewer, "walkPauseVariance"),
        (validator, "OWBD_PROFILE_SIZE = 72"),
        (validator, "OWBD_OVERRIDE_PROFILE_SIZE = 212"),
    ):
        if required not in source:
            raise SystemExit(f"Walk pause consumer is missing: {required}")

    print("overworld Walk per-tile pause schema and lifecycle routing verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
