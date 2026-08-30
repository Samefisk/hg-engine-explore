#!/usr/bin/env python3
"""Verify the exact-frame Walk profile schema and editor migration."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"
HEADER_PATH = ROOT / "include/overworld_wild_behavior_data.h"
DATA_PATH = ROOT / "data/OverworldWildBehaviorData.c"
V2_PROFILE_EDITOR_PATH = ROOT / "tools/overworld-viewer-v2/static/profiles.js"


def load_viewer():
    spec = importlib.util.spec_from_file_location("overworld_behavior_profile_viewer", VIEWER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("could not load behavior profile editor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    viewer = load_viewer()
    header = HEADER_PATH.read_text()
    v2_editor = V2_PROFILE_EDITOR_PATH.read_text()

    require(viewer.PROFILE_FIELDS[-1] == "walkStompTime", "Walk stomp time is not stored separately")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN["chillSpeed"] == 1, "Walk time accepts zero")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["chillSpeed"] == 32, "Walk time does not accept 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["maxWalkSpeed"] == 32, "Fastest Walk time does not accept 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["chainRepositionSpeed"] == 32, "Reposition Walk time does not accept 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["walkStompTime"] == 32, "Stomp threshold does not accept 0/off or 1..32")
    require(
        viewer.canonical_profile_change_raw("chillSpeed", "10", {}) == "10",
        "Walk time is restricted to presets instead of accepting any value",
    )
    require(viewer.legacy_walk_speed_to_time(1) == 16, "legacy Walk tier 1 did not migrate to 16 frames")
    require(viewer.legacy_walk_speed_to_time(2) == 8, "legacy Walk tier 2 did not migrate to 8 frames")
    require(viewer.legacy_walk_speed_to_time(3) == 4, "legacy Walk tier 3 did not migrate to 4 frames")
    require(viewer.legacy_walk_speed_to_time(4) == 2, "legacy Walk tier 4 did not migrate to 2 frames")
    require(
        viewer.legacy_movement_speed_range_to_walk_time(2, 4) == (2, 8),
        "legacy speed range endpoints were not swapped when converted to Walk time",
    )
    require(
        viewer.legacy_movement_speed_range_to_walk_time(1, 3) == (4, 16),
        "legacy conditional speed range did not preserve its inclusive tier range",
    )
    legacy_wide_profile = viewer.parse_profile(
        ["0"] * (len(viewer.PROFILE_FIELDS) + 1),
        {},
    )
    require(
        viewer.numeric(legacy_wide_profile["maxWalkSpeed"]) == 2,
        "legacy profile without an authored max speed did not retain tier-4 timing",
    )

    def parse_legacy_chill_speed_override(
        stored_raw: str,
        *,
        relative: bool = False,
        at_least: bool = False,
        at_most: bool = False,
    ) -> dict:
        profile_items = ["0"] * len(viewer.PROFILE_FIELDS_V71)
        profile_items[viewer.PROFILE_FIELDS_V71.index("chillSpeed")] = stored_raw
        field_mask = "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED"
        return viewer.parse_behavior_override([
            field_mask,
            "0",
            "0",
            profile_items,
            field_mask if relative else "0",
            "0",
            "0",
            field_mask if at_least else "0",
            "0",
            "0",
            field_mask if at_most else "0",
            "0",
            "0",
        ], {})

    migrated_relative = parse_legacy_chill_speed_override(
        "OW_WILD_BEHAVIOR_RELATIVE(+1)",
        relative=True,
    )
    require(
        migrated_relative["profile"]["chillSpeed"]["raw"] == "-1",
        "legacy faster relative tier override did not become a faster frame delta",
    )
    migrated_numeric_relative = parse_legacy_chill_speed_override(
        "1",
        relative=True,
    )
    require(
        migrated_numeric_relative["profile"]["chillSpeed"]["raw"] == "-1",
        "legacy raw numeric relative tier was converted as an absolute Walk time",
    )
    migrated_at_least = parse_legacy_chill_speed_override(
        "OW_WILD_BEHAVIOR_AT_LEAST(2)",
        at_least=True,
    )
    require(
        migrated_at_least["profile"]["chillSpeed"]["raw"] == "/>8"
        and "chillSpeed" in migrated_at_least["atMostFields"]
        and "chillSpeed" not in migrated_at_least["atLeastFields"],
        "legacy minimum-speed bound did not become the inverse frame-time bound",
    )
    migrated_at_most = parse_legacy_chill_speed_override(
        "OW_WILD_BEHAVIOR_AT_MOST(2)",
        at_most=True,
    )
    require(
        migrated_at_most["profile"]["chillSpeed"]["raw"] == "/<8"
        and "chillSpeed" in migrated_at_most["atLeastFields"]
        and "chillSpeed" not in migrated_at_most["atMostFields"],
        "legacy maximum-speed bound did not become the inverse frame-time bound",
    )
    for legacy_tier, expected_time in ((1, 16), (2, 8), (3, 4), (4, 2)):
        compound_profile_items = ["0"] * len(viewer.PROFILE_FIELDS_V71)
        compound_bound_items = ["0"] * len(viewer.PROFILE_FIELDS_V71)
        chill_speed_index = viewer.PROFILE_FIELDS_V71.index("chillSpeed")
        compound_profile_items[chill_speed_index] = "OW_WILD_BEHAVIOR_RELATIVE(+1)"
        compound_bound_items[chill_speed_index] = str(legacy_tier)
        field_mask = "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED"
        migrated_compound = viewer.parse_behavior_override([
            field_mask,
            "0",
            "0",
            compound_profile_items,
            field_mask,
            "0",
            "0",
            field_mask,
            "0",
            "0",
            "0",
            "0",
            "0",
            compound_bound_items,
        ], {})
        require(
            migrated_compound["profile"]["chillSpeed"]["raw"]
                == f"-1, />{expected_time}"
            and "chillSpeed" in migrated_compound["atMostFields"],
            f"legacy compound tier {legacy_tier} was not converted exactly once",
        )

    legacy_items = ["0"] * len(viewer.PROFILE_FIELDS_V71)
    legacy_indexes = {field: index for index, field in enumerate(viewer.PROFILE_FIELDS_V71)}
    legacy_items[legacy_indexes["chillSpeed"]] = "1"
    legacy_items[legacy_indexes["maxWalkSpeed"]] = "OW_WILD_BEHAVIOR_MAX_WALK_SPEED_DEFAULT"
    legacy_items[legacy_indexes["chaseBoostSpeed"]] = "2"
    legacy_items[legacy_indexes["chainRepositionSpeed"]] = "3"
    legacy_items[legacy_indexes["walkOptions"]] = str(1 | (3 << 1) | (1 << 4))
    migrated = viewer.parse_profile(
        legacy_items,
        {"OW_WILD_BEHAVIOR_MAX_WALK_SPEED_DEFAULT": 2},
    )
    require(viewer.numeric(migrated["chillSpeed"]) == 16, "legacy base Walk tier did not migrate")
    require(viewer.numeric(migrated["maxWalkSpeed"]) == 2, "legacy fastest Walk default did not migrate")
    require(viewer.numeric(migrated["chaseBoostSpeed"]) == 8, "legacy chase Walk tier did not migrate")
    require(viewer.numeric(migrated["chainRepositionSpeed"]) == 4, "legacy reposition Walk tier did not migrate")
    require(viewer.numeric(migrated["walkOptions"]) == 17, "legacy stomp bits remained in Walk options")
    require(viewer.numeric(migrated["walkStompTime"]) == 4, "legacy stomp tier did not migrate to time")

    data = viewer.build_data(include_routes=False, include_spawn_settings=False)
    base_profile = copy.deepcopy(data["classes"][0]["profile"])
    relative_override = data["variableOverrides"][8]["behavior"]
    require(
        relative_override["profile"]["chillSpeed"]["raw"] == "-8",
        "legacy relative speed override retained its old signed tier delta",
    )
    viewer.merge_profile(base_profile, relative_override)
    require(
        viewer.numeric(base_profile["chillSpeed"]) == 8,
        "migrated relative Walk-time override does not resolve from 16 to 8 frames",
    )
    data_source = DATA_PATH.read_text()
    require(
        "OW_WILD_BEHAVIOR_RELATIVE(-8)" in data_source,
        "authored relative Walk-time storage does not show the migrated direct-time delta",
    )

    class_raws = viewer.raw_values(data["classes"][0]["profile"])
    serialized = viewer.format_profile_initializer(class_raws, "")
    reparsed = viewer.parse_profile(viewer.parse_initializer(serialized), {})
    require(
        viewer.raw_values(reparsed) == class_raws,
        "current exact-frame Walk profile did not round-trip through the editor serializer",
    )
    require("OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 72" in header, "behavior blob version was not advanced")
    require("u8 walkStompTime;" in header, "profile ABI lacks separate stomp time")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_WALK_STOMP_TIME" in header, "stomp time cannot be overridden")
    require("OW_WILD_BEHAVIOR_NO_SLOWER_THAN" in header, "time-aware no-slower-than bound is missing")
    require("OW_WILD_BEHAVIOR_NO_FASTER_THAN" in header, "time-aware no-faster-than bound is missing")
    require("const CONDITIONAL_MOVEMENT_SPEED_MAX = 32;" in v2_editor, "V2 conditional Walk-time ranges stop before 32")
    require('walkStompTime: "walkStompTime"' in v2_editor, "V2 editor cannot edit the separate stomp time")
    require("Stomp at speed" not in v2_editor, "V2 editor still stores stomp as a packed speed tier")
    require("no faster than" in v2_editor and "no slower than" in v2_editor, "V2 editor does not explain inverted Walk-time bounds")
    require(
        'operator.operand > 0 ? "slower" : "faster"' in v2_editor,
        "V2 editor does not explain signed Walk-time adjustments",
    )

    print("Overworld wild exact-frame Walk profile timing verification passed.")


if __name__ == "__main__":
    main()
