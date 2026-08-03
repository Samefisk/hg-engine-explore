#!/usr/bin/env python3
"""Canonical authored model and deterministic OWBD v40 wire codec.

The JSON model is the only authoring input.  The compact binary member is a
projection of that model; legacy profile tables and stable-key registries are
not consulted while encoding.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any, Iterable

try:
    from overworld_wild_behavior_v40_field_metadata import (
        scalar_value_valid,
        state_body_values_valid,
    )
except ModuleNotFoundError:
    from scripts.overworld_wild_behavior_v40_field_metadata import (
        scalar_value_valid,
        state_body_values_valid,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "data" / "OverworldWildBehaviorModelV40.json"
DEFAULT_OUTPUT = ROOT / "data" / "OverworldWildBehaviorDataV40.generated.inc"
DEFAULT_HEADER = ROOT / "include" / "overworld_wild_behavior_data.h"

MAGIC = 0x4F574244
VERSION = 40
HEADER_SIZE = 216
CHECKSUM_OFFSET = 16
HARD_CAP = 0x3000
PINNED_STABLE_HISTORY_CHECKPOINT_SHA256 = (
    "24ad20902f6efa7ef7f3164dd9ff9d84cf5ef1725141a32eb6a3ed2712074a83"
)
PINNED_STABLE_HISTORY_ACCEPTED_HEAD_VERSION = 1
PINNED_STABLE_HISTORY_ACCEPTED_HEAD_SHA256 = (
    "e460674ae4181f270a2430acdeb00e51dab5263f4749eae12543d0f1ae06e445"
)

STATE_FIELDS = (
    "behaviorKind", "locomotion", "target", "speed", "movementRange",
    "jumpLevel", "allowedTile", "allowedTile2", "hopAllowNonCardinal",
    "hopMinDistance", "hopMaxDistance", "hopPause", "hopTimePerTile",
    "hopSpinSpeed", "teleportTime", "teleportPause",
    "ramAccelerationSteps", "ramMaxSpeed", "chaseBoostDistance",
    "chaseBoostSpeed", "circleRadius", "continueWhenArrived",
    "avoidPreviousTile", "chainPauseAction", "chainMovementVariance",
    "chainPauseVariance", "battleTrigger", "playerAdjacentDirectionMask",
)

SOURCE_PROFILE_FIELDS = (
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

SECTIONS = (
    ("stateBodies", 32), ("profileIdentities", 8),
    ("controllers", 24), ("controllerNodes", 12),
    ("sourceClassProfiles", 72), ("genericAssignments", 20),
    ("speciesAssignments", 8), ("overrideSources", 28),
    ("overrideMembers", 2), ("overrideActions", 12),
    ("spawnPolicies", 12), ("populationPolicies", 10),
    ("hookSets", 8), ("owners", 6), ("overrideDefinitions", 36),
    ("transitions", 24), ("transitionGuards", 12),
    ("transitionOperations", 18), ("transitionActions", 10),
    ("recoveryActions", 8), ("importRecipes", 24),
    ("applicability", 16), ("tiredTranslations", 24),
    ("semanticIds", 8),
)


class ModelError(ValueError):
    """The authored model cannot be represented by the v40 wire schema."""


def _record_schema(format_string: str, fields: tuple[str, ...]):
    if len(struct.Struct(format_string).unpack(b"\0" * struct.calcsize(format_string))) != len(fields):
        raise AssertionError(f"field count does not match {format_string}")
    return struct.Struct(format_string), fields


RECORD_SCHEMAS = {
    "speciesAssignments": _record_schema("<HHHH", (
        "stableId", "species", "controllerIndex", "dispatchPriority")),
    "spawnPolicies": _record_schema("<3H6B", (
        "stableId", "nameId", "provenanceId", "spawnState", "destination",
        "minimumDistance", "maximumDistance", "spawnHopTime", "flags")),
    "populationPolicies": _record_schema("<4H2B", (
        "stableId", "nameId", "populationGroupId", "provenanceId", "limit", "flags")),
    "hookSets": _record_schema("<2H4B", (
        "stableId", "nameId", "helpCallInvocation", "pickupThrowEntry",
        "pickupThrowActiveLoop", "flags")),
    "owners": _record_schema("<HHBB", ("stableId", "nameId", "kind", "flags")),
    "overrideDefinitions": _record_schema("<8H20B", (
        "stableId", "nameId", "controllerId", "nodeId", "requiredOwnerId",
        "recoveryTransitionId", "applicabilityId", "priority", "kind", "channel",
        "selectorKind", "semanticRoleId", "mapLifetime", "battleLifetime",
        "timerClock", "timerSource", "hiddenTimerPolicy", "recoveryPolicy",
        "timerValue", "hasTiredOriginKind", "tiredOriginKind",
        "hasRequiredOwnerId", "allowMultipleOwners", "allowMultipleInstancesPerOwner",
        "authoredTiredBound", "flags", "reserved0", "reserved1")),
    "importRecipes": _record_schema("<10H4B", (
        "stableId", "ownerId", "controllerId", "nodeId", "profileId",
        "recoveryTransitionId", "sourceOverrideId", "actionStart", "actionCount",
        "reserved", "semanticRoleId", "lifetime", "contextual", "flags")),
    "applicability": _record_schema("<HHIHHBBH", (
        "stableId", "kind", "groupMask", "controllerId", "profileId",
        "minimum", "maximum", "flags")),
    "tiredTranslations": _record_schema("<HBB6H4B2H", (
        "stableId", "originKind", "authoredBound", "controllerId", "profileId",
        "definitionId", "recoveryTransitionId", "fallbackControllerId",
        "fallbackNodeId", "removeCandidate", "removeCalm", "cooldownKind",
        "required", "flags", "reserved")),
    "semanticIds": _record_schema("<HBBHH", (
        "stableId", "kind", "value", "reserved0", "reserved1")),
}

CONTROLLER_STRUCT, CONTROLLER_FIELDS = _record_schema("<7H10B", (
    "stableId", "nameId", "nodeStart", "nodeCount", "spawnPolicyId",
    "populationPolicyId", "hookSetId", "alertState", "alertEmote", "alertTime",
    "alertness", "alertRange", "alertChance", "stamina", "restTime", "flags0", "flags1"))
NODE_STRUCT, NODE_FIELDS = _record_schema("<4HBBH", (
    "stableId", "controllerId", "profileId", "customRoleId", "semanticRoleId", "flags", "reserved"))
OVERRIDE_ACTION_STRUCT, OVERRIDE_ACTION_FIELDS = _record_schema("<HBB8s", (
    "stableId", "kind", "flags", "payload"))
TRANSITION_STRUCT, TRANSITION_FIELDS = _record_schema("<9H4BH", (
    "stableId", "definitionId", "ownerId", "guardStart", "guardCount",
    "operationStart", "operationCount", "actionStart", "actionCount", "trigger",
    "fromRoleMask", "recoveryStart", "recoveryCount", "dispatchPriority"))
GUARD_STRUCT, GUARD_FIELDS = _record_schema("<HH4BHH", (
    "stableId", "transitionId", "kind", "negate", "payload", "flags", "referenceId", "reserved"))
OPERATION_STRUCT, OPERATION_FIELDS = _record_schema("<7H4B", (
    "stableId", "transitionId", "definitionId", "ownerId",
    "replacementDefinitionId", "policyId", "instanceKey", "kind", "busyPolicy",
    "required", "flags"))
TRANSITION_ACTION_STRUCT, TRANSITION_ACTION_FIELDS = _record_schema("<HHBBHH", (
    "stableId", "transitionId", "phase", "kind", "referenceId", "payload"))
RECOVERY_STRUCT, RECOVERY_FIELDS = _record_schema("<HHHBB", (
    "stableId", "transitionId", "ownerId", "kind", "required"))


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def stable_history_digest(history: dict[str, Any]) -> str:
    payload = {
        "schema": history.get("schema"),
        "allocations": history.get("allocations"),
        "tombstones": history.get("tombstones"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _history_event_digest(previous: str, event: dict[str, Any]) -> str:
    payload = {key: value for key, value in event.items() if key != "eventSha256"}
    raw = previous.encode() + b"\0" + json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def effective_stable_history(history: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    """Authenticate the frozen checkpoint and apply append-only extension events."""
    allocations = history.get("allocations")
    tombstones = history.get("tombstones")
    extensions = history.get("extensions")
    if (history.get("schema") != 3 or not isinstance(allocations, dict)
            or not isinstance(tombstones, list) or not isinstance(extensions, list)):
        raise ModelError("stableIdHistory must contain schema-3 checkpoint data and extensions")
    checkpoint = stable_history_digest(history)
    if checkpoint != PINNED_STABLE_HISTORY_CHECKPOINT_SHA256:
        raise ModelError("stableIdHistory checkpoint differs from the independent pinned history")
    if history.get("checkpointSha256") != PINNED_STABLE_HISTORY_CHECKPOINT_SHA256:
        raise ModelError("stableIdHistory checkpoint declaration is stale")
    if history.get("allocationPolicy") != "append-only-above-high-water-mark":
        raise ModelError("stableIdHistory allocation policy is unsupported")

    effective_allocations = dict(allocations)
    effective_tombstones = list(tombstones)
    previous = checkpoint
    high_water = max(effective_allocations.values(), default=0)
    for index, event in enumerate(extensions):
        if not isinstance(event, dict) or event.get("previousSha256") != previous:
            raise ModelError(f"stableIdHistory extension {index} breaks the append-only chain")
        if event.get("eventSha256") != _history_event_digest(previous, event):
            raise ModelError(f"stableIdHistory extension {index} has a stale event seal")
        kind, key = event.get("kind"), event.get("registryKey")
        if kind == "allocate":
            if not isinstance(key, str) or not key:
                raise ModelError(f"stableIdHistory extension {index} has no registry key")
            stable_id = event.get("stableId")
            if key in effective_allocations or stable_id != high_water + 1 or stable_id > 0xFFFF:
                raise ModelError(f"stableIdHistory extension {index} violates high-water allocation")
            effective_allocations[key] = stable_id
            high_water = stable_id
        elif kind == "retire":
            if not isinstance(key, str) or not key:
                raise ModelError(f"stableIdHistory extension {index} has no registry key")
            if key not in effective_allocations or key in effective_tombstones or "stableId" in event:
                raise ModelError(f"stableIdHistory extension {index} is not an append-only retirement")
            effective_tombstones.append(key)
        elif kind == "checkpoint":
            if (event.get("version") != PINNED_STABLE_HISTORY_ACCEPTED_HEAD_VERSION
                    or set(event) != {"kind", "version", "previousSha256", "eventSha256"}):
                raise ModelError(f"stableIdHistory extension {index} has an invalid checkpoint event")
        else:
            raise ModelError(f"stableIdHistory extension {index} has an unknown kind")
        previous = event["eventSha256"]
    if history.get("historySha256") != previous:
        raise ModelError("stableIdHistory final extension seal is stale")
    if (history.get("acceptedHeadVersion") != PINNED_STABLE_HISTORY_ACCEPTED_HEAD_VERSION
            or previous != PINNED_STABLE_HISTORY_ACCEPTED_HEAD_SHA256):
        raise ModelError("stableIdHistory tail differs from the independently accepted head")
    if history.get("nextUnallocatedId") != high_water + 1:
        raise ModelError("stableIdHistory.nextUnallocatedId does not follow its high-water mark")
    return effective_allocations, effective_tombstones


def load_model(path: Path = DEFAULT_MODEL) -> dict[str, Any]:
    data = json.loads(path.read_text())
    validate_model(data)
    return data


def _integer(value: Any, label: str, maximum: int = 0xFFFF) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ModelError(f"{label} must be an integer in 0..{maximum}")
    return value


def _unique_ids(records: Iterable[dict[str, Any]], label: str) -> set[int]:
    ids: set[int] = set()
    for index, record in enumerate(records):
        stable_id = _integer(record.get("stableId"), f"{label}[{index}].stableId")
        if stable_id == 0 or stable_id in ids:
            raise ModelError(f"{label} contains a zero or duplicate stableId {stable_id}")
        ids.add(stable_id)
    return ids


def _all_records(model: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for profile in model["stateProfiles"]:
        yield "stateProfiles", profile
    for controller in model["controllers"]:
        yield "controllers", controller
        for node in controller["nodes"]:
            yield "controllerNodes", node
    for override in model["overrides"]:
        yield "overrides", override
        for action in override["actions"]:
            yield "overrideActions", action
    for action in model["assignmentActions"]:
        yield "assignmentActions", action
    for transition in model["transitions"]:
        yield "transitions", transition
        for key in ("guards", "operations", "actions", "recoveryActions"):
            for child in transition[key]:
                yield key, child
    for key in (
        "genericAssignments", "speciesAssignments", "spawnPolicies",
        "populationPolicies", "hookSets", "owners", "overrideDefinitions",
        "importRecipes", "applicability", "tiredTranslations", "semanticIds",
    ):
        for record in model[key]:
            yield key, record


def validate_model(model: dict[str, Any]) -> None:
    if model.get("schema") != "overworld-wild-behavior-model-v40" or model.get("modelVersion") != VERSION:
        raise ModelError("canonical model schema/version mismatch")
    wire = model.get("wire", {})
    if wire.get("magic") != MAGIC or wire.get("headerSize") != HEADER_SIZE:
        raise ModelError("wire magic/header contract mismatch")
    _integer(wire.get("flags"), "wire.flags", 0xFFFFFFFF)
    _integer(wire.get("schemaFingerprint"), "wire.schemaFingerprint", 0xFFFFFFFF)

    profiles = model.get("stateProfiles")
    controllers = model.get("controllers")
    if not isinstance(profiles, list) or not isinstance(controllers, list):
        raise ModelError("stateProfiles and controllers must be arrays")
    profile_ids = _unique_ids(profiles, "stateProfiles")
    body_ids: set[int] = set()
    for profile in profiles:
        if "semanticRole" in profile or "semanticRoleId" in profile:
            raise ModelError("semantic roles belong to controller nodes, not profiles")
        body_id = _integer(profile.get("bodyId"), "profile.bodyId")
        if body_id == 0 or body_id in body_ids:
            raise ModelError(f"profile bodyId {body_id} is zero or duplicated")
        body_ids.add(body_id)
        body = profile.get("body")
        if not isinstance(body, dict) or set(body.get("values", {})) != set(STATE_FIELDS):
            raise ModelError(f"profile {profile['stableId']} must own one complete 28-field body")
        provenance_kind = _integer(
            body.get("provenanceKind"), "profile.body.provenanceKind", 0xFF
        )
        if not 1 <= provenance_kind <= 7:
            raise ModelError(f"profile {profile['stableId']} has an unknown provenance kind")
        for name in STATE_FIELDS:
            _integer(body["values"][name], f"profile.body.values.{name}", 0xFF)
        body_values = bytes(body["values"][name] for name in STATE_FIELDS)
        if not state_body_values_valid(body_values):
            raise ModelError(f"profile {profile['stableId']} body violates its closed typed domains")

    controller_ids = _unique_ids(controllers, "controllers")
    node_ids: set[int] = set()
    for controller in controllers:
        for field, name in enumerate((
            "alertState", "alertEmote", "alertTime", "alertness",
            "alertRange", "alertChance", "stamina",
        ), 1):
            value = _integer(controller.get(name), f"controller.{name}", 0xFF)
            if not scalar_value_valid(5, field, value):
                raise ModelError(
                    f"controller {controller['stableId']} field {name} violates its closed typed domain"
                )
        _integer(controller.get("restTime"), "controller.restTime", 0xFF)
        nodes = controller.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ModelError(f"controller {controller['stableId']} must own nodes")
        bases = 0
        selectors: set[tuple[int, int]] = set()
        for node in nodes:
            node_id = _integer(node.get("stableId"), "controller node stableId")
            if node_id == 0 or node_id in node_ids:
                raise ModelError(f"controller node stableId {node_id} is zero or duplicated")
            node_ids.add(node_id)
            if node.get("profileId") not in profile_ids:
                raise ModelError(f"node {node_id} references unknown profile")
            role = _integer(node.get("semanticRoleId"), "node.semanticRoleId", 0xFF)
            custom = _integer(node.get("customRoleId", 0), "node.customRoleId")
            selector = (role, custom)
            if selector in selectors:
                raise ModelError(f"controller {controller['stableId']} has duplicate semantic selector {selector}")
            selectors.add(selector)
            bases += bool(node.get("base"))
        if bases != 1:
            raise ModelError(f"controller {controller['stableId']} must have exactly one base node")

    for policy in model["spawnPolicies"]:
        values = tuple(policy[name] for name in (
            "spawnState", "destination", "minimumDistance", "maximumDistance", "spawnHopTime"
        ))
        if (not all(scalar_value_valid(7, field, value)
                    for field, value in enumerate(values, 1))
                or policy["minimumDistance"] > policy["maximumDistance"]):
            raise ModelError(f"spawn policy {policy['stableId']} violates its closed typed domain")
    for policy in model["populationPolicies"]:
        if not scalar_value_valid(9, 1, policy["limit"]):
            raise ModelError(f"population policy {policy['stableId']} violates its closed typed domain")

    history = model.get("stableIdHistory", {})
    allocations, tombstones = effective_stable_history(history)
    if len(tombstones) != len(set(tombstones)) or any(key not in allocations for key in tombstones):
        raise ModelError("stableIdHistory tombstones are malformed")
    allocation_values = list(allocations.values())
    if len(allocation_values) != len(set(allocation_values)):
        raise ModelError("stableIdHistory contains numeric ID collisions")
    for key, value in allocations.items():
        _integer(value, f"stableIdHistory.allocations[{key!r}]")
        if value == 0:
            raise ModelError("stable ID zero is reserved")
    live_ids: set[int] = set()
    live_owner: dict[int, str] = {}
    for label, record in _all_records(model):
        stable_id = record["stableId"]
        if stable_id in live_ids:
            raise ModelError(
                f"live stable ID {stable_id} is shared by {live_owner[stable_id]} and {label}"
            )
        live_ids.add(stable_id)
        live_owner[stable_id] = label
    for body_id in body_ids:
        if body_id in live_ids:
            raise ModelError(f"state body ID {body_id} collides with {live_owner[body_id]}")
        live_ids.add(body_id)
        live_owner[body_id] = "stateBodies"
    if not live_ids.issubset(set(allocation_values)):
        missing = sorted(live_ids - set(allocation_values))
        raise ModelError(f"live stable IDs are absent from allocation history: {missing[:3]}")
    retired_ids = {allocations[key] for key in tombstones}
    if retired_ids & live_ids:
        raise ModelError(f"tombstoned IDs are live again: {sorted(retired_ids & live_ids)[:3]}")

    live_registry_keys: set[str] = set()
    for label, record in _all_records(model):
        registry_key = record.get("registryKey")
        if (not isinstance(registry_key, str)
                or allocations.get(registry_key) != record["stableId"]
                or registry_key in tombstones):
            raise ModelError(
                f"{label} stableId {record['stableId']} does not match its live registryKey"
            )
        live_registry_keys.add(registry_key)
    for profile in profiles:
        body_key = profile.get("bodyRegistryKey")
        if (not isinstance(body_key, str) or allocations.get(body_key) != profile["bodyId"]
                or body_key in tombstones):
            raise ModelError(
                f"state body {profile['bodyId']} does not match its live registryKey"
            )
        live_registry_keys.add(body_key)
    if "reservedRegistryKeys" in history:
        raise ModelError("stableIdHistory does not permit unauthenticated reservations")
    nonretired_keys = set(allocations) - set(tombstones)
    if nonretired_keys != live_registry_keys:
        unretired = sorted(nonretired_keys - live_registry_keys)
        missing = sorted(live_registry_keys - nonretired_keys)
        raise ModelError(
            f"stableIdHistory requires explicit retirement/allocation events; "
            f"unretired={unretired[:3]} missing={missing[:3]}"
        )

    spawn_ids = {record["stableId"] for record in model["spawnPolicies"]}
    population_ids = {record["stableId"] for record in model["populationPolicies"]}
    hook_ids = {record["stableId"] for record in model["hookSets"]}
    owner_ids = {record["stableId"] for record in model["owners"]}
    definition_ids = {record["stableId"] for record in model["overrideDefinitions"]}
    transition_ids = {record["stableId"] for record in model["transitions"]}
    applicability_ids = {record["stableId"] for record in model["applicability"]}
    override_ids = {record["stableId"] for record in model["overrides"]}
    semantic_by_id: dict[int, tuple[int, int]] = {}
    semantic_by_kind_value: dict[tuple[int, int], int] = {}
    closed_semantic_values = {
        1: frozenset(range(1, 8)),
        2: frozenset(range(1, 4)),
        3: frozenset((1, 2, 3, 6, 7, 11)),
    }
    for record in model["semanticIds"]:
        kind_value = (record["kind"], record["value"])
        if kind_value in semantic_by_kind_value:
            raise ModelError(f"semanticIds duplicates kind/value {kind_value}")
        if record["value"] not in closed_semantic_values.get(record["kind"], ()):
            raise ModelError(f"semanticId {record['stableId']} has an invalid kind/value")
        semantic_by_id[record["stableId"]] = kind_value
        semantic_by_kind_value[kind_value] = record["stableId"]
    expected_semantic_layout = {
        (kind, value) for kind, values in closed_semantic_values.items() for value in values
    }
    if set(semantic_by_kind_value) != expected_semantic_layout:
        raise ModelError("semanticIds does not contain the exact closed kind/value layout")

    def require_reference(value: int, targets: set[int], label: str, *, optional: bool = False) -> None:
        if optional and value == 0:
            return
        if value not in targets:
            raise ModelError(f"{label} references unknown stableId {value}")

    for profile in profiles:
        expected = (1, profile["body"]["provenanceKind"])
        if semantic_by_id.get(profile["provenanceId"]) != expected:
            raise ModelError(
                f"profile {profile['stableId']} provenance does not match body provenance kind"
            )
    for controller in controllers:
        require_reference(controller["spawnPolicyId"], spawn_ids, "controller.spawnPolicyId")
        require_reference(controller["populationPolicyId"], population_ids,
                          "controller.populationPolicyId")
        require_reference(controller["hookSetId"], hook_ids, "controller.hookSetId")
        for node in controller["nodes"]:
            require_reference(node["profileId"], profile_ids, "node.profileId")
            role = node["semanticRoleId"]
            if not 1 <= role <= 7:
                raise ModelError(f"node {node['stableId']} semanticRoleId is outside 1..7")
            custom_role_id = node["customRoleId"]
            if role == 7:
                if semantic_by_id.get(custom_role_id, (0, 0))[0] != 2:
                    raise ModelError(
                        f"custom node {node['stableId']} must reference a custom semanticId"
                    )
            elif custom_role_id != 0:
                raise ModelError(
                    f"noncustom node {node['stableId']} cannot carry a customRoleId"
                )
    for policy in model["spawnPolicies"]:
        if semantic_by_id.get(policy["provenanceId"]) != (1, 1):
            raise ModelError(
                f"spawn policy {policy['stableId']} has the wrong provenance semanticId"
            )
    expected_population_provenance = ((1, 1), (1, 2), (1, 3), 0x5002, 0x5003, 0x5007)
    expected_population_groups = (1, 2, 3, 6, 7, 11)
    for policy_index, policy in enumerate(_sorted(model["populationPolicies"])):
        if semantic_by_id.get(policy["populationGroupId"]) != (
            3, expected_population_groups[policy_index]
        ):
            raise ModelError(
                f"population policy {policy['stableId']} must reference a population-group semanticId"
            )
        expected_provenance = expected_population_provenance[policy_index]
        if (semantic_by_id.get(policy["provenanceId"]) != expected_provenance
                if isinstance(expected_provenance, tuple)
                else policy["provenanceId"] != expected_provenance):
            raise ModelError(
                f"population policy {policy['stableId']} has the wrong provenance"
            )
    for definition in model["overrideDefinitions"]:
        require_reference(definition["controllerId"], controller_ids,
                          "definition.controllerId", optional=True)
        require_reference(definition["nodeId"], node_ids, "definition.nodeId", optional=True)
        require_reference(definition["requiredOwnerId"], owner_ids,
                          "definition.requiredOwnerId", optional=True)
        require_reference(definition["recoveryTransitionId"], transition_ids,
                          "definition.recoveryTransitionId", optional=True)
        require_reference(definition["applicabilityId"], applicability_ids,
                          "definition.applicabilityId")
    for transition in model["transitions"]:
        require_reference(transition["definitionId"], definition_ids,
                          "transition.definitionId")
        require_reference(transition["ownerId"], owner_ids, "transition.ownerId")
        for guard in transition["guards"]:
            require_reference(guard["referenceId"], live_ids, "guard.referenceId", optional=True)
        for operation in transition["operations"]:
            for field in ("definitionId", "replacementDefinitionId"):
                require_reference(operation[field], definition_ids, f"operation.{field}", optional=True)
            require_reference(operation["ownerId"], owner_ids, "operation.ownerId", optional=True)
            require_reference(operation["policyId"], live_ids, "operation.policyId", optional=True)
            require_reference(operation["instanceKey"], live_ids,
                              "operation.instanceKey", optional=True)
        for action in transition["actions"]:
            require_reference(action["referenceId"], live_ids,
                              "transitionAction.referenceId", optional=True)
        for recovery in transition["recoveryActions"]:
            require_reference(recovery["ownerId"], owner_ids, "recovery.ownerId")
    for recipe in model["importRecipes"]:
        require_reference(recipe["ownerId"], owner_ids, "import.ownerId")
        require_reference(recipe["controllerId"], controller_ids,
                          "import.controllerId", optional=True)
        require_reference(recipe["nodeId"], node_ids, "import.nodeId", optional=True)
        require_reference(recipe["profileId"], profile_ids, "import.profileId")
        require_reference(recipe["recoveryTransitionId"], transition_ids,
                          "import.recoveryTransitionId", optional=True)
        require_reference(recipe["sourceOverrideId"], override_ids,
                          "import.sourceOverrideId", optional=True)
    for item in model["applicability"]:
        require_reference(item["controllerId"], controller_ids,
                          "applicability.controllerId", optional=True)
        require_reference(item["profileId"], profile_ids,
                          "applicability.profileId", optional=True)
    for item in model["tiredTranslations"]:
        require_reference(item["controllerId"], controller_ids, "tired.controllerId")
        require_reference(item["profileId"], profile_ids, "tired.profileId")
        require_reference(item["definitionId"], definition_ids, "tired.definitionId")
        require_reference(item["recoveryTransitionId"], transition_ids,
                          "tired.recoveryTransitionId")
        require_reference(item["fallbackControllerId"], controller_ids,
                          "tired.fallbackControllerId", optional=True)
        require_reference(item["fallbackNodeId"], node_ids,
                          "tired.fallbackNodeId", optional=True)

    all_override_actions = model["assignmentActions"] + [
        action for override in model["overrides"] for action in override["actions"]
    ]
    for action in all_override_actions:
        payload = bytes(action["payload"])
        if len(payload) != 8:
            raise ModelError(f"override action {action['stableId']} payload must be exactly 8 bytes")
        words = struct.unpack("<4H", payload)
        if action["kind"] == 1:
            require_reference(words[0], controller_ids, "assignmentAction.controllerId")
        elif action["kind"] == 2:
            require_reference(words[0], controller_ids, "profileAction.controllerId")
            require_reference(words[1], node_ids, "profileAction.nodeId")
            require_reference(words[2], profile_ids, "profileAction.profileId")
        elif action["kind"] == 8:
            require_reference(words[0], population_ids, "populationAction.policyId")
        elif action["kind"] == 10:
            require_reference(words[0], hook_ids, "hookAction.hookSetId")
        elif action["kind"] == 11:
            require_reference(words[0], controller_ids, "timerAction.controllerId")
            require_reference(words[1], node_ids, "timerAction.nodeId")


def _named_record(record: tuple[Any, ...], fields: tuple[str, ...]) -> dict[str, Any]:
    return dict(zip(fields, record))


def _pack_named(record: dict[str, Any], section: str, codec: struct.Struct,
                fields: tuple[str, ...]) -> bytes:
    try:
        values = [record[name] for name in fields]
    except KeyError as error:
        raise ModelError(f"{section} record is missing {error.args[0]}") from error
    try:
        return codec.pack(*values)
    except (struct.error, TypeError) as error:
        raise ModelError(f"{section} record is outside its wire domain: {error}") from error


def _decode_match(raw: bytes) -> dict[str, int]:
    values = struct.unpack("<IH5B", raw[:11])
    return dict(zip(("groupMask", "species", "terrain", "minimumLevel",
                     "maximumLevel", "shiny", "behaviorClass"), values))


def _encode_match(match: dict[str, Any]) -> bytes:
    fields = ("groupMask", "species", "terrain", "minimumLevel", "maximumLevel", "shiny", "behaviorClass")
    try:
        return struct.pack("<IH5B", *(match[name] for name in fields)) + b"\0"
    except (KeyError, struct.error, TypeError) as error:
        raise ModelError(f"invalid match record: {error}") from error


def _decode_sections(blob: bytes) -> dict[str, list[bytes]]:
    if len(blob) < HEADER_SIZE:
        raise ModelError("OWBD blob is truncated")
    magic, version, header_size, size, flags, checksum, fingerprint = struct.unpack_from("<IHHIIII", blob)
    if (magic, version, header_size, size) != (MAGIC, VERSION, HEADER_SIZE, len(blob)):
        raise ModelError("OWBD header is invalid")
    sealed = bytearray(blob)
    struct.pack_into("<I", sealed, CHECKSUM_OFFSET, 0)
    if binascii.crc32(sealed) & 0xFFFFFFFF != checksum:
        raise ModelError("OWBD checksum is invalid")
    sections: dict[str, list[bytes]] = {}
    previous_end = HEADER_SIZE
    for index, (name, expected_stride) in enumerate(SECTIONS):
        offset, count, stride = struct.unpack_from("<IHH", blob, 24 + index * 8)
        end = offset + count * stride
        if stride != expected_stride or offset < previous_end or end > len(blob) or offset & 3:
            raise ModelError(f"OWBD {name} directory entry is invalid")
        if any(blob[previous_end:offset]):
            raise ModelError(f"OWBD {name} alignment padding is not zero")
        sections[name] = [blob[offset + item * stride:offset + (item + 1) * stride]
                          for item in range(count)]
        previous_end = end
    if previous_end != len(blob):
        raise ModelError("OWBD has unclaimed trailing data")
    sections["_wire"] = [{"flags": flags, "schemaFingerprint": fingerprint}]  # type: ignore[list-item]
    return sections


def decode_blob(blob: bytes, *, stable_id_history: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decode an exact wire member into the normalized canonical projection."""
    sections = _decode_sections(blob)
    if stable_id_history is None:
        raise ModelError("decode_blob requires explicit authenticated stable-ID history")
    history = stable_id_history
    allocations, _ = effective_stable_history(history)
    key_by_id = {value: key for key, value in allocations.items()}

    def registry_key(stable_id: int) -> str:
        key = key_by_id.get(stable_id)
        if key is None:
            raise ModelError(f"wire stableId {stable_id} is absent from authenticated history")
        return key

    bodies: dict[int, dict[str, Any]] = {}
    body_order: list[int] = []
    for raw in sections["stateBodies"]:
        stable_id, kind, count, values = struct.unpack("<HBB28s", raw)
        if count != len(STATE_FIELDS):
            raise ModelError(f"state body {stable_id} is not complete")
        bodies[stable_id] = {"provenanceKind": kind, "values": dict(zip(STATE_FIELDS, values))}
        body_order.append(stable_id)
    profiles = []
    used_bodies: set[int] = set()
    for raw in sections["profileIdentities"]:
        stable_id, body_id, provenance_id, tag_a, tag_b = struct.unpack("<HHHBB", raw)
        if body_id not in bodies or body_id in used_bodies:
            raise ModelError(f"profile {stable_id} has an invalid body reference")
        used_bodies.add(body_id)
        identity_registry_key = registry_key(stable_id)
        name, tags = _display_metadata(
            identity_registry_key, stable_id, bodies[body_id]["provenanceKind"]
        )
        profiles.append({
            "stableId": stable_id, "bodyId": body_id, "provenanceId": provenance_id,
            "sourceTags": {"tagA": tag_a, "tagB": tag_b}, "body": bodies[body_id],
            "name": name, "descriptiveTags": tags, "registryKey": identity_registry_key,
            "bodyRegistryKey": registry_key(body_id),
        })
    if used_bodies != set(bodies):
        raise ModelError("every state body must be owned by exactly one profile")

    node_records = [NODE_STRUCT.unpack(raw) for raw in sections["controllerNodes"]]
    claimed_nodes = [False] * len(node_records)
    controllers = []
    for controller_index, raw in enumerate(sections["controllers"]):
        record = _named_record(CONTROLLER_STRUCT.unpack(raw), CONTROLLER_FIELDS)
        start, count = record.pop("nodeStart"), record.pop("nodeCount")
        if start > len(node_records) or count > len(node_records) - start:
            raise ModelError(f"controller {record['stableId']} has an invalid node slice")
        nodes = []
        for index in range(start, start + count):
            if claimed_nodes[index]:
                raise ModelError("controller node slices overlap")
            claimed_nodes[index] = True
            node = _named_record(node_records[index], NODE_FIELDS)
            if node.pop("controllerId") != record["stableId"]:
                raise ModelError("controller node owner does not match its slice")
            flags = node.pop("flags")
            node.update({"base": bool(flags & 1), "optional": bool(flags & 2),
                         "hidden": bool(flags & 4), "flags": flags & ~7,
                         "registryKey": registry_key(node["stableId"])})
            nodes.append(node)
        record.update({"nodes": nodes, "name": f"Controller {controller_index + 1}",
                       "registryKey": registry_key(record["stableId"])})
        controllers.append(record)
    if not all(claimed_nodes):
        raise ModelError("controller node slices do not claim every node")

    source_profiles = []
    for raw in sections["sourceClassProfiles"]:
        source_profiles.append(dict(zip(SOURCE_PROFILE_FIELDS, raw)))

    generic_assignments = []
    for raw in sections["genericAssignments"]:
        stable_id = struct.unpack_from("<H", raw)[0]
        match = _decode_match(raw[2:14])
        controller_index, dispatch_priority = struct.unpack_from("<HH", raw, 14)
        generic_assignments.append({"stableId": stable_id, "match": match,
                                    "controllerIndex": controller_index,
                                    "dispatchPriority": dispatch_priority,
                                    "registryKey": registry_key(stable_id)})
    species_assignments = [_named_record(RECORD_SCHEMAS["speciesAssignments"][0].unpack(raw),
                                         RECORD_SCHEMAS["speciesAssignments"][1])
                           for raw in sections["speciesAssignments"]]
    for assignment in species_assignments:
        assignment["registryKey"] = registry_key(assignment["stableId"])

    member_records = [struct.unpack("<H", raw)[0] for raw in sections["overrideMembers"]]
    override_action_records = [OVERRIDE_ACTION_STRUCT.unpack(raw) for raw in sections["overrideActions"]]
    claimed_members = [False] * len(member_records)
    first_override_action = min(
        (struct.unpack_from("<H", raw, 20)[0] for raw in sections["overrideSources"]),
        default=len(override_action_records),
    )
    assignment_actions = []
    for action_record in override_action_records[:first_override_action]:
        action = _named_record(action_record, OVERRIDE_ACTION_FIELDS)
        action["payload"] = list(action["payload"])
        action["registryKey"] = registry_key(action["stableId"])
        assignment_actions.append(action)
    claimed_actions = [index < first_override_action for index in range(len(override_action_records))]
    overrides = []
    for raw in sections["overrideSources"]:
        stable_id, name_id = struct.unpack_from("<HH", raw)
        member_start, member_count, action_start, action_count, target_mode, order, priority = \
            struct.unpack_from("<4HBBH", raw, 16)
        members = []
        for index in range(member_start, member_start + member_count):
            if index >= len(member_records) or claimed_members[index]:
                raise ModelError(f"override {stable_id} has an invalid member slice")
            claimed_members[index] = True
            members.append(member_records[index])
        actions = []
        for index in range(action_start, action_start + action_count):
            if index >= len(override_action_records) or claimed_actions[index]:
                raise ModelError(f"override {stable_id} has an invalid action slice")
            claimed_actions[index] = True
            action = _named_record(override_action_records[index], OVERRIDE_ACTION_FIELDS)
            action["payload"] = list(action["payload"])
            action["registryKey"] = registry_key(action["stableId"])
            actions.append(action)
        overrides.append({"stableId": stable_id, "nameId": name_id,
                          "match": _decode_match(raw[4:16]), "members": members,
                          "actions": actions, "targetMode": target_mode,
                          "order": order, "dispatchPriority": priority,
                          "registryKey": registry_key(stable_id)})
    if not all(claimed_members) or not all(claimed_actions):
        raise ModelError("override slices do not claim every member/action")

    records: dict[str, list[dict[str, Any]]] = {}
    for section in RECORD_SCHEMAS:
        codec, fields = RECORD_SCHEMAS[section]
        records[section] = [_named_record(codec.unpack(raw), fields) for raw in sections[section]]
        for record in records[section]:
            record["registryKey"] = registry_key(record["stableId"])

    guards = [GUARD_STRUCT.unpack(raw) for raw in sections["transitionGuards"]]
    operations = [OPERATION_STRUCT.unpack(raw) for raw in sections["transitionOperations"]]
    actions = [TRANSITION_ACTION_STRUCT.unpack(raw) for raw in sections["transitionActions"]]
    recoveries = [RECOVERY_STRUCT.unpack(raw) for raw in sections["recoveryActions"]]
    child_sets = (("guards", guards, GUARD_FIELDS), ("operations", operations, OPERATION_FIELDS),
                  ("actions", actions, TRANSITION_ACTION_FIELDS),
                  ("recoveryActions", recoveries, RECOVERY_FIELDS))
    claims = {name: [False] * len(values) for name, values, _ in child_sets}
    transitions = []
    for raw in sections["transitions"]:
        record = _named_record(TRANSITION_STRUCT.unpack(raw), TRANSITION_FIELDS)
        for name, values, fields in child_sets:
            prefix = "recovery" if name == "recoveryActions" else name[:-1] if name.endswith("s") else name
            start, count = record.pop(prefix + "Start"), record.pop(prefix + "Count")
            children = []
            for index in range(start, start + count):
                if index >= len(values) or claims[name][index]:
                    raise ModelError(f"transition {record['stableId']} has an invalid {name} slice")
                claims[name][index] = True
                child = _named_record(values[index], fields)
                if child.pop("transitionId") != record["stableId"]:
                    raise ModelError(f"transition {record['stableId']} does not own {name} child")
                child["registryKey"] = registry_key(child["stableId"])
                children.append(child)
            record[name] = children
        record["registryKey"] = registry_key(record["stableId"])
        transitions.append(record)
    if any(not all(values) for values in claims.values()):
        raise ModelError("transition slices do not claim every child")

    model = {
        "schema": "overworld-wild-behavior-model-v40", "modelVersion": VERSION,
        "wire": {"magic": MAGIC, "headerSize": HEADER_SIZE,
                 "flags": sections["_wire"][0]["flags"],  # type: ignore[index]
                 "schemaFingerprint": sections["_wire"][0]["schemaFingerprint"],  # type: ignore[index]
                 "hardCap": HARD_CAP},
        "stableIdHistory": history,
        "stateProfiles": profiles, "controllers": controllers,
        "sourceClassProfiles": source_profiles,
        "genericAssignments": generic_assignments,
        "speciesAssignments": species_assignments, "assignmentActions": assignment_actions,
        "overrides": overrides, "transitions": transitions,
    }
    for section in RECORD_SCHEMAS:
        if section not in ("speciesAssignments",):
            model[section] = records[section]
    validate_model(model)
    return model


