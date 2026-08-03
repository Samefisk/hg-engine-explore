"""Atomic persistence for the compact OWBD v40 behavior-model editor graph.

The editor submits only authored fields.  This module owns stable identity,
registry history, canonical JSON materialization, wire generation, validation,
and the three-file transaction.  It deliberately has no HTTP dependencies.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import overworld_wild_behavior_model_v40 as v40  # noqa: E402


class BehaviorModelWriteError(ValueError):
    """The compact editor transaction is invalid or cannot be persisted."""


MODEL_PATH = Path("data/OverworldWildBehaviorModelV40.json")
INC_PATH = Path("data/OverworldWildBehaviorDataV40.generated.inc")
HEADER_PATH = Path("include/overworld_wild_behavior_data.h")
MANAGED_PATHS = (MODEL_PATH, INC_PATH, HEADER_PATH)

DOMAIN_KEYS = frozenset(("stateProfiles", "controllers", "transitions"))
DELTA_KEYS = frozenset(("create", "update", "remove"))
SCALAR_KEYS = (
    "alertState", "alertEmote", "alertTime", "alertness",
    "alertRange", "alertChance", "stamina", "restTime",
)
POLICY_KEYS = ("spawnPolicyId", "populationPolicyId", "hookSetId")
PROFILE_FIELDS = frozenset((
    "draftId", "stableId", "name", "descriptiveTags", "values", "templateProvenance",
))
CONTROLLER_FIELDS = frozenset((
    "draftId", "stableId", "name", "nodes", "scalarDefaults", "policyIds",
))
NODE_FIELDS = frozenset((
    "draftId", "stableId", "profileRef", "semanticRoleId", "customRoleId",
    "base", "optional", "hidden",
))
TRANSITION_FIELDS = frozenset((
    "draftId", "stableId", "name", "controllerIds", "candidateDefinitionId",
    "candidateDefinition", "ownerId", "trigger", "fromRoleMask",
    "dispatchPriority", "order", "guards", "operations", "actions", "recoveryActions",
))
DEFINITION_AUTHORED_FIELDS = (
    "controllerId", "nodeId", "requiredOwnerId", "recoveryTransitionId",
    "applicabilityId", "priority", "kind", "channel", "selectorKind",
    "semanticRoleId", "mapLifetime", "battleLifetime", "timerClock",
    "timerSource", "hiddenTimerPolicy", "recoveryPolicy", "timerValue",
    "hasTiredOriginKind", "tiredOriginKind", "hasRequiredOwnerId",
    "allowMultipleOwners", "allowMultipleInstancesPerOwner",
    "authoredTiredBound", "flags", "reserved0", "reserved1",
)
DEFINITION_FIELDS = frozenset((
    "draftId", "stableId", "name", "applicability", *DEFINITION_AUTHORED_FIELDS,
))
APPLICABILITY_AUTHORED_FIELDS = (
    "kind", "groupMask", "controllerId", "profileId", "minimum", "maximum", "flags",
)
APPLICABILITY_FIELDS = frozenset((
    "draftId", "stableId", "name", *APPLICABILITY_AUTHORED_FIELDS,
))
CHILD_FIELDS = {
    "guards": frozenset(("draftId", "stableId", "kind", "negate", "payload", "referenceId")),
    "operations": frozenset((
        "draftId", "stableId", "definitionId", "ownerId", "replacementDefinitionId",
        "policyId", "instanceKey", "kind", "busyPolicy", "required",
    )),
    "actions": frozenset(("draftId", "stableId", "phase", "kind", "referenceId", "payload")),
    "recoveryActions": frozenset(("draftId", "stableId", "ownerId", "kind", "required")),
}
DRAFT_RE = re.compile(r"^draft:[^\s]{1,160}$")


def _error(message: str) -> BehaviorModelWriteError:
    return BehaviorModelWriteError(message)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(f"{path} must be an array")
    return value


def _keys(value: dict[str, Any], allowed: frozenset[str], required: Iterable[str], path: str) -> None:
    unknown = set(value) - allowed
    missing = set(required) - set(value)
    if unknown:
        raise _error(f"{path} contains non-authored fields: {sorted(unknown)}")
    if missing:
        raise _error(f"{path} is missing authored fields: {sorted(missing)}")


def _stable_id(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 0xFFFF:
        raise _error(f"{path} must be a non-zero 16-bit stable ID")
    return value


def _draft_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not DRAFT_RE.fullmatch(value):
        raise _error(f"{path} must be a draft: identity")
    return value


def _integer(value: Any, path: str, maximum: int = 0xFFFF) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise _error(f"{path} must be an integer in 0..{maximum}")
    return value


def _name(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
        raise _error(f"{path} must be a non-empty name of at most 160 characters")
    return value.strip()


def _tags(value: Any, path: str) -> list[str]:
    values = _array(value, path)
    result: list[str] = []
    for index, tag in enumerate(values):
        if not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 80:
            raise _error(f"{path}[{index}] must be a non-empty tag of at most 80 characters")
        normalized = tag.strip()
        if normalized not in result:
            result.append(normalized)
    return result


def _identity(entity: dict[str, Any], creating: bool, path: str) -> int | str:
    if creating:
        if entity.get("stableId") is not None:
            raise _error(f"{path} cannot mix draft and stable identity")
        return _draft_id(entity.get("draftId"), f"{path}.draftId")
    if "draftId" in entity and entity.get("draftId") is not None:
        raise _error(f"{path} cannot mix stable and draft identity")
    return _stable_id(entity.get("stableId"), f"{path}.stableId")


def _parse_payload(payload: Any) -> dict[str, dict[str, list[Any]]]:
    root = _object(payload, "payload")
    allowed = DOMAIN_KEYS | {"modelVersion"}
    unknown = set(root) - allowed
    if unknown:
        raise _error(f"payload contains unsupported or legacy domains: {sorted(unknown)}")
    if root.get("modelVersion", 40) != 40:
        raise _error("payload.modelVersion must be 40")
    result: dict[str, dict[str, list[Any]]] = {}
    for domain in DOMAIN_KEYS:
        raw = root.get(domain)
        if raw is None:
            result[domain] = {key: [] for key in DELTA_KEYS}
            continue
        delta = _object(raw, f"payload.{domain}")
        extra = set(delta) - DELTA_KEYS
        if extra:
            raise _error(f"payload.{domain} contains unsupported operations: {sorted(extra)}")
        result[domain] = {
            key: _array(delta.get(key, []), f"payload.{domain}.{key}") for key in DELTA_KEYS
        }
    return result


class _Allocator:
    def __init__(self, model: dict[str, Any]):
        self.next_id = model["stableIdHistory"]["nextUnallocatedId"]
        self.draft_map: dict[str, int] = {}
        self.registry_by_draft: dict[str, str] = {}
        self.events: list[tuple[str, str]] = []

    def draft(self, draft_id: str, kind: str) -> int:
        if draft_id in self.draft_map:
            raise _error(f"draft identity is owned more than once: {draft_id}")
        stable_id = self.next_id
        if stable_id > 0xFFFF:
            raise _error("stable ID space is exhausted")
        self.next_id += 1
        registry_key = f"editor:{kind}:{stable_id}"
        self.draft_map[draft_id] = stable_id
        self.registry_by_draft[draft_id] = registry_key
        self.events.append(("allocate", registry_key))
        return stable_id

    def owned(self, kind: str) -> tuple[int, str]:
        stable_id = self.next_id
        if stable_id > 0xFFFF:
            raise _error("stable ID space is exhausted")
        self.next_id += 1
        registry_key = f"editor:{kind}:{stable_id}"
        self.events.append(("allocate", registry_key))
        return stable_id, registry_key


def _nested_identity(entity: Any, creating_parent: bool, path: str) -> tuple[str, int | str]:
    item = _object(entity, path)
    if item.get("stableId") is None:
        return "draft", _draft_id(item.get("draftId"), f"{path}.draftId")
    if creating_parent:
        raise _error(f"{path} under a new parent must use draft identity")
    if item.get("draftId") is not None:
        raise _error(f"{path} cannot mix stable and draft identity")
    return "stable", _stable_id(item["stableId"], f"{path}.stableId")


def _scan_allocations(changes: dict[str, dict[str, list[Any]]], allocator: _Allocator) -> None:
    # Parent then owned descendants is the stable, deterministic depth-first order.
    for index, raw in enumerate(changes["stateProfiles"]["create"]):
        item = _object(raw, f"stateProfiles.create[{index}]")
        draft = _draft_id(item.get("draftId"), f"stateProfiles.create[{index}].draftId")
        allocator.draft(draft, "state-profile")
        allocator.owned("state-body")

    for operation in ("create", "update"):
        for index, raw in enumerate(changes["controllers"][operation]):
            path = f"controllers.{operation}[{index}]"
            item = _object(raw, path)
            creating = operation == "create"
            if creating:
                allocator.draft(_draft_id(item.get("draftId"), f"{path}.draftId"), "controller")
            for node_index, raw_node in enumerate(_array(item.get("nodes"), f"{path}.nodes")):
                kind, identity = _nested_identity(raw_node, creating, f"{path}.nodes[{node_index}]")
                if kind == "draft":
                    allocator.draft(identity, "controller-node")  # type: ignore[arg-type]

    definitions_seen: dict[str, dict[str, Any]] = {}
    applicability_seen: dict[str, dict[str, Any]] = {}
    for operation in ("create", "update"):
        for index, raw in enumerate(changes["transitions"][operation]):
            path = f"transitions.{operation}[{index}]"
            item = _object(raw, path)
            creating = operation == "create"
            if creating:
                allocator.draft(_draft_id(item.get("draftId"), f"{path}.draftId"), "transition")
            definition = _object(item.get("candidateDefinition"), f"{path}.candidateDefinition")
            if definition.get("stableId") is None:
                draft = _draft_id(definition.get("draftId"), f"{path}.candidateDefinition.draftId")
                previous = definitions_seen.get(draft)
                if previous is None:
                    definitions_seen[draft] = definition
                    allocator.draft(draft, "override-definition")
                elif previous != definition:
                    raise _error(f"shared candidate definition {draft} has conflicting authored values")
            applicability = _object(
                definition.get("applicability"), f"{path}.candidateDefinition.applicability"
            )
            if applicability.get("stableId") is None:
                draft = _draft_id(
                    applicability.get("draftId"),
                    f"{path}.candidateDefinition.applicability.draftId",
                )
                previous = applicability_seen.get(draft)
                if previous is None:
                    applicability_seen[draft] = applicability
                    allocator.draft(draft, "applicability")
                elif previous != applicability:
                    raise _error(f"shared applicability {draft} has conflicting authored values")
            for child_key in ("guards", "operations", "actions", "recoveryActions"):
                for child_index, raw_child in enumerate(_array(item.get(child_key), f"{path}.{child_key}")):
                    kind, identity = _nested_identity(
                        raw_child, creating, f"{path}.{child_key}[{child_index}]"
                    )
                    if kind == "draft":
                        allocator.draft(identity, child_key.removesuffix("s"))  # type: ignore[arg-type]


def _resolve(value: Any, allocator: _Allocator, path: str, *, optional: bool = False) -> int:
    if optional and (value is None or value == 0):
        return 0
    if isinstance(value, str):
        if not DRAFT_RE.fullmatch(value):
            raise _error(f"{path} mixes an unsupported reference representation")
        if value not in allocator.draft_map:
            raise _error(f"{path} references unknown draft identity {value}")
        return allocator.draft_map[value]
    return _stable_id(value, path)


def _registry_for_draft(allocator: _Allocator, draft: str) -> str:
    try:
        return allocator.registry_by_draft[draft]
    except KeyError as exc:
        raise _error(f"unknown allocated draft identity {draft}") from exc


def _index(records: list[dict[str, Any]], label: str) -> dict[int, dict[str, Any]]:
    result = {record["stableId"]: record for record in records}
    if len(result) != len(records):
        raise _error(f"canonical {label} contains duplicate identities")
    return result


def _existing(identity: int, records: dict[int, dict[str, Any]], path: str) -> dict[str, Any]:
    try:
        return records[identity]
    except KeyError as exc:
        raise _error(f"{path} references unknown saved stable ID {identity}") from exc


def _retire(key: str, retirements: list[str], seen: set[str]) -> None:
    if key not in seen:
        seen.add(key)
        retirements.append(key)


def _profile_record(
    item: dict[str, Any], creating: bool, existing: dict[str, Any] | None,
    allocator: _Allocator, provenance_by_kind: dict[int, int], path: str,
) -> dict[str, Any]:
    required = ("name", "descriptiveTags", "values", "templateProvenance") if creating \
        else ("name", "descriptiveTags", "values")
    _keys(item, PROFILE_FIELDS, required, path)
    identity = _identity(item, creating, path)
    values = _object(item["values"], f"{path}.values")
    if set(values) != set(v40.STATE_FIELDS):
        raise _error(f"{path}.values must contain exactly the 28 V40 state fields")
    typed_values = {key: _integer(values[key], f"{path}.values.{key}", 0xFF) for key in v40.STATE_FIELDS}
    if creating:
        draft = identity  # type: ignore[assignment]
        stable_id = allocator.draft_map[draft]
        body_id = stable_id + 1
        body_key = f"editor:state-body:{body_id}"
        template = _object(item["templateProvenance"], f"{path}.templateProvenance")
        _keys(template, frozenset(("kind", "provenanceId")),
              ("kind", "provenanceId"), f"{path}.templateProvenance")
        provenance_kind = _integer(template["kind"], f"{path}.templateProvenance.kind", 7)
        provenance_id = _stable_id(
            template["provenanceId"], f"{path}.templateProvenance.provenanceId"
        )
        if provenance_kind not in provenance_by_kind or provenance_by_kind[provenance_kind] != provenance_id:
            raise _error(f"{path}.templateProvenance kind and semantic ID do not match")
        return {
            "stableId": stable_id, "bodyId": body_id,
            "registryKey": _registry_for_draft(allocator, draft), "bodyRegistryKey": body_key,
            "name": _name(item["name"], f"{path}.name"),
            "descriptiveTags": _tags(item["descriptiveTags"], f"{path}.descriptiveTags"),
            "provenanceId": provenance_id, "sourceTags": {"tagA": 0, "tagB": 0},
            "body": {"provenanceKind": provenance_kind, "values": typed_values},
        }
    assert existing is not None
    if "templateProvenance" in item:
        template = _object(item["templateProvenance"], f"{path}.templateProvenance")
        if template != {
            "kind": existing["body"]["provenanceKind"],
            "provenanceId": existing["provenanceId"],
        }:
            raise _error(f"{path}.templateProvenance is read-only")
    result = copy.deepcopy(existing)
    result["name"] = _name(item["name"], f"{path}.name")
    result["descriptiveTags"] = _tags(item["descriptiveTags"], f"{path}.descriptiveTags")
    result["body"]["values"] = typed_values
    return result


def _node_record(
    item: dict[str, Any], creating_parent: bool, old_nodes: dict[int, dict[str, Any]],
    allocator: _Allocator, path: str,
) -> dict[str, Any]:
    _keys(item, NODE_FIELDS, (
        "profileRef", "semanticRoleId", "customRoleId", "base", "optional", "hidden",
    ), path)
    kind, identity = _nested_identity(item, creating_parent, path)
    if kind == "draft":
        stable_id = allocator.draft_map[identity]  # type: ignore[index]
        registry_key = _registry_for_draft(allocator, identity)  # type: ignore[arg-type]
        flags = reserved = 0
    else:
        previous = _existing(identity, old_nodes, path)  # type: ignore[arg-type]
        stable_id, registry_key = previous["stableId"], previous["registryKey"]
        flags, reserved = previous.get("flags", 0), previous.get("reserved", 0)
    role = _integer(item["semanticRoleId"], f"{path}.semanticRoleId", 7)
    custom = _resolve(item["customRoleId"], allocator, f"{path}.customRoleId", optional=True)
    return {
        "stableId": stable_id, "registryKey": registry_key,
        "profileId": _resolve(item["profileRef"], allocator, f"{path}.profileRef"),
        "semanticRoleId": role, "customRoleId": custom,
        "base": bool(item["base"]), "optional": bool(item["optional"]),
        "hidden": bool(item["hidden"]), "flags": flags, "reserved": reserved,
    }


def _controller_record(
    item: dict[str, Any], creating: bool, existing: dict[str, Any] | None,
    allocator: _Allocator, path: str, retirements: list[str], retired: set[str],
) -> dict[str, Any]:
    _keys(item, CONTROLLER_FIELDS, ("name", "nodes", "scalarDefaults", "policyIds"), path)
    identity = _identity(item, creating, path)
    old_nodes = _index(existing["nodes"], "controller nodes") if existing else {}
    nodes = [
        _node_record(_object(node, f"{path}.nodes[{index}]"), creating, old_nodes, allocator,
                     f"{path}.nodes[{index}]")
        for index, node in enumerate(_array(item["nodes"], f"{path}.nodes"))
    ]
    kept = {node["stableId"] for node in nodes}
    for stable_id, node in old_nodes.items():
        if stable_id not in kept:
            _retire(node["registryKey"], retirements, retired)
    scalar = _object(item["scalarDefaults"], f"{path}.scalarDefaults")
    policy = _object(item["policyIds"], f"{path}.policyIds")
    if set(scalar) != set(SCALAR_KEYS) or set(policy) != set(POLICY_KEYS):
        raise _error(f"{path} must contain the exact scalarDefaults and policyIds field sets")
    if creating:
        draft = identity  # type: ignore[assignment]
        stable_id = allocator.draft_map[draft]
        result = {
            "stableId": stable_id, "registryKey": _registry_for_draft(allocator, draft),
            "nameId": stable_id, "flags0": 0, "flags1": 0,
        }
    else:
        assert existing is not None
        result = {key: copy.deepcopy(value) for key, value in existing.items() if key != "nodes"}
    result.update({
        "name": _name(item["name"], f"{path}.name"), "nodes": nodes,
        **{key: _integer(scalar[key], f"{path}.scalarDefaults.{key}", 0xFF) for key in SCALAR_KEYS},
        **{key: _resolve(policy[key], allocator, f"{path}.policyIds.{key}") for key in POLICY_KEYS},
    })
    return result


def _applicability_record(
    item: dict[str, Any], allocator: _Allocator,
    existing_applicability: dict[int, dict[str, Any]], path: str,
) -> dict[str, Any]:
    _keys(item, APPLICABILITY_FIELDS, APPLICABILITY_AUTHORED_FIELDS, path)
    if item.get("stableId") is None:
        draft = _draft_id(item.get("draftId"), f"{path}.draftId")
        result = {
            "stableId": allocator.draft_map[draft],
            "registryKey": _registry_for_draft(allocator, draft),
        }
    else:
        stable_id = _stable_id(item["stableId"], f"{path}.stableId")
        if item.get("draftId") is not None:
            raise _error(f"{path} cannot mix stable and draft identity")
        result = copy.deepcopy(_existing(stable_id, existing_applicability, path))
    result.update({
        "kind": _integer(item["kind"], f"{path}.kind"),
        "groupMask": _integer(item["groupMask"], f"{path}.groupMask", 0xFFFFFFFF),
        "controllerId": _resolve(item["controllerId"], allocator, f"{path}.controllerId", optional=True),
        "profileId": _resolve(item["profileId"], allocator, f"{path}.profileId", optional=True),
        "minimum": _integer(item["minimum"], f"{path}.minimum", 0xFF),
        "maximum": _integer(item["maximum"], f"{path}.maximum", 0xFF),
        "flags": _integer(item["flags"], f"{path}.flags"),
    })
    return result


def _definition_record(
    item: dict[str, Any], allocator: _Allocator, existing_definitions: dict[int, dict[str, Any]],
    existing_applicability: dict[int, dict[str, Any]], path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _keys(item, DEFINITION_FIELDS, DEFINITION_AUTHORED_FIELDS, path)
    if item.get("stableId") is None:
        draft = _draft_id(item.get("draftId"), f"{path}.draftId")
        stable_id = allocator.draft_map[draft]
        result = {
            "stableId": stable_id, "registryKey": _registry_for_draft(allocator, draft),
            "nameId": stable_id,
        }
    else:
        stable_id = _stable_id(item["stableId"], f"{path}.stableId")
        if item.get("draftId") is not None:
            raise _error(f"{path} cannot mix stable and draft identity")
        result = copy.deepcopy(_existing(stable_id, existing_definitions, path))
    applicability = _applicability_record(
        _object(item["applicability"], f"{path}.applicability"), allocator,
        existing_applicability, f"{path}.applicability",
    )
    if _resolve(item["applicabilityId"], allocator, f"{path}.applicabilityId") != applicability["stableId"]:
        raise _error(f"{path}.applicabilityId does not match its embedded applicability")
    optional_refs = {"controllerId", "nodeId", "requiredOwnerId", "recoveryTransitionId"}
    byte_fields = set(DEFINITION_AUTHORED_FIELDS[8:])
    for key in DEFINITION_AUTHORED_FIELDS:
        value = item[key]
        if key in optional_refs:
            result[key] = _resolve(value, allocator, f"{path}.{key}", optional=True)
        elif key in ("applicabilityId",):
            result[key] = _resolve(value, allocator, f"{path}.{key}")
        elif key in byte_fields:
            result[key] = _integer(value, f"{path}.{key}", 0xFF)
        else:
            result[key] = _integer(value, f"{path}.{key}")
    return result, applicability


def _child_record(
    kind: str, item: dict[str, Any], creating_parent: bool,
    old_children: dict[int, dict[str, Any]], allocator: _Allocator, path: str,
) -> dict[str, Any]:
    required = CHILD_FIELDS[kind] - {"draftId", "stableId"}
    _keys(item, CHILD_FIELDS[kind], required, path)
    identity_kind, identity = _nested_identity(item, creating_parent, path)
    if identity_kind == "draft":
        stable_id = allocator.draft_map[identity]  # type: ignore[index]
        result = {"stableId": stable_id, "registryKey": _registry_for_draft(allocator, identity)}  # type: ignore[arg-type]
    else:
        result = copy.deepcopy(_existing(identity, old_children, path))  # type: ignore[arg-type]
    optional_refs = {
        "guards": {"referenceId"},
        "operations": {"definitionId", "ownerId", "replacementDefinitionId", "policyId", "instanceKey"},
        "actions": {"referenceId"},
        "recoveryActions": set(),
    }[kind]
    bool_fields = {"negate", "required"}
    for key in required:
        if key in optional_refs:
            result[key] = _resolve(item[key], allocator, f"{path}.{key}", optional=True)
        elif key in ("ownerId",) and kind == "recoveryActions":
            result[key] = _resolve(item[key], allocator, f"{path}.{key}")
        elif key in bool_fields:
            result[key] = int(bool(item[key]))
        else:
            maximum = 0xFF if key in ("kind", "busyPolicy", "phase") or (kind == "guards" and key == "payload") else 0xFFFF
            result[key] = _integer(item[key], f"{path}.{key}", maximum)
    if kind == "guards":
        result.setdefault("flags", 0)
        result.setdefault("reserved", 0)
    elif kind == "operations":
        result.setdefault("flags", 0)
    return result


def _transition_record(
    item: dict[str, Any], creating: bool, existing: dict[str, Any] | None,
    allocator: _Allocator, definitions: dict[int, dict[str, Any]], path: str,
    retirements: list[str], retired: set[str], definition_updates: dict[int, dict[str, Any]],
    applicability: dict[int, dict[str, Any]], applicability_updates: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    _keys(item, TRANSITION_FIELDS, (
        "name", "controllerIds", "candidateDefinitionId", "candidateDefinition",
        "ownerId", "trigger", "fromRoleMask", "dispatchPriority", "order",
        "guards", "operations", "actions", "recoveryActions",
    ), path)
    identity = _identity(item, creating, path)
    definition, applicability_record = _definition_record(
        _object(item["candidateDefinition"], f"{path}.candidateDefinition"), allocator,
        definitions, applicability, f"{path}.candidateDefinition",
    )
    definition_ref = _resolve(item["candidateDefinitionId"], allocator, f"{path}.candidateDefinitionId")
    if definition_ref != definition["stableId"]:
        raise _error(f"{path}.candidateDefinitionId does not match its embedded definition")
    prior_definition = definition_updates.get(definition_ref)
    if prior_definition is not None and prior_definition != definition:
        raise _error(f"candidate definition {definition_ref} has conflicting authored updates")
    definition_updates[definition_ref] = definition
    applicability_id = applicability_record["stableId"]
    prior_applicability = applicability_updates.get(applicability_id)
    if prior_applicability is not None and prior_applicability != applicability_record:
        raise _error(f"applicability {applicability_id} has conflicting authored updates")
    applicability_updates[applicability_id] = applicability_record

    # controllerIds is a derived scope check, never a separately persisted relation.
    controller_ids = [_resolve(value, allocator, f"{path}.controllerIds[{index}]")
                      for index, value in enumerate(_array(item["controllerIds"], f"{path}.controllerIds"))]
    expected_scope = [definition["controllerId"]] if definition["controllerId"] else None
    if expected_scope is not None and controller_ids != expected_scope:
        raise _error(f"{path}.controllerIds conflicts with its candidate-definition scope")

    old_children_by_kind = {
        key: _index(existing[key], f"transition {key}") if existing else {} for key in CHILD_FIELDS
    }
    children: dict[str, list[dict[str, Any]]] = {}
    for child_key in ("guards", "operations", "actions", "recoveryActions"):
        children[child_key] = [
            _child_record(child_key, _object(child, f"{path}.{child_key}[{index}]"),
                          creating, old_children_by_kind[child_key], allocator,
                          f"{path}.{child_key}[{index}]")
            for index, child in enumerate(_array(item[child_key], f"{path}.{child_key}"))
        ]
        kept = {child["stableId"] for child in children[child_key]}
        for stable_id, child in old_children_by_kind[child_key].items():
            if stable_id not in kept:
                _retire(child["registryKey"], retirements, retired)
    if creating:
        draft = identity  # type: ignore[assignment]
        stable_id = allocator.draft_map[draft]
        result = {"stableId": stable_id, "registryKey": _registry_for_draft(allocator, draft)}
    else:
        assert existing is not None
        result = {key: copy.deepcopy(value) for key, value in existing.items() if key not in CHILD_FIELDS}
    result.update({
        "name": _name(item["name"], f"{path}.name"), "definitionId": definition_ref,
        "order": _integer(item["order"], f"{path}.order"),
        "ownerId": _resolve(item["ownerId"], allocator, f"{path}.ownerId"),
        "trigger": _integer(item["trigger"], f"{path}.trigger", 0xFF),
        "fromRoleMask": _integer(item["fromRoleMask"], f"{path}.fromRoleMask", 0xFF),
        "dispatchPriority": _integer(item["dispatchPriority"], f"{path}.dispatchPriority"),
        **children,
    })
    return result


def _materialize(
    model: dict[str, Any], changes: dict[str, dict[str, list[Any]]]
) -> tuple[dict[str, Any], dict[str, int]]:
    result = copy.deepcopy(model)
    allocator = _Allocator(result)
    _scan_allocations(changes, allocator)
    retirements: list[str] = []
    retired: set[str] = set()

    provenance_by_kind = {
        record["value"]: record["stableId"] for record in result["semanticIds"]
        if record["kind"] == 1
    }
    profiles = _index(result["stateProfiles"], "state profiles")
    for raw_id in changes["stateProfiles"]["remove"]:
        stable_id = _stable_id(raw_id, "stateProfiles.remove[]")
        record = _existing(stable_id, profiles, "stateProfiles.remove[]")
        _retire(record["registryKey"], retirements, retired)
        _retire(record["bodyRegistryKey"], retirements, retired)
        del profiles[stable_id]
    for index, raw in enumerate(changes["stateProfiles"]["update"]):
        path = f"stateProfiles.update[{index}]"
        item = _object(raw, path)
        stable_id = _stable_id(item.get("stableId"), f"{path}.stableId")
        profiles[stable_id] = _profile_record(
            item, False, _existing(stable_id, profiles, path), allocator, provenance_by_kind, path
        )
    for index, raw in enumerate(changes["stateProfiles"]["create"]):
        path = f"stateProfiles.create[{index}]"
        item = _object(raw, path)
        record = _profile_record(item, True, None, allocator, provenance_by_kind, path)
        profiles[record["stableId"]] = record
    result["stateProfiles"] = list(profiles.values())

    controllers = _index(result["controllers"], "controllers")
    for raw_id in changes["controllers"]["remove"]:
        stable_id = _stable_id(raw_id, "controllers.remove[]")
        record = _existing(stable_id, controllers, "controllers.remove[]")
        _retire(record["registryKey"], retirements, retired)
        for node in record["nodes"]:
            _retire(node["registryKey"], retirements, retired)
        del controllers[stable_id]
    for operation in ("update", "create"):
        for index, raw in enumerate(changes["controllers"][operation]):
            path = f"controllers.{operation}[{index}]"
            item = _object(raw, path)
            creating = operation == "create"
            stable_id = (allocator.draft_map[_draft_id(item.get("draftId"), f"{path}.draftId")]
                         if creating else _stable_id(item.get("stableId"), f"{path}.stableId"))
            previous = None if creating else _existing(stable_id, controllers, path)
            controllers[stable_id] = _controller_record(
                item, creating, previous, allocator, path, retirements, retired
            )
    result["controllers"] = list(controllers.values())

    transitions = _index(result["transitions"], "transitions")
    definitions = _index(result["overrideDefinitions"], "override definitions")
    applicability = _index(result["applicability"], "applicability")
    for raw_id in changes["transitions"]["remove"]:
        stable_id = _stable_id(raw_id, "transitions.remove[]")
        record = _existing(stable_id, transitions, "transitions.remove[]")
        _retire(record["registryKey"], retirements, retired)
        for key in CHILD_FIELDS:
            for child in record[key]:
                _retire(child["registryKey"], retirements, retired)
        del transitions[stable_id]
    definition_updates: dict[int, dict[str, Any]] = {}
    applicability_updates: dict[int, dict[str, Any]] = {}
    for operation in ("update", "create"):
        for index, raw in enumerate(changes["transitions"][operation]):
            path = f"transitions.{operation}[{index}]"
            item = _object(raw, path)
            creating = operation == "create"
            stable_id = (allocator.draft_map[_draft_id(item.get("draftId"), f"{path}.draftId")]
                         if creating else _stable_id(item.get("stableId"), f"{path}.stableId"))
            previous = None if creating else _existing(stable_id, transitions, path)
            transitions[stable_id] = _transition_record(
                item, creating, previous, allocator, definitions, path,
                retirements, retired, definition_updates, applicability, applicability_updates,
            )
    definitions.update(definition_updates)
    applicability.update(applicability_updates)

    # Candidate definitions and applicability records are graph-owned.  Retire
    # them only after their final transition/operation/static backlink is gone.
    referenced_definitions = {
        transition["definitionId"] for transition in transitions.values()
    }
    for transition in transitions.values():
        for operation in transition["operations"]:
            referenced_definitions.update(
                value for value in (
                    operation["definitionId"], operation["replacementDefinitionId"],
                    operation["instanceKey"],
                ) if value in definitions
            )
    referenced_definitions.update(item["definitionId"] for item in result["tiredTranslations"])
    for stable_id, definition in list(definitions.items()):
        if stable_id not in referenced_definitions:
            _retire(definition["registryKey"], retirements, retired)
            del definitions[stable_id]

    referenced_applicability = {definition["applicabilityId"] for definition in definitions.values()}
    for stable_id, rule in list(applicability.items()):
        if stable_id not in referenced_applicability:
            _retire(rule["registryKey"], retirements, retired)
            del applicability[stable_id]

    ordered_transitions = sorted(
        transitions.values(), key=lambda record: (record["order"], record["stableId"])
    )
    for order, transition in enumerate(ordered_transitions):
        transition["order"] = order
    result["transitions"] = ordered_transitions
    result["overrideDefinitions"] = list(definitions.values())
    result["applicability"] = list(applicability.values())

    history_events = allocator.events + [("retire", key) for key in retirements]
    result["stableIdHistory"], allocated = v40.append_stable_history_events(
        result["stableIdHistory"], history_events
    )
    for draft, registry_key in allocator.registry_by_draft.items():
        if allocated.get(registry_key) != allocator.draft_map[draft]:
            raise _error("stable ID history allocation order changed unexpectedly")
    return result, dict(allocator.draft_map)


def _render_files(root: Path, model: dict[str, Any]) -> dict[Path, bytes]:
    v40.validate_model(model)
    model_bytes = v40.canonical_json_bytes(model)
    reloaded = json.loads(model_bytes)
    if v40.canonical_json_bytes(reloaded) != model_bytes:
        raise _error("canonical JSON roundtrip is not deterministic")
    blob = v40.encode_model(model)
    decoded = v40.decode_blob(blob, stable_id_history=model["stableIdHistory"])
    v40.validate_model(decoded)
    if v40.encode_model(decoded) != blob:
        raise _error("OWBD v40 encode/decode roundtrip changed the generated blob")
    authored_projection = v40.merge_authored_metadata(decoded, reloaded)
    if v40.canonical_json_bytes(authored_projection) != model_bytes:
        raise _error("canonical authored projection changed across generated decode/reload")
    inc_bytes = v40.render_inc(blob).encode()
    parsed_inc = bytes(int(value, 16) for value in re.findall(rb"\b0x([0-9A-Fa-f]{2})\b", inc_bytes))
    if parsed_inc != blob:
        raise _error("generated include does not reproduce the validated blob")
    header_path = root / HEADER_PATH
    header_bytes = v40.render_header(model, blob, header_path.read_text()).encode()
    return {
        root / MODEL_PATH: model_bytes,
        root / INC_PATH: inc_bytes,
        header_path: header_bytes,
    }


def _replace_atomically(
    rendered: dict[Path, bytes],
    *,
    replace_func: Callable[[str | os.PathLike[str], str | os.PathLike[str]], None] = os.replace,
    before_replace: Callable[[int, Path], None] | None = None,
) -> None:
    originals = {path: path.read_bytes() for path in rendered}
    changed = [path for path, data in rendered.items() if originals[path] != data]
    if not changed:
        return
    temporary: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path in changed:
            descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            temporary[path] = Path(raw_path)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(rendered[path])
                stream.flush()
                os.fsync(stream.fileno())
        for index, path in enumerate(changed):
            if before_replace is not None:
                before_replace(index, path)
            replaced.append(path)
            replace_func(temporary[path], path)
            temporary.pop(path, None)
    except BaseException:
        # Rollback does not use the injected replacement hook: it is the final
        # recovery path and must restore every already-published original.
        for path in reversed(replaced):
            descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.rollback.", suffix=".tmp", dir=path.parent)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(originals[path])
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(raw_path, path)
        raise
    finally:
        for path in temporary.values():
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def apply_behavior_model_changes(
    root: str | os.PathLike[str], payload: Any, *,
    _replace_func: Callable[[str | os.PathLike[str], str | os.PathLike[str]], None] = os.replace,
    _before_replace: Callable[[int, Path], None] | None = None,
) -> dict[str, int]:
    """Validate and atomically persist one compact V40 authoring transaction.

    The return value maps every explicit ``draft:`` identity in the payload to
    its newly allocated stable ID.  No managed file is changed unless all
    canonical and generated representations validate in memory first.
    """
    workspace = Path(root).resolve()
    paths = [workspace / relative for relative in MANAGED_PATHS]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise _error(f"behavior-model workspace is missing managed files: {missing}")
    changes = _parse_payload(payload)
    model = v40.load_model(workspace / MODEL_PATH)
    if not any(changes[domain][operation] for domain in DOMAIN_KEYS for operation in DELTA_KEYS):
        return {}
    materialized, draft_map = _materialize(model, changes)
    rendered = _render_files(workspace, materialized)
    _replace_atomically(
        rendered, replace_func=_replace_func, before_replace=_before_replace
    )
    return draft_map


__all__ = ["BehaviorModelWriteError", "apply_behavior_model_changes"]
