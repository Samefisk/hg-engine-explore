#!/usr/bin/env python3
"""Canonical authored model and deterministic OWBD v40 wire codec.

The JSON model is the only authoring input.  The compact binary member is a
projection of that model; legacy profile tables and stable-key registries are
not consulted while encoding.
"""

from __future__ import annotations

import binascii
import copy
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path
from typing import Any, Iterable

try:
    from overworld_wild_behavior_v40_field_metadata import (
        numeric_bounds,
        operator_allowed,
        scalar_value_valid,
        state_body_values_valid,
    )
except ModuleNotFoundError:
    from scripts.overworld_wild_behavior_v40_field_metadata import (
        numeric_bounds,
        operator_allowed,
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

SECTIONS = (
    ("stateBodies", 32), ("profileIdentities", 8),
    ("controllers", 24), ("controllerNodes", 12),
    ("genericAssignments", 20),
    ("speciesAssignments", 8), ("overrideSources", 28),
    ("overrideMembers", 2), ("overrideActions", 12),
    ("spawnPolicies", 12), ("populationPolicies", 10),
    ("hookSets", 8), ("owners", 6), ("overrideDefinitions", 36),
    ("modifierOperations", 11),
    ("transitions", 24), ("transitionGuards", 12),
    ("transitionOperations", 18), ("transitionActions", 10),
    ("recoveryActions", 8), ("importRecipes", 24),
    ("applicability", 16), ("tiredTranslations", 24),
    ("semanticIds", 8),
)


def schema_fingerprint() -> int:
    schema = b"OWBD40\0" + json.dumps(
        SECTIONS, separators=(",", ":")
    ).encode("ascii")
    return zlib.crc32(schema) & 0xFFFFFFFF


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
    "modifierOperations": _record_schema("<HHh5B", (
        "stableId", "definitionId", "operand", "fieldNamespace", "fieldId",
        "operatorKind", "bound", "order")),
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


def _state_body_signature(profile: dict[str, Any]) -> tuple[int, tuple[int, ...]]:
    body = profile["body"]
    return (
        body["provenanceKind"],
        tuple(body["values"][name] for name in STATE_FIELDS),
    )


def _validate_promotion_provenance_shape(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "kind", "sourceProfileId", "sourceBodyId", "winningLayer",
        "normalizations", "fieldProvenance",
    }:
        raise ModelError(f"{label} has an invalid bounded shape")
    if value["kind"] != "effective-stack-preview":
        raise ModelError(f"{label}.kind is invalid")
    for key in ("sourceProfileId", "sourceBodyId"):
        if _integer(value[key], f"{label}.{key}") == 0:
            raise ModelError(f"{label}.{key} cannot be zero")
    winning = value["winningLayer"]
    if winning is not None:
        if not isinstance(winning, dict) or set(winning) != {
                "definitionId", "ownerId", "instanceKey"}:
            raise ModelError(f"{label}.winningLayer has an invalid bounded shape")
        for key in ("definitionId", "ownerId", "instanceKey"):
            _integer(winning[key], f"{label}.winningLayer.{key}")
    normalizations = value["normalizations"]
    if not isinstance(normalizations, list) or len(normalizations) > len(STATE_FIELDS):
        raise ModelError(f"{label}.normalizations is invalid")
    for index, record in enumerate(normalizations):
        path = f"{label}.normalizations[{index}]"
        if not isinstance(record, dict) or set(record) != {
                "field", "rule", "before", "after"}:
            raise ModelError(f"{path} has an invalid bounded shape")
        if record["field"] not in STATE_FIELDS or record["rule"] not in {
                "MAX_AT_LEAST_MIN", "DUPLICATE_SECONDARY_TILE"}:
            raise ModelError(f"{path} has an invalid field/rule")
        _integer(record["before"], f"{path}.before", 0xFF)
        _integer(record["after"], f"{path}.after", 0xFF)
    fields = value["fieldProvenance"]
    if not isinstance(fields, dict) or set(fields) != set(STATE_FIELDS):
        raise ModelError(f"{label}.fieldProvenance must contain every state field")
    allowed = {"kind", "profileId", "nodeId", "definitionId", "ownerId", "instanceKey"}
    for field, record in fields.items():
        path = f"{label}.fieldProvenance.{field}"
        if not isinstance(record, dict) or not set(record) <= allowed or "kind" not in record:
            raise ModelError(f"{path} has an invalid bounded shape")
        if record["kind"] not in {"base", "override", "modifier"}:
            raise ModelError(f"{path}.kind is invalid")
        for key in set(record) - {"kind"}:
            _integer(record[key], f"{path}.{key}")
        if record["kind"] in {"base", "override"} and not {
                "profileId", "nodeId"} <= set(record):
            raise ModelError(f"{path} is missing state source identities")
        if record["kind"] == "modifier" and not {
                "definitionId", "ownerId", "instanceKey"} <= set(record):
            raise ModelError(f"{path} is missing modifier source identities")


def intern_state_bodies(
    model: dict[str, Any], *, allow_identity_collapse: bool = False,
) -> tuple[dict[str, Any], int]:
    """Optionally coalesce bodies for one-off imports, never ordinary authoring.

    V51 authoring treats body identity as deliberate: equal values do not imply
    shared ownership.  Callers performing a legacy import must opt in to the
    destructive identity collapse explicitly.
    """
    result = copy.deepcopy(model)
    if not allow_identity_collapse:
        validate_model(result)
        return result, 0
    groups: dict[tuple[int, tuple[int, ...]], list[dict[str, Any]]] = {}
    for profile in result["stateProfiles"]:
        groups.setdefault(_state_body_signature(profile), []).append(profile)
    retirements: dict[int, str] = {}
    for profiles in groups.values():
        representative = min(profiles, key=lambda item: item["bodyId"])
        body_id = representative["bodyId"]
        body_key = representative["bodyRegistryKey"]
        for profile in profiles:
            if profile["bodyId"] != body_id:
                retirements[profile["bodyId"]] = profile["bodyRegistryKey"]
            profile["bodyId"] = body_id
            profile["bodyRegistryKey"] = body_key
            profile["body"] = copy.deepcopy(representative["body"])
    if retirements:
        result["stableIdHistory"], _ = append_stable_history_events(
            result["stableIdHistory"],
            [("retire", retirements[stable_id]) for stable_id in sorted(retirements)],
        )
    validate_model(result)
    return result, len(retirements)


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
    accepted_head_seen = False
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
            if (index != 0 or accepted_head_seen
                    or event.get("version") != PINNED_STABLE_HISTORY_ACCEPTED_HEAD_VERSION
                    or set(event) != {"kind", "version", "previousSha256", "eventSha256"}):
                raise ModelError(f"stableIdHistory extension {index} has an invalid checkpoint event")
            if event["eventSha256"] != PINNED_STABLE_HISTORY_ACCEPTED_HEAD_SHA256:
                raise ModelError("stableIdHistory accepted checkpoint differs from the independent pin")
            accepted_head_seen = True
        else:
            raise ModelError(f"stableIdHistory extension {index} has an unknown kind")
        previous = event["eventSha256"]
    if history.get("historySha256") != previous:
        raise ModelError("stableIdHistory final extension seal is stale")
    if (history.get("acceptedHeadVersion") != PINNED_STABLE_HISTORY_ACCEPTED_HEAD_VERSION
            or not accepted_head_seen):
        raise ModelError("stableIdHistory is missing the independently accepted head checkpoint")
    if history.get("nextUnallocatedId") != high_water + 1:
        raise ModelError("stableIdHistory.nextUnallocatedId does not follow its high-water mark")
    return effective_allocations, effective_tombstones


def append_stable_history_events(
    history: dict[str, Any], events: Iterable[tuple[str, str]]
) -> tuple[dict[str, Any], dict[str, int]]:
    """Append sealed allocation/retirement events without rewriting history.

    Returns an independent history value plus the IDs allocated by this call.
    The frozen checkpoint remains untouched; all new identities are strictly
    above the authenticated high-water mark.
    """
    allocations, tombstones = effective_stable_history(history)
    result = copy.deepcopy(history)
    extensions = result["extensions"]
    previous = result["historySha256"]
    high_water = result["nextUnallocatedId"] - 1
    allocated: dict[str, int] = {}
    retired = set(tombstones)
    for kind, key in events:
        if not isinstance(key, str) or not key:
            raise ModelError("stableIdHistory event has no registry key")
        if kind == "allocate":
            if key in allocations or key in allocated:
                raise ModelError(f"stableIdHistory registry key is already allocated: {key}")
            high_water += 1
            if high_water > 0xFFFF:
                raise ModelError("stableIdHistory exhausted the 16-bit stable ID space")
            event = {
                "kind": "allocate", "registryKey": key, "stableId": high_water,
                "previousSha256": previous,
            }
            allocated[key] = high_water
            allocations[key] = high_water
        elif kind == "retire":
            if key not in allocations or key in retired:
                raise ModelError(f"stableIdHistory registry key cannot be retired: {key}")
            event = {"kind": "retire", "registryKey": key, "previousSha256": previous}
            retired.add(key)
        else:
            raise ModelError(f"stableIdHistory event kind is unsupported: {kind}")
        event["eventSha256"] = _history_event_digest(previous, event)
        extensions.append(event)
        previous = event["eventSha256"]
    result["historySha256"] = previous
    result["nextUnallocatedId"] = high_water + 1
    effective_stable_history(result)
    return result, allocated


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
        "modifierOperations",
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
    if wire.get("schemaFingerprint") != schema_fingerprint():
        raise ModelError("wire schema fingerprint does not match the section contract")

    required_arrays = (
        "stateProfiles", "controllers", "genericAssignments",
        "speciesAssignments", "overrides", "assignmentActions",
        "spawnPolicies", "populationPolicies", "hookSets", "owners",
        "overrideDefinitions", "transitions", "importRecipes",
        "modifierOperations",
        "applicability", "tiredTranslations", "semanticIds",
    )
    for domain in required_arrays:
        if not isinstance(model.get(domain), list):
            raise ModelError(f"{domain} must be an array")

    profiles = model["stateProfiles"]
    controllers = model["controllers"]
    profile_ids = _unique_ids(profiles, "stateProfiles")
    profiles_by_id = {profile["stableId"]: profile for profile in profiles}
    body_ids: set[int] = set()
    bodies_by_id: dict[int, tuple[str, dict[str, Any]]] = {}
    for profile in profiles:
        if "semanticRole" in profile or "semanticRoleId" in profile:
            raise ModelError("semantic roles belong to controller nodes, not profiles")
        body_id = _integer(profile.get("bodyId"), "profile.bodyId")
        if body_id == 0:
            raise ModelError("profile bodyId zero is reserved")
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
        body_key = profile.get("bodyRegistryKey")
        prior = bodies_by_id.get(body_id)
        if prior is not None and prior != (body_key, body):
            raise ModelError(f"shared state body {body_id} has conflicting records")
        bodies_by_id[body_id] = (body_key, body)
        body_ids.add(body_id)
        if "promotionProvenance" in profile:
            _validate_promotion_provenance_shape(
                profile["promotionProvenance"],
                f"profile {profile['stableId']}.promotionProvenance",
            )

    controller_ids = _unique_ids(controllers, "controllers")
    node_ids: set[int] = set()
    nodes_by_id: dict[int, tuple[int, dict[str, Any]]] = {}
    for controller in controllers:
        if controller.get("nameId") != controller["stableId"]:
            raise ModelError("controller nameId must equal its stableId")
        if controller.get("flags0") != 0 or controller.get("flags1") != 0:
            raise ModelError("controller reserved flags must be zero")
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
            nodes_by_id[node_id] = (controller["stableId"], node)
            if node.get("profileId") not in profile_ids:
                raise ModelError(f"node {node_id} references unknown profile")
            role = _integer(node.get("semanticRoleId"), "node.semanticRoleId", 0xFF)
            custom = _integer(node.get("customRoleId", 0), "node.customRoleId")
            selector = (role, custom)
            if selector in selectors:
                raise ModelError(f"controller {controller['stableId']} has duplicate semantic selector {selector}")
            selectors.add(selector)
            for flag in ("base", "optional", "hidden"):
                if not isinstance(node.get(flag), bool):
                    raise ModelError(f"node.{flag} must be boolean")
            if node.get("flags") != 0 or node.get("reserved") != 0:
                raise ModelError("controller node reserved fields must be zero")
            bases += node["base"]
        if bases != 1:
            raise ModelError(f"controller {controller['stableId']} must have exactly one base node")

    for assignment in model["genericAssignments"]:
        _validate_match(assignment.get("match", {}), "genericAssignment.match")
        controller_index = _integer(
            assignment.get("controllerIndex"), "genericAssignment.controllerIndex")
        if controller_index >= len(model["assignmentActions"]):
            raise ModelError("generic assignment references an unknown assignment-action index")
        _integer(assignment.get("dispatchPriority"),
                 "genericAssignment.dispatchPriority")
    assigned_species: set[int] = set()
    for assignment in model["speciesAssignments"]:
        species = _integer(assignment.get("species"), "speciesAssignment.species")
        if species == 0 or species in assigned_species:
            raise ModelError("species assignments must target unique nonzero species")
        assigned_species.add(species)
        controller_index = _integer(
            assignment.get("controllerIndex"), "speciesAssignment.controllerIndex")
        if controller_index >= len(model["assignmentActions"]):
            raise ModelError("species assignment references an unknown assignment-action index")
        _integer(assignment.get("dispatchPriority"),
                 "speciesAssignment.dispatchPriority")

    for policy in model["spawnPolicies"]:
        for name in ("nameId", "provenanceId"):
            _integer(policy.get(name), f"spawnPolicy.{name}")
        if _integer(policy.get("flags"), "spawnPolicy.flags", 0xFF) != 0:
            raise ModelError("spawn policy flags must be zero")
        if policy["nameId"] != policy["stableId"]:
            raise ModelError("spawn policy nameId must equal its stableId")
        values = tuple(policy[name] for name in (
            "spawnState", "destination", "minimumDistance", "maximumDistance", "spawnHopTime"
        ))
        if (not all(scalar_value_valid(7, field, value)
                    for field, value in enumerate(values, 1))
                or policy["minimumDistance"] > policy["maximumDistance"]):
            raise ModelError(f"spawn policy {policy['stableId']} violates its closed typed domain")
    for policy in model["populationPolicies"]:
        for name in ("nameId", "populationGroupId", "provenanceId"):
            _integer(policy.get(name), f"populationPolicy.{name}")
        if _integer(policy.get("flags"), "populationPolicy.flags", 0xFF) != 0:
            raise ModelError("population policy flags must be zero")
        if policy["nameId"] != policy["stableId"]:
            raise ModelError("population policy nameId must equal its stableId")
        if not scalar_value_valid(9, 1, policy["limit"]):
            raise ModelError(f"population policy {policy['stableId']} violates its closed typed domain")
    for hook in model["hookSets"]:
        _integer(hook.get("nameId"), "hookSet.nameId")
        values = tuple(_integer(hook.get(name), f"hookSet.{name}", 1) for name in (
            "helpCallInvocation", "pickupThrowEntry", "pickupThrowActiveLoop",
        ))
        if (hook["nameId"] != hook["stableId"] or hook.get("flags") != 0
                or values[1] != values[2] or (values[0] and values[1])):
            raise ModelError("hook set violates its closed typed domain")
    for owner in model["owners"]:
        _integer(owner.get("nameId"), "owner.nameId")
        kind = _integer(owner.get("kind"), "owner.kind", 0xFF)
        _integer(owner.get("flags"), "owner.flags", 0xFF)
        if (kind != 1 or owner["nameId"] != owner["stableId"]
                or owner["flags"] != 0):
            raise ModelError("owner records must remain system-owned")
    for action in model["assignmentActions"]:
        _integer(action.get("kind"), "assignmentAction.kind", 0xFF)
        if _integer(action.get("flags"), "assignmentAction.flags", 0xFF) != 0:
            raise ModelError("assignment action flags must be zero")
    override_orders: set[int] = set()
    for override in model["overrides"]:
        _integer(override.get("nameId"), "override.nameId")
        _validate_match(override.get("match", {}), "override.match")
        members = override.get("members")
        actions = override.get("actions")
        if not isinstance(members, list) or not isinstance(actions, list):
            raise ModelError("override members/actions must be arrays")
        for member in members:
            if _integer(member, "override.member") == 0:
                raise ModelError("override members cannot contain zero")
        if len(members) != len(set(members)):
            raise ModelError("override members must be unique")
        target_mode = _integer(override.get("targetMode"), "override.targetMode", 2)
        if target_mode == 1 and not members:
            raise ModelError("member-targeted override requires at least one member")
        override_orders.add(_integer(override.get("order"), "override.order", 0xFF))
        _integer(override.get("dispatchPriority"), "override.dispatchPriority")
        if override["nameId"] != override["stableId"]:
            raise ModelError("override nameId must equal its stableId")
        for action in actions:
            _integer(action.get("kind"), "overrideAction.kind", 0xFF)
            if _integer(action.get("flags"), "overrideAction.flags", 0xFF) != 0:
                raise ModelError("override action flags must be zero")
    if override_orders != set(range(1, len(model["overrides"]) + 1)):
        raise ModelError("override order must be one unique contiguous sequence")

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
    for body_id, (body_key, _body) in bodies_by_id.items():
        if (not isinstance(body_key, str) or allocations.get(body_key) != body_id
                or body_key in tombstones):
            raise ModelError(
                f"state body {body_id} does not match its live registryKey"
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
    transition_orders = [
        _integer(record.get("order"), "transition.order")
        for record in model["transitions"]
    ]
    if sorted(transition_orders) != list(range(len(transition_orders))):
        raise ModelError("transition order must be one unique contiguous sequence")
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
        if semantic_by_id.get(profile["provenanceId"], (0, 0))[0] != 1:
            raise ModelError(
                f"profile {profile['stableId']} provenance is not a provenance semanticId"
            )
        promotion = profile.get("promotionProvenance")
        if promotion:
            require_reference(
                promotion["sourceProfileId"], profile_ids,
                "promotion.sourceProfileId",
            )
            require_reference(
                promotion["sourceBodyId"], body_ids,
                "promotion.sourceBodyId",
            )
            winning = promotion["winningLayer"]
            if winning:
                require_reference(
                    winning["definitionId"], definition_ids,
                    "promotion.winningLayer.definitionId",
                )
                require_reference(
                    winning["ownerId"], owner_ids,
                    "promotion.winningLayer.ownerId",
                )
            for record in promotion["fieldProvenance"].values():
                if "profileId" in record:
                    require_reference(record["profileId"], profile_ids,
                                      "promotion.field.profileId")
                if "nodeId" in record:
                    require_reference(record["nodeId"], node_ids,
                                      "promotion.field.nodeId")
                if "definitionId" in record:
                    require_reference(record["definitionId"], definition_ids,
                                      "promotion.field.definitionId")
                if "ownerId" in record:
                    require_reference(record["ownerId"], owner_ids,
                                      "promotion.field.ownerId")
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
    group_limits: dict[int, int] = {}
    for policy in model["populationPolicies"]:
        if semantic_by_id.get(policy["populationGroupId"], (0, 0))[0] != 3:
            raise ModelError(
                f"population policy {policy['stableId']} must reference a population-group semanticId"
            )
        if (semantic_by_id.get(policy["provenanceId"], (0, 0))[0] != 1
                and policy["provenanceId"] not in override_ids):
            raise ModelError(
                f"population policy {policy['stableId']} has the wrong provenance"
            )
        previous_limit = group_limits.setdefault(
            policy["populationGroupId"], policy["limit"]
        )
        if previous_limit != policy["limit"]:
            raise ModelError("population policies disagree on a shared population group limit")
    definitions_by_id = {
        definition["stableId"]: definition
        for definition in model["overrideDefinitions"]
    }
    generated_owner_keys = {
        0: "owner:4",  # stamina
        1: "owner:6",  # battle fled
        2: "owner:5",  # RAM crash
        3: "owner:7",  # throw recovery
    }
    generated_owner_ids = {
        origin: allocations.get(registry_key)
        for origin, registry_key in generated_owner_keys.items()
    }
    if any(owner_id not in owner_ids for owner_id in generated_owner_ids.values()):
        raise ModelError("generated tired owner registry is incomplete")
    expected_owner_ids = {
        allocations.get(f"owner:{index}") for index in range(1, 11)
    }
    if None in expected_owner_ids or owner_ids != expected_owner_ids:
        raise ModelError("system owner registry differs from its frozen allocation set")
    for definition in model["overrideDefinitions"]:
        for name in (
            "nameId", "controllerId", "nodeId", "requiredOwnerId",
            "recoveryTransitionId", "applicabilityId",
        ):
            _integer(definition.get(name), f"definition.{name}")
        priority = _integer(definition.get("priority"), "definition.priority", 0xFF)
        for name in (
            "kind", "channel", "selectorKind", "semanticRoleId",
            "mapLifetime", "battleLifetime", "timerClock", "timerSource",
            "hiddenTimerPolicy", "recoveryPolicy", "timerValue",
            "tiredOriginKind", "flags", "reserved0", "reserved1",
        ):
            _integer(definition.get(name), f"definition.{name}", 0xFF)
        for name in (
            "hasTiredOriginKind", "hasRequiredOwnerId",
            "allowMultipleOwners", "allowMultipleInstancesPerOwner",
            "authoredTiredBound",
        ):
            if _integer(definition.get(name), f"definition.{name}", 1) not in (0, 1):
                raise ModelError(f"definition.{name} must be boolean")
        if definition["kind"] not in (1, 2):
            raise ModelError("definition kind is outside its closed domain")
        if not 0 <= definition["channel"] <= 5:
            raise ModelError("definition channel is outside its closed domain")
        if (definition["kind"] == 1 and definition["selectorKind"] not in (1, 2)):
            raise ModelError("definition selector kind is outside its closed domain")
        if definition["mapLifetime"] not in (1, 2, 3):
            raise ModelError("definition map lifetime is outside its closed domain")
        if definition["battleLifetime"] not in (1, 2, 3):
            raise ModelError("definition battle lifetime is outside its closed domain")
        if (definition["timerClock"] not in (0, 1, 2)
                or definition["timerSource"] not in (0, 1, 2, 3)
                or definition["hiddenTimerPolicy"] not in (0, 1, 2, 3)
                or definition["recoveryPolicy"] not in (0, 1)):
            raise ModelError("definition timer/recovery policy is outside its closed domain")
        timer_present = definition["timerClock"] != 0
        if ((definition["timerSource"] != 0) != timer_present
                or (definition["timerValue"] != 0) != timer_present
                or (definition["hiddenTimerPolicy"] != 0 and not timer_present)
                or ((definition["recoveryPolicy"] != 0)
                    != (definition["recoveryTransitionId"] != 0))):
            raise ModelError("definition timer/recovery fields are noncanonical")
        if definition["reserved0"] != 0 or definition["reserved1"] != 0:
            raise ModelError("definition reserved fields must be zero")
        has_origin = definition["hasTiredOriginKind"]
        origin = definition["tiredOriginKind"]
        has_owner = definition["hasRequiredOwnerId"]
        required_owner = definition["requiredOwnerId"]
        if has_origin != int(origin != 0):
            raise ModelError("definition tired-origin tag/value pair is noncanonical")
        if has_owner != int(required_owner != 0):
            raise ModelError("definition required-owner tag/value pair is noncanonical")
        if has_origin and (origin not in (1, 2, 3) or not has_owner):
            raise ModelError("generated tired origin requires canonical owner metadata")
        generated = bool(has_origin or has_owner)
        if not generated:
            if definition["channel"] == 5:
                raise ModelError("ordinary definitions cannot use System Safety")
            if definition["flags"] != 0 or definition["authoredTiredBound"] != 0:
                raise ModelError("ordinary definition carries generated-only flags")
        else:
            expected_owner = generated_owner_ids.get(origin)
            expected_timer_source = 3 if origin == 0 else 1
            if (expected_owner is None or required_owner != expected_owner
                    or priority != 100 or definition["channel"] != 2
                    or definition["allowMultipleOwners"] != 0
                    or definition["allowMultipleInstancesPerOwner"] != 0
                    or definition["mapLifetime"] != 2
                    or definition["battleLifetime"] != 1
                    or definition["timerClock"] != 1
                    or definition["timerSource"] != expected_timer_source
                    or definition["hiddenTimerPolicy"] != 1
                    or definition["recoveryPolicy"] != 1
                    or definition["timerValue"] != 4
                    or definition["authoredTiredBound"] != 0):
                raise ModelError(
                    "generated tired definition differs from its frozen owner/origin metadata"
                )
            if definition["selectorKind"] not in (1, 2):
                raise ModelError("generated tired definition has an invalid selector")
            if (definition["selectorKind"] == 2
                    and definition["semanticRoleId"] != 3):
                raise ModelError("generated semantic tired definition must select TIRED")
            if (definition["selectorKind"] == 1
                    and definition["semanticRoleId"] != 0):
                raise ModelError("generated exact tired definition cannot carry a role")
            if (definition["selectorKind"] == 2
                    and (definition["controllerId"] != 0
                         or definition["nodeId"] != 0
                         or definition["flags"] != 0)):
                raise ModelError("generated semantic tired definition has exact-selector data")
            if (definition["selectorKind"] == 1
                    and (definition["controllerId"] == 0
                         or definition["nodeId"] == 0
                         or definition["flags"] != 1)):
                raise ModelError("generated exact tired definition is missing fallback data")
        if definition["kind"] == 2:
            if (not 1 <= definition["channel"] <= 4
                    or definition["controllerId"] != 0 or definition["nodeId"] != 0
                    or definition["selectorKind"] != 0
                    or definition["semanticRoleId"] != 0
                    or definition["requiredOwnerId"] != 0
                    or definition["recoveryTransitionId"] != 0
                    or definition["timerClock"] != 0
                    or definition["timerSource"] != 0
                    or definition["hiddenTimerPolicy"] != 0
                    or definition["recoveryPolicy"] != 0
                    or definition["timerValue"] != 0
                    or definition["hasTiredOriginKind"] != 0
                    or definition["tiredOriginKind"] != 0
                    or definition["hasRequiredOwnerId"] != 0
                    or definition["authoredTiredBound"] != 0
                    or definition["flags"] != 0):
                raise ModelError("modifier definition carries candidate or generated metadata")
        elif definition["selectorKind"] == 2:
            if (definition["controllerId"] != 0 or definition["nodeId"] != 0
                    or not 1 <= definition["semanticRoleId"] <= 7):
                raise ModelError("semantic definition selector is noncanonical")
        else:
            node_record = nodes_by_id.get(definition["nodeId"])
            if (definition["semanticRoleId"] != 0 or node_record is None
                    or node_record[0] != definition["controllerId"]):
                raise ModelError("exact definition selector is noncanonical")
        require_reference(definition["controllerId"], controller_ids,
                          "definition.controllerId", optional=True)
        require_reference(definition["nodeId"], node_ids, "definition.nodeId", optional=True)
        require_reference(definition["requiredOwnerId"], owner_ids,
                          "definition.requiredOwnerId", optional=True)
        require_reference(definition["recoveryTransitionId"], transition_ids,
                          "definition.recoveryTransitionId", optional=True)
        require_reference(definition["applicabilityId"], applicability_ids,
                          "definition.applicabilityId")
    modifier_operations_by_definition: dict[int, list[dict[str, Any]]] = {
        stable_id: [] for stable_id in definition_ids
    }
    for operation in model["modifierOperations"]:
        definition_id = _integer(
            operation.get("definitionId"), "modifierOperation.definitionId"
        )
        require_reference(
            definition_id, definition_ids, "modifierOperation.definitionId"
        )
        namespace = _integer(
            operation.get("fieldNamespace"),
            "modifierOperation.fieldNamespace", 0xFF,
        )
        field = _integer(operation.get("fieldId"), "modifierOperation.fieldId", 0xFF)
        operator = _integer(
            operation.get("operatorKind"), "modifierOperation.operatorKind", 0xFF
        )
        bound = _integer(operation.get("bound"), "modifierOperation.bound", 0xFF)
        order = _integer(operation.get("order"), "modifierOperation.order", 0xFF)
        operand = operation.get("operand")
        if (isinstance(operand, bool) or not isinstance(operand, int)
                or not -0x8000 <= operand <= 0x7FFF):
            raise ModelError("modifierOperation.operand must be a signed 16-bit integer")
        kind = {1: 4, 2: 5}.get(namespace)
        if (kind is None or not operator_allowed(kind, field, operator)):
            raise ModelError("modifier operation namespace/field/operator is unsupported")
        if operator in (2, 5, 6):
            if operator == 2 and bound != 0:
                raise ModelError("plain relative modifier operation cannot carry a bound")
            if operator in (5, 6) and not scalar_value_valid(kind, field, bound):
                raise ModelError("compound modifier bound is outside the field domain")
        else:
            if bound != 0 or not scalar_value_valid(kind, field, operand):
                raise ModelError("exact modifier operand/bound is outside the field domain")
        modifier_operations_by_definition[definition_id].append(operation)
    for definition_id, operations in modifier_operations_by_definition.items():
        definition = definitions_by_id[definition_id]
        if definition["kind"] == 1:
            if operations:
                raise ModelError("state-candidate definition cannot own modifier operations")
            continue
        if not 1 <= len(operations) <= 16:
            raise ModelError("modifier definition must own 1..16 operations")
        orders = [operation["order"] for operation in operations]
        if sorted(orders) != list(range(len(operations))):
            raise ModelError("modifier operation order must be one contiguous sequence")
        lower_bounds: set[tuple[int, int]] = set()
        upper_bounds: set[tuple[int, int]] = set()
        for operation in operations:
            field_key = (operation["fieldNamespace"], operation["fieldId"])
            if operation["operatorKind"] == 3:
                lower_bounds.add(field_key)
            elif operation["operatorKind"] == 4:
                upper_bounds.add(field_key)
        if lower_bounds & upper_bounds:
            raise ModelError(
                "modifier definition cannot combine AT_LEAST and AT_MOST on one field"
            )
    for transition in model["transitions"]:
        for name in ("definitionId", "ownerId", "order", "dispatchPriority"):
            _integer(transition.get(name), f"transition.{name}")
        for name in ("trigger", "fromRoleMask"):
            _integer(transition.get(name), f"transition.{name}", 0xFF)
        if (not 1 <= transition["trigger"] <= 13 or not transition["fromRoleMask"]
                or transition["fromRoleMask"] & ~0x7F):
            raise ModelError("transition trigger/from-role mask violates its closed domain")
        require_reference(transition["definitionId"], definition_ids,
                          "transition.definitionId")
        require_reference(transition["ownerId"], owner_ids, "transition.ownerId")
        required_owner = definitions_by_id[transition["definitionId"]]["requiredOwnerId"]
        if required_owner and transition["ownerId"] != required_owner:
            raise ModelError("transition owner is not authorized by its generated definition")
        for child_name in ("guards", "operations", "actions", "recoveryActions"):
            if not isinstance(transition.get(child_name), list):
                raise ModelError(f"transition.{child_name} must be an array")
        for guard in transition["guards"]:
            for name in ("kind", "negate", "payload", "flags"):
                _integer(guard.get(name), f"guard.{name}", 0xFF)
            _integer(guard.get("reserved"), "guard.reserved")
            require_reference(guard["referenceId"], live_ids, "guard.referenceId", optional=True)
            kind = guard["kind"]
            payload = guard["payload"]
            reference = guard["referenceId"]
            if (not 1 <= kind <= 8 or guard["negate"] not in (0, 1)
                    or guard["flags"] != 0 or guard["reserved"] != 0):
                raise ModelError("transition guard violates its closed domain")
            if ((kind == 1 and (payload or reference))
                    or (kind == 2 and (not 1 <= payload <= 7 or reference))
                    or (kind == 3 and (payload or reference not in node_ids))
                    or (kind in (4, 5) and (payload or reference not in owner_ids))
                    or (kind == 6 and (not 1 <= payload <= 3 or reference))
                    or (kind == 7 and (payload > 100 or reference))
                    or (kind == 8 and (not 1 <= payload <= 13 or reference))):
                raise ModelError("transition guard payload/reference is noncanonical")
        for operation in transition["operations"]:
            for name in ("kind", "busyPolicy", "required", "flags"):
                _integer(operation.get(name), f"operation.{name}", 0xFF)
            for field in ("definitionId", "replacementDefinitionId"):
                require_reference(operation[field], definition_ids, f"operation.{field}", optional=True)
            require_reference(operation["ownerId"], owner_ids, "operation.ownerId", optional=True)
            require_reference(operation["policyId"], live_ids, "operation.policyId", optional=True)
            require_reference(operation["instanceKey"], live_ids,
                              "operation.instanceKey", optional=True)
            kind = operation["kind"]
            definition_id = operation["definitionId"]
            replacement = operation["replacementDefinitionId"]
            owner = operation["ownerId"]
            policy = operation["policyId"]
            instance = operation["instanceKey"]
            if (not 1 <= kind <= 6 or operation["busyPolicy"] not in (1, 2)
                    or operation["required"] not in (0, 1) or operation["flags"] != 0):
                raise ModelError("transition operation violates its closed domain")
            if ((kind == 1 and (not definition_id or replacement or policy
                                or instance != definition_id or operation["required"]))
                    or (kind == 2 and (not definition_id or not replacement or policy
                                       or instance != definition_id or operation["required"]))
                    or (kind == 3 and (not definition_id or replacement or policy or instance
                                       or operation["required"] != 1))
                    or (kind == 4 and (not definition_id or replacement or policy or instance
                                       or operation["required"]))
                    or (kind == 5 and (definition_id or replacement or policy or instance
                                       or operation["required"]))
                    or (kind == 6 and (definition_id or owner or replacement or not policy
                                       or instance or operation["required"]))):
                raise ModelError("transition operation payload is noncanonical")
            if (kind <= 5 and owner not in owner_ids) or (kind == 6 and owner != 0):
                raise ModelError("transition operation owner is noncanonical")
            if kind <= 4:
                for candidate_id in (definition_id, replacement) if kind == 2 else (definition_id,):
                    candidate_owner = definitions_by_id[candidate_id]["requiredOwnerId"]
                    if candidate_owner and candidate_owner != owner:
                        raise ModelError("transition operation is not authorized for generated wrapper")
        for action in transition["actions"]:
            for name in ("phase", "kind"):
                _integer(action.get(name), f"transitionAction.{name}", 0xFF)
            _integer(action.get("payload"), "transitionAction.payload")
            require_reference(action["referenceId"], live_ids,
                              "transitionAction.referenceId", optional=True)
            if (not 1 <= action["phase"] <= 4 or not 1 <= action["kind"] <= 8
                    or action["referenceId"] != 0 or action["payload"] != 0):
                raise ModelError("transition action payload is noncanonical")
        for recovery in transition["recoveryActions"]:
            for name in ("kind", "required"):
                _integer(recovery.get(name), f"recovery.{name}", 0xFF)
            require_reference(recovery["ownerId"], owner_ids, "recovery.ownerId")
            if not 1 <= recovery["kind"] <= 4 or recovery["required"] not in (0, 1):
                raise ModelError("recovery action violates its closed domain")
            if recovery["ownerId"] != transition["ownerId"]:
                raise ModelError("recovery action owner differs from its transition owner")
    action_cursor = len(model["assignmentActions"])
    override_action_slices: dict[int, tuple[int, int]] = {}
    for override in _sorted(model["overrides"]):
        override_action_slices[override["stableId"]] = (
            action_cursor, len(override["actions"])
        )
        action_cursor += len(override["actions"])
    for recipe in model["importRecipes"]:
        for name in (
            "ownerId", "controllerId", "nodeId", "profileId",
            "recoveryTransitionId", "sourceOverrideId", "actionStart",
            "actionCount", "reserved",
        ):
            _integer(recipe.get(name), f"import.{name}")
        for name in ("semanticRoleId", "lifetime", "contextual", "flags"):
            _integer(recipe.get(name), f"import.{name}", 0xFF)
        if (not 1 <= recipe["semanticRoleId"] <= 7
                or recipe["lifetime"] not in (1, 2, 3)
                or recipe["contextual"] not in (0, 1) or recipe["flags"] != 0):
            raise ModelError("import recipe violates its closed domain")
        if ((recipe["contextual"] == 0 and recipe["reserved"] != 0xFFFF)
                or (recipe["contextual"] == 1 and recipe["reserved"] != 0)):
            raise ModelError("import recipe reserved/contextual pair is noncanonical")
        require_reference(recipe["ownerId"], owner_ids, "import.ownerId")
        require_reference(recipe["controllerId"], controller_ids,
                          "import.controllerId", optional=True)
        require_reference(recipe["nodeId"], node_ids, "import.nodeId", optional=True)
        require_reference(recipe["profileId"], profile_ids, "import.profileId")
        require_reference(recipe["recoveryTransitionId"], transition_ids,
                          "import.recoveryTransitionId", optional=True)
        require_reference(recipe["sourceOverrideId"], override_ids,
                          "import.sourceOverrideId", optional=True)
        expected_slice = (
            (0, 0) if recipe["sourceOverrideId"] == 0
            else override_action_slices[recipe["sourceOverrideId"]]
        )
        if (recipe["actionStart"], recipe["actionCount"]) != expected_slice:
            raise ModelError("import recipe action slice differs from its source override")
    for item in model["applicability"]:
        _integer(item.get("kind"), "applicability.kind")
        _integer(item.get("groupMask"), "applicability.groupMask", 0xFFFFFFFF)
        for name in ("controllerId", "profileId", "flags"):
            _integer(item.get(name), f"applicability.{name}")
        minimum = _integer(item.get("minimum"), "applicability.minimum", 0xFF)
        maximum = _integer(item.get("maximum"), "applicability.maximum", 0xFF)
        kind = item["kind"]
        if (not kind or kind & ~0xF or item["flags"] != 0 or maximum != 0
                or ((kind & 1) == 0) != (item["groupMask"] == 0)
                or ((kind & 2) == 0) != (item["controllerId"] == 0)
                or ((kind & 4) == 0) != (item["profileId"] == 0)
                or ((kind & 8) and not 1 <= minimum <= 7)
                or (not (kind & 8) and minimum != 0)):
            raise ModelError("applicability record is noncanonical")
        require_reference(item["controllerId"], controller_ids,
                          "applicability.controllerId", optional=True)
        require_reference(item["profileId"], profile_ids,
                          "applicability.profileId", optional=True)
    applicability_claims = {
        stable_id: 0 for stable_id in applicability_ids
    }
    applicability_by_id = {
        item["stableId"]: item for item in model["applicability"]
    }
    for definition in model["overrideDefinitions"]:
        applicability_claims[definition["applicabilityId"]] += 1
        rule = applicability_by_id[definition["applicabilityId"]]
        if definition["kind"] == 1 and rule["kind"] & 0xC:
            raise ModelError("state-candidate applicability cannot target profile/role")
        if (definition["selectorKind"] == 1
                and rule["controllerId"] != definition["controllerId"]):
            raise ModelError("exact definition applicability targets another controller")
    if set(applicability_claims.values()) != {1}:
        raise ModelError("each applicability record must be owned by exactly one definition")
    transition_dispatch_domains = []
    for transition in model["transitions"]:
        definition = definitions_by_id[transition["definitionId"]]
        application = applicability_by_id[definition["applicabilityId"]]
        transition_dispatch_domains.append((
            transition,
            definition["controllerId"] or application["controllerId"],
        ))
    for left_index, (left, left_controller) in enumerate(transition_dispatch_domains):
        for right, right_controller in transition_dispatch_domains[left_index + 1:]:
            if (left["dispatchPriority"] != right["dispatchPriority"]
                    or left["trigger"] != right["trigger"]
                    or not left["fromRoleMask"] & right["fromRoleMask"]
                    or (left_controller and right_controller
                        and left_controller != right_controller)):
                continue
            raise ModelError(
                f"transitions {left['stableId']} and {right['stableId']} "
                "have an ambiguous dispatch overlap"
            )
    for item in model["tiredTranslations"]:
        for name in (
            "stableId", "controllerId", "profileId", "definitionId",
            "recoveryTransitionId", "fallbackControllerId", "fallbackNodeId",
            "flags", "reserved",
        ):
            _integer(item.get(name), f"tired.{name}")
        for name in (
            "originKind", "authoredBound", "removeCandidate", "removeCalm",
            "cooldownKind", "required",
        ):
            _integer(item.get(name), f"tired.{name}", 0xFF)
        if item["originKind"] not in (1, 2, 3):
            raise ModelError("tired translation has an invalid origin")
        for name in ("authoredBound", "removeCandidate", "removeCalm", "required"):
            if item[name] not in (0, 1):
                raise ModelError(f"tired.{name} must be boolean")
        if (item["flags"] != 0 or item["reserved"] != 0
                or item["removeCandidate"] != 1 or item["removeCalm"] != 1
                or item["cooldownKind"] != 2 or item["required"] != 1):
            raise ModelError("tired translation policy is noncanonical")
        require_reference(item["controllerId"], controller_ids, "tired.controllerId")
        require_reference(item["profileId"], profile_ids, "tired.profileId")
        require_reference(item["definitionId"], definition_ids, "tired.definitionId")
        require_reference(item["recoveryTransitionId"], transition_ids,
                          "tired.recoveryTransitionId")
        require_reference(item["fallbackControllerId"], controller_ids,
                          "tired.fallbackControllerId", optional=True)
        require_reference(item["fallbackNodeId"], node_ids,
                          "tired.fallbackNodeId", optional=True)
        definition = definitions_by_id[item["definitionId"]]
        if (definition["hasTiredOriginKind"] != 1
                or definition["tiredOriginKind"] != item["originKind"]
                or definition["hasRequiredOwnerId"] != 1):
            raise ModelError(
                "tired translation definition does not match generated origin/owner metadata"
            )
        if definition["recoveryTransitionId"] != item["recoveryTransitionId"]:
            raise ModelError("tired translation recovery differs from its definition")
        if item["authoredBound"]:
            if (item["fallbackControllerId"] != 0 or item["fallbackNodeId"] != 0
                    or definition["selectorKind"] != 2):
                raise ModelError("authored tired translation has fallback-only data")
        else:
            if (item["fallbackControllerId"] != item["controllerId"]
                    or item["fallbackNodeId"] == 0
                    or definition["selectorKind"] != 1
                    or definition["controllerId"] != item["fallbackControllerId"]
                    or definition["nodeId"] != item["fallbackNodeId"]):
                raise ModelError("fallback tired translation is noncanonical")

    for action in model["assignmentActions"]:
        _validate_static_action(
            action, assignment=True, controller_ids=controller_ids,
            nodes_by_id=nodes_by_id, profiles_by_id=profiles_by_id,
            spawn_ids=spawn_ids, population_ids=population_ids, hook_ids=hook_ids,
        )
    for override in model["overrides"]:
        for action in override["actions"]:
            _validate_static_action(
                action, assignment=False, controller_ids=controller_ids,
                nodes_by_id=nodes_by_id, profiles_by_id=profiles_by_id,
                spawn_ids=spawn_ids, population_ids=population_ids,
                hook_ids=hook_ids,
            )


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


def _validate_match(match: Any, label: str) -> None:
    if not isinstance(match, dict):
        raise ModelError(f"{label} must be an object")
    expected = {
        "groupMask", "species", "terrain", "minimumLevel",
        "maximumLevel", "shiny", "behaviorClass",
    }
    if set(match) != expected:
        raise ModelError(f"{label} must contain the exact match fields")
    _integer(match["groupMask"], f"{label}.groupMask", 0xFFFFFFFF)
    _integer(match["species"], f"{label}.species")
    terrain = _integer(match["terrain"], f"{label}.terrain", 0xFF)
    minimum = _integer(match["minimumLevel"], f"{label}.minimumLevel", 0xFF)
    maximum = _integer(match["maximumLevel"], f"{label}.maximumLevel", 0xFF)
    shiny = _integer(match["shiny"], f"{label}.shiny", 0xFF)
    behavior_class = _integer(
        match["behaviorClass"], f"{label}.behaviorClass", 0xFF
    )
    if (terrain not in (0, 1, 2, 3, 0xFF)
            or (minimum and maximum and minimum > maximum)
            or shiny not in (0, 1, 0xFF)
            or behavior_class not in (0, 1, 2, 3, 0xFD, 0xFF)):
        raise ModelError(f"{label} violates its closed typed domain")


def _modifier_payload_valid(kind: int, field: int, operator: int,
                            delta_byte: int, bound: int) -> bool:
    numeric_masks = {4: 0x031FFE18, 5: 0x000000D8, 7: 0x00000038, 9: 0x00000002}
    if kind not in numeric_masks or not 1 <= field < 32 or not 1 <= operator <= 6:
        return False
    numeric = bool(numeric_masks[kind] & (1 << field))
    if not numeric and operator != 1:
        return False
    if operator < 5 and bound:
        return False
    delta = delta_byte - 0x100 if delta_byte >= 0x80 else delta_byte
    if operator == 2 or operator >= 5:
        if not -32 <= delta <= 32:
            return False
    elif not scalar_value_valid(kind, field, delta_byte):
        return False
    return operator < 5 or scalar_value_valid(kind, field, bound)


def _validate_static_action(
    action: dict[str, Any], *, assignment: bool,
    controller_ids: set[int], nodes_by_id: dict[int, tuple[int, dict[str, Any]]],
    profiles_by_id: dict[int, dict[str, Any]], spawn_ids: set[int],
    population_ids: set[int],
    hook_ids: set[int],
) -> None:
    try:
        payload = bytes(action["payload"])
    except (KeyError, TypeError, ValueError) as error:
        raise ModelError(
            f"override action {action.get('stableId')} payload is invalid"
        ) from error
    if len(payload) != 8:
        raise ModelError(
            f"override action {action.get('stableId')} payload must be exactly 8 bytes"
        )
    kind = action["kind"]
    if assignment:
        if (kind != 1 or struct.unpack_from("<H", payload)[0] not in controller_ids
                or any(payload[2:])):
            raise ModelError("assignment action payload is noncanonical")
        return
    if not 2 <= kind <= 11:
        raise ModelError("static override action kind is unsupported")
    first, second, third, fourth = struct.unpack("<4H", payload)
    if kind == 2:
        node = nodes_by_id.get(second)
        profile = profiles_by_id.get(third)
        valid = (first in controller_ids and node is not None and node[0] == first
                 and profile is not None
                 and profile["body"]["values"]["behaviorKind"] != 0 and fourth == 0)
    elif kind == 3:
        node = nodes_by_id.get(second)
        valid = (first in controller_ids and node is not None and node[0] == first
                 and not node[1]["base"] and third == 0 and fourth == 0)
    elif kind in (4, 5, 7, 9):
        field, operator, delta, bound, role_mask, reserved = payload[:6]
        controller = struct.unpack_from("<H", payload, 6)[0]
        field_ranges = {4: (1, 27), 5: (1, 7), 7: (1, 5), 9: (1, 1)}
        minimum, maximum = field_ranges[kind]
        valid = (
            minimum <= field <= maximum and not (kind == 4 and field == 22)
            and reserved == 0
            and ((kind == 4 and role_mask != 0 and not role_mask & ~7
                  and (controller == 0 or controller in controller_ids))
                 or (kind != 4 and role_mask == 0 and controller == 0))
            and _modifier_payload_valid(kind, field, operator, delta, bound)
        )
    elif kind in (6, 8, 10):
        targets = {6: spawn_ids, 8: population_ids, 10: hook_ids}[kind]
        valid = first in targets and second == 0 and third == 0 and fourth == 0
    else:
        node = nodes_by_id.get(second)
        operator = payload[4]
        delta = payload[5] - 0x100 if payload[5] >= 0x80 else payload[5]
        valid = (
            first in controller_ids and node is not None and node[0] == first
            and node[1]["semanticRoleId"] == 3 and not node[1]["base"]
            and payload[6:] == b"\0\0"
            and (operator == 1 or (operator == 2 and -32 <= delta <= 32))
        )
    if not valid:
        raise ModelError(f"static override action {action['stableId']} payload is noncanonical")


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
        if body_id not in bodies:
            raise ModelError(f"profile {stable_id} has an invalid body reference")
        used_bodies.add(body_id)
        identity_registry_key = registry_key(stable_id)
        name, tags = _display_metadata(
            identity_registry_key, stable_id, bodies[body_id]["provenanceKind"]
        )
        profiles.append({
            "stableId": stable_id, "bodyId": body_id, "provenanceId": provenance_id,
            "sourceTags": {"tagA": tag_a, "tagB": tag_b},
            "body": copy.deepcopy(bodies[body_id]),
            "name": name, "descriptiveTags": tags, "registryKey": identity_registry_key,
            "bodyRegistryKey": registry_key(body_id),
        })
    if used_bodies != set(bodies):
        raise ModelError("every state body must be referenced by at least one profile")

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
    for order, raw in enumerate(sections["transitions"]):
        record = _named_record(TRANSITION_STRUCT.unpack(raw), TRANSITION_FIELDS)
        record["order"] = order
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
    bodies: dict[int, dict[str, Any]] = {}
    for profile in profiles:
        prior = bodies.setdefault(profile["bodyId"], profile["body"])
        if prior != profile["body"]:
            raise ModelError(f"shared state body {profile['bodyId']} has conflicting records")
    for body_id, body in sorted(bodies.items()):
        values = bytes(body["values"][name] for name in STATE_FIELDS)
        output["stateBodies"].append(struct.pack(
            "<HBB28s", body_id, body["provenanceKind"], len(values), values,
        ))
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
        if section == "semanticIds":
            records = sorted(model[section], key=lambda record: (record["kind"], record["value"]))
        elif section == "modifierOperations":
            records = sorted(
                model[section],
                key=lambda record: (
                    record["definitionId"], record["order"], record["stableId"]
                ),
            )
        else:
            records = _sorted(model[section])
        for record in records:
            output[section].append(_pack_named(record, section, codec, fields))

    guard_cursor = operation_cursor = transition_action_cursor = recovery_cursor = 0
    for transition in sorted(model["transitions"], key=lambda record: (record["order"], record["stableId"])):
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
    """Encode the canonical model in stable-ID and explicit authored semantic order."""
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


def merge_authored_metadata(
    wire_model: dict[str, Any], authored_model: dict[str, Any]
) -> dict[str, Any]:
    """Restore canonical editor metadata that is intentionally absent on wire."""
    result = copy.deepcopy(wire_model)
    for section, fields in (
        ("stateProfiles", ("name", "descriptiveTags", "promotionProvenance")),
        ("controllers", ("name",)),
        ("transitions", ("name",)),
        ("overrideDefinitions", ("name",)),
    ):
        authored = {record["stableId"]: record for record in authored_model[section]}
        projected = {record["stableId"]: record for record in result[section]}
        if set(authored) != set(projected):
            raise ModelError(f"{section} canonical metadata identities differ from the wire projection")
        for stable_id, target in projected.items():
            for field in fields:
                if field in authored[stable_id]:
                    target[field] = copy.deepcopy(authored[stable_id][field])
                else:
                    target.pop(field, None)
    validate_model(result)
    return result


def render_inc(blob: bytes) -> str:
    lines = ["/* Generated from OverworldWildBehaviorModelV40.json; do not edit. */"]
    for offset in range(0, len(blob), 16):
        lines.append("    " + ", ".join(f"0x{value:02X}" for value in blob[offset:offset + 16]) + ",")
    return "\n".join(lines) + "\n"


HEADER_COUNT_DEFINES = {
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
    "OWBD_MODIFIER_OPERATION_COUNT": "modifierOperations",
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
    "append_stable_history_events", "canonical_json_bytes", "decode_blob", "encode_model",
    "intern_state_bodies",
    "load_model", "read_inc",
    "merge_authored_metadata", "render_header", "render_inc", "section_counts", "stable_history_digest",
    "validate_model", "wire_projection",
]