def _display_metadata(registry_key: str, stable_id: int, kind: int) -> tuple[str, list[str]]:
    role_labels = {1: "Calm", 2: "Active", 3: "Tired", 4: "Asleep",
                   5: "Carried", 6: "Follower", 7: "Fallback tired"}
    role = role_labels.get(kind, f"Kind {kind}")
    source = registry_key.removeprefix("authored-profile:")
    parts = [part for part in source.split(":") if part]
    tags = [part.replace("-", " ") for part in parts]
    if parts and parts[0].startswith("class-") and len(parts) >= 2:
        name = f"Class {int(parts[0].removeprefix('class-')) + 1} · {role}"
    elif parts and parts[0].startswith("override-") and len(parts) >= 3:
        name = (f"Override {int(parts[0].removeprefix('override-')) + 1} · "
                f"Controller {int(parts[1].removeprefix('controller-')) + 1} · {role}")
    elif parts[:1] == ["system"]:
        name = " · ".join(part.replace("-", " ").title() for part in parts)
    elif parts[:1] == ["fallback"]:
        name = f"Controller {int(parts[1]) + 1} · Fallback tired"
    else:
        name = f"State profile {stable_id}"
    return name, tags


def _sorted(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: record["stableId"])


def _flatten_model(model: dict[str, Any]) -> dict[str, list[bytes]]:
    validate_model(model)
    output: dict[str, list[bytes]] = {name: [] for name, _ in SECTIONS}
    profiles = _sorted(model["stateProfiles"])
    for profile in sorted(profiles, key=lambda item: item["bodyId"]):
        values = bytes(profile["body"]["values"][name] for name in STATE_FIELDS)
        output["stateBodies"].append(struct.pack("<HBB28s", profile["bodyId"],
                                                  profile["body"]["provenanceKind"], len(values), values))
    for profile in profiles:
        tags = profile["sourceTags"]
        output["profileIdentities"].append(struct.pack("<HHHBB", profile["stableId"],
            profile["bodyId"], profile["provenanceId"], tags["tagA"], tags["tagB"]))

    node_cursor = 0
    for controller in _sorted(model["controllers"]):
        wire = dict(controller)
        nodes = wire.pop("nodes")
        wire["nodeStart"], wire["nodeCount"] = node_cursor, len(nodes)
        output["controllers"].append(_pack_named(wire, "controllers", CONTROLLER_STRUCT, CONTROLLER_FIELDS))
        for node in nodes:
            node_wire = dict(node)
            flags = node_wire.pop("flags", 0) | int(bool(node_wire.pop("base"))) \
                | (int(bool(node_wire.pop("optional"))) << 1) \
                | (int(bool(node_wire.pop("hidden"))) << 2)
            node_wire.update({"controllerId": controller["stableId"], "flags": flags})
            output["controllerNodes"].append(_pack_named(node_wire, "controllerNodes", NODE_STRUCT, NODE_FIELDS))
            node_cursor += 1

    for profile in model["sourceClassProfiles"]:
        try:
            output["sourceClassProfiles"].append(bytes(profile[name] for name in SOURCE_PROFILE_FIELDS))
        except (KeyError, TypeError, ValueError) as error:
            raise ModelError(f"sourceClassProfiles record is invalid: {error}") from error
    for record in _sorted(model["genericAssignments"]):
        output["genericAssignments"].append(struct.pack("<H", record["stableId"])
            + _encode_match(record["match"])
            + struct.pack("<HH2x", record["controllerIndex"], record["dispatchPriority"]))
    for record in _sorted(model["speciesAssignments"]):
        codec, fields = RECORD_SCHEMAS["speciesAssignments"]
        output["speciesAssignments"].append(_pack_named(record, "speciesAssignments", codec, fields))

    member_cursor = 0
    for action in model["assignmentActions"]:
        action_wire = dict(action)
        try:
            action_wire["payload"] = bytes(action_wire["payload"])
        except (TypeError, ValueError) as error:
            raise ModelError(f"assignment action payload is invalid: {error}") from error
        output["overrideActions"].append(_pack_named(
            action_wire, "overrideActions", OVERRIDE_ACTION_STRUCT, OVERRIDE_ACTION_FIELDS))
    action_cursor = len(model["assignmentActions"])
    for override in _sorted(model["overrides"]):
        members, actions = override["members"], override["actions"]
        output["overrideSources"].append(struct.pack("<HH", override["stableId"], override["nameId"])
            + _encode_match(override["match"])
            + struct.pack("<4HBBH", member_cursor, len(members), action_cursor, len(actions),
                          override["targetMode"], override["order"], override["dispatchPriority"]))
        output["overrideMembers"].extend(struct.pack("<H", member) for member in members)
        for action in actions:
            action_wire = dict(action)
            try:
                action_wire["payload"] = bytes(action_wire["payload"])
            except (TypeError, ValueError) as error:
                raise ModelError(f"override action payload is invalid: {error}") from error
            output["overrideActions"].append(_pack_named(
                action_wire, "overrideActions", OVERRIDE_ACTION_STRUCT, OVERRIDE_ACTION_FIELDS))
        member_cursor += len(members)
        action_cursor += len(actions)

    for section, (codec, fields) in RECORD_SCHEMAS.items():
        if section == "speciesAssignments":
            continue
        # Semantic IDs are grouped by kind/value on wire; every other
        # top-level record family uses ascending stable ID order.
        records = (sorted(model[section], key=lambda record: (record["kind"], record["value"]))
                   if section == "semanticIds" else _sorted(model[section]))
        for record in records:
            output[section].append(_pack_named(record, section, codec, fields))

    guard_cursor = operation_cursor = transition_action_cursor = recovery_cursor = 0
    for transition in _sorted(model["transitions"]):
        wire = dict(transition)
        wire.update({"guardStart": guard_cursor, "guardCount": len(transition["guards"]),
                     "operationStart": operation_cursor, "operationCount": len(transition["operations"]),
                     "actionStart": transition_action_cursor, "actionCount": len(transition["actions"]),
                     "recoveryStart": recovery_cursor,
                     "recoveryCount": len(transition["recoveryActions"])})
        output["transitions"].append(_pack_named(wire, "transitions", TRANSITION_STRUCT, TRANSITION_FIELDS))
        child_specs = (
            ("guards", "transitionGuards", GUARD_STRUCT, GUARD_FIELDS),
            ("operations", "transitionOperations", OPERATION_STRUCT, OPERATION_FIELDS),
            ("actions", "transitionActions", TRANSITION_ACTION_STRUCT, TRANSITION_ACTION_FIELDS),
            ("recoveryActions", "recoveryActions", RECOVERY_STRUCT, RECOVERY_FIELDS),
        )
        for model_key, section, codec, fields in child_specs:
            for child in transition[model_key]:
                child_wire = dict(child)
                child_wire["transitionId"] = transition["stableId"]
                output[section].append(_pack_named(child_wire, section, codec, fields))
        guard_cursor += len(transition["guards"])
        operation_cursor += len(transition["operations"])
        transition_action_cursor += len(transition["actions"])
        recovery_cursor += len(transition["recoveryActions"])
    return output


