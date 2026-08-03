#!/usr/bin/env python3
"""Emit the compact, authored-source OWBD v40 wire member.

The normal path reads only the separately frozen v39 artifact and the checked
stable-ID registry.  It never imports the live viewer/exporter and never emits
the 67 resolved outputs, 296 conclusion stacks, or 22,272 context results.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
from pathlib import Path

from overworld_wild_behavior_v39_frozen import load_frozen
from overworld_wild_behavior_v40_field_metadata import (
    SIGNED_DELTA_OPERATORS,
    operator_allowed,
    scalar_value_valid,
    state_body_values_valid,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "OverworldWildBehaviorV40StableIds.json"
REGISTRY_MANIFEST = ROOT / "data" / "OverworldWildBehaviorV40StableIds.manifest.json"
DEFAULT_OUTPUT = ROOT / "data" / "OverworldWildBehaviorDataV40.generated.inc"

MAGIC = 0x4F574244
VERSION = 40
FLAGS = 0x6  # names-hashed + compact authored source
HEADER_SIZE = 216
CHECKSUM_OFFSET = 16
HARD_CAP = 0x3000
SCHEMA_REVISION = b"owbd-v40-authored-r10:candidate-timer-fold:closed-scalar-domains:exact-recovery-topology"
PINNED_REGISTRY_MANIFEST_SHA256 = "42f8ede614c7ff08c967086c7a2fae66cd4c9c6c182bded1a5e1fb48ca8ac5f4"

PROFILE_FIELDS = (
    "chillState", "alertState", "alertEmote", "alertTime", "alertness",
    "attentiveState", "stamina", "tiredState", "restTime", "chillSpeed",
    "attentiveSpeed", "tiredSpeed", "range", "jumpLevel", "profileId",
    "spawnState", "chillAction", "chillTarget", "alertRange",
    "playerAdjacentDirectionMasks", "targetSelector", "movementStyle",
    "alertChance", "spawnDestination", "attentiveBattle", "specialAction",
    "hopAllowNonCardinal", "hopMinDistance", "hopMaxDistance", "hopPause",
    "teleportTime", "teleportPause", "alertSpecialAction", "overworldLimit",
    "spawnDestinationMinDistance", "spawnDestinationMaxDistance",
    "ramAccelerationSteps", "ramMaxSpeed", "chainPauseAction",
    "chillAllowedTile", "attentiveAllowedTile", "tiredAllowedTile",
    "chillAllowedTile2", "attentiveAllowedTile2", "tiredAllowedTile2",
    "attentiveHopAllowNonCardinal", "attentiveHopMinDistance",
    "attentiveHopMaxDistance", "attentiveHopPause", "attentiveTeleportTime",
    "attentiveTeleportPause", "attentiveRamAccelerationSteps",
    "attentiveRamMaxSpeed", "tiredHopAllowNonCardinal",
    "tiredHopMinDistance", "tiredHopMaxDistance", "tiredHopPause",
    "tiredTeleportTime", "tiredTeleportPause", "tiredRamAccelerationSteps",
    "tiredRamMaxSpeed", "hopTime", "attentiveChaseBoostDistance",
    "attentiveChaseBoostSpeed", "hopSpinSpeed", "spawnHopTime",
    "attentiveHopSpinSpeed", "attentiveCircleRadius",
    "attentiveContinueWhenArrived", "attentiveAvoidPreviousTile",
    "chainMovementVariance", "chainPauseVariance",
)
FIELD_INDEX = {name: index for index, name in enumerate(PROFILE_FIELDS)}
ROLE = {"CHILL": 1, "ACTIVE": 2, "TIRED": 3}
OPERATORS = {
    "replace": 1, "relative": 2, "atLeast": 3, "atMost": 4,
    "addAtLeast": 5, "addAtMost": 6,
}
DEAD_DIAGNOSTIC_FIELDS = {"profileId", "attentiveAvoidPreviousTile"}

CONTROLLER_FIELDS = {
    "alertState": 1, "alertEmote": 2, "alertTime": 3, "alertness": 4,
    "alertRange": 5, "alertChance": 6, "stamina": 7,
}
SPAWN_FIELDS = {
    "spawnState": 1, "spawnDestination": 2, "spawnDestinationMinDistance": 3,
    "spawnDestinationMaxDistance": 4, "spawnHopTime": 5,
}
STATE_FIELDS = {
    "chillAction": 1, "movementStyle": 1, "chillTarget": 2, "targetSelector": 2,
    "chillSpeed": 3, "attentiveSpeed": 3, "tiredSpeed": 3, "range": 4,
    "jumpLevel": 5, "chillAllowedTile": 6, "attentiveAllowedTile": 6,
    "tiredAllowedTile": 6, "chillAllowedTile2": 7, "attentiveAllowedTile2": 7,
    "tiredAllowedTile2": 7, "hopAllowNonCardinal": 8,
    "attentiveHopAllowNonCardinal": 8, "tiredHopAllowNonCardinal": 8,
    "hopMinDistance": 9, "attentiveHopMinDistance": 9, "tiredHopMinDistance": 9,
    "hopMaxDistance": 10, "attentiveHopMaxDistance": 10, "tiredHopMaxDistance": 10,
    "hopPause": 11, "attentiveHopPause": 11, "tiredHopPause": 11,
    "hopTime": 12, "hopSpinSpeed": 13, "attentiveHopSpinSpeed": 13,
    "teleportTime": 14, "attentiveTeleportTime": 14, "tiredTeleportTime": 14,
    "teleportPause": 15, "attentiveTeleportPause": 15, "tiredTeleportPause": 15,
    "ramAccelerationSteps": 16, "attentiveRamAccelerationSteps": 16,
    "tiredRamAccelerationSteps": 16, "ramMaxSpeed": 17,
    "attentiveRamMaxSpeed": 17, "tiredRamMaxSpeed": 17,
    "attentiveChaseBoostDistance": 18, "attentiveChaseBoostSpeed": 19,
    "attentiveCircleRadius": 20, "attentiveContinueWhenArrived": 21,
    "chainPauseAction": 23, "chainMovementVariance": 24,
    "chainPauseVariance": 25, "attentiveBattle": 26,
    "playerAdjacentDirectionMasks": 27,
}

# Reviewed v39 field lowering.  This is deliberately explicit: spelling and
# prefixes are not semantic input.  roleMask is CALM=1, ATTENTIVE=2, TIRED=4.
EXPLICIT_ACTION_MAP = {
    "chillState": (5, 1, 1), "attentiveState": (5, 1, 2), "tiredState": (5, 1, 4),
    "chillAction": (1, 1, 1), "movementStyle": (1, 1, 2), "specialAction": (1, 1, 4),
    "chillTarget": (1, 2, 1), "targetSelector": (1, 2, 2),
    "chillSpeed": (1, 3, 1), "attentiveSpeed": (1, 3, 2), "tiredSpeed": (1, 3, 4),
    "range": (1, 4, 7), "jumpLevel": (1, 5, 7),
    "chillAllowedTile": (1, 6, 1), "attentiveAllowedTile": (1, 6, 2), "tiredAllowedTile": (1, 6, 4),
    "chillAllowedTile2": (1, 7, 1), "attentiveAllowedTile2": (1, 7, 2), "tiredAllowedTile2": (1, 7, 4),
    "hopAllowNonCardinal": (1, 8, 1), "attentiveHopAllowNonCardinal": (1, 8, 2), "tiredHopAllowNonCardinal": (1, 8, 4),
    "hopMinDistance": (1, 9, 1), "attentiveHopMinDistance": (1, 9, 2), "tiredHopMinDistance": (1, 9, 4),
    "hopMaxDistance": (1, 10, 1), "attentiveHopMaxDistance": (1, 10, 2), "tiredHopMaxDistance": (1, 10, 4),
    "hopPause": (1, 11, 1), "attentiveHopPause": (1, 11, 2), "tiredHopPause": (1, 11, 4),
    "hopTime": (1, 12, 7), "hopSpinSpeed": (1, 13, 5), "attentiveHopSpinSpeed": (1, 13, 2),
    "teleportTime": (1, 14, 1), "attentiveTeleportTime": (1, 14, 2), "tiredTeleportTime": (1, 14, 4),
    "teleportPause": (1, 15, 1), "attentiveTeleportPause": (1, 15, 2), "tiredTeleportPause": (1, 15, 4),
    "ramAccelerationSteps": (1, 16, 1), "attentiveRamAccelerationSteps": (1, 16, 2), "tiredRamAccelerationSteps": (1, 16, 4),
    "ramMaxSpeed": (1, 17, 1), "attentiveRamMaxSpeed": (1, 17, 2), "tiredRamMaxSpeed": (1, 17, 4),
    "attentiveChaseBoostDistance": (1, 18, 2), "attentiveChaseBoostSpeed": (1, 19, 2),
    "attentiveCircleRadius": (1, 20, 2), "attentiveContinueWhenArrived": (1, 21, 2),
    "chainPauseAction": (1, 23, 7), "chainMovementVariance": (1, 24, 7), "chainPauseVariance": (1, 25, 7),
    "attentiveBattle": (1, 26, 2), "playerAdjacentDirectionMasks": (1, 27, 7),
    "alertState": (2, 1, 0), "alertEmote": (2, 2, 0), "alertTime": (2, 3, 0),
    "alertness": (2, 4, 0), "alertRange": (2, 5, 0), "alertChance": (2, 6, 0), "stamina": (2, 7, 0),
    "spawnState": (3, 1, 0), "spawnDestination": (3, 2, 0),
    "spawnDestinationMinDistance": (3, 3, 0), "spawnDestinationMaxDistance": (3, 4, 0), "spawnHopTime": (3, 5, 0),
    "overworldLimit": (4, 1, 0), "alertSpecialAction": (6, 1, 0), "restTime": (7, 1, 0),
}


def typed_action(field):
    try:
        target, typed_field, _ = EXPLICIT_ACTION_MAP[field]
        return target, typed_field
    except KeyError as error:
        raise ValueError(f"untyped authored action field: {field}") from error


def scalar(value):
    return value.get("value", 0) if isinstance(value, dict) else value


def match_bytes(match):
    return struct.pack("<IH5B", scalar(match["groupMask"]), scalar(match["species"]),
                       scalar(match["terrain"]), scalar(match["minLevel"]),
                       scalar(match["maxLevel"]), scalar(match["shiny"]),
                       scalar(match["behaviorClass"])) + b"\0"


def state_values(source, role_name):
    f = lambda name, default=0: scalar(source.get(name, default))
    prefix = {"CHILL": "chill", "ACTIVE": "attentive", "TIRED": "tired"}[role_name]
    locomotion = {"CHILL": "chillAction", "ACTIVE": "movementStyle", "TIRED": "specialAction"}[role_name]
    target = {"CHILL": "chillTarget", "ACTIVE": "targetSelector", "TIRED": None}[role_name]
    return [
        f(prefix + "State"), f(locomotion), f(target) if target else 0, f(prefix + "Speed"),
        f("range"), f("jumpLevel"), f(prefix + "AllowedTile"), f(prefix + "AllowedTile2"),
        f(("" if role_name == "CHILL" else prefix) + ("HopAllowNonCardinal" if role_name != "CHILL" else "hopAllowNonCardinal")),
        f(("" if role_name == "CHILL" else prefix) + ("HopMinDistance" if role_name != "CHILL" else "hopMinDistance")),
        f(("" if role_name == "CHILL" else prefix) + ("HopMaxDistance" if role_name != "CHILL" else "hopMaxDistance")),
        f(("" if role_name == "CHILL" else prefix) + ("HopPause" if role_name != "CHILL" else "hopPause")),
        f("hopTime"), f("attentiveHopSpinSpeed" if role_name == "ACTIVE" else "hopSpinSpeed"),
        f(("" if role_name == "CHILL" else prefix) + ("TeleportTime" if role_name != "CHILL" else "teleportTime")),
        f(("" if role_name == "CHILL" else prefix) + ("TeleportPause" if role_name != "CHILL" else "teleportPause")),
        f(("" if role_name == "CHILL" else prefix) + ("RamAccelerationSteps" if role_name != "CHILL" else "ramAccelerationSteps")),
        f(("" if role_name == "CHILL" else prefix) + ("RamMaxSpeed" if role_name != "CHILL" else "ramMaxSpeed")),
        f("attentiveChaseBoostDistance") if role_name == "ACTIVE" else 0,
        f("attentiveChaseBoostSpeed") if role_name == "ACTIVE" else 0,
        f("attentiveCircleRadius") if role_name == "ACTIVE" else 0,
        f("attentiveContinueWhenArrived") if role_name == "ACTIVE" else 0,
        (1 if f("attentiveState") == 3 and f("targetSelector") != 1 else 0)
            if role_name == "ACTIVE" else 0,
        f("chainPauseAction"), f("chainMovementVariance"), f("chainPauseVariance"),
        f("attentiveBattle") if role_name == "ACTIVE" else 0, f("playerAdjacentDirectionMasks"),
    ]


def canonical_body(role_name, values):
    if not state_body_values_valid(bytes(values)):
        raise ValueError(f"authored {role_name} state body is outside its closed scalar domains")
    return bytes(values), 0, 0


def digest_key(prefix, payload):
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"


def fixed_ids():
    values = {}
    def add(prefix, start, count):
        for i in range(count): values[f"{prefix}:{i}"] = start + i
    add("controller", 0x3001, 3); add("node", 0x3101, 21)
    add("spawn", 0x4001, 3); add("population", 0x4101, 6); add("hook", 0x4201, 3)
    add("override", 0x5001, 11); add("override-action", 0x6001, 204)
    add("assignment-action", 0x5401, 3)
    add("definition", 0x7001, 19)
    for i in range(1, 11): values[f"owner:{i}"] = 0x8101 + i
    add("transition", 0xA001, 26); add("guard", 0xB001, 26)
    add("operation", 0xC001, 35); add("transition-action", 0xD001, 32)
    add("exact-calm-operation", 0xC02D, 18)
    add("exact-cooldown-action", 0xD02A, 9)
    add("recovery", 0xE001, 15); add("import", 0xF001, 12)
    add("applicability", 0xF101, 19); add("tired-translation", 0xF201, 18)
    add("assignment", 0x5301, 115)
    add("provenance", 0x9001, 7); add("custom-role", 0x9201, 3)
    add("population-group", 0x4501, 6)
    return values


def prepare_registry(data, extend_registry):
    body_payloads, identities = {}, {}
    authored_identity = {}
    for controller_index, class_profile in enumerate(data["classProfiles"]):
        source = class_profile["sourceProfile"]
        for role_name, role in ROLE.items():
            values = state_values(source, role_name)
            body, tag_a, tag_b = canonical_body(role_name, values)
            body_key = f"authored-body:class-{controller_index}:{role_name.lower()}"
            body_payloads[body_key] = (role, body)
            identity_key = f"authored-profile:class-{controller_index}:{role_name.lower()}"
            identities[identity_key] = (body_key, role, tag_a, tag_b)
            authored_identity[(controller_index, role_name)] = identity_key
    carried = state_values(data["classProfiles"][3]["sourceProfile"], "CHILL")
    carried[:4] = [1, 0, 0, 1]
    system_values = {("carried", 0): bytes(carried)}
    for controller_index in range(3):
        follower = state_values(data["classProfiles"][controller_index]["sourceProfile"], "CHILL")
        follower[:4], follower[27] = [3, 1, 6, max(2, follower[3])], 1
        asleep = state_values(data["classProfiles"][controller_index]["sourceProfile"], "TIRED")
        asleep[:4] = [8, 0, 0, max(1, asleep[3])]
        system_values[("follower", controller_index)] = bytes(follower)
        system_values[("asleep", controller_index)] = bytes(asleep)
    system_identity = {}
    for (name, controller_index), body in system_values.items():
        role = {"carried": 5, "follower": 6, "asleep": 4}[name]
        suffix = name if controller_index == 0 else f"{name}:controller-{controller_index}"
        body_key = f"authored-body:system:{suffix}"
        body_payloads[body_key] = (role, body)
        identity_key = f"authored-profile:system:{suffix}"
        tag_a = {"follower": 12, "asleep": 13, "carried": 14}[name]
        identities[identity_key] = (body_key, role, tag_a, 0 if name == "carried" else controller_index + 1)
        system_identity[(name, controller_index)] = identity_key

    fallback_identity = {}
    for controller_index in range(3):
        values = state_values(data["classProfiles"][controller_index]["sourceProfile"], "TIRED")
        values[0] = 10
        body_key = f"authored-body:fallback:{controller_index}"
        identity_key = f"authored-profile:fallback:{controller_index}"
        body_payloads[body_key] = (7, bytes(values))
        identities[identity_key] = (body_key, 7, 15, controller_index + 1)
        fallback_identity[controller_index] = identity_key

    override_identity = {}
    state_role = {"chillState": "CHILL", "attentiveState": "ACTIVE", "tiredState": "TIRED"}
    for override_index, override in enumerate(data["overrides"]):
        for operation in override["operations"]:
            if operation["field"] not in state_role:
                continue
            role_name = state_role[operation["field"]]
            for controller_index in range(3):
                values = state_values(data["classProfiles"][controller_index]["sourceProfile"], role_name)
                values[0] = scalar(operation["value"])
                values[22] = 1 if role_name == "ACTIVE" and values[0] == 3 and values[2] != 1 else 0
                body_key = f"authored-body:override-{override_index}:controller-{controller_index}:{role_name.lower()}"
                identity_key = f"authored-profile:override-{override_index}:controller-{controller_index}:{role_name.lower()}"
                body_payloads[body_key] = (ROLE[role_name], bytes(values))
                identities[identity_key] = (body_key, ROLE[role_name], override_index + 1, controller_index + 1)
                override_identity[(override_index, controller_index, role_name)] = identity_key

    for body_key, (_role, body) in body_payloads.items():
        if not state_body_values_valid(body):
            raise ValueError(f"state body is outside its closed scalar domains: {body_key}")

    required = fixed_ids()
    for index, key in enumerate(body_payloads):
        if key.startswith("authored-body:class-3:"):
            required[key] = 0x120D + ("chill", "active", "tired").index(key.rsplit(":", 1)[1])
        elif key.startswith("authored-body:system:"):
            suffix = key.split("authored-body:system:", 1)[1]
            if suffix in ("carried", "follower", "asleep"):
                required[key] = 0x120A + ("carried", "follower", "asleep").index(suffix)
            else:
                name, controller = suffix.split(":controller-")
                required[key] = 0x1250 + (int(controller) - 1) * 2 + (0 if name == "follower" else 1)
        elif key.startswith("authored-body:fallback:"):
            required[key] = 0x1210 + int(key.rsplit(":", 1)[1])
        elif key.startswith("authored-body:override-"):
            required[key] = 0x1301 + len([item for item in required if item.startswith("authored-body:override-")])
        else:
            controller, role_name = key.split(":")[1:]
            required[key] = 0x1201 + int(controller[-1]) * 3 + ("chill", "active", "tired").index(role_name)
    for key in identities:
        body_key = identities[key][0]
        required[key] = required[body_key] + 0x1000
    if not REGISTRY.exists():
        raise ValueError("stable-ID registry missing; append-only allocation cannot bootstrap over history")
    registry_raw = REGISTRY.read_bytes()
    if not REGISTRY_MANIFEST.exists():
        raise ValueError("independent stable-ID registry manifest missing")
    manifest_raw = REGISTRY_MANIFEST.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != PINNED_REGISTRY_MANIFEST_SHA256:
        raise ValueError("stable-ID registry manifest differs from independently pinned history")
    registry_manifest = json.loads(manifest_raw)
    if registry_manifest.get("registrySha256") != hashlib.sha256(registry_raw).hexdigest():
        raise ValueError("stable-ID registry history hash does not match pinned manifest")
    registry = json.loads(registry_raw)
    ids = registry.get("ids", {})
    tombstones = registry.get("tombstones")
    if (registry.get("schema") != 3 or not isinstance(tombstones, list)
            or len(tombstones) != len(set(tombstones)) or any(key not in ids for key in tombstones)):
        raise ValueError("stable-ID registry tombstone history is malformed")
    if (registry_manifest.get("schema") != 1 or registry_manifest.get("registryCount") != len(ids)
            or registry_manifest.get("tombstoneCount") != len(tombstones)):
        raise ValueError("stable-ID registry manifest metadata mismatch")
    conflicts = {key: (ids[key], value) for key, value in required.items() if key in ids and ids[key] != value}
    if conflicts:
        raise ValueError(f"stable-ID registry allocation changed: {next(iter(conflicts.items()))}")
    reactivated = sorted(set(required).intersection(tombstones))
    if reactivated:
        raise ValueError(f"required stable-ID key is a historical tombstone: {reactivated[0]}")
    missing = {key: value for key, value in required.items() if key not in ids}
    if missing and not extend_registry:
        raise ValueError(f"stable-ID registry requires explicit append-only extension: {next(iter(missing))}")
    if missing:
        used = set(ids.values())
        if used.intersection(missing.values()):
            raise ValueError("append-only stable-ID allocation collides with historical/tombstoned ID")
        ids.update(missing)
        registry["schema"] = 3
        REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
        raise ValueError("registry extended; independently review and repin its manifest before generation")
    updated_tombstones = registry_tombstone_update(ids, tombstones, required, extend_registry)
    if updated_tombstones != tombstones:
        registry["tombstones"] = updated_tombstones
        REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
        raise ValueError("registry tombstones appended; independently review and repin its manifest")
    if len(ids.values()) != len(set(ids.values())) or any(not 0 < value <= 0xFFFF for value in ids.values()):
        raise ValueError("stable-ID registry contains a collision or invalid ID")
    return ids, body_payloads, identities, system_identity, authored_identity, fallback_identity, override_identity


def registry_tombstone_update(ids, tombstones, required, extend_registry):
    historical = set(tombstones)
    live = set(required)
    reactivated = sorted(historical.intersection(live))
    if reactivated:
        raise ValueError(f"required stable-ID key is a historical tombstone: {reactivated[0]}")
    unclaimed = set(ids) - live
    missing_history = sorted(historical - unclaimed)
    if missing_history:
        raise ValueError(f"stable-ID tombstone history is no longer unclaimed: {missing_history[0]}")
    newly_retired = sorted(unclaimed - historical)
    if newly_retired and not extend_registry:
        raise ValueError(f"stable-ID registry has newly unclaimed keys: {newly_retired[:3]}")
    return list(tombstones) + newly_retired


def assert_destructive_registry_history_rejected():
    registry = json.loads(REGISTRY.read_text())
    victim = registry["tombstones"][0]
    registry["tombstones"].remove(victim)
    del registry["ids"][victim]
    mutated = (json.dumps(registry, indent=2, sort_keys=True) + "\n").encode()
    sibling = (json.dumps({"registryCount": len(registry["ids"]),
                           "registrySha256": hashlib.sha256(mutated).hexdigest(),
                           "schema": 1, "tombstoneCount": len(registry["tombstones"])},
                          indent=2, sort_keys=True) + "\n").encode()
    if hashlib.sha256(sibling).hexdigest() == PINNED_REGISTRY_MANIFEST_SHA256:
        raise ValueError("destructive registry history unexpectedly matched pinned manifest")
    try:
        registry_tombstone_update({"old": 1, "live": 2}, ["old"], {"old": 1, "live": 2}, True)
    except ValueError:
        pass
    else:
        raise ValueError("historical tombstone reactivation was not rejected")
    appended = registry_tombstone_update(
        {"old": 1, "live": 2, "retired": 3}, ["old"], {"live": 2}, True)
    if appended != ["old", "retired"]:
        raise ValueError("newly retired key did not append after historical tombstones")


def pack_profile(source):
    return bytes(scalar(source[name]) for name in PROFILE_FIELDS)


def transition_guard(trigger):
    if trigger == 1:
        return 2, 1
    if trigger == 3:
        return 6, 3
    return 8, trigger


def generate(data, extend_registry=False):
    if len(data["classProfiles"]) != 4 or len(data["classRules"]) != 115 or len(data["overrides"]) != 11:
        raise ValueError("frozen authored-source counts changed")
    ids, body_payloads, identities, system_identity, authored_identity, fallback_identity, override_identity = prepare_registry(data, extend_registry)

    bodies = []
    for key in sorted(body_payloads, key=lambda item: ids[item]):
        role, values = body_payloads[key]
        bodies.append(struct.pack("<HBB28s", ids[key], role, len(values), values.ljust(28, b"\0")))
    identity_records = []
    for key in sorted(identities, key=lambda item: ids[item]):
        body_key, role, tag_a, tag_b = identities[key]
        identity_records.append(struct.pack("<HHHBB", ids[key], ids[body_key], ids[f"provenance:{role - 1}"], tag_a, tag_b))

    def identity_for(controller_index, role_name):
        return ids[authored_identity[(controller_index, role_name)]]

    base_profiles = [pack_profile(item["sourceProfile"]) for item in data["classProfiles"]]
    generic, species = [], []
    for rule in data["classRules"]:
        behavior_class = scalar(rule["behaviorClass"])
        assignment_id = ids[f"assignment:{rule['order'] - 1}"]
        priority = (0x1000 if rule["storage"] == "full" else 0x2000) + rule["order"]
        action_index = behavior_class
        if rule["storage"] == "full":
            generic.append(struct.pack("<H12sHH2x", assignment_id, match_bytes(rule["match"]),
                                       action_index, priority))
        else:
            species.append(struct.pack("<HHHH", assignment_id, scalar(rule["match"]["species"]),
                                       action_index, priority))
    if (len(generic), len(species)) != (2, 113): raise ValueError("assignment split changed")

    controllers, nodes, spawn, population, hooks = [], [], [], [], []
    for index in range(3):
        source = data["classProfiles"][index]["sourceProfile"]
        controller_values = [scalar(source[name]) for name in
                             ("alertState", "alertEmote", "alertTime", "alertness",
                              "alertRange", "alertChance", "stamina")]
        if not all(scalar_value_valid(5, field, value)
                   for field, value in enumerate(controller_values, 1)):
            raise ValueError(f"controller {index} scalar is outside its closed domain")
        spawn_values = [scalar(source[name]) for name in
                        ("spawnState", "spawnDestination", "spawnDestinationMinDistance",
                         "spawnDestinationMaxDistance", "spawnHopTime")]
        if (not all(scalar_value_valid(7, field, value)
                    for field, value in enumerate(spawn_values, 1))
                or spawn_values[2] > spawn_values[3]):
            raise ValueError(f"spawn policy {index} scalar is outside its closed domain")
        if not scalar_value_valid(9, 1, scalar(source["overworldLimit"])):
            raise ValueError(f"population policy {index} limit is outside 0..10")
        controllers.append(struct.pack("<7H10B", ids[f"controller:{index}"], ids[f"controller:{index}"],
            index * 7, 7, ids[f"spawn:{index}"], ids[f"population:{index}"], ids["hook:0"],
            *controller_values, scalar(source["restTime"]), 0, 0))
        for role_index, role_name in enumerate(ROLE):
            nodes.append(struct.pack("<4HBBH", ids[f"node:{index * 7 + role_index}"], ids[f"controller:{index}"],
                identity_for(index, role_name), 0, role_index + 1, 1 if role_index == 0 else 0, 0))
        for offset, (system_name, role) in enumerate((("carried", 5), ("follower", 6), ("asleep", 4))):
            nodes.append(struct.pack("<4HBBH", ids[f"node:{index * 7 + 3 + offset}"], ids[f"controller:{index}"],
                ids[system_identity[(system_name, 0 if system_name == "carried" else index)]], 0, role, 2, 0))
        nodes.append(struct.pack("<4HBBH", ids[f"node:{index * 7 + 6}"], ids[f"controller:{index}"],
            ids[fallback_identity[index]], ids[f"custom-role:{index}"], 7, 6, 0))
        spawn.append(struct.pack("<3H6B", ids[f"spawn:{index}"], ids[f"spawn:{index}"], ids["provenance:0"],
            *spawn_values, 0))
        population.append(struct.pack("<4H2B", ids[f"population:{index}"], ids[f"population:{index}"],
            ids[f"population-group:{index}"], ids[f"provenance:{index}"],
            scalar(source["overworldLimit"]), 0))
        hooks.append(struct.pack("<2H4B", ids[f"hook:{index}"], ids[f"hook:{index}"],
                                 1 if index == 1 else 0,
                                 1 if index == 2 else 0,
                                 1 if index == 2 else 0, 0))

    population_override_policy = {1: 3, 2: 4, 6: 5}
    population_legacy_keys = (0, 1, 2, 5, 6, 10)
    for override_index, policy_index in population_override_policy.items():
        operation = next((op for op in data["overrides"][override_index]["operations"]
                          if op["field"] == "overworldLimit"), None)
        if operation is None:
            raise ValueError(f"population override {override_index} lost its authored limit")
        if not scalar_value_valid(9, 1, scalar(operation["value"])):
            raise ValueError(f"population override {override_index} limit is outside 0..10")
        population.append(struct.pack("<4H2B", ids[f"population:{policy_index}"],
            ids[f"population:{policy_index}"], ids[f"population-group:{policy_index}"],
            ids[f"override:{override_index}"], scalar(operation["value"]), 0))

    override_sources, members, override_action_slices = [], [], {}
    actions = [struct.pack("<HBB8s", ids[f"assignment-action:{index}"], 1, 0,
                           struct.pack("<4H", ids[f"controller:{index}"], 0, 0, 0))
               for index in range(3)]
    diagnostic_counts = {"profileId": 0, "attentiveAvoidPreviousTile": 0}
    for index, override in enumerate(data["overrides"]):
        member_start, action_start = len(members), len(actions)
        members.extend(struct.pack("<H", scalar(item)) for item in override["members"])
        for operation in override["operations"]:
            field = operation["field"]
            if field in DEAD_DIAGNOSTIC_FIELDS:
                diagnostic_counts[field] += 1
                continue
            value = scalar(operation["value"])
            if field in ("chillState", "attentiveState", "tiredState"):
                role_name = {"chillState": "CHILL", "attentiveState": "ACTIVE", "tiredState": "TIRED"}[field]
                role_offset = {"CHILL": 0, "ACTIVE": 1, "TIRED": 2}[role_name]
                for controller_index in range(3):
                    action_id = ids[f"override-action:{len(actions) - 3}"]
                    payload = struct.pack("<4H", ids[f"controller:{controller_index}"],
                                          ids[f"node:{controller_index * 7 + role_offset}"],
                                          ids[override_identity[(index, controller_index, role_name)]], 0)
                    actions.append(struct.pack("<HBB8s", action_id, 2, 0, payload))
                continue
            if field == "alertSpecialAction":
                action_id = ids[f"override-action:{len(actions) - 3}"]
                actions.append(struct.pack("<HBB8s", action_id, 10, 0,
                    struct.pack("<4H", ids[f"hook:{value}"], 0, 0, 0)))
                continue
            if field == "restTime":
                operator_kind = OPERATORS[operation["operator"]]
                signed_value = value if value < 128 else value - 256
                if not operator_allowed(11, 1, operator_kind):
                    raise ValueError(f"candidate timer operator is illegal: {operation['operator']}")
                if operator_kind == 2 and not -32 <= signed_value <= 32:
                    raise ValueError(f"candidate timer ADD is outside -32..32: {signed_value}")
                for controller_index in range(3):
                    action_id = ids[f"override-action:{len(actions) - 3}"]
                    payload = struct.pack("<HHBBH", ids[f"controller:{controller_index}"],
                                          ids[f"node:{controller_index * 7 + 2}"],
                                          operator_kind, value & 0xFF, 0)
                    actions.append(struct.pack("<HBB8s", action_id, 11, 0, payload))
                continue
            if field == "overworldLimit":
                policy_index = population_override_policy.get(index)
                if policy_index is None:
                    raise ValueError(f"unregistered population policy source override {index}")
                action_id = ids[f"override-action:{len(actions) - 3}"]
                actions.append(struct.pack("<HBB8s", action_id, 8, 0,
                    struct.pack("<4H", ids[f"population:{policy_index}"], 0, 0, 0)))
                continue
            lowered = [EXPLICIT_ACTION_MAP[field]]
            lowered_value = value
            for target_kind, typed_field, role_mask in lowered:
                action_id = ids[f"override-action:{len(actions) - 3}"]
                action_kind = {1: 4, 2: 5, 3: 7}[target_kind]
                operator_kind = OPERATORS[operation["operator"]]
                signed_value = lowered_value if lowered_value < 128 else lowered_value - 256
                if not operator_allowed(action_kind, typed_field, operator_kind):
                    raise ValueError(f"operator is illegal for typed field: {field}/{operation['operator']}")
                if operator_kind in SIGNED_DELTA_OPERATORS and not -32 <= signed_value <= 32:
                    raise ValueError(f"typed numeric delta is outside -32..32: {field}/{signed_value}")
                payload = struct.pack("<BBbBBBH", typed_field, operator_kind,
                                      signed_value,
                                      0, role_mask, 0, 0)
                actions.append(struct.pack("<HBB8s", action_id, action_kind, 0, payload))
        override_sources.append(struct.pack("<HH", ids[f"override:{index}"], ids[f"override:{index}"])
            + match_bytes(override["match"])
            + struct.pack("<4HBBH", member_start, len(members) - member_start,
                          action_start, len(actions) - action_start, scalar(override["targetMode"]), override["order"],
                          0x4000 + index))
        override_action_slices[index] = (action_start, len(actions) - action_start)
    if diagnostic_counts != {"profileId": 3, "attentiveAvoidPreviousTile": 2} or len(actions) != 207:
        raise ValueError(f"retired-write diagnostics changed: {diagnostic_counts}, live={len(actions)}")

    owners = [struct.pack("<HHBB", ids[f"owner:{i}"], ids[f"owner:{i}"], 1, 0)
              for i in range(1, 11)]
    # owner, recovery, channel, role, origin, map/battle lifetime,
    # clock/source/hidden policy, recovery policy, timer value
    definition_specs = [
        (0x8102, 0,      1, 2, 0, 2, 1, 0, 0, 0, 0, 0),
        (0x8103, 0,      1, 2, 0, 2, 1, 0, 0, 0, 0, 0),
        (0x8104, 0,      1, 2, 0, 2, 1, 0, 0, 0, 0, 0),
        (0x8105, 0xA003, 2, 3, 0, 2, 1, 1, 3, 1, 1, 4),
        (0x8107, 0xA005, 2, 3, 1, 2, 1, 1, 1, 1, 1, 4),
        (0x8106, 0xA007, 2, 3, 2, 2, 1, 1, 1, 1, 1, 4),
        (0x8108, 0xA009, 2, 3, 3, 2, 1, 1, 1, 1, 1, 4),
        (0x8109, 0,      4, 5, 0, 1, 1, 0, 0, 0, 0, 0),
        (0x810B, 0xA011, 4, 6, 0, 3, 1, 0, 0, 0, 1, 0),
        (0x810A, 0xA00F, 2, 4, 0, 2, 1, 1, 1, 2, 1, 4),
    ]
    definitions, applicability = [], []
    for index, (owner, recovery_id, channel, role, origin, map_life, battle_life,
                clock, timer_source, hidden, recovery_policy, timer_value) in enumerate(definition_specs):
        applicability_id = ids[f"applicability:{index}"]
        applicability.append(struct.pack("<HHIHHBBH", applicability_id, 1, 0xFFFFFFFF,
                                         0, 0, 0, 0, 0))
        priority = (200 if role in (2, 4, 5) else 100)
        generated_owner = owner if index in (3, 4, 5, 6) else 0
        definitions.append(struct.pack("<8H20B", ids[f"definition:{index}"], ids[f"definition:{index}"], 0, 0,
            generated_owner, recovery_id, applicability_id, priority, 1, channel, 2, role, map_life, battle_life, clock,
            timer_source, hidden, recovery_policy, timer_value, 1 if origin else 0, origin,
            1 if generated_owner else 0, 0, 1 if index == 9 else 0, 0, 0, 0, 0))

    # Only the absent-authored-TIRED arm needs a controller-local exact
    # fallback.  The authored-bound arm reuses the portable semantic-origin
    # definitions above, as required by the translation contract.
    for origin in (1, 2, 3):
        for controller_index in range(3):
            index = len(definitions)
            owner = {1: 0x8107, 2: 0x8106, 3: 0x8108}[origin]
            recovery_id = ids[f"transition:{17 + (origin - 1) * 3 + controller_index}"]
            controller_id = ids[f"controller:{controller_index}"]
            node_id = ids[f"node:{controller_index * 7 + 6}"]
            applicability_id = ids[f"applicability:{index}"]
            applicability.append(struct.pack("<HHIHHBBH", applicability_id, 3, 0xFFFFFFFF,
                                             controller_id, 0, 0, 0, 0))
            definitions.append(struct.pack("<8H20B", ids[f"definition:{index}"], ids[f"definition:{index}"],
                controller_id, node_id, owner, recovery_id, applicability_id, 100,
                1, 2, 1, 0, 2, 1, 1, 1, 1, 1, 4, 1, origin, 1, 0, 0,
                0, 1, 0, 0))

    route_specs = [
        (0, 1, "apply", [1, 7, 6]), (3, 2, "apply", [3]), (3, 3, "calm", [2, 4]),
        (4, 6, "apply", [3]), (4, 3, "remove", [2, 4]), (5, 7, "apply", [3]),
        (5, 3, "calm", [2, 4]), (6, 8, "apply", [3]), (6, 3, "calm", [2, 4]),
        (7, 4, "apply", [3]), (7, 5, "remove", [3]), (1, 9, "apply", [1]),
        (2, 10, "apply", [1]), (9, 11, "apply", [3]), (9, 3, "remove", [2]),
        (8, 12, "apply", [3]), (8, 13, "remove", [3]),
    ]
    transitions, guards, operations, typed_actions, recoveries = [], [], [], [], []
    for route_index, (definition_index, trigger, family, action_kinds) in enumerate(route_specs):
        tid, did = ids[f"transition:{route_index}"], ids[f"definition:{definition_index}"]
        owner = definition_specs[definition_index][0]
        op_start = len(operations)
        kind = 1 if family == "apply" else 3
        operations.append(struct.pack("<7H4B", ids[f"operation:{len(operations)}"], tid, did, owner, 0, 0,
                                      did if kind == 1 else 0,
                                      kind, 1, 0 if kind == 1 else 1, 0))
        if family == "calm":
            for calm_owner in (0x8102, 0x8103, 0x8104):
                operations.append(struct.pack("<7H4B", ids[f"operation:{len(operations)}"], tid, 0, calm_owner,
                                              0, 0, 0, 5, 1, 0, 0))
        action_start = len(typed_actions)
        for action_kind in action_kinds:
            typed_actions.append(struct.pack("<HHBBHH", ids[f"transition-action:{len(typed_actions)}"], tid,
                                             2 if family != "apply" else 1, action_kind, 0, 0))
        guard_kind, guard_payload = transition_guard(trigger)
        if trigger == 2 and (guard_kind, guard_payload) != (8, 2):
            raise ValueError(
                "stamina exhaustion must require its exact system route")
        guards.append(struct.pack("<HH4BHH", ids[f"guard:{route_index}"], tid, guard_kind, 0,
                                  guard_payload, 0, 0, 0))
        recovery_start = len(recoveries)
        if route_index in (2, 4, 6, 8, 14, 16):
            recoveries.append(struct.pack("<HHHBB", ids[f"recovery:{len(recoveries)}"], tid, owner,
                                          1 if route_index in (4, 14, 16) else 2, 1))
        transitions.append(struct.pack("<9H4BH", tid, did, owner, route_index, 1, op_start,
            len(operations) - op_start, action_start, len(typed_actions) - action_start,
            trigger, 0x7F, recovery_start, len(recoveries) - recovery_start, 0x2000 + route_index))
    if (len(operations), len(typed_actions), len(recoveries)) != (26, 23, 6):
        raise ValueError("shared transition topology counts changed")
    for wrapper_offset in range(9):
        definition_index = 10 + wrapper_offset
        tid, did = ids[f"transition:{17 + wrapper_offset}"], ids[f"definition:{definition_index}"]
        origin = wrapper_offset // 3 + 1
        owner = {1: 0x8107, 2: 0x8106, 3: 0x8108}[origin]
        guard_start, op_start = len(guards), len(operations)
        action_start, recovery_start = len(typed_actions), len(recoveries)
        guards.append(struct.pack("<HH4BHH", ids[f"guard:{len(guards)}"], tid, 6, 0, 3, 0, 0, 0))
        operations.append(struct.pack("<7H4B", ids[f"operation:{26 + wrapper_offset}"], tid, did, owner,
                                      0, 0, 0, 3, 1, 1, 0))
        if origin in (2, 3):
            for calm_index, calm_owner in enumerate((0x8102, 0x8103, 0x8104)):
                added_index = (wrapper_offset - 3) * 3 + calm_index
                operations.append(struct.pack("<7H4B", ids[f"exact-calm-operation:{added_index}"], tid,
                    0, calm_owner, 0, 0, 0, 5, 1, 0, 0))
        typed_actions.append(struct.pack("<HHBBHH",
            ids[f"transition-action:{23 + wrapper_offset}"], tid, 2, 2, 0, 0))
        typed_actions.append(struct.pack("<HHBBHH",
            ids[f"exact-cooldown-action:{wrapper_offset}"], tid, 2, 4, 0, 0))
        recoveries.append(struct.pack("<HHHBB", ids[f"recovery:{len(recoveries)}"],
            tid, owner, 1 if origin == 1 else 2, 1))
        transitions.append(struct.pack("<9H4BH", tid, did, owner, guard_start, 1, op_start,
            len(operations) - op_start, action_start, len(typed_actions) - action_start,
            3, 1 << (7 - 1), recovery_start, 1, 0x3000 + wrapper_offset))
    if (len(operations), len(typed_actions), len(recoveries)) != (53, 41, 15):
        raise ValueError("exact tired fallback topology counts changed")

    imports = []
    # Semantic sources are serialized, never inferred from a legacy index.
    import_specs = [
        ("carried", 0x8109, 0, 5, 1, None),
        ("follower", 0x810B, 0xA011, 6, 3, 10),
        ("asleep", 0x810A, 0xA00F, 4, 2, 9),
    ]
    for controller_index in range(3):
        for name, owner, recovery_id, role, lifetime, source_override in import_specs:
            index = len(imports)
            node_offset = {"carried": 3, "follower": 4, "asleep": 5}[name]
            action_start, action_count = (0, 0) if source_override is None else override_action_slices[source_override]
            imports.append(struct.pack("<10H4B", ids[f"import:{index}"], owner,
                ids[f"controller:{controller_index}"], ids[f"node:{controller_index * 7 + node_offset}"],
                ids[system_identity[(name, 0 if name == "carried" else controller_index)]], recovery_id,
                0 if source_override is None else ids[f"override:{source_override}"],
                action_start, action_count, 0xFFFF, role, lifetime, 0, 0))
    for role_name, role in ROLE.items():
        index = len(imports)
        imports.append(struct.pack("<10H4B", ids[f"import:{index}"], 0x8109, 0, 0,
            identity_for(3, role_name), 0, 0, 0, 0, 0, role, 1, 1, 0))

    tired_translations = []
    tired_definition = {1: ids["definition:4"], 2: ids["definition:5"], 3: ids["definition:6"]}
    tired_recovery = {1: ids["transition:4"], 2: ids["transition:6"], 3: ids["transition:8"]}
    for origin in (1, 2, 3):
        for controller_index in range(3):
            for authored_bound in (0, 1):
                fallback_definition_index = 10 + (origin - 1) * 3 + controller_index
                candidate_definition_id = (tired_definition[origin] if authored_bound
                    else ids[f"definition:{fallback_definition_index}"])
                recovery_transition_id = (tired_recovery[origin] if authored_bound
                    else ids[f"transition:{17 + (origin - 1) * 3 + controller_index}"])
                tired_translations.append(struct.pack("<HBB6H4B2H",
                    ids[f"tired-translation:{len(tired_translations)}"], origin, authored_bound,
                    ids[f"controller:{controller_index}"],
                    identity_for(controller_index, "TIRED") if authored_bound else ids[fallback_identity[controller_index]],
                    candidate_definition_id, recovery_transition_id,
                    0 if authored_bound else ids[f"controller:{controller_index}"],
                    0 if authored_bound else ids[f"node:{controller_index * 7 + 6}"],
                    1, 1, 2, 1, 0, 0))

    semantic_ids = [struct.pack("<HBBHH", ids[f"provenance:{index}"], 1, index + 1, 0, 0) for index in range(7)] \
        + [struct.pack("<HBBHH", ids[f"custom-role:{index}"], 2, index + 1, 0, 0) for index in range(3)] \
        + [struct.pack("<HBBHH", ids[f"population-group:{index}"], 3,
                       population_legacy_keys[index] + 1, 0, 0) for index in range(6)]
    sections = [
        ("stateBodies", bodies, 32), ("profileIdentities", identity_records, 8),
        ("controllers", controllers, 24), ("controllerNodes", nodes, 12),
        ("sourceClassProfiles", base_profiles, 72), ("genericAssignments", generic, 20),
        ("speciesAssignments", species, 8), ("overrideSources", override_sources, 28),
        ("overrideMembers", members, 2), ("overrideActions", actions, 12),
        ("spawnPolicies", spawn, 12), ("populationPolicies", population, 10),
        ("hookSets", hooks, 8), ("owners", owners, 6), ("overrideDefinitions", definitions, 36),
        ("transitions", transitions, 24), ("transitionGuards", guards, 12),
        ("transitionOperations", operations, 18), ("transitionActions", typed_actions, 10),
        ("recoveryActions", recoveries, 8), ("importRecipes", imports, 24),
        ("applicability", applicability, 16), ("tiredTranslations", tired_translations, 24),
        ("semanticIds", semantic_ids, 8),
    ]
    payload = bytearray(b"\0" * HEADER_SIZE)
    descriptors = []
    for name, records, stride in sections:
        while len(payload) & 3: payload.append(0)
        offset = len(payload)
        for record in records:
            if len(record) != stride: raise ValueError(f"{name} record stride {len(record)} != {stride}")
            payload.extend(record)
        descriptors.append((offset, len(records), stride))
    if len(payload) > HARD_CAP: raise ValueError(f"authored member {len(payload)} exceeds 0x{HARD_CAP:X}")
    wire_directory = ";".join(f"{name}:{stride}" for name, _, stride in sections).encode()
    registry_digest = hashlib.sha256(SCHEMA_REVISION + b";" + wire_directory + b";" + REGISTRY.read_bytes()).digest()
    fingerprint = struct.unpack_from("<I", registry_digest)[0]
    struct.pack_into("<IHHIIII", payload, 0, MAGIC, VERSION, HEADER_SIZE, len(payload), FLAGS, 0, fingerprint)
    for index, descriptor in enumerate(descriptors): struct.pack_into("<IHH", payload, 24 + index * 8, *descriptor)
    checksum = binascii.crc32(payload) & 0xFFFFFFFF
    struct.pack_into("<I", payload, CHECKSUM_OFFSET, checksum)
    counts = {name: len(records) for name, records, _ in sections}
    return bytes(payload), counts, fingerprint, diagnostic_counts


def render_inc(blob):
    lines = ["/* Generated compact authored-source OWBD v40 bytes. */"]
    for offset in range(0, len(blob), 16):
        lines.append("    " + ", ".join(f"0x{value:02X}" for value in blob[offset:offset + 16]) + ",")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extend-registry", action="store_true",
                        help="append reviewed allocations without changing or deleting historical IDs")
    parser.add_argument("--registry-history-self-test", action="store_true")
    args = parser.parse_args()
    blob, counts, fingerprint, diagnostics = generate(load_frozen(), args.extend_registry)
    rendered = render_inc(blob)
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            raise SystemExit(f"stale generated file: {args.output}")
    else:
        args.output.write_text(rendered)
    if args.raw_output: args.raw_output.write_bytes(blob)
    checksum = struct.unpack_from("<I", blob, CHECKSUM_OFFSET)[0]
    print(f"OWBD v40 authored: size={len(blob)} checksum=0x{checksum:08X} fingerprint=0x{fingerprint:08X}")
    print("counts=" + json.dumps(counts, sort_keys=True))
    print("retired diagnostics=" + json.dumps(diagnostics, sort_keys=True))
    if args.registry_history_self_test:
        assert_destructive_registry_history_rejected()
        print("stable-ID history: destructive tombstone/ID deletion plus sibling reseal rejected")


if __name__ == "__main__":
    main()
