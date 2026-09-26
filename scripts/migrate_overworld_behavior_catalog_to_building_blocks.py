#!/usr/bin/env python3
"""Migrate the frozen V4 catalog to the PB0 V5 building-block catalog."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/overworld_behavior_profiles.json"
DEFAULT_MANIFEST = ROOT / "tools/overworld/fixtures/profile_building_blocks_target_v1.json"
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"


def _load_viewer():
    spec = importlib.util.spec_from_file_location("building_block_viewer", VIEWER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = _load_viewer()


def _replace(value):
    return {"operator": "replace", "value": value}


def _relative_minimum(value: int, minimum: int):
    return {
        "operator": "relativeThenAtLeast",
        "value": value,
        "threshold": minimum,
    }


def _ram_capability_fields(source_fields: dict) -> dict:
    """Return the complete field contract owned by the reusable Ram block."""

    fields = {
        key: copy.deepcopy(value)
        for key, value in source_fields.items()
        if key in {
            "alertEmote", "alertTime", "battleTrigger", "walkOptions",
            "walkStompTime", "chainMovementVariance", "chainPauseVariance",
        }
    }
    fields.update({
        "chillTarget": _replace(
            "OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE"
        ),
        "ramAccelerationSteps": _replace(3),
        "ramMaxSpeed": _replace(4),
    })
    return fields


def _without(fields: dict, *names: str) -> dict:
    omitted = set(names)
    return {
        key: copy.deepcopy(value)
        for key, value in fields.items()
        if key not in omitted
    }


def _normal(profile_id: str, name: str, classification: str, fields: dict) -> dict:
    return {
        "id": profile_id,
        "name": name,
        "parent": "default",
        "kind": "normal",
        "classification": classification,
        "fields": copy.deepcopy(fields),
    }


def _conditional(
    profile_id: str,
    name: str,
    classification: str,
    fields: dict,
    conditions: list[dict],
) -> dict:
    profile = _normal(profile_id, name, classification, fields)
    profile["kind"] = "conditional"
    profile["conditions"] = conditions
    return profile


def _target(match: dict, members: list[str]) -> dict:
    return {
        "mode": "members",
        "match": copy.deepcopy(match),
        "members": list(members),
    }


def _subjects(match: dict, members: list[str]) -> dict:
    return _target(match, members)


def _notice(
    condition_id: str,
    subjects: dict,
    target: dict,
    *,
    duration: int,
    cooldown: int,
    kind: str = "notice-target",
) -> dict:
    return {
        "id": condition_id,
        "subjects": copy.deepcopy(subjects),
        "when": {
            "kind": kind,
            "vision": {"mode": "current"},
            "chancePercent": 100,
        },
        "activation": {
            "mode": "timed",
            "durationFrames": duration,
            "cooldownFrames": cooldown,
        },
        "target": copy.deepcopy(target),
    }


def _while_true(
    condition_id: str,
    subjects: dict,
    target: dict,
    *,
    kind: str,
) -> dict:
    return {
        "id": condition_id,
        "subjects": copy.deepcopy(subjects),
        "when": {
            "kind": kind,
            "vision": {"mode": "current"},
            "chancePercent": 100,
        },
        "activation": {"mode": "while-true"},
        "target": copy.deepcopy(target),
    }


def _terrain_condition(
    condition_id: str,
    subjects: dict,
    terrain_mask: str,
) -> dict:
    return {
        "id": condition_id,
        "subjects": copy.deepcopy(subjects),
        "when": {
            "kind": "terrain-motion",
            "terrainMask": terrain_mask,
            "terrainOverrideMask": terrain_mask,
            "minMovementSpeed": 0,
            "maxMovementSpeed": 0,
        },
        "activation": {"mode": "while-true"},
        "target": {"kind": "none"},
    }


def migrate(source: dict, manifest: dict) -> dict:
    if source.get("catalogVersion") == 5:
        migrated = copy.deepcopy(source)
        migrated["runtimeBindings"].pop("pickedUpProfile", None)
        playful = next(
            profile for profile in migrated["profiles"]
            if profile["id"] == "playful"
        )
        playful["fields"]["chillTarget"] = _replace(
            "OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER"
        )
        ram = next(
            profile for profile in migrated["profiles"]
            if profile["id"] == "ram"
        )
        ram["fields"] = _ram_capability_fields(ram["fields"])
        VIEWER.validate_behavior_catalog(migrated)
        return migrated
    if source.get("catalogVersion") != 4:
        raise ValueError("input must be the frozen V4 catalog or the migrated V5 catalog")

    source = VIEWER._behavior_catalog_v4_with_vision_defaults(source)
    VIEWER.validate_behavior_catalog(source)
    profiles = {profile["id"]: profile for profile in source["profiles"]}
    applications = {
        application["id"]: application for application in source["applications"]
    }
    match = VIEWER.default_behavior_match_raws()
    target_manifest = manifest["target"]
    sets = target_manifest["membershipSets"]
    named_pool_members = {
        pool["id"]: pool["members"] for pool in target_manifest["namedPools"]
    }

    def fields(profile_id: str) -> dict:
        return copy.deepcopy(profiles[profile_id]["fields"])

    def members(application_id: str) -> list[str]:
        return list(applications[application_id]["target"]["members"])

    root = copy.deepcopy(profiles["default"])
    root["fields"]["tiredProfile"] = _replace("apply-rest")

    bird_fields = _without(
        fields("bird"),
        "spawnState", "spawnHopTime", "spawnHopSwayWidth",
    )
    flutter_fields = _without(
        fields("flying-insect"),
        "alertEmote", "alertTime", "alertSpecialAction",
        "spawnState", "spawnHopTime", "spawnHopSwayWidth",
    )
    flutter_fields["tiredProfile"] = _replace("apply-rest")
    meander_fields = _without(
        fields("gentle-grazer"),
        "alertEmote", "alertTime",
    )
    hop_around_fields = _without(
        fields("swaying-plant"),
        "tiredProfile", "walkOptions",
    )
    hop_around_fields.update({
        "chillAction": _replace("OW_WILD_BEHAVIOR_LOCOMOTION_HOP"),
        "hopAllowNonCardinal": _replace(
            "OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL"
        ),
        "hopMinDistance": _replace(1),
        "hopMaxDistance": _replace(2),
        "hopPause": _replace(4),
        "hopTime": _replace(7),
    })
    idle_fields = _without(
        fields("ambush-plant"),
        "alertEmote", "alertTime", "tiredProfile",
    )
    idle_fields["tiredProfile"] = _replace("apply-rest")
    scavenger_fields = fields("nervous-scavenger")
    scavenger_fields["tiredProfile"] = _replace("apply-rest")

    playful_fields = {
        "alertEmote": _replace("OW_WILD_SPAWNER_BUBBLE_ID_HEART"),
        "alertTime": _replace(20),
        "chillState": _replace("OW_WILD_BEHAVIOR_KIND_CHASE"),
        "chillTarget": _replace("OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER"),
        "continueWhenArrived": _replace("OW_WILD_BEHAVIOR_BOOL_YES"),
        "circleRadius": _replace(1),
        "chainPauseAction": _replace(
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE"
        ),
        "chainPauseActionChance": _replace(60),
        "chillSpeed": _relative_minimum(-2, 1),
        "hopTime": _relative_minimum(-2, 1),
    }
    ram_fields = _ram_capability_fields(fields("aggressive-ram-override"))

    profiles_v5 = [root]
    profiles_v5.extend([
        _normal("scavenger", "Scavenger", "routine", scavenger_fields),
        _normal("sprint", "Sprint", "routine", fields("runner")),
        _normal("floaty-bounce", "Floaty Bounce", "routine", fields("floaty-bounce")),
        _normal("small-bird-hop", "Small Bird Hop", "routine", bird_fields),
        _normal("erratic-flutter", "Erratic Flutter", "routine", flutter_fields),
        _normal("meander", "Meander", "routine", meander_fields),
        _normal("hop-around", "Hop Around", "routine", hop_around_fields),
        _normal("idle", "Idle", "routine", idle_fields),
        _conditional(
            "perch", "Perch", "routine", fields("bird-rooftop"),
            [_terrain_condition(
                "condition-perch-on-elevated-surface",
                _subjects(match, sets["birds"]),
                "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP | "
                "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST | "
                "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX",
            )],
        ),
        _normal("rest", "Rest", "routine", {}),
        _normal(
            "fly-in", "Fly In", "placement",
            {"spawnState": _replace("OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN")},
        ),
        _normal("canopy-access", "Canopy Access", "placement", fields("canopy-hopper")),
        _normal("flower-bed", "Flower Bed", "placement", fields("flower")),
        _conditional(
            "notice-player", "Notice Player", "capability",
            {
                "alertEmote": _replace("OW_WILD_SPAWNER_BUBBLE_ID_EXCLAMATION_MARK"),
                "alertTime": _replace(10),
            },
            [_notice(
                "condition-notice-player",
                {"mode": "all", "match": copy.deepcopy(match), "members": []},
                {"kind": "player"},
                duration=960,
                cooldown=970,
            )],
        ),
        _normal("teleport", "Teleport", "capability", fields("teleport-stalker-override")),
        _conditional(
            "stalker", "Stalker", "capability",
            {
                "chillState": _replace("OW_WILD_BEHAVIOR_KIND_CHASE"),
                "chillTarget": _replace("OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER"),
                "playerAdjacentDirectionMasks": _replace(
                    "OW_WILD_BEHAVIOR_PLAYER_ADJACENT_BEHIND"
                ),
            },
            [_while_true(
                "condition-stalker-unseen-by-player",
                _subjects(match, sets["teleport-stalker"]),
                {"kind": "player"},
                kind="target-cannot-see-subject",
            )],
        ),
        _normal(
            "long-hop", "Long Hop", "capability",
            {
                key: copy.deepcopy(value)
                for key, value in fields("hopping-scavenger").items()
                if key in {
                    "chillAction", "hopAllowNonCardinal", "hopMinDistance",
                    "hopMaxDistance", "hopPause", "hopTime",
                    "hopElevationTimeScale", "hopElevationArcScale",
                }
            },
        ),
        _conditional(
            "canopy-hop", "Canopy Hop", "capability", fields("canopy-hop-surface"),
            [_terrain_condition(
                "condition-canopy-hop-on-canopy",
                _subjects(match, members("apply-canopy-hopper")),
                "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY",
            )],
        ),
        _conditional(
            "throw", "Throw", "capability", fields("throwing"),
            [_notice(
                "condition-throw-notices-player",
                _subjects(match, members("apply-throwing")),
                {"kind": "player"},
                duration=2880,
                cooldown=2890,
            )],
        ),
        _conditional(
            "ram", "Ram", "capability", ram_fields,
            [_notice(
                "condition-ram-notices-player",
                _subjects(match, members("apply-aggressive-ram-override")),
                {"kind": "player"},
                duration=96,
                cooldown=100,
            )],
        ),
        _conditional(
            "startled", "Startled", "attitude",
            {
                "alertEmote": _replace("OW_WILD_SPAWNER_BUBBLE_ID_EXCLAMATION_MARK"),
                "alertTime": _replace(10),
                "chillState": _replace("OW_WILD_BEHAVIOR_KIND_FLEE"),
                "chillTarget": _replace("OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER"),
            },
            [_notice(
                "condition-startled-notices-player",
                _subjects(
                    match,
                    sets["plant-meander-waddle-startled"]
                    + sets["plant-hop-around-startled"],
                ),
                {"kind": "player"},
                duration=44,
                cooldown=164,
            )],
        ),
        _conditional(
            "ambush", "Ambush", "attitude", fields("ambush-plant-active"),
            [_notice(
                "condition-ambush-notices-player",
                _subjects(match, sets["plant-idle-ambush-rest"]),
                {"kind": "player"},
                duration=36,
                cooldown=126,
            )],
        ),
        _conditional(
            "playful", "Playful", "attitude", playful_fields,
            [
                _notice(
                    "condition-playful-notices-compatible-actor",
                    {"pool": "playful-pokemon"},
                    {
                        "kind": "actor",
                        "roles": ["wild", "follower"],
                        "selection": "nearest",
                        "pool": "playful-pokemon",
                    },
                    duration=420,
                    cooldown=430,
                ),
                _notice(
                    "condition-playful-notices-player",
                    {"pool": "playful-pokemon"},
                    {"kind": "player"},
                    duration=420,
                    cooldown=430,
                ),
            ],
        ),
        _conditional(
            "skittish", "Skittish", "attitude",
            {
                "chillState": _replace("OW_WILD_BEHAVIOR_KIND_FLEE"),
                "chillTarget": _replace("OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER"),
            },
            [_notice(
                "condition-baby-notices-player",
                {"pool": "baby-pokemon"},
                {"kind": "player"},
                duration=960,
                cooldown=970,
            )],
        ),
        _normal(
            "waddle", "Waddle", "style",
            {"walkSwayWidth": _replace(4)},
        ),
        _normal("follower", "Follower", "follower-mount", fields("follower-pokemon")),
        _normal(
            "mounted", "Mounted", "follower-mount",
            {
                "chillSpeed": {"operator": "atMost", "value": 8},
                "tilesToAccelerate": _replace(3),
                "maxWalkSpeed": _replace(2),
                "walkAccelerationStep": _replace(1),
                "walkTimeVariance": _replace(0),
                "tilesBeforeTurnSkid": _replace(1),
                "planTurnSkidPath": _replace("OW_WILD_BEHAVIOR_BOOL_NO"),
                "stopSkid": _replace("OW_WILD_BEHAVIOR_BOOL_NO"),
                "walkPause": _replace(0),
            },
        ),
        _normal("asleep", "Asleep", "modifier", fields("forced-asleep")),
    ])

    direct_members = {
        "apply-scavenger": members("apply-nervous-scavenger"),
        "apply-sprint": members("apply-runner"),
        "apply-floaty-bounce": members("apply-floaty-bounce"),
        "apply-small-bird-hop": sets["birds"],
        "apply-erratic-flutter": sets["flying-insects"],
        "apply-meander": members("apply-gentle-grazer")
            + sets["plant-meander-waddle-startled"],
        "apply-hop-around": sets["plant-hop-around-startled"],
        "apply-idle": sets["plant-idle-ambush-rest"],
        "apply-fly-in": sets["birds"] + sets["flying-insects"],
        "apply-canopy-access": members("apply-canopy-hopper"),
        "apply-flower-bed": members("apply-flower"),
        "apply-teleport": sets["teleport-stalker"],
        "apply-long-hop": members("apply-hopping-scavenger"),
        "apply-waddle": sets["plant-meander-waddle-startled"],
    }
    conditional_profiles = {
        profile["id"] for profile in profiles_v5 if profile["kind"] == "conditional"
    }
    linked_profiles = {"rest", "follower", "mounted", "asleep"}
    applications_v5 = []
    for expected in target_manifest["applications"]:
        application = {"id": expected["id"], "profile": expected["profile"]}
        if expected["profile"] not in conditional_profiles | linked_profiles:
            application["target"] = _target(match, direct_members[expected["id"]])
        applications_v5.append(application)

    selectors = copy.deepcopy(source["selectors"])
    for selector in selectors:
        selector["profile"] = "default"

    result = {
        "catalogVersion": 5,
        "schema": VIEWER.BEHAVIOR_CATALOG_SCHEMA_V5,
        "fieldSchema": source["fieldSchema"],
        "generatedCompatibilityOutput": source["generatedCompatibilityOutput"],
        "rootProfile": "default",
        "profiles": profiles_v5,
        "selectors": selectors,
        "pools": [
            {
                "id": pool["id"],
                "name": pool["name"],
                "mode": "members",
                "match": copy.deepcopy(match),
                "members": copy.deepcopy(named_pool_members[pool["id"]]),
            }
            for pool in target_manifest["namedPools"]
        ],
        "applications": applications_v5,
        "runtimeBindings": {
            "classOrder": copy.deepcopy(target_manifest["classBindings"]),
            "speciesSelectors": copy.deepcopy(
                source["runtimeBindings"]["speciesSelectors"]
            ),
            "followerApplication": "apply-follower",
            "mountedApplication": "apply-mounted",
            "defaultTiredApplication": "apply-rest",
            "forcedAsleepApplication": "apply-asleep",
            "forcedAsleepClassToken": source["runtimeBindings"][
                "forcedAsleepClassToken"
            ],
        },
    }
    VIEWER.validate_behavior_catalog(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    migrated = migrate(source, manifest)
    rendered = json.dumps(migrated, indent=2, ensure_ascii=False) + "\n"
    output = args.output or args.input
    current = output.read_text(encoding="utf-8") if output.exists() else None
    if args.check:
        if current != rendered:
            raise SystemExit(f"building-block migration is not current: {output}")
        return 0
    output.write_text(rendered, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
