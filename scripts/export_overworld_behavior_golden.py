#!/usr/bin/env python3
"""Export a deterministic legacy overworld-behavior migration oracle.

The exporter deliberately delegates C parsing, matching, override composition,
normalization, primitive resolution, and stable source reads to the existing
profile viewer backend.  Its job is to canonicalize that source-backed model
into a compact artifact that a replacement state-profile resolver can produce
and compare against during migration.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LEGACY_VIEWER_SOURCE = ROOT / "scripts/overworld_behavior_profile_viewer.py"
V2_BACKEND_DIR = ROOT / "tools/overworld-viewer-v2"
ARTIFACT_SCHEMA = "hg-engine.overworld-behavior.legacy-golden"
ARTIFACT_SCHEMA_VERSION = 1


# Every legacy profile field is assigned to one migration concern.  Shared
# runtime fields are repeated in each one-state projection so every projection
# remains independently useful, but they have one authoritative classification
# here for coverage checks.
FIELD_CLASSIFICATION = {
    "CHILL": (
        "chillState",
        "chillSpeed",
        "chillAction",
        "chillTarget",
        "hopAllowNonCardinal",
        "hopMinDistance",
        "hopMaxDistance",
        "hopPause",
        "teleportTime",
        "teleportPause",
        "ramAccelerationSteps",
        "ramMaxSpeed",
        "chillAllowedTile",
        "chillAllowedTile2",
    ),
    "ACTIVE": (
        "attentiveState",
        "attentiveSpeed",
        "targetSelector",
        "movementStyle",
        "attentiveBattle",
        "attentiveAllowedTile",
        "attentiveAllowedTile2",
        "attentiveHopAllowNonCardinal",
        "attentiveHopMinDistance",
        "attentiveHopMaxDistance",
        "attentiveHopPause",
        "attentiveTeleportTime",
        "attentiveTeleportPause",
        "attentiveRamAccelerationSteps",
        "attentiveRamMaxSpeed",
        "attentiveChaseBoostDistance",
        "attentiveChaseBoostSpeed",
        "attentiveHopSpinSpeed",
        "attentiveCircleRadius",
        "attentiveContinueWhenArrived",
        "attentiveAvoidPreviousTile",
    ),
    "TIRED": (
        "tiredState",
        "tiredSpeed",
        "specialAction",
        "tiredAllowedTile",
        "tiredAllowedTile2",
        "tiredHopAllowNonCardinal",
        "tiredHopMinDistance",
        "tiredHopMaxDistance",
        "tiredHopPause",
        "tiredTeleportTime",
        "tiredTeleportPause",
        "tiredRamAccelerationSteps",
        "tiredRamMaxSpeed",
    ),
    "CHILL+TIRED": ("hopSpinSpeed",),
    "transition": (
        "alertState",
        "alertEmote",
        "alertTime",
        "alertness",
        "stamina",
        "restTime",
        "alertRange",
        "alertChance",
        "alertSpecialAction",
    ),
    "spawn": (
        "spawnState",
        "spawnDestination",
        "overworldLimit",
        "spawnDestinationMinDistance",
        "spawnDestinationMaxDistance",
        "spawnHopTime",
    ),
    "shared": (
        "range",
        "jumpLevel",
        "profileId",
        "playerAdjacentDirectionMasks",
        "chainPauseAction",
        "chainMovementVariance",
        "chainPauseVariance",
        "hopTime",
    ),
}

SHARED_STATE_FIELDS = {
    "range": "range",
    "jumpLevel": "jumpLevel",
    "playerAdjacentDirectionMasks": "playerAdjacentDirectionMasks",
    "hopTime": "hopTime",
    "chainPauseAction": "chainPauseAction",
    "chainMovementVariance": "chainMovementVariance",
    "chainPauseVariance": "chainPauseVariance",
}

STATE_FIELD_MAPS = {
    "CHILL": {
        "behaviorKind": "chillState",
        "speed": "chillSpeed",
        "configuredLocomotion": "chillAction",
        "configuredTarget": "chillTarget",
        "allowedTile": "chillAllowedTile",
        "allowedTile2": "chillAllowedTile2",
        "hopAllowNonCardinal": "hopAllowNonCardinal",
        "hopMinDistance": "hopMinDistance",
        "hopMaxDistance": "hopMaxDistance",
        "hopPause": "hopPause",
        "hopSpinSpeed": "hopSpinSpeed",
        "teleportTime": "teleportTime",
        "teleportPause": "teleportPause",
        "ramAccelerationSteps": "ramAccelerationSteps",
        "ramMaxSpeed": "ramMaxSpeed",
    },
    "ACTIVE": {
        "behaviorKind": "attentiveState",
        "speed": "attentiveSpeed",
        "configuredLocomotion": "movementStyle",
        "configuredTarget": "targetSelector",
        "battleTrigger": "attentiveBattle",
        "allowedTile": "attentiveAllowedTile",
        "allowedTile2": "attentiveAllowedTile2",
        "hopAllowNonCardinal": "attentiveHopAllowNonCardinal",
        "hopMinDistance": "attentiveHopMinDistance",
        "hopMaxDistance": "attentiveHopMaxDistance",
        "hopPause": "attentiveHopPause",
        "hopSpinSpeed": "attentiveHopSpinSpeed",
        "teleportTime": "attentiveTeleportTime",
        "teleportPause": "attentiveTeleportPause",
        "ramAccelerationSteps": "attentiveRamAccelerationSteps",
        "ramMaxSpeed": "attentiveRamMaxSpeed",
        "chaseBoostDistance": "attentiveChaseBoostDistance",
        "chaseBoostSpeed": "attentiveChaseBoostSpeed",
        "circleRadius": "attentiveCircleRadius",
        "continueWhenArrived": "attentiveContinueWhenArrived",
        "avoidPreviousTile": "attentiveAvoidPreviousTile",
    },
    "TIRED": {
        "behaviorKind": "tiredState",
        "speed": "tiredSpeed",
        "configuredLocomotion": "specialAction",
        "allowedTile": "tiredAllowedTile",
        "allowedTile2": "tiredAllowedTile2",
        "hopAllowNonCardinal": "tiredHopAllowNonCardinal",
        "hopMinDistance": "tiredHopMinDistance",
        "hopMaxDistance": "tiredHopMaxDistance",
        "hopPause": "tiredHopPause",
        "hopSpinSpeed": "hopSpinSpeed",
        "teleportTime": "tiredTeleportTime",
        "teleportPause": "tiredTeleportPause",
        "ramAccelerationSteps": "tiredRamAccelerationSteps",
        "ramMaxSpeed": "tiredRamMaxSpeed",
    },
}

STATE_PRIMITIVE_MAPS = {
    "CHILL": {
        "effectiveLocomotion": "chillLocomotion",
        "effectiveTarget": "chillTarget",
    },
    "ACTIVE": {
        "effectiveLocomotion": "attentiveLocomotion",
        "effectiveTarget": "attentiveTarget",
        "reaction": "activeReaction",
    },
    "TIRED": {
        "effectiveLocomotion": "tiredLocomotion",
        "effectiveTarget": "tiredTarget",
        "reaction": "tiredReaction",
    },
}

TRANSITION_FIELDS = {
    "alertMode": "alertState",
    "alertEmote": "alertEmote",
    "alertTime": "alertTime",
    "alertness": "alertness",
    "alertRange": "alertRange",
    "alertChance": "alertChance",
    "alertSpecialAction": "alertSpecialAction",
    "stamina": "stamina",
    "restTime": "restTime",
}

SPAWN_FIELDS = {
    "spawnState": "spawnState",
    "spawnDestination": "spawnDestination",
    "minimumDistance": "spawnDestinationMinDistance",
    "maximumDistance": "spawnDestinationMaxDistance",
    "spawnHopTime": "spawnHopTime",
    "overworldLimit": "overworldLimit",
}


@dataclass
class ParsedModel:
    macros: dict[str, int]
    terrain_values: dict[str, int]
    class_labels: dict[int, dict[str, Any]]
    group_labels: dict[int, dict[str, Any]]
    primitive_maps: dict[str, list[Any]]
    class_profiles: list[dict[str, dict[str, Any]]]
    class_rules: list[dict[str, Any]]
    overrides: list[dict[str, Any]]
    override_names: dict[int, str]
    group_species: dict[int, list[str]]
    species: list[dict[str, Any]]
    species_by_symbol: dict[str, dict[str, Any]]


def load_module(name: str, path: Path) -> ModuleType:
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Python backend: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def load_backends() -> tuple[ModuleType, ModuleType]:
    if str(V2_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(V2_BACKEND_DIR))
    legacy = load_module("_hg_engine_overworld_behavior_golden_legacy", LEGACY_VIEWER_SOURCE)
    reliability = load_module(
        "_hg_engine_overworld_behavior_golden_reliability",
        V2_BACKEND_DIR / "reliability.py",
    )
    return legacy, reliability


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_id(prefix: str, value: Any, length: int = 24) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"{prefix}:{digest[:length]}"


def atom(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "raw": value.get("raw", ""),
        "symbol": value.get("symbol"),
        "value": value.get("value"),
    }


def canonical_profile(
    profile: dict[str, dict[str, Any]], legacy: ModuleType
) -> dict[str, dict[str, Any] | None]:
    return {field: atom(profile[field]) for field in legacy.PROFILE_FIELDS}


def canonical_match(match: dict[str, dict[str, Any]], legacy: ModuleType) -> dict[str, Any]:
    return {field: atom(match[field]) for field in legacy.MATCH_FIELDS}


def canonical_change(change: dict[str, Any]) -> dict[str, Any]:
    result = {
        "field": change.get("field"),
        "before": atom(change.get("before")),
        "after": atom(change.get("after")),
    }
    for key in ("relative", "operator"):
        if key in change:
            result[key] = change[key]
    for key in ("delta", "operand"):
        if change.get(key) is not None:
            result[key] = atom(change[key])
    return result


def canonical_primitives(primitives: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {field: atom(value) for field, value in primitives.items()}


def project_state(
    role: str,
    profile: dict[str, dict[str, Any]],
    primitives: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fields = {
        key: atom(profile[source_field])
        for key, source_field in STATE_FIELD_MAPS[role].items()
    }
    fields.update(
        {
            key: atom(primitives.get(source_field))
            for key, source_field in STATE_PRIMITIVE_MAPS[role].items()
        }
    )
    return {
        "role": role,
        "fields": fields,
        "sharedRuntime": {
            key: atom(profile[source_field])
            for key, source_field in SHARED_STATE_FIELDS.items()
        },
        "legacyFieldSources": {
            **STATE_FIELD_MAPS[role],
            **{key: f"derived:{value}" for key, value in STATE_PRIMITIVE_MAPS[role].items()},
            **{f"sharedRuntime.{key}": value for key, value in SHARED_STATE_FIELDS.items()},
        },
    }


def effective_profile_record(
    profile: dict[str, dict[str, Any]],
    primitive_maps: dict[str, list[Any]],
    macros: dict[str, int],
    legacy: ModuleType,
) -> dict[str, Any]:
    primitives = legacy.resolve_primitives(profile, primitive_maps, macros)
    return {
        "legacyProfile": canonical_profile(profile, legacy),
        "states": {
            role: project_state(role, profile, primitives)
            for role in ("CHILL", "ACTIVE", "TIRED")
        },
        "transition": {
            key: atom(profile[source_field])
            for key, source_field in TRANSITION_FIELDS.items()
        },
        "spawn": {
            key: atom(profile[source_field])
            for key, source_field in SPAWN_FIELDS.items()
        },
        "identity": {"profileId": atom(profile["profileId"])},
        "effectivePrimitives": canonical_primitives(primitives),
    }


def parse_model(legacy: ModuleType) -> ParsedModel:
    source = legacy.strip_c_comments(
        legacy.join_line_continuations(legacy.OVERLAY_SOURCE.read_text())
    )
    raw_behavior_data = legacy.BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = legacy.strip_c_comments(
        legacy.join_line_continuations(raw_behavior_data)
    )
    expressions, species_order = legacy.parse_define_expressions(
        legacy.DEFINE_SOURCE_FILES
    )
    macros = legacy.evaluate_defines(expressions)
    macros.update(
        legacy.evaluate_armips_equ([legacy.ARMIPS_CONFIG, legacy.ARMIPS_CONSTANTS])
    )
    terrain_values, destination_values = legacy.parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)

    class_labels = legacy.invert_labels(macros, legacy.CLASS_PREFIX)
    group_labels = legacy.invert_labels(macros, legacy.GROUP_PREFIX)
    class_profiles = [
        legacy.parse_profile(entry, macros)
        for entry in legacy.parse_initializer(
            legacy.extract_braced_initializer(
                behavior_source, "sOverworldWildBehaviorClassProfiles"
            )
        )
    ]
    class_rules = legacy.parse_behavior_class_rules(
        behavior_source, macros, group_labels, class_labels
    )
    overrides = legacy.parse_behavior_overrides(
        behavior_source, macros, group_labels
    )
    override_names = legacy.parse_override_profile_names(raw_behavior_data)
    legacy.validate_override_profile_groups(overrides, override_names)

    group_species = legacy.parse_group_species(source, macros)
    species = legacy.parse_species(expressions, macros, species_order)
    legacy.apply_species_type_metadata(
        species, legacy.parse_species_type_metadata(macros)
    )
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    return ParsedModel(
        macros=macros,
        terrain_values=terrain_values,
        class_labels=class_labels,
        group_labels=group_labels,
        primitive_maps=legacy.parse_primitive_maps(source, macros),
        class_profiles=class_profiles,
        class_rules=class_rules,
        overrides=overrides,
        override_names=override_names,
        group_species=group_species,
        species=species,
        species_by_symbol=species_by_symbol,
    )


def validate_field_classification(legacy: ModuleType) -> list[str]:
    classified = [
        field for fields in FIELD_CLASSIFICATION.values() for field in fields
    ]
    missing = sorted(set(legacy.PROFILE_FIELDS) - set(classified))
    extra = sorted(set(classified) - set(legacy.PROFILE_FIELDS))
    duplicates = sorted(
        field for field in set(classified) if classified.count(field) > 1
    )
    if missing or extra or duplicates:
        raise RuntimeError(
            "legacy profile field classification drifted: "
            f"missing={missing}, extra={extra}, duplicates={duplicates}"
        )
    if SHARED_STATE_FIELDS.get("hopTime") != "hopTime":
        raise RuntimeError("hopTime is not classified as shared by every state")
    if FIELD_CLASSIFICATION.get("CHILL+TIRED") != ("hopSpinSpeed",):
        raise RuntimeError("hopSpinSpeed is not classified as CHILL+TIRED shared state")
    if (
        STATE_FIELD_MAPS["CHILL"].get("hopSpinSpeed") != "hopSpinSpeed"
        or STATE_FIELD_MAPS["TIRED"].get("hopSpinSpeed") != "hopSpinSpeed"
        or STATE_FIELD_MAPS["ACTIVE"].get("hopSpinSpeed")
        != "attentiveHopSpinSpeed"
    ):
        raise RuntimeError("state hop-spin field selection drifted")
    return [
        "all 72 legacy profile fields have one migration classification",
        "hopTime is shared by CHILL, ACTIVE, and TIRED",
        "hopSpinSpeed is shared by CHILL and TIRED; ACTIVE uses attentiveHopSpinSpeed",
    ]


def validate_named_groups(model: ParsedModel, legacy: ModuleType) -> list[str]:
    referenced: set[str] = set()
    for rule in [*model.class_rules, *model.overrides]:
        raw = str(rule.get("match", {}).get("groupMask", {}).get("raw", ""))
        referenced.update(
            symbol
            for symbol in re.findall(
                r"\bOW_WILD_BEHAVIOR_GROUP_[A-Z0-9_]+\b", raw
            )
            if symbol != "OW_WILD_BEHAVIOR_GROUP_NONE"
            and not symbol.startswith("OW_WILD_BEHAVIOR_GROUP_TYPE_")
        )
    empty = sorted(
        symbol
        for symbol in referenced
        if not model.group_species.get(model.macros.get(symbol, -1))
    )
    if empty:
        raise RuntimeError(
            "referenced named behavior groups have no parsed members: "
            + ", ".join(empty)
        )
    fixtures = (
        ("OW_WILD_BEHAVIOR_GROUP_BABY", "SPECIES_PICHU"),
        ("OW_WILD_BEHAVIOR_GROUP_GHOST", "SPECIES_GASTLY"),
    )
    for group_symbol, species_symbol in fixtures:
        group_value = model.macros.get(group_symbol)
        if (
            group_value is None
            or species_symbol not in model.species_by_symbol
            or species_symbol not in model.group_species.get(group_value, [])
        ):
            raise RuntimeError(
                f"group parser parity failed: {species_symbol} is not in {group_symbol}"
            )
    return [
        "referenced named groups are populated",
        "SPECIES_PICHU is in OW_WILD_BEHAVIOR_GROUP_BABY",
        "SPECIES_GASTLY is in OW_WILD_BEHAVIOR_GROUP_GHOST",
    ]


def validate_runtime_normalization(model: ParsedModel, legacy: ModuleType) -> list[str]:
    profile = legacy.clone_profile(model.class_profiles[0])

    def put_into(target: dict[str, dict[str, Any]], field: str, raw: str) -> None:
        target[field] = legacy.make_value(raw, field, model.macros)

    def put(field: str, raw: str) -> None:
        put_into(profile, field, raw)

    def focused_fixture(
        name: str,
        values: dict[str, str],
        expected_fields: list[str],
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        target = legacy.clone_profile(model.class_profiles[0])
        for field, raw in values.items():
            put_into(target, field, raw)
        fixture_changes = legacy.normalize_profile(target, model.macros)
        actual_fields = [change["field"] for change in fixture_changes]
        if actual_fields != expected_fields:
            raise RuntimeError(
                f"{name} normalization drifted: "
                f"expected {expected_fields}, got {actual_fields}"
            )
        return target, fixture_changes

    for field in (
        "chillState",
        "chillAction",
        "movementStyle",
        "specialAction",
        "alertSpecialAction",
        "overworldLimit",
        "attentiveChaseBoostDistance",
        "attentiveChaseBoostSpeed",
        "hopAllowNonCardinal",
        "ramAccelerationSteps",
        "chainMovementVariance",
        "chainPauseAction",
        "attentiveCircleRadius",
        "attentiveContinueWhenArrived",
        "attentiveAvoidPreviousTile",
        "chillTarget",
        "targetSelector",
        "attentiveState",
        "tiredState",
        "jumpLevel",
        "spawnState",
        "alertState",
        "alertRange",
        "spawnDestination",
        "attentiveBattle",
    ):
        put(field, "255")
    put("alertEmote", "14")
    put("hopMinDistance", "8")
    put("hopMaxDistance", "1")
    put("spawnDestinationMinDistance", "0")
    put("spawnDestinationMaxDistance", "255")
    for field, value in (
        ("attentiveHopAllowNonCardinal", "255"),
        ("attentiveHopMinDistance", "8"),
        ("attentiveHopMaxDistance", "1"),
        ("tiredHopAllowNonCardinal", "255"),
        ("tiredHopMinDistance", "8"),
        ("tiredHopMaxDistance", "1"),
    ):
        put(field, value)

    changes = legacy.normalize_profile(profile, model.macros)
    expected_order = [
        "chillState",
        "chillAction",
        "movementStyle",
        "specialAction",
        "alertSpecialAction",
        "overworldLimit",
        "attentiveChaseBoostDistance",
        "attentiveChaseBoostSpeed",
        "hopAllowNonCardinal",
        "hopMaxDistance",
        "ramAccelerationSteps",
        "chainMovementVariance",
        "chainPauseAction",
        "attentiveCircleRadius",
        "attentiveContinueWhenArrived",
        "attentiveAvoidPreviousTile",
        "chillTarget",
        "targetSelector",
        "attentiveState",
        "tiredState",
        "jumpLevel",
        "spawnState",
        "alertState",
        "alertEmote",
        "alertRange",
        "spawnDestination",
        "spawnDestinationMinDistance",
        "spawnDestinationMaxDistance",
        "attentiveBattle",
    ]
    actual_order = [change["field"] for change in changes]
    if actual_order != expected_order:
        raise RuntimeError(
            "runtime normalization order drifted: "
            f"expected {expected_order}, got {actual_order}"
        )
    preserved = {
        field: legacy.numeric(profile[field])
        for field in (
            "attentiveHopAllowNonCardinal",
            "attentiveHopMinDistance",
            "attentiveHopMaxDistance",
            "tiredHopAllowNonCardinal",
            "tiredHopMinDistance",
            "tiredHopMaxDistance",
        )
    }
    if preserved != {
        "attentiveHopAllowNonCardinal": 255,
        "attentiveHopMinDistance": 8,
        "attentiveHopMaxDistance": 1,
        "tiredHopAllowNonCardinal": 255,
        "tiredHopMinDistance": 8,
        "tiredHopMaxDistance": 1,
    }:
        raise RuntimeError(f"runtime-only hop fields were unexpectedly normalized: {preserved}")
    yes = model.macros.get("OW_WILD_BEHAVIOR_BOOL_YES", 1)
    if any(
        legacy.numeric(profile[field]) != yes
        for field in (
            "hopAllowNonCardinal",
            "attentiveContinueWhenArrived",
            "attentiveAvoidPreviousTile",
        )
    ):
        raise RuntimeError("runtime boolean clamp parity failed")

    asleep = model.macros.get("OW_WILD_BEHAVIOR_KIND_ASLEEP", 8)
    chill_asleep, _ = focused_fixture(
        "chill-asleep",
        {
            "chillState": "OW_WILD_BEHAVIOR_KIND_ASLEEP",
            "tiredState": "OW_WILD_BEHAVIOR_KIND_NONE",
            "stamina": "0",
            "alertness": "9",
            "alertChance": "100",
            "restTime": "0",
        },
        ["tiredState", "stamina", "alertness", "alertChance"],
    )
    if (
        legacy.numeric(chill_asleep["tiredState"]) != asleep
        or legacy.numeric(chill_asleep["stamina"]) != 1
        or legacy.numeric(chill_asleep["alertness"]) != 0
        or legacy.numeric(chill_asleep["alertChance"]) != 0
        or legacy.numeric(chill_asleep["restTime"]) != 0
    ):
        raise RuntimeError("chill-asleep normalization values drifted")

    tired_asleep, _ = focused_fixture(
        "tired-asleep",
        {
            "chillState": "OW_WILD_BEHAVIOR_KIND_IDLE",
            "tiredState": "OW_WILD_BEHAVIOR_KIND_ASLEEP",
            "stamina": "0",
            "restTime": "0",
        },
        ["stamina"],
    )
    if (
        legacy.numeric(tired_asleep["stamina"]) != 1
        or legacy.numeric(tired_asleep["restTime"]) != 0
    ):
        raise RuntimeError("tired-asleep stamina/rest normalization drifted")

    active_tired, _ = focused_fixture(
        "active-tired",
        {
            "chillState": "OW_WILD_BEHAVIOR_KIND_IDLE",
            "attentiveState": "OW_WILD_BEHAVIOR_KIND_NONE",
            "targetSelector": "OW_WILD_BEHAVIOR_TARGET_NONE",
            "movementStyle": "OW_WILD_BEHAVIOR_LOCOMOTION_NONE",
            "attentiveBattle": "255",
            "tiredState": "OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE",
            "stamina": "0",
            "restTime": "0",
        },
        ["stamina", "restTime", "attentiveBattle"],
    )
    if (
        legacy.numeric(active_tired["stamina"]) != 1
        or legacy.numeric(active_tired["restTime"]) != 1
        or legacy.numeric(active_tired["attentiveBattle"])
        != model.macros.get("OW_WILD_BEHAVIOR_BATTLE_TRIGGER_NONE", 0)
    ):
        raise RuntimeError("active+tired stamina/rest normalization drifted")

    alert_none, alert_none_changes = focused_fixture(
        "alert-emote-none",
        {"alertEmote": "OW_WILD_SPAWNER_BUBBLE_ID_NONE"},
        [],
    )
    if (
        legacy.numeric(alert_none["alertEmote"])
        != model.macros.get("OW_WILD_SPAWNER_BUBBLE_ID_NONE", 0xFF)
        or alert_none_changes
    ):
        raise RuntimeError("alert-emote NONE sentinel was not preserved")

    spawn_distances, distance_changes = focused_fixture(
        "spawn-distance-two-step",
        {
            "spawnDestinationMinDistance": "OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE",
            "spawnDestinationMaxDistance": "0",
        },
        ["spawnDestinationMaxDistance", "spawnDestinationMaxDistance"],
    )
    distance_values = [legacy.numeric(change["after"]) for change in distance_changes]
    if (
        distance_values
        != [
            model.macros.get("OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE", 1),
            model.macros.get("OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE", 8),
        ]
        or legacy.numeric(spawn_distances["spawnDestinationMaxDistance"])
        != model.macros.get("OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE", 8)
    ):
        raise RuntimeError("spawn-distance two-step normalization drifted")

    if legacy.numeric(chill_asleep["chillState"]) != asleep:
        raise RuntimeError("behavior-kind fixture constants drifted")
    return [
        "runtime normalization field order matches C",
        "active/tired hop-only values remain untouched",
        "runtime boolean values clamp to YES",
        "chill/tired asleep normalization fixtures match C",
        "active+tired stamina/rest normalization fixture matches C order",
        "alert-emote NONE and two-step spawn-distance fixtures match C",
    ]


def validate_class_resolution(model: ParsedModel, legacy: ModuleType) -> list[str]:
    any_match_raws = legacy.default_behavior_match_raws()
    class_one = legacy.make_value("1", "behaviorClass", model.macros)
    rule_one = {
        "order": 1,
        "storage": "full",
        "match": legacy.parse_match(
            [any_match_raws[field] for field in legacy.MATCH_FIELDS], model.macros
        ),
        "behaviorClass": class_one,
    }
    chained_raws = dict(any_match_raws)
    chained_raws["behaviorClass"] = "1"
    rule_two = {
        "order": 2,
        "storage": "full",
        "match": legacy.parse_match(
            [chained_raws[field] for field in legacy.MATCH_FIELDS], model.macros
        ),
        "behaviorClass": legacy.make_value("2", "behaviorClass", model.macros),
    }
    context = {
        "species": model.macros.get("SPECIES_PICHU", 0),
        "groupFlags": 0,
        "level": 1,
        "terrain": model.macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0),
        "shiny": 0,
        "behaviorClass": model.macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0),
    }
    resolved, hits = legacy.class_for_context(
        context, [rule_one, rule_two], len(model.class_profiles), model.macros
    )
    if resolved != 1 or [rule["order"] for rule in hits] != [1]:
        raise RuntimeError("full class rules incorrectly chain through prior results")
    compact = {
        "order": 3,
        "storage": "species",
        "match": legacy.parse_match(
            [
                (
                    "SPECIES_PICHU"
                    if field == "species"
                    else any_match_raws[field]
                )
                for field in legacy.MATCH_FIELDS
            ],
            model.macros,
        ),
        "behaviorClass": legacy.make_value("2", "behaviorClass", model.macros),
    }
    resolved, hits = legacy.class_for_context(
        context,
        [rule_one, rule_two, compact],
        len(model.class_profiles),
        model.macros,
    )
    if resolved != 2 or [rule["order"] for rule in hits] != [1, 3]:
        raise RuntimeError("compact species class rule did not apply after full rules")
    return [
        "full class rules use the unchanged incoming context",
        "compact species class rules apply in a second pass",
    ]


class EffectiveProfileRegistry:
    def __init__(self, model: ParsedModel, legacy: ModuleType):
        self.model = model
        self.legacy = legacy
        self.records: dict[str, dict[str, Any]] = {}
        self.ids_by_key: dict[bytes, str] = {}

    def add(self, profile: dict[str, dict[str, Any]]) -> str:
        profile_key = canonical_json_bytes(canonical_profile(profile, self.legacy))
        existing = self.ids_by_key.get(profile_key)
        if existing is not None:
            return existing
        record = effective_profile_record(
            profile,
            self.model.primitive_maps,
            self.model.macros,
            self.legacy,
        )
        identifier = sha256_id("effective", record)
        collision = self.records.get(identifier)
        if collision is not None and collision != record:
            raise RuntimeError(f"effective profile digest collision: {identifier}")
        self.records[identifier] = record
        self.ids_by_key[profile_key] = identifier
        return identifier


class ResolutionStackRegistry:
    def __init__(self):
        self.records: dict[str, list[dict[str, Any]]] = {}

    def add(self, layers: list[dict[str, Any]]) -> str:
        identifier = sha256_id("stack", layers)
        collision = self.records.get(identifier)
        if collision is not None and collision != layers:
            raise RuntimeError(f"resolution stack digest collision: {identifier}")
        self.records[identifier] = layers
        return identifier


def canonical_class_rule(rule: dict[str, Any], legacy: ModuleType) -> dict[str, Any]:
    return {
        "order": int(rule["order"]),
        "storage": rule.get("storage"),
        "match": canonical_match(rule["match"], legacy),
        "behaviorClass": atom(rule["behaviorClass"]),
    }


def override_field_operations(
    behavior: dict[str, Any], legacy: ModuleType
) -> list[dict[str, Any]]:
    relative = set(behavior.get("relativeFields") or [])
    at_least = set(behavior.get("atLeastFields") or [])
    at_most = set(behavior.get("atMostFields") or [])
    operations = []
    for field in legacy.behavior_override_field_keys(behavior):
        if field in relative and field in at_least:
            operator = "relativeAtLeast"
        elif field in relative and field in at_most:
            operator = "relativeAtMost"
        elif field in relative:
            operator = "relative"
        elif field in at_least:
            operator = "atLeast"
        elif field in at_most:
            operator = "atMost"
        else:
            operator = "replace"
        operation = {
            "field": field,
            "operator": operator,
            "value": atom(behavior["profile"][field]),
        }
        if field in at_least or field in at_most:
            operation["bound"] = atom(
                behavior.get("compoundBoundProfile", {}).get(
                    field, behavior["profile"][field]
                )
            )
        operations.append(operation)
    return operations


def canonical_override(
    override: dict[str, Any], model: ParsedModel, legacy: ModuleType
) -> dict[str, Any]:
    order = int(override["order"])
    behavior = override["behavior"]
    masks = {}
    for key in (
        "mask",
        "mask2",
        "mask3",
        "relativeMask",
        "relativeMask2",
        "relativeMask3",
        "atLeastMask",
        "atLeastMask2",
        "atLeastMask3",
        "atMostMask",
        "atMostMask2",
        "atMostMask3",
    ):
        parsed = behavior.get(key, {})
        masks[key] = {"raw": parsed.get("raw", "0"), "value": parsed.get("value")}
    override_index = int(override.get("profileOrder", order)) - 1
    follower_index = model.macros.get(
        "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON", -1
    )
    match_class = legacy.numeric(override["match"]["behaviorClass"])
    forced_asleep_class = model.macros.get(
        "OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP", 0xFD
    )
    if override_index == follower_index:
        runtime_activation = "forced-by-follower-slot"
    elif match_class == forced_asleep_class:
        runtime_activation = "dormant-no-runtime-caller-produces-sentinel"
    elif legacy.numeric(override.get("targetMode", {})) == model.macros.get(
        "OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED", 0
    ):
        runtime_activation = "disabled"
    else:
        runtime_activation = "natural-context-match"
    return {
        "order": order,
        "index": override_index,
        "profileOrder": int(override.get("profileOrder", order)),
        "name": model.override_names.get(order, "") or f"Override profile #{order}",
        "runtimeActivation": runtime_activation,
        "targetMode": atom(override.get("targetMode")),
        "match": canonical_match(override["match"], legacy),
        "memberStart": override.get("memberStart"),
        "memberCount": int(override.get("memberCount", len(override.get("members") or []))),
        "members": [
            {"symbol": member.get("symbol") or member.get("raw"), "value": member.get("value")}
            for member in override.get("members") or []
        ],
        "masks": masks,
        "operations": override_field_operations(behavior, legacy),
    }


def normalized_class_profiles(
    model: ParsedModel,
    registry: EffectiveProfileRegistry,
    legacy: ModuleType,
) -> list[dict[str, Any]]:
    rules_by_class: dict[int, list[int]] = {}
    for rule in model.class_rules:
        target = legacy.numeric(rule["behaviorClass"])
        if target is not None:
            rules_by_class.setdefault(target, []).append(int(rule["order"]))
    result = []
    for index, source_profile in enumerate(model.class_profiles):
        normalized = legacy.clone_profile(source_profile)
        normalizations = legacy.normalize_profile(normalized, model.macros)
        label = model.class_labels.get(
            index,
            {"symbol": str(index), "name": f"Class {index}", "value": index},
        )
        result.append(
            {
                "index": index,
                "symbol": label.get("symbol", str(index)),
                "name": label.get("name", f"Class {index}"),
                "sourceProfile": canonical_profile(source_profile, legacy),
                "effectiveProfileId": registry.add(normalized),
                "normalizations": [canonical_change(item) for item in normalizations],
                "targetedByClassRuleOrders": rules_by_class.get(index, []),
            }
        )
    return result


def boundary_levels(
    rules: Iterable[dict[str, Any]], legacy: ModuleType
) -> list[int]:
    levels = {1, 100}
    for rule in rules:
        match = rule.get("match", {})
        for field in ("minLevel", "maxLevel"):
            value = legacy.numeric(match.get(field, {}))
            if value in (None, 0):
                continue
            for candidate in (value - 1, value, value + 1):
                if 1 <= candidate <= 100:
                    levels.add(candidate)
    return sorted(levels)


def group_symbols(flags: int, model: ParsedModel) -> list[str]:
    return [
        str(label.get("symbol", group))
        for group, label in sorted(model.group_labels.items())
        if group and flags & group
    ]


def behavior_limit_key(
    value: int,
    *,
    kind: str,
    class_index: int | None = None,
    override: dict[str, Any] | None = None,
    application: list[str] | None = None,
) -> dict[str, Any]:
    writer: dict[str, Any] = {"kind": kind}
    if class_index is not None:
        writer["classIndex"] = class_index
    if override is not None:
        writer.update(
            {
                "overrideIndex": int(override.get("profileOrder", override["order"])) - 1,
                "overrideOrder": int(override["order"]),
                "overrideProfileOrder": int(
                    override.get("profileOrder", override["order"])
                ),
                "application": application or [],
            }
        )
    return {"value": value, "provenance": writer}


def resolve_live_composition(
    context: dict[str, Any],
    behavior_class: int,
    class_hits: list[dict[str, Any]],
    model: ParsedModel,
    legacy: ModuleType,
    *,
    forced_override_index: int | None = None,
) -> dict[str, Any]:
    default_class = model.macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0)
    base_class = behavior_class
    if base_class < 0 or base_class >= len(model.class_profiles):
        base_class = default_class
    profile = legacy.clone_profile(model.class_profiles[base_class])
    layers: list[dict[str, Any]] = [
        {
            "kind": "class",
            "classIndex": base_class,
            "incomingBehaviorClass": behavior_class,
            "classRuleOrders": [int(rule["order"]) for rule in class_hits],
            "changes": [],
        }
    ]
    limit = behavior_limit_key(base_class, kind="class", class_index=base_class)
    picked_up_class = model.macros.get("OW_WILD_BEHAVIOR_CLASS_PICKED_UP", -1)
    if base_class != picked_up_class:
        for override in model.overrides:
            override_index = int(
                override.get("profileOrder", override["order"])
            ) - 1
            natural = legacy.behavior_override_applies(context, override, model.macros)
            forced = override_index == forced_override_index
            if not natural and not forced:
                continue
            application = []
            if natural:
                application.append("natural-context-match")
            if forced:
                application.append("forced-profile-index")
            changes = legacy.merge_profile(profile, override["behavior"])
            layers.append(
                {
                    "kind": "override",
                    "order": int(override["order"]),
                    "profileOrder": int(
                        override.get("profileOrder", override["order"])
                    ),
                    "overrideIndex": override_index,
                    "application": application,
                    "changes": [canonical_change(change) for change in changes],
                }
            )
            if "overworldLimit" in legacy.behavior_override_field_keys(
                override["behavior"]
            ):
                limit = behavior_limit_key(
                    len(model.class_profiles) + override_index,
                    kind="override",
                    override=override,
                    application=application,
                )
    normalizations = legacy.normalize_profile(profile, model.macros)
    if normalizations:
        layers.append(
            {
                "kind": "normalization",
                "changes": [canonical_change(change) for change in normalizations],
            }
        )
    return {
        "profile": profile,
        "layers": layers,
        "behaviorLimitKey": limit,
        "baseClassIndex": base_class,
    }


def resolve_natural_context(
    species_entry: dict[str, Any],
    level: int,
    terrain_symbol: str,
    terrain: int,
    shiny: int,
    model: ParsedModel,
    registry: EffectiveProfileRegistry,
    stack_registry: ResolutionStackRegistry,
    legacy: ModuleType,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    symbol = species_entry["symbol"]
    flags = legacy.group_flags_for_species(
        symbol,
        model.group_species,
        model.species_by_symbol,
        model.macros,
    )
    context = {
        "species": species_entry["value"],
        "symbol": symbol,
        "level": level,
        "terrain": terrain,
        "shiny": shiny,
        "groupFlags": flags,
        "behaviorClass": model.macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0),
    }
    behavior_class, class_hits = legacy.class_for_context(
        context, model.class_rules, len(model.class_profiles), model.macros
    )
    context["behaviorClass"] = behavior_class
    composition = resolve_live_composition(
        context, behavior_class, class_hits, model, legacy
    )
    record = {
        "id": f"{symbol}/L{level}/{terrain_symbol}/S{shiny}",
        "species": {"symbol": symbol, "value": species_entry["value"]},
        "level": level,
        "terrain": {"symbol": terrain_symbol, "value": terrain},
        "shiny": bool(shiny),
        "groupFlags": flags,
        "groups": group_symbols(flags, model),
        "behaviorClass": behavior_class,
        "effectiveProfileId": registry.add(composition["profile"]),
        "resolutionStackId": stack_registry.add(composition["layers"]),
        "behaviorLimitKey": composition["behaviorLimitKey"],
    }
    return record, context, class_hits


def context_matrix(
    model: ParsedModel,
    registry: EffectiveProfileRegistry,
    stack_registry: ResolutionStackRegistry,
    legacy: ModuleType,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[
        tuple[str, int, bytes],
        tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]],
    ],
]:
    levels = boundary_levels([*model.class_rules, *model.overrides], legacy)
    terrains = sorted(model.terrain_values.items(), key=lambda item: (item[1], item[0]))
    species_entries = sorted(
        model.species, key=lambda item: (int(item["value"]), str(item["symbol"]))
    )
    contexts = []
    representatives = {}
    for species in species_entries:
        for level in levels:
            for terrain_symbol, terrain_value in terrains:
                for shiny in (0, 1):
                    resolved = resolve_natural_context(
                        species,
                        level,
                        terrain_symbol,
                        terrain_value,
                        shiny,
                        model,
                        registry,
                        stack_registry,
                        legacy,
                    )
                    record, runtime_context, class_hits = resolved
                    contexts.append(record)
                    # Followers can come from any eligible party Pokemon, so one
                    # deepest representative per class is insufficient.  Retain
                    # one deterministic context for every natural stack and its
                    # resolved class/behavior-limit provenance.
                    representative_key = (
                        record["resolutionStackId"],
                        int(record["behaviorClass"]),
                        canonical_json_bytes(
                            record["behaviorLimitKey"]["provenance"]
                        ),
                    )
                    representatives.setdefault(representative_key, resolved)
    axes = {
        "speciesCount": len(species_entries),
        "levels": levels,
        "terrains": [
            {"symbol": symbol, "value": value} for symbol, value in terrains
        ],
        "shiny": [False, True],
        "policy": (
            "all parsed species x every min/max boundary and adjacent level x "
            "every terrain x both shiny values"
        ),
    }
    return axes, contexts, representatives


def isolated_override_probes(
    model: ParsedModel,
    registry: EffectiveProfileRegistry,
    stack_registry: ResolutionStackRegistry,
    legacy: ModuleType,
) -> list[dict[str, Any]]:
    """Compose one override alone; these are deliberately not live resolver calls."""

    probes = []
    picked_up_class = model.macros.get("OW_WILD_BEHAVIOR_CLASS_PICKED_UP", -1)
    for class_index, source_profile in enumerate(model.class_profiles):
        for override in model.overrides:
            working = legacy.clone_profile(source_profile)
            changes = legacy.merge_profile(working, override["behavior"])
            normalizations = legacy.normalize_profile(working, model.macros)
            override_index = int(
                override.get("profileOrder", override["order"])
            ) - 1
            application = ["synthetic-isolated"]
            layers = [
                {
                    "kind": "class",
                    "classIndex": class_index,
                    "incomingBehaviorClass": class_index,
                    "classRuleOrders": [],
                    "changes": [],
                },
                {
                    "kind": "override",
                    "order": int(override["order"]),
                    "profileOrder": int(
                        override.get("profileOrder", override["order"])
                    ),
                    "overrideIndex": override_index,
                    "application": application,
                    "changes": [canonical_change(change) for change in changes],
                },
            ]
            if normalizations:
                layers.append(
                    {
                        "kind": "normalization",
                        "changes": [
                            canonical_change(change) for change in normalizations
                        ],
                    }
                )
            if "overworldLimit" in legacy.behavior_override_field_keys(
                override["behavior"]
            ):
                limit = behavior_limit_key(
                    len(model.class_profiles) + override_index,
                    kind="override",
                    override=override,
                    application=application,
                )
            else:
                limit = behavior_limit_key(
                    class_index, kind="class", class_index=class_index
                )
            probes.append(
                {
                    "semantics": "synthetic-isolated-not-live-contextual-resolution",
                    "classIndex": class_index,
                    "baseClassAllowsRuntimeOverrides": class_index != picked_up_class,
                    "baseClassConstraint": (
                        "live resolver bypasses all overrides for PICKED_UP"
                        if class_index == picked_up_class
                        else None
                    ),
                    "overrideOrder": int(override["order"]),
                    "overrideProfileOrder": int(
                        override.get("profileOrder", override["order"])
                    ),
                    "effectiveProfileId": registry.add(working),
                    "resolutionStackId": stack_registry.add(layers),
                    "behaviorLimitKey": limit,
                }
            )
    return probes


def contextual_forced_probes(
    model: ParsedModel,
    representatives: dict[
        tuple[str, int, bytes],
        tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]],
    ],
    registry: EffectiveProfileRegistry,
    stack_registry: ResolutionStackRegistry,
    legacy: ModuleType,
) -> list[dict[str, Any]]:
    follower_index = model.macros.get(
        "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON", -1
    )
    if not 0 <= follower_index < len(model.overrides):
        raise RuntimeError("follower forced override index is outside the profile table")
    picked_up_class = model.macros.get("OW_WILD_BEHAVIOR_CLASS_PICKED_UP", -1)
    default_terrain = model.macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0)
    probes = []
    ordered_representatives = sorted(
        representatives.values(),
        key=lambda item: (
            int(item[0]["behaviorClass"]),
            str(item[0]["resolutionStackId"]),
            str(item[0]["id"]),
        ),
    )
    for context_record, runtime_context, class_hits in ordered_representatives:
        class_index = int(context_record["behaviorClass"])
        if class_index == picked_up_class:
            continue
        runtime_context = dict(runtime_context)
        runtime_context["behaviorClass"] = class_index
        composition = resolve_live_composition(
            runtime_context,
            class_index,
            class_hits,
            model,
            legacy,
            forced_override_index=follower_index,
        )
        forced_applied = any(
            layer.get("kind") == "override"
            and layer.get("overrideIndex") == follower_index
            for layer in composition["layers"]
        )
        probes.append(
            {
                "semantics": "live-contextual-forced-profile-index",
                "forcedOverrideIndex": follower_index,
                "forcedOverrideOrder": follower_index + 1,
                "purpose": "follower-slot override",
                "classIndex": class_index,
                "naturalContextId": context_record["id"],
                "naturalResolutionStackId": context_record["resolutionStackId"],
                "naturalBehaviorLimitKey": context_record["behaviorLimitKey"],
                "liveReachable": True,
                "unreachableReason": None,
                "forcedOverrideApplied": forced_applied,
                "effectiveProfileId": registry.add(composition["profile"]),
                "resolutionStackId": stack_registry.add(composition["layers"]),
                "behaviorLimitKey": composition["behaviorLimitKey"],
            }
        )

    picked_up_context = {
        "species": model.macros.get("SPECIES_NONE", 0),
        "symbol": "SPECIES_NONE",
        "level": 1,
        "terrain": default_terrain,
        "shiny": 0,
        "groupFlags": 0,
        "behaviorClass": picked_up_class,
    }
    picked_up_composition = resolve_live_composition(
        picked_up_context,
        picked_up_class,
        [],
        model,
        legacy,
        forced_override_index=follower_index,
    )
    probes.append(
        {
            "semantics": "live-contextual-forced-profile-index",
            "forcedOverrideIndex": follower_index,
            "forcedOverrideOrder": follower_index + 1,
            "purpose": "follower-slot override",
            "classIndex": picked_up_class,
            "naturalContextId": None,
            "naturalResolutionStackId": None,
            "naturalBehaviorLimitKey": None,
            "liveReachable": False,
            "unreachableReason": "live resolver bypasses all overrides for PICKED_UP",
            "forcedOverrideApplied": False,
            "effectiveProfileId": registry.add(picked_up_composition["profile"]),
            "resolutionStackId": stack_registry.add(picked_up_composition["layers"]),
            "behaviorLimitKey": picked_up_composition["behaviorLimitKey"],
        }
    )
    return probes


def validate_contextual_forced_probes(
    probes: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    model: ParsedModel,
    registry: EffectiveProfileRegistry,
    stack_registry: ResolutionStackRegistry,
    legacy: ModuleType,
) -> str:
    picked_up_class = model.macros.get("OW_WILD_BEHAVIOR_CLASS_PICKED_UP", -1)
    follower_index = model.macros.get(
        "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON", -1
    )
    follower_override = next(
        (
            override
            for override in model.overrides
            if int(override.get("profileOrder", override["order"])) - 1
            == follower_index
        ),
        None,
    )
    if follower_override is None:
        raise RuntimeError("follower forced override profile is missing")
    follower_fields = set(
        legacy.behavior_override_field_keys(follower_override["behavior"])
    )
    expected_follower_fields = {
        "chillState",
        "chillSpeed",
        "spawnState",
        "alertChance",
        "spawnDestination",
        "chillTarget",
        "playerAdjacentDirectionMasks",
    }
    if follower_fields != expected_follower_fields:
        raise RuntimeError(
            "follower override field set drifted: "
            f"expected {sorted(expected_follower_fields)}, got {sorted(follower_fields)}"
        )

    def natural_key(record: dict[str, Any]) -> tuple[str, int, bytes]:
        return (
            str(record["resolutionStackId"]),
            int(record["behaviorClass"]),
            canonical_json_bytes(record["behaviorLimitKey"]["provenance"]),
        )

    expected_by_key: dict[tuple[str, int, bytes], dict[str, Any]] = {}
    for context in contexts:
        if int(context["behaviorClass"]) != picked_up_class:
            expected_by_key.setdefault(natural_key(context), context)

    reachable_probes = [probe for probe in probes if probe.get("liveReachable")]
    actual_by_key: dict[tuple[str, int, bytes], dict[str, Any]] = {}
    for probe in reachable_probes:
        key = (
            str(probe.get("naturalResolutionStackId")),
            int(probe["classIndex"]),
            canonical_json_bytes(
                (probe.get("naturalBehaviorLimitKey") or {}).get("provenance")
            ),
        )
        if key in actual_by_key:
            raise RuntimeError(f"duplicate contextual follower probe for {key[:2]}")
        actual_by_key[key] = probe
    if set(actual_by_key) != set(expected_by_key):
        missing = sorted(set(expected_by_key) - set(actual_by_key))
        extra = sorted(set(actual_by_key) - set(expected_by_key))
        raise RuntimeError(
            "contextual follower probes do not cover every reachable natural stack: "
            f"missing={[(item[0], item[1]) for item in missing[:5]]}, "
            f"extra={[(item[0], item[1]) for item in extra[:5]]}"
        )

    for key, probe in actual_by_key.items():
        if probe.get("forcedOverrideIndex") != follower_index:
            raise RuntimeError("contextual follower probe uses the wrong forced index")
        if not probe.get("forcedOverrideApplied"):
            raise RuntimeError(
                f"reachable follower probe did not apply for {probe['naturalContextId']}"
            )
        if probe.get("behaviorLimitKey") != probe.get("naturalBehaviorLimitKey"):
            raise RuntimeError(
                f"follower composition changed behavior-limit provenance for {key[:2]}"
            )
        natural_layers = stack_registry.records[key[0]]
        forced_layers = stack_registry.records[probe["resolutionStackId"]]
        natural_resolution_layers = [
            layer for layer in natural_layers if layer.get("kind") != "normalization"
        ]
        forced_resolution_layers = [
            layer for layer in forced_layers if layer.get("kind") != "normalization"
        ]
        follower_layers = [
            layer
            for layer in forced_resolution_layers
            if layer.get("kind") == "override"
            and layer.get("overrideIndex") == follower_index
        ]
        if (
            len(follower_layers) != 1
            or follower_layers[0].get("application") != ["forced-profile-index"]
            or forced_resolution_layers[:-1] != natural_resolution_layers
            or forced_resolution_layers[-1] != follower_layers[0]
        ):
            raise RuntimeError(
                f"follower layer is not after the complete natural stack for {key[:2]}"
            )

    unreachable = [probe for probe in probes if not probe.get("liveReachable")]
    if len(unreachable) != 1:
        raise RuntimeError(
            f"expected one unreachable PICKED_UP follower probe, got {len(unreachable)}"
        )
    picked_up_probe = unreachable[0]
    picked_up_layers = stack_registry.records[picked_up_probe["resolutionStackId"]]
    if (
        int(picked_up_probe["classIndex"]) != picked_up_class
        or picked_up_probe.get("naturalContextId") is not None
        or picked_up_probe.get("naturalResolutionStackId") is not None
        or picked_up_probe.get("naturalBehaviorLimitKey") is not None
        or picked_up_probe.get("forcedOverrideApplied")
        or any(layer.get("kind") == "override" for layer in picked_up_layers)
    ):
        raise RuntimeError("PICKED_UP follower override probe became reachable")

    probe_by_natural_key = actual_by_key

    def validate_fixture(
        species_symbol: str,
        override_name: str,
        expected_fields: dict[str, str],
    ) -> None:
        fixture_contexts = [
            context
            for context in contexts
            if context["species"]["symbol"] == species_symbol
        ]
        fixture_keys = {natural_key(context) for context in fixture_contexts}
        if len(fixture_keys) != 1:
            raise RuntimeError(
                f"{species_symbol} fixture resolved to {len(fixture_keys)} natural stacks"
            )
        fixture_key = next(iter(fixture_keys))
        fixture_context = expected_by_key[fixture_key]
        fixture_probe = probe_by_natural_key[fixture_key]
        override_order = next(
            (
                int(override["order"])
                for override in model.overrides
                if model.override_names.get(int(override["order"])) == override_name
            ),
            None,
        )
        if override_order is None or not any(
            layer.get("kind") == "override"
            and layer.get("order") == override_order
            for layer in stack_registry.records[fixture_key[0]]
        ):
            raise RuntimeError(
                f"{species_symbol} fixture is missing its {override_name} natural layer"
            )
        natural_profile = registry.records[fixture_context["effectiveProfileId"]][
            "legacyProfile"
        ]
        forced_profile = registry.records[fixture_probe["effectiveProfileId"]][
            "legacyProfile"
        ]
        changed_unmasked = sorted(
            field
            for field in legacy.PROFILE_FIELDS
            if field not in follower_fields
            and natural_profile[field] != forced_profile[field]
        )
        if changed_unmasked:
            raise RuntimeError(
                f"{species_symbol} follower composition masked natural fields: "
                f"{changed_unmasked}"
            )
        for field, expected_symbol in expected_fields.items():
            expected_value = model.macros.get(expected_symbol)
            if (
                expected_value is None
                or natural_profile[field].get("value") != expected_value
                or forced_profile[field] != natural_profile[field]
            ):
                raise RuntimeError(
                    f"{species_symbol} {override_name} fixture lost {field}="
                    f"{expected_symbol} underneath follower composition"
                )

    validate_fixture(
        "SPECIES_PICHU",
        "Skittish",
        {
            "attentiveState": "OW_WILD_BEHAVIOR_KIND_FLEE",
            "targetSelector": "OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER",
        },
    )
    validate_fixture(
        "SPECIES_GASTLY",
        "Phantom stalker override",
        {
            "movementStyle": "OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT",
            "targetSelector": "OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER",
        },
    )
    return (
        "contextual follower probes cover every reachable natural stack; the "
        "seven-field follower layer follows natural overrides; Pichu Skittish "
        "and Gastly Phantom values survive; PICKED_UP remains unreachable"
    )


def dormant_context_probes(
    model: ParsedModel,
    registry: EffectiveProfileRegistry,
    stack_registry: ResolutionStackRegistry,
    legacy: ModuleType,
) -> list[dict[str, Any]]:
    sentinel = model.macros.get("OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP", 0xFD)
    override = next(
        (
            item
            for item in model.overrides
            if legacy.numeric(item["match"]["behaviorClass"]) == sentinel
        ),
        None,
    )
    if override is None:
        return []
    context = {
        "species": model.macros.get("SPECIES_NONE", 0),
        "symbol": "SPECIES_NONE",
        "level": 1,
        "terrain": model.macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0),
        "shiny": 0,
        "groupFlags": 0,
        "behaviorClass": sentinel,
    }
    composition = resolve_live_composition(
        context, sentinel, [], model, legacy
    )
    return [
        {
            "semantics": "synthetic-dormant-sentinel-context",
            "incomingBehaviorClass": sentinel,
            "overrideOrder": int(override["order"]),
            "liveReachable": False,
            "unreachableReason": "no runtime caller produces the forced-asleep sentinel class",
            "runtimeStatus": "dormant-no-runtime-caller-produces-sentinel",
            "effectiveProfileId": registry.add(composition["profile"]),
            "resolutionStackId": stack_registry.add(composition["layers"]),
            "behaviorLimitKey": composition["behaviorLimitKey"],
        }
    ]


def validate_behavior_limit_provenance(
    records: Iterable[dict[str, Any]],
    model: ParsedModel,
    stack_registry: ResolutionStackRegistry,
) -> str:
    for record in records:
        layers = stack_registry.records[record["resolutionStackId"]]
        limit_writers = [
            layer
            for layer in layers
            if layer.get("kind") == "override"
            and any(
                change.get("field") == "overworldLimit"
                for change in layer.get("changes", [])
            )
        ]
        actual = record["behaviorLimitKey"]
        if limit_writers:
            expected_layer = limit_writers[-1]
            expected_value = len(model.class_profiles) + int(
                expected_layer["overrideIndex"]
            )
            expected_kind = "override"
            expected_index = int(expected_layer["overrideIndex"])
            if (
                actual.get("value") != expected_value
                or actual.get("provenance", {}).get("kind") != expected_kind
                or actual.get("provenance", {}).get("overrideIndex") != expected_index
            ):
                raise RuntimeError(
                    f"behavior limit provenance drifted for {record.get('id', record)}"
                )
        else:
            class_layer = layers[0]
            expected_value = int(class_layer["classIndex"])
            if (
                actual.get("value") != expected_value
                or actual.get("provenance", {}).get("kind") != "class"
                or actual.get("provenance", {}).get("classIndex") != expected_value
            ):
                raise RuntimeError(
                    f"class behavior limit provenance drifted for {record.get('id', record)}"
                )
    return "behaviorLimitKey provenance follows the last applicable overworld-limit writer"


def validate_effective_profile_atoms(registry: EffectiveProfileRegistry) -> str:
    unresolved: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if "raw" in value and "value" in value and value.get("value") is None:
                unresolved.append(path)
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    for identifier, record in registry.records.items():
        visit(record, identifier)
    if unresolved:
        preview = ", ".join(unresolved[:5])
        raise RuntimeError(
            f"effective profiles contain {len(unresolved)} unresolved numeric atom(s): "
            f"{preview}"
        )
    return "every effective-profile atom has a resolved numeric value"


def source_entries(
    legacy: ModuleType, reliability: ModuleType
) -> list[dict[str, Any]]:
    paths = set(legacy.DEFINE_SOURCE_FILES) | {
        legacy.OVERLAY_SOURCE,
        legacy.BEHAVIOR_DATA_SOURCE,
        legacy.BEHAVIOR_DATA_HEADER,
        legacy.ARMIPS_CONFIG,
        legacy.ARMIPS_CONSTANTS,
        legacy.MONDATA_SOURCE,
    }
    return [
        reliability.source_entry(path.resolve(), ROOT)
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())
    ]


def build_artifact(legacy: ModuleType, reliability: ModuleType) -> dict[str, Any]:
    classification_checks = validate_field_classification(legacy)
    model = parse_model(legacy)
    if model.macros.get("OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES") != 0xF:
        raise RuntimeError(
            "OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES did not resolve to 0xF"
        )
    self_checks = [
        *classification_checks,
        *validate_named_groups(model, legacy),
        *validate_runtime_normalization(model, legacy),
        *validate_class_resolution(model, legacy),
    ]
    registry = EffectiveProfileRegistry(model, legacy)
    stack_registry = ResolutionStackRegistry()
    classes = normalized_class_profiles(model, registry, legacy)
    axes, contexts, representatives = context_matrix(
        model, registry, stack_registry, legacy
    )
    isolated_probes = isolated_override_probes(
        model, registry, stack_registry, legacy
    )
    forced_probes = contextual_forced_probes(
        model, representatives, registry, stack_registry, legacy
    )
    dormant_probes = dormant_context_probes(
        model, registry, stack_registry, legacy
    )
    self_checks.append(
        validate_contextual_forced_probes(
            forced_probes,
            contexts,
            model,
            registry,
            stack_registry,
            legacy,
        )
    )
    self_checks.append(validate_effective_profile_atoms(registry))
    self_checks.append(
        validate_behavior_limit_provenance(
            [*contexts, *isolated_probes, *forced_probes, *dormant_probes],
            model,
            stack_registry,
        )
    )
    override_records = [
        canonical_override(override, model, legacy) for override in model.overrides
    ]

    sources = source_entries(legacy, reliability)
    source_revision_input = "".join(
        f"{entry['path']}\0{entry['sha256'] or 'missing'}\n" for entry in sources
    ).encode("utf-8")
    artifact: dict[str, Any] = {
        "schema": ARTIFACT_SCHEMA,
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "sourceRevision": f"sha256:{hashlib.sha256(source_revision_input).hexdigest()}",
        "behaviorDataVersion": model.macros.get(
            "OVERWORLD_WILD_BEHAVIOR_DATA_VERSION"
        ),
        "resolverContract": {
            "fullClassRulesUseUnchangedIncomingContext": True,
            "compactSpeciesRulesApplyAfterFullRules": True,
            "overridesApplyInOrder": True,
            "lastMatchingOverrideWinsPerField": True,
            "lastAppliedOverworldLimitWriterOwnsBehaviorLimitKey": True,
            "normalizationRunsAfterOverrides": True,
            "fieldClassification": {
                key: list(fields) for key, fields in FIELD_CLASSIFICATION.items()
            },
        },
        "selfChecks": {"passed": True, "checks": self_checks},
        "sources": sources,
        "counts": {
            "profileFields": len(legacy.PROFILE_FIELDS),
            "classProfiles": len(model.class_profiles),
            "classRules": len(model.class_rules),
            "fullClassRules": sum(
                1 for rule in model.class_rules if rule.get("storage") == "full"
            ),
            "speciesClassRules": sum(
                1 for rule in model.class_rules if rule.get("storage") == "species"
            ),
            "overrideProfiles": len(model.overrides),
            "overrideMembers": sum(
                len(override.get("members") or []) for override in model.overrides
            ),
            "species": len(model.species),
            "contexts": len(contexts),
            "isolatedOverrideProbes": len(isolated_probes),
            "contextualForcedProbes": len(forced_probes),
            "dormantContextProbes": len(dormant_probes),
        },
        "classProfiles": classes,
        "classRules": [
            canonical_class_rule(rule, legacy) for rule in model.class_rules
        ],
        "overrides": override_records,
        "contextAxes": axes,
        "contexts": contexts,
        "isolatedOverrideProbes": isolated_probes,
        "contextualForcedProbes": forced_probes,
        "dormantContextProbes": dormant_probes,
    }
    artifact["effectiveProfiles"] = {
        key: registry.records[key] for key in sorted(registry.records)
    }
    artifact["counts"]["effectiveProfiles"] = len(registry.records)
    artifact["resolutionStacks"] = {
        key: stack_registry.records[key] for key in sorted(stack_registry.records)
    }
    artifact["counts"]["resolutionStacks"] = len(stack_registry.records)
    return artifact


def with_digest(artifact: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(artifact)
    result["digest"] = {
        "algorithm": "sha256",
        "scope": "canonical artifact excluding digest",
        "value": hashlib.sha256(canonical_json_bytes(result)).hexdigest(),
    }
    return result


def validate_stored_digest(artifact: Any) -> str | None:
    if not isinstance(artifact, dict):
        return "artifact root is not an object"
    digest = artifact.get("digest")
    if not isinstance(digest, dict) or digest.get("algorithm") != "sha256":
        return "artifact has no supported sha256 digest"
    expected = digest.get("value")
    unsigned = {key: value for key, value in artifact.items() if key != "digest"}
    actual = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    if expected != actual:
        return f"stored digest is invalid (stored {expected}, calculated {actual})"
    return None


def json_differences(
    expected: Any,
    actual: Any,
    *,
    path: str = "$",
    limit: int = 50,
) -> dict[str, Any]:
    differences: list[dict[str, Any]] = []
    total = 0

    def record(difference: dict[str, Any]) -> None:
        nonlocal total
        total += 1
        if len(differences) < limit:
            differences.append(difference)

    def visit(left: Any, right: Any, current: str) -> None:
        if type(left) is not type(right):
            record({"path": current, "expected": left, "actual": right})
            return
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child = f"{current}.{key}"
                if key not in left:
                    record({"path": child, "expected": None, "actual": right[key]})
                elif key not in right:
                    record({"path": child, "expected": left[key], "actual": None})
                else:
                    visit(left[key], right[key], child)
            return
        if isinstance(left, list):
            if len(left) != len(right):
                record(
                    {
                        "path": f"{current}.length",
                        "expected": len(left),
                        "actual": len(right),
                    }
                )
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                visit(left_item, right_item, f"{current}[{index}]")
            return
        if left != right:
            record({"path": current, "expected": left, "actual": right})

    visit(expected, actual, path)
    return {
        "items": differences,
        "total": total,
        "limit": limit,
        "truncated": total > len(differences),
    }


def comparison_payload(expected: Any, actual: dict[str, Any]) -> dict[str, Any]:
    expected_digest = expected.get("digest", {}).get("value") if isinstance(expected, dict) else None
    actual_digest = actual["digest"]["value"]
    digest_error = validate_stored_digest(expected)
    equal = digest_error is None and canonical_json_bytes(expected) == canonical_json_bytes(actual)
    difference_summary = (
        {"items": [], "total": 0, "limit": 50, "truncated": False}
        if equal
        else json_differences(expected, actual)
    )
    return {
        "equal": equal,
        "expectedDigest": expected_digest,
        "actualDigest": actual_digest,
        "expectedDigestError": digest_error,
        "differenceCount": difference_summary["total"],
        "differenceLimit": difference_summary["limit"],
        "differencesTruncated": difference_summary["truncated"],
        "differences": difference_summary["items"],
    }


def rendered_json(value: Any, compact: bool) -> bytes:
    if compact:
        return canonical_json_bytes(value) + b"\n"
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def write_output(path: str, body: bytes) -> None:
    if path == "-":
        sys.stdout.buffer.write(body)
        return
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination_mode = destination.stat().st_mode & 0o7777
    else:
        current_umask = os.umask(0)
        os.umask(current_umask)
        destination_mode = 0o666 & ~current_umask
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        os.fchmod(descriptor, destination_mode)
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, destination)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_descriptor = os.open(destination.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def load_json(path: str) -> Any:
    try:
        return json.loads(Path(path).expanduser().read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read baseline {path}: {exc}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export or check the deterministic legacy overworld-behavior golden oracle."
        )
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--check",
        metavar="BASELINE.json",
        help="exit successfully only if BASELINE exactly matches current sources",
    )
    modes.add_argument(
        "--compare",
        metavar="BASELINE.json",
        help="emit a machine-readable comparison against BASELINE",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        metavar="PATH",
        help="write JSON to PATH (default: stdout; use - for stdout)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="write canonical compact JSON instead of indented JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check and args.output != "-":
        raise ValueError("--output is not used with --check")

    legacy, reliability = load_backends()
    with reliability.workspace_guard(ROOT):
        artifact, _workspace_revision = reliability.stable_source_read(
            legacy,
            ROOT,
            lambda: build_artifact(legacy, reliability),
            cache_key=None,
        )
    current = with_digest(artifact)

    if args.check:
        expected = load_json(args.check)
        comparison = comparison_payload(expected, current)
        if comparison["equal"]:
            print(
                f"legacy overworld behavior golden matches {args.check} "
                f"({comparison['actualDigest']})",
                file=sys.stderr,
            )
            return 0
        print(
            f"legacy overworld behavior golden differs from {args.check}: "
            f"expected {comparison['expectedDigest']}, actual {comparison['actualDigest']}",
            file=sys.stderr,
        )
        if comparison["expectedDigestError"]:
            print(comparison["expectedDigestError"], file=sys.stderr)
        print(
            f"  {comparison['differenceCount']} total difference(s); "
            f"showing {min(10, len(comparison['differences']))}",
            file=sys.stderr,
        )
        for difference in comparison["differences"][:10]:
            print(f"  {difference['path']}", file=sys.stderr)
        return 1

    if args.compare:
        expected = load_json(args.compare)
        comparison = comparison_payload(expected, current)
        write_output(args.output, rendered_json(comparison, args.compact))
        return 0 if comparison["equal"] else 1

    write_output(args.output, rendered_json(current, args.compact))
    if args.output != "-":
        print(
            f"wrote {args.output} ({current['digest']['value']})",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