def encode_model(model: dict[str, Any]) -> bytes:
    """Encode the canonical model in stable-ID and nested authored order."""
    sections = _flatten_model(model)
    payload = bytearray(b"\0" * HEADER_SIZE)
    descriptors = []
    for name, stride in SECTIONS:
        while len(payload) & 3:
            payload.append(0)
        offset = len(payload)
        records = sections[name]
        if any(len(record) != stride for record in records):
            raise ModelError(f"{name} contains a record with the wrong stride")
        payload.extend(b"".join(records))
        descriptors.append((offset, len(records), stride))
    if len(payload) > model["wire"].get("hardCap", HARD_CAP):
        raise ModelError(f"authored member {len(payload)} exceeds its hard cap")
    struct.pack_into("<IHHIIII", payload, 0, MAGIC, VERSION, HEADER_SIZE, len(payload),
                     model["wire"]["flags"], 0, model["wire"]["schemaFingerprint"])
    for index, descriptor in enumerate(descriptors):
        struct.pack_into("<IHH", payload, 24 + index * 8, *descriptor)
    struct.pack_into("<I", payload, CHECKSUM_OFFSET, binascii.crc32(payload) & 0xFFFFFFFF)
    return bytes(payload)


def wire_projection(model: dict[str, Any]) -> dict[str, Any]:
    """Return the normalized JSON projection represented by the wire member."""
    return decode_blob(encode_model(model), stable_id_history=model["stableIdHistory"])


