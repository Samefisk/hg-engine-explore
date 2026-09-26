#!/usr/bin/env python3
"""Verify the exact-frame Walk profile schema and editor migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"
HEADER_PATH = ROOT / "include/overworld_wild_behavior_data.h"
DATA_PATH = ROOT / "data/OverworldWildBehaviorData.c"
V2_PROFILE_EDITOR_PATH = ROOT / "tools/overworld-viewer-v2/static/profiles.js"
WILD_SPAWNS_PATH = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


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
    viewer_source = VIEWER_PATH.read_text()
    v2_editor = V2_PROFILE_EDITOR_PATH.read_text()

    require(viewer.PROFILE_FIELDS[-1] == "planTurnSkidPath", "Turn-skid path planning is not stored separately")
    require("walkAccelerationStep" in viewer.PROFILE_FIELDS, "Walk acceleration amount is not stored separately")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN["chillSpeed"] == 1, "Walk time accepts zero")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["chillSpeed"] == 32, "Walk time does not accept 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["maxWalkSpeed"] == 32, "Fastest Walk time does not accept 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["chainRepositionSpeed"] == 32, "Reposition Walk time does not accept 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["walkStompTime"] == 32, "Stomp threshold does not accept 0/off or 1..32")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN["walkAccelerationStep"] == 0, "Acceleration amount does not accept none")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["walkAccelerationStep"] == 33, "Acceleration amount does not accept none, 1..32 frame removals, and /2")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN["walkTimeVariance"] == 0, "Walk variance cannot be disabled")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["walkTimeVariance"] == 32, "Walk variance does not accept 0..32 frames")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN["walkPauseVariance"] == 0, "Walk pause variance cannot be disabled")
    require(viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX["walkPauseVariance"] == 32, "Walk pause variance does not accept 0..32 frames")
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
        ["0"] * len(viewer.LEGACY_PROFILE_FIELDS),
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

    legacy_relative_deltas = [
        viewer.legacy_walk_speed_to_time(min(tier + 1, 4))
        - viewer.legacy_walk_speed_to_time(tier)
        for tier in range(1, 5)
    ]
    require(
        legacy_relative_deltas == [-8, -4, -2, 0],
        "legacy relative tiers unexpectedly have one exact frame delta",
    )
    for stored_raw in ("OW_WILD_BEHAVIOR_RELATIVE(+1)", "1"):
        try:
            parse_legacy_chill_speed_override(stored_raw, relative=True)
        except viewer.ParseError as error:
            require(
                "manual exact-frame value" in str(error),
                "legacy relative Walk rejection did not explain the required migration",
            )
        else:
            raise SystemExit("legacy relative Walk override was migrated approximately")
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
    for legacy_tier in range(1, 5):
        compound_profile_items = ["0"] * len(viewer.PROFILE_FIELDS_V71)
        compound_bound_items = ["0"] * len(viewer.PROFILE_FIELDS_V71)
        chill_speed_index = viewer.PROFILE_FIELDS_V71.index("chillSpeed")
        compound_profile_items[chill_speed_index] = "OW_WILD_BEHAVIOR_RELATIVE(+1)"
        compound_bound_items[chill_speed_index] = str(legacy_tier)
        field_mask = "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED"
        try:
            viewer.parse_behavior_override([
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
        except viewer.ParseError as error:
            require(
                "manual exact-frame value" in str(error),
                f"legacy compound tier {legacy_tier} did not fail closed",
            )
        else:
            raise SystemExit(
                f"legacy compound tier {legacy_tier} was migrated approximately"
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
    require(viewer.numeric(migrated["walkAccelerationStep"]) == 33, "legacy profile did not retain /2 acceleration")

    v72_items = ["0"] * len(viewer.PROFILE_FIELDS_V72)
    v72_items[viewer.PROFILE_FIELDS_V72.index("chillSpeed")] = "10"
    migrated_v72 = viewer.parse_profile(v72_items, {})
    require(viewer.numeric(migrated_v72["chillSpeed"]) == 10, "v72 exact Walk time was remigrated as a speed tier")
    require(viewer.numeric(migrated_v72["walkAccelerationStep"]) == 33, "v72 profile did not retain /2 acceleration")
    require(viewer.numeric(migrated_v72["walkTimeVariance"]) == 0, "v72 profile gained Walk variance")

    v73_items = ["0"] * len(viewer.PROFILE_FIELDS_V73)
    v73_items[viewer.PROFILE_FIELDS_V73.index("hopAllowNonCardinal")] = "2"
    migrated_v73 = viewer.parse_profile(v73_items, {})
    require(viewer.numeric(migrated_v73["hopAllowNonCardinal"]) == 2, "v73 direction mode changed")
    require(viewer.numeric(migrated_v73["walkTimeVariance"]) == 0, "v73 profile gained Walk variance")

    v74_items = ["0"] * len(viewer.PROFILE_FIELDS_V74)
    migrated_v74 = viewer.parse_profile(v74_items, {})
    require(viewer.numeric(migrated_v74["walkPauseVariance"]) == 0, "v74 profile gained Walk pause variance")

    v75_items = ["0"] * len(viewer.PROFILE_FIELDS_V75)
    v75_items[viewer.PROFILE_FIELDS_V75.index("tilesBeforeTurnSkid")] = "3"
    migrated_v75 = viewer.parse_profile(v75_items, {})
    require(viewer.numeric(migrated_v75["tilesBeforeTurnSkid"]) == 3, "v75 turn-skid buildup changed")
    require(viewer.numeric(migrated_v75["stopSkid"]) == 0, "v75 profile gained a stop skid")

    v76_items = ["0"] * len(viewer.PROFILE_FIELDS_V76)
    v76_items[viewer.PROFILE_FIELDS_V76.index("tilesBeforeTurnSkid")] = "3"
    v76_items[viewer.PROFILE_FIELDS_V76.index("stopSkid")] = "1"
    migrated_v76 = viewer.parse_profile(v76_items, {})
    require(viewer.numeric(migrated_v76["tilesBeforeTurnSkid"]) == 3, "v76 turn-skid buildup changed")
    require(viewer.numeric(migrated_v76["stopSkid"]) == 1, "v76 stop skid changed")
    require(viewer.numeric(migrated_v76["planTurnSkidPath"]) == 0, "v76 profile gained turn-skid path planning")

    data = viewer.build_data(include_routes=False, include_spawn_settings=False)
    acceleration_options = data["editOptions"]["walkAccelerationStep"]
    require(
        [option["raw"] for option in acceleration_options[:3]] == ["0", "33", "1"],
        "editor acceleration choices do not start with none, /2, then fixed steps",
    )
    require(
        [option["label"] for option in acceleration_options[:2]]
        == ["0 — None", "/2 — Old rule"],
        "editor acceleration choices do not label none and the old rule clearly",
    )
    require(
        acceleration_options[2]["label"] == "1 — Remove 1 frame",
        "editor acceleration choice makes 1 look like a negative stored value",
    )
    require(
        viewer.canonical_profile_change_raw(
            "walkAccelerationStep", "-1", {}, allow_relative=True
        ) == "1",
        "a typed -1 acceleration amount is not normalized to stored value 1",
    )
    base_classes = [profile for profile in data["classes"] if not profile.get("isOverrideProfile")]
    require(
        all(
            viewer.numeric(profile["editProfile"]["walkAccelerationStep"]) == 1
            for profile in base_classes
        ),
        "base profiles do not use the one-frame acceleration default",
    )
    require(
        all(
            viewer.numeric(profile["editProfile"]["walkTimeVariance"]) == 0
            for profile in base_classes
        ),
        "existing base profiles did not keep Walk variance disabled",
    )
    relative_override = next(
        override["behavior"]
        for override in data["variableOverrides"]
        if "SPECIES_MEWTWO" in (override.get("memberSymbols") or ())
    )
    require(
        relative_override["profile"]["chillSpeed"]["raw"] == "-8",
        "legacy relative speed override retained its old signed tier delta",
    )
    mewtwo = next(
        assignment
        for assignment in data["assignments"]
        if assignment["species"]["symbol"] == "SPECIES_MEWTWO"
    )
    require(
        viewer.numeric(mewtwo["profile"]["chillSpeed"]) == 8,
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
    changed_raws = dict(
        class_raws,
        hopAllowNonCardinal="OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY",
        walkAccelerationStep="3",
        walkTimeVariance="7",
        walkPauseVariance="8",
        tilesBeforeTurnSkid="3",
        planTurnSkidPath="OW_WILD_BEHAVIOR_BOOL_YES",
        stopSkid="OW_WILD_BEHAVIOR_BOOL_YES",
    )
    changed_serialized = viewer.format_profile_initializer(changed_raws, "")
    require(
        "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS("
        f"{changed_raws['chainRepositionAllowDiagonal']}, 7)"
        in changed_serialized,
        "editor serializer did not pack Reposition diagonal allowance and Walk variance independently",
    )
    require(
        "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_CARDINAL_OPTIONS("
        f"{changed_raws['chainRepositionAllowCardinal']}, 8)"
        in changed_serialized,
        "editor serializer did not pack Reposition cardinal allowance and Walk pause variance independently",
    )
    require(
        "OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(3, OW_WILD_BEHAVIOR_BOOL_YES, OW_WILD_BEHAVIOR_BOOL_YES)"
        in changed_serialized,
        "editor serializer did not pack all turn-skid options independently",
    )
    changed_reparsed = viewer.parse_profile(viewer.parse_initializer(changed_serialized), {})
    require(
        viewer.numeric(changed_reparsed["walkAccelerationStep"]) == 3,
        "editor serializer did not retain a chosen acceleration amount",
    )
    require(
        changed_reparsed["hopAllowNonCardinal"]["raw"]
        == "OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY"
        and viewer.numeric(changed_reparsed["walkTimeVariance"]) == 7,
        "packed Reposition options did not round-trip as independent values",
    )
    require(
        viewer.numeric(changed_reparsed["walkPauseVariance"]) == 8,
        "packed Walk pause variance did not round-trip independently",
    )
    require(
        viewer.numeric(changed_reparsed["tilesBeforeTurnSkid"]) == 3
        and changed_reparsed["planTurnSkidPath"]["raw"] == "OW_WILD_BEHAVIOR_BOOL_YES"
        and changed_reparsed["stopSkid"]["raw"] == "OW_WILD_BEHAVIOR_BOOL_YES",
        "packed turn-skid options did not round-trip independently",
    )
    require("OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 81" in header, "behavior blob version is not current")
    require("u8 walkStompTime;" in header, "profile ABI lacks separate stomp time")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_WALK_STOMP_TIME" in header, "stomp time cannot be overridden")
    require("u8 walkAccelerationStep;" in header, "profile ABI lacks acceleration amount")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_WALK_ACCELERATION_STEP" in header, "acceleration amount cannot be overridden")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_WALK_TIME_VARIANCE" in header, "Walk variance cannot be overridden")
    require("OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MAX 32" in header, "Walk variance bound differs")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE_VARIANCE" in header, "Walk pause variance cannot be overridden")
    require("OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MAX 32" in header, "Walk pause variance bound differs")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_STOP_SKID" in header, "stop skid cannot be overridden")
    require("OW_WILD_BEHAVIOR_STOPS_WITH_SKID" in header, "stop-skid accessor is missing")
    require("OW_WILD_BEHAVIOR_OVERRIDE3_PLAN_TURN_SKID_PATH" in header, "turn-skid path planning cannot be overridden")
    require("OW_WILD_BEHAVIOR_PLANS_TURN_SKID_PATH" in header, "turn-skid path-planning accessor is missing")
    require(
        "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS" in header,
        "packed Reposition options helper is missing",
    )
    require("OW_WILD_BEHAVIOR_NO_SLOWER_THAN" in header, "time-aware no-slower-than bound is missing")
    require("OW_WILD_BEHAVIOR_NO_FASTER_THAN" in header, "time-aware no-faster-than bound is missing")
    require("const CONDITIONAL_MOVEMENT_SPEED_MAX = 32;" in v2_editor, "V2 conditional Walk-time ranges stop before 32")
    require('walkStompTime: "walkStompTime"' in v2_editor, "V2 editor cannot edit the separate stomp time")
    require('walkAccelerationStep: "walkAccelerationStep"' in v2_editor, "V2 editor cannot edit the acceleration amount")
    require(
        'if (!isNumericProfileField(fieldKey)) {' in v2_editor
        and 'const showSuggestions = fieldKey !== "walkAccelerationStep";' in v2_editor,
        "V2 acceleration amount is still a fixed option list",
    )
    require(
        'fieldKey !== "walkAccelerationStep"\n          && (options.numberLimits'
        not in viewer_source,
        "legacy acceleration amount is still a fixed option list",
    )
    require('walkTimeVariance: "walkTimeVariance"' in v2_editor, "V2 editor cannot edit Walk variance")
    require('label: "Walk time variance"' in v2_editor, "V2 editor does not label Walk variance")
    require('walkPauseVariance: "walkPauseVariance"' in v2_editor, "V2 editor cannot edit Walk pause variance")
    require('label: "Pause variance"' in v2_editor, "V2 editor does not label Walk pause variance")
    require('stopSkid: "stopSkid"' in v2_editor, "V2 editor cannot edit stop skid")
    require('planTurnSkidPath: "planTurnSkidPath"' in v2_editor, "V2 editor cannot edit turn-skid path planning")
    require('"OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD": "Jump forward"' in v2_editor,
            "V2 editor does not offer Jump forward")
    require('"0 — None"' in v2_editor, "V2 editor does not offer no acceleration")
    require('"/2 — Old rule"' in v2_editor, "V2 editor does not offer the old acceleration rule")
    require("Stomp at speed" not in v2_editor, "V2 editor still stores stomp as a packed speed tier")
    require("no faster than" in v2_editor and "no slower than" in v2_editor, "V2 editor does not explain inverted Walk-time bounds")
    require(
        'operator.operand > 0 ? "slower" : "faster"' in v2_editor,
        "V2 editor does not explain signed Walk-time adjustments",
    )
    require(
        "& OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK"
        in WILD_SPAWNS_PATH.read_text(),
        "Walk pause variance bits can be mistaken for Reposition permission",
    )

    print("Overworld wild exact-frame Walk profile timing verification passed.")


if __name__ == "__main__":
    main()
