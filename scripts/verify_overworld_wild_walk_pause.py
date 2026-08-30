#!/usr/bin/env python3
"""Verify that normal Walk tile timing is profile data, not lifecycle policy."""

from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str) -> str:
    start = source.find(name)
    if start < 0:
        raise SystemExit(f"missing function: {name}")
    opening = source.find("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise SystemExit(f"unterminated function: {name}")


def profile_slice(source: str, name: str, next_name: str) -> str:
    start = source.find(f"/* profile: {name} */")
    end = source.find(f"/* profile: {next_name} */", start)
    if start < 0 or end < 0:
        raise SystemExit(f"missing profile range: {name}")
    return source[start:end]


def main() -> int:
    header = (REPO / "include/overworld_wild_behavior_data.h").read_text()
    runtime = (
        REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    ).read_text()
    spawns = (
        REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    data = (REPO / "data/OverworldWildBehaviorData.c").read_text()
    backend = (REPO / "scripts/overworld_behavior_profile_viewer.py").read_text()
    viewer = (REPO / "tools/overworld-viewer-v2/static/profiles.js").read_text()
    validator = (REPO / "scripts/validate_overworld_wild_blobs.py").read_text()

    for required in (
        "#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 71",
        "u8 walkPause;",
        "#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE (1u << 22)",
        "OverworldWildBehaviorProfileDataSizeMustRemain70Bytes",
        "OverworldWildBehaviorOverrideProfileSizeMustRemain212Bytes",
    ):
        if required not in header:
            raise SystemExit(f"Walk pause schema is incomplete: {required}")

    completion = function_body(
        spawns,
        "OverworldWildSpawns_HandleFinishedMovementCommand",
    )
    if "lane->walkPause" not in completion:
        raise SystemExit("Walk completion does not read the lane Walk pause")
    if completion.count("== OW_WILD_BEHAVIOR_LOCOMOTION_WANDER") < 3:
        raise SystemExit("Walk pause is not routed through all three lifecycle lanes")
    if completion.count("lane->walkPause") != 3:
        raise SystemExit("Each Walk lifecycle lane must use its resolved tile wait")
    if "slot == OW_WILD_FOLLOWER_SLOT" in completion:
        raise SystemExit("Follower Walk timing is still hard-coded in the engine")

    nervous = profile_slice(data, "Nervous scavenger", "Follower Pokemon")
    for required in (
        "OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE",
        "OW_WILD_BEHAVIOR_OVERRIDE3_TILES_BEFORE_TURN_SKID",
        "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_NERVOUS_SCAVENGER",
    ):
        if required not in nervous:
            raise SystemExit(f"Nervous scavenger Walk pause is incomplete: {required}")
    if not re.search(
        r"30,\s*60,\s*OW_WILD_BEHAVIOR_WALK_PAUSE_DEFAULT,\s*3,\s*\}",
        nervous,
    ):
        raise SystemExit(
            "Nervous scavenger does not use its normal tile wait and three-tile skid buildup"
        )

    for name, next_name in (
        ("Follower Pokemon", "Aggressive ram override"),
        ("Default Active", "Default Tired"),
    ):
        profile = profile_slice(data, name, next_name)
        if "OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE" not in profile:
            raise SystemExit(f"{name} does not preserve its zero Walk wait")

    for source, required in (
        (runtime, "OverworldWildRuntimeBehaviorProfileDataSizeMustRemain70"),
        (runtime, "OverworldWildRuntimeBehaviorRelativeFieldCountMustRemain66"),
        (backend, '"walkPause"'),
        (viewer, "walkPause"),
        (validator, "OWBD_PROFILE_SIZE = 70"),
        (validator, "OWBD_OVERRIDE_PROFILE_SIZE = 212"),
    ):
        if required not in source:
            raise SystemExit(f"Walk pause consumer is missing: {required}")

    print("overworld Walk per-tile pause schema and lifecycle routing verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