def render_inc(blob: bytes) -> str:
    lines = ["/* Generated from OverworldWildBehaviorModelV40.json; do not edit. */"]
    for offset in range(0, len(blob), 16):
        lines.append("    " + ", ".join(f"0x{value:02X}" for value in blob[offset:offset + 16]) + ",")
    return "\n".join(lines) + "\n"


HEADER_COUNT_DEFINES = {
    "OWBD_CLASS_PROFILE_COUNT": "sourceClassProfiles",
    "OWBD_CLASS_RULE_COUNT": "genericAssignments",
    "OWBD_SPECIES_CLASS_RULE_COUNT": "speciesAssignments",
    "OWBD_OVERRIDE_PROFILE_COUNT": "overrideSources",
    "OWBD_OVERRIDE_MEMBER_COUNT": "overrideMembers",
    "OWBD_STATE_BODY_COUNT": "stateBodies",
    "OWBD_PROFILE_IDENTITY_COUNT": "profileIdentities",
    "OWBD_CONTROLLER_COUNT": "controllers",
    "OWBD_CONTROLLER_NODE_COUNT": "controllerNodes",
    "OWBD_TRANSITION_COUNT": "transitions",
    "OWBD_SPAWN_POLICY_COUNT": "spawnPolicies",
    "OWBD_POPULATION_POLICY_COUNT": "populationPolicies",
    "OWBD_HOOK_SET_COUNT": "hookSets",
    "OWBD_OVERRIDE_DEFINITION_COUNT": "overrideDefinitions",
    "OWBD_OVERRIDE_SOURCE_COUNT": "overrideSources",
    "OWBD_OVERRIDE_ACTION_COUNT": "overrideActions",
    "OWBD_OWNER_COUNT": "owners",
    "OWBD_RECOVERY_ACTION_COUNT": "recoveryActions",
    "OWBD_TRANSITION_GUARD_COUNT": "transitionGuards",
    "OWBD_TRANSITION_OPERATION_COUNT": "transitionOperations",
    "OWBD_TRANSITION_ACTION_COUNT": "transitionActions",
    "OWBD_IMPORT_RECIPE_COUNT": "importRecipes",
    "OWBD_APPLICABILITY_COUNT": "applicability",
    "OWBD_TIRED_TRANSLATION_COUNT": "tiredTranslations",
    "OWBD_SEMANTIC_ID_COUNT": "semanticIds",
}


def section_counts(model: dict[str, Any]) -> dict[str, int]:
    flattened = _flatten_model(model)
    return {name: len(records) for name, records in flattened.items()}


def render_header(model: dict[str, Any], blob: bytes, current: str) -> str:
    checksum = struct.unpack_from("<I", blob, CHECKSUM_OFFSET)[0]
    values = {
        "OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE": len(blob),
        "OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM": checksum,
        "OVERWORLD_WILD_BEHAVIOR_DATA_SCHEMA_FINGERPRINT": model["wire"]["schemaFingerprint"],
    }
    counts = section_counts(model)
    for define, section in HEADER_COUNT_DEFINES.items():
        values[define] = counts[section]
    rendered = current
    for name, value in values.items():
        if name.endswith(("CHECKSUM", "FINGERPRINT")):
            replacement = f"0x{value:08X}u"
        elif name == "OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE":
            replacement = f"{value}u"
        else:
            replacement = str(value)
        pattern = rf"(^\s*#\s*define\s+{re.escape(name)}\s+)(?:0[xX][0-9A-Fa-f]+|[0-9]+)(?:u)?\b"
        rendered, count = re.subn(pattern, rf"\g<1>{replacement}", rendered, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ModelError(f"generated header define is missing or duplicated: {name}")
    return rendered


def read_inc(path: Path = DEFAULT_OUTPUT) -> bytes:
    values = re.findall(r"\b0x([0-9A-Fa-f]{2})\b", path.read_text())
    return bytes(int(value, 16) for value in values)


__all__ = [
    "DEFAULT_HEADER", "DEFAULT_MODEL", "DEFAULT_OUTPUT", "HARD_CAP", "ModelError",
    "canonical_json_bytes", "decode_blob", "encode_model", "load_model", "read_inc",
    "render_header", "render_inc", "section_counts", "stable_history_digest",
    "validate_model", "wire_projection",
]
