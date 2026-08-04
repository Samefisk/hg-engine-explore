#!/usr/bin/env python3
"""Independently validate and replay the emitted direct-cutover v40 graph."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import re
import struct
import tempfile
from pathlib import Path

try:
    from overworld_wild_behavior_v40_field_metadata import (
        SIGNED_DELTA_OPERATORS, numeric_bounds, operator_allowed,
        scalar_value_valid, state_body_values_valid,
    )
except ModuleNotFoundError:
    from scripts.overworld_wild_behavior_v40_field_metadata import (
        SIGNED_DELTA_OPERATORS, numeric_bounds, operator_allowed,
        scalar_value_valid, state_body_values_valid,
    )

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_MODEL = ROOT / "data" / "OverworldWildBehaviorModelV40.json"
EXPECTED_TYPED_EVENT_DIGEST = "1f57fc0f2996f8c25d1838db27e895cda1ce63a15b24d080847f923041238701"

# Deliberately duplicated wire decode vocabulary.  The replay executor must
# not import generator mappings or the host validator it is cross-checking.
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
DEAD_DIAGNOSTIC_FIELDS = {"profileId"}
SECTION_SPECS = (
    ("stateBodies", 32), ("profileIdentities", 8),
    ("controllers", 24), ("controllerNodes", 12),
    ("genericAssignments", 20), ("speciesAssignments", 8),
    ("overrideSources", 28), ("overrideMembers", 2),
    ("overrideActions", 12), ("spawnPolicies", 12),
    ("populationPolicies", 10), ("hookSets", 8), ("owners", 6),
    ("overrideDefinitions", 36), ("modifierOperations", 11),
    ("transitions", 24),
    ("transitionGuards", 12), ("transitionOperations", 18),
    ("transitionActions", 10), ("recoveryActions", 8),
    ("importRecipes", 24), ("applicability", 16),
    ("tiredTranslations", 24), ("semanticIds", 8),
)


class Graph:
    def __init__(self, blob, source, path):
        self.blob, self.path, self.sections = blob, path, {}
        cursor = 216
        for index, (name, expected_stride) in enumerate(SECTION_SPECS):
            offset, count, stride = struct.unpack_from("<IHH", blob, 24 + index * 8)
            if offset != cursor or stride != expected_stride or count > (len(blob) - offset) // stride:
                raise ValueError(f"{path}: independent directory mismatch for {name}")
            cursor += count * stride
            aligned = (cursor + 3) & ~3
            if blob[cursor:aligned] != bytes(aligned - cursor):
                raise ValueError(f"{path}: independent nonzero section padding")
            cursor = aligned
            self.sections[name] = (offset, count, stride)
        if cursor != len(blob): raise ValueError(f"{path}: independent unclaimed blob bytes")

    def records(self, name, fmt):
        offset, count, stride = self.sections[name]
        if struct.calcsize(fmt) != stride: raise ValueError(f"{self.path}: independent decoder stride")
        return [struct.unpack_from(fmt, self.blob, offset + index * stride) for index in range(count)]


def _wire_match_valid(raw):
    group, species, terrain, minimum, maximum, shiny, behavior_class, reserved = \
        struct.unpack("<IH6B", raw)
    return (reserved == 0 and terrain in (0, 1, 2, 3, 0xFF)
            and (not minimum or not maximum or minimum <= maximum)
            and shiny in (0, 1, 0xFF)
            and behavior_class in (0, 1, 2, 3, 0xFD, 0xFF))


def _wire_modifier_valid(kind, payload):
    field, operator, delta_byte, bound, role_mask, reserved = payload[:6]
    controller = struct.unpack_from("<H", payload, 6)[0]
    field_ranges = {4: (1, 27), 5: (1, 7), 7: (1, 5), 9: (1, 1)}
    minimum, maximum = field_ranges[kind]
    numeric_masks = {4: 0x031FFE18, 5: 0x000000D8, 7: 0x00000038, 9: 0x00000002}
    if (not minimum <= field <= maximum or (kind == 4 and field == 22)
            or reserved or not 1 <= operator <= 6):
        return False
    if kind == 4:
        if not role_mask or role_mask & ~7:
            return False
    elif role_mask or controller:
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


def validate_graph_closure(graph, live_ids, body_roles, identities, semantic,
                           controller_ids, nodes):
    """Validate variable-size authored graph closure without baseline identities/counts."""
    path = graph.path
    semantic_pairs = set()
    semantic_domains = {
        1: frozenset(range(1, 8)),
        2: frozenset(range(1, 4)),
        3: frozenset((1, 2, 3, 6, 7, 11)),
    }
    for stable, kind, value, reserved0, reserved1 in semantic.values():
        if (kind, value) in semantic_pairs or value not in semantic_domains.get(kind, ()) \
                or reserved0 or reserved1:
            raise ValueError(f"{path}: independent semantic identity mismatch")
        semantic_pairs.add((kind, value))

    controllers = graph.records("controllers", "<7H10B")
    controller_records = {record[0]: record for record in controllers}
    for controller in controllers:
        stable, name, start, count = controller[:4]
        local = list(nodes.values())[start:start + count]
        selectors = {(record[4], record[3]) for record in local}
        if (stable != name or len(local) != count or len(selectors) != count):
            raise ValueError(f"{path}: independent controller identity/selector mismatch")
    for stable, controller, profile, custom, role, flags, reserved in nodes.values():
        if (flags & ~7 or (role == 7) != bool(custom)
                or (custom and semantic.get(custom, (0, 0))[1] != 2)):
            raise ValueError(f"{path}: independent controller node selector mismatch")

    actions = graph.records("overrideActions", "<HBB8s")
    assignment_count = 0
    while assignment_count < len(actions) and actions[assignment_count][1] == 1:
        assignment_count += 1
    if any(record[1] == 1 for record in actions[assignment_count:]):
        raise ValueError(f"{path}: independent assignment action prefix mismatch")
    for stable, kind, flags, payload in actions[:assignment_count]:
        controller, zero0, zero1, zero2 = struct.unpack("<4H", payload)
        if kind != 1 or flags or controller not in controller_ids or zero0 or zero1 or zero2:
            raise ValueError(f"{path}: independent assignment action mismatch")

    seen_species = set()
    for stable, raw, action_index, priority, reserved in \
            graph.records("genericAssignments", "<H12sHHH"):
        if (not _wire_match_valid(raw) or action_index >= assignment_count
                or reserved):
            raise ValueError(f"{path}: independent generic assignment mismatch")
    for stable, species, action_index, priority in \
            graph.records("speciesAssignments", "<4H"):
        if (not species or species in seen_species or action_index >= assignment_count
                ):
            raise ValueError(f"{path}: independent species assignment mismatch")
        seen_species.add(species)

    spawn = {record[0]: record for record in graph.records("spawnPolicies", "<3H6B")}
    population = {record[0]: record for record in graph.records("populationPolicies", "<4H2B")}
    hooks = {record[0]: record for record in graph.records("hookSets", "<2H4B")}
    override_ids = {record[0] for record in graph.records("overrideSources", "<HH12s4HBBH")}
    for record in spawn.values():
        if semantic.get(record[2], (0, 0))[1] != 1:
            raise ValueError(f"{path}: independent spawn provenance mismatch")
    for record in population.values():
        if (semantic.get(record[2], (0, 0))[1] != 3
                or (semantic.get(record[3], (0, 0))[1] != 1
                    and record[3] not in override_ids)):
            raise ValueError(f"{path}: independent population semantic/provenance mismatch")

    member_cursor = 0
    action_cursor = assignment_count
    override_slices = {}
    override_orders = set()
    override_records = graph.records("overrideSources", "<HH12s4HBBH")
    members = [record[0] for record in graph.records("overrideMembers", "<H")]
    for (stable, name, raw, member_start, member_count, action_start,
         action_count, target, order, priority) in override_records:
        local_members = members[member_start:member_start + member_count]
        if (stable != name or not _wire_match_valid(raw)
                or member_start != member_cursor or action_start != action_cursor
                or len(local_members) != member_count or len(set(local_members)) != member_count
                or any(not member for member in local_members)
                or target not in (0, 1, 2) or (target == 1 and not member_count)
                or order in override_orders):
            raise ValueError(f"{path}: independent override source/slice mismatch")
        override_orders.add(order)
        override_slices[stable] = (action_start, action_count)
        member_cursor += member_count
        action_cursor += action_count
    if (member_cursor != len(members) or action_cursor != len(actions) \
            or override_orders != set(range(1, len(override_records) + 1))):
        raise ValueError(f"{path}: independent unclaimed override slice")

    profile_values = {
        stable: graph_record[3]
        for stable, body, provenance, tag_a, tag_b in identities.values()
        for graph_record in graph.records("stateBodies", "<HBB28s")
        if graph_record[0] == body
    }
    for stable, kind, flags, payload in actions[assignment_count:]:
        first, second, third, fourth = struct.unpack("<4H", payload)
        valid = not flags and 2 <= kind <= 11
        if valid and kind == 2:
            valid = (first in controller_ids and second in nodes
                     and nodes[second][1] == first and third in identities
                     and profile_values[third][0] != 0 and fourth == 0)
        elif valid and kind == 3:
            valid = (first in controller_ids and second in nodes
                     and nodes[second][1] == first and not nodes[second][5] & 1
                     and third == 0 and fourth == 0)
        elif valid and kind in (4, 5, 7, 9):
            valid = _wire_modifier_valid(kind, payload)
            if kind == 4:
                target_controller = struct.unpack_from("<H", payload, 6)[0]
                valid = valid and (not target_controller or target_controller in controller_ids)
        elif valid and kind in (6, 8, 10):
            targets = {6: spawn, 8: population, 10: hooks}[kind]
            valid = first in targets and second == third == fourth == 0
        elif valid and kind == 11:
            operator, delta = payload[4], payload[5] - (0x100 if payload[5] >= 0x80 else 0)
            valid = (first in controller_ids and second in nodes and nodes[second][1] == first
                     and nodes[second][4] == 3 and not nodes[second][5] & 1
                     and payload[6:] == b"\0\0" and (operator == 1 or operator == 2 and -32 <= delta <= 32))
        if not valid:
            raise ValueError(f"{path}: independent static override action mismatch")

    owners = {record[0]: record for record in graph.records("owners", "<2H2B")}
    for stable, name, kind, flags in owners.values():
        if stable != name or kind != 1 or flags:
            raise ValueError(f"{path}: independent owner mismatch")
    definitions = {record[0]: record for record in graph.records("overrideDefinitions", "<8H20B")}
    applicability = {record[0]: record for record in graph.records("applicability", "<HHIHHBBH")}
    transitions = {record[0]: record for record in graph.records("transitions", "<9H4BH")}
    applicability_claims = {stable: 0 for stable in applicability}
    for stable, kind, group, controller, profile, minimum, maximum, flags in applicability.values():
        if (not kind or kind & ~0xF or flags or maximum
                or ((kind & 1) == 0) != (group == 0)
                or ((kind & 2) == 0) != (controller == 0)
                or ((kind & 4) == 0) != (profile == 0)
                or ((kind & 8) and not 1 <= minimum <= 7)
                or (not kind & 8 and minimum)
                or (controller and controller not in controller_ids)
                or (profile and profile not in identities)):
            raise ValueError(f"{path}: independent applicability mismatch")
    for definition in definitions.values():
        (stable, name, controller, node, owner, recovery, application, priority,
         kind, channel, selector, role, map_lifetime, battle_lifetime,
         timer_clock, timer_source, hidden_timer, recovery_policy, timer_value,
         has_origin, origin, has_owner, multiple_owners, multiple_instances,
         authored_bound, flags, reserved0, reserved1) = definition
        generated = bool(has_origin or has_owner)
        if (kind not in (1, 2) or not 0 <= channel <= 5
                or not ((kind == 1 and selector in (1, 2)) or (kind == 2 and selector == 0))
                or map_lifetime not in (1, 2, 3) or battle_lifetime not in (1, 2, 3)
                or timer_clock not in (0, 1, 2) or timer_source not in (0, 1, 2, 3)
                or hidden_timer not in (0, 1, 2, 3) or recovery_policy not in (0, 1)
                or any(value not in (0, 1) for value in (has_origin, has_owner,
                                                        multiple_owners, multiple_instances,
                                                        authored_bound))
                or reserved0 or reserved1 or application not in applicability
                or (owner and owner not in owners) or (recovery and recovery not in transitions)
                or has_origin != int(origin != 0) or has_owner != int(owner != 0)
                or (has_origin and (origin not in (1, 2, 3) or not has_owner))
                or ((timer_source != 0) != (timer_clock != 0))
                or ((timer_value != 0) != (timer_clock != 0))
                or (hidden_timer and not timer_clock)
                or ((recovery_policy != 0) != (recovery != 0))
                or (not generated and (channel == 5 or authored_bound or flags))
                or (generated and flags != (1 if selector == 1 else 0))):
            raise ValueError(f"{path}: independent definition domain/reference mismatch")
        if kind == 2:
            if (not 1 <= channel <= 4 or controller or node or owner or recovery or role
                    or timer_clock or timer_source or hidden_timer or recovery_policy
                    or timer_value or has_origin or origin or has_owner
                    or authored_bound or flags):
                raise ValueError(f"{path}: independent modifier definition payload mismatch")
        elif selector == 2:
            if controller or node or not 1 <= role <= 7:
                raise ValueError(f"{path}: independent semantic definition selector mismatch")
        elif (not controller or node not in nodes or nodes[node][1] != controller or role):
            raise ValueError(f"{path}: independent exact definition selector mismatch")
        rule = applicability[application]
        if kind == 1 and rule[1] & 0xC:
            raise ValueError(f"{path}: independent definition applicability mismatch")
        if selector == 1 and rule[3] != controller:
            raise ValueError(f"{path}: independent exact definition scope mismatch")
        applicability_claims[application] += 1
    if any(claim != 1 for claim in applicability_claims.values()):
        raise ValueError(f"{path}: independent applicability ownership mismatch")

    modifier_by_definition = {stable: [] for stable in definitions}
    for record in graph.records("modifierOperations", "<HHh5B"):
        stable, definition_id, operand, namespace, field, operator, bound, order = record
        kind = {1: 4, 2: 5}.get(namespace)
        if (definition_id not in definitions or kind is None
                or not operator_allowed(kind, field, operator)
                or (operator in SIGNED_DELTA_OPERATORS
                    and ((operator == 2 and bound)
                         or (operator != 2 and not scalar_value_valid(kind, field, bound))))
                or (operator not in SIGNED_DELTA_OPERATORS
                    and (bound or not scalar_value_valid(kind, field, operand)))):
            raise ValueError(f"{path}: independent modifier operation mismatch")
        modifier_by_definition[definition_id].append(record)
    for definition_id, records in modifier_by_definition.items():
        if definitions[definition_id][8] == 1:
            if records:
                raise ValueError(f"{path}: state candidate owns modifier operations")
            continue
        if (not 1 <= len(records) <= 16
                or sorted(record[7] for record in records) != list(range(len(records)))):
            raise ValueError(f"{path}: modifier operation order/count mismatch")
        lower = {(record[3], record[4]) for record in records if record[5] == 3}
        upper = {(record[3], record[4]) for record in records if record[5] == 4}
        if lower & upper:
            raise ValueError(f"{path}: modifier minimum/maximum conflict")

    guards = {record[0]: record for record in graph.records("transitionGuards", "<HH4BHH")}
    operations = {record[0]: record for record in graph.records("transitionOperations", "<7H4B")}
    transition_actions = {record[0]: record for record in graph.records("transitionActions", "<HHBBHH")}
    recoveries = {record[0]: record for record in graph.records("recoveryActions", "<HHHBB")}
    for transition in transitions.values():
        stable, definition_id, owner_id = transition[:3]
        required_owner = definitions[definition_id][4]
        if required_owner and owner_id != required_owner:
            raise ValueError(f"{path}: independent transition owner mismatch")
    for stable, transition, kind, negate, payload, flags, reference, reserved in guards.values():
        valid = (transition in transitions and 1 <= kind <= 8 and negate in (0, 1)
                 and not flags and not reserved)
        valid = valid and (
            (kind == 1 and not payload and not reference)
            or (kind == 2 and 1 <= payload <= 7 and not reference)
            or (kind == 3 and not payload and reference in nodes)
            or (kind in (4, 5) and not payload and reference in owners)
            or (kind == 6 and 1 <= payload <= 3 and not reference)
            or (kind == 7 and payload <= 100 and not reference)
            or (kind == 8 and 1 <= payload <= 13 and not reference))
        if not valid:
            raise ValueError(f"{path}: independent transition guard reference mismatch")
    for (stable, transition, definition_id, owner, replacement, policy, instance,
         kind, busy, required, flags) in operations.values():
        valid = (transition in transitions and 1 <= kind <= 6 and busy in (1, 2)
                 and required in (0, 1) and not flags
                 and (not definition_id or definition_id in definitions)
                 and (not replacement or replacement in definitions)
                 and (not owner or owner in owners) and (not policy or policy in live_ids)
                 and (not instance or instance in live_ids)
                 and ((kind <= 5 and owner in owners) or (kind == 6 and not owner)))
        if valid and kind <= 4:
            for candidate in ((definition_id, replacement) if kind == 2 else (definition_id,)):
                valid = valid and bool(candidate)
                if candidate and definitions[candidate][4]:
                    valid = valid and owner == definitions[candidate][4]
        valid = valid and (
            (kind == 1 and bool(definition_id) and not replacement and not policy
             and instance == definition_id and not required)
            or (kind == 2 and bool(definition_id) and bool(replacement) and not policy
                and instance == definition_id and not required)
            or (kind == 3 and bool(definition_id) and not replacement and not policy
                and not instance and required == 1)
            or (kind == 4 and bool(definition_id) and not replacement and not policy
                and not instance and not required)
            or (kind == 5 and not definition_id and bool(owner) and not replacement
                and not policy and not instance and not required)
            or (kind == 6 and not definition_id and not owner and not replacement
                and bool(policy) and not instance and not required)
        )
        if not valid:
            raise ValueError(f"{path}: independent transition operation reference mismatch")
    for stable, transition, phase, kind, reference, payload in transition_actions.values():
        if transition not in transitions or not 1 <= phase <= 4 or not 1 <= kind <= 8 \
                or reference or payload:
            raise ValueError(f"{path}: independent transition action mismatch")
    for stable, transition, owner, kind, required in recoveries.values():
        if (transition not in transitions or owner not in owners or not 1 <= kind <= 4
                or required not in (0, 1) or owner != transitions[transition][2]):
            raise ValueError(f"{path}: independent recovery action mismatch")

    imports = graph.records("importRecipes", "<10H4B")
    for (stable, owner, controller, node, profile, recovery, source, action_start,
         action_count, reserved, role, lifetime, contextual, flags) in imports:
        expected_slice = (0, 0) if not source else override_slices.get(source)
        if (owner not in owners or (controller and controller not in controller_ids)
                or (node and (node not in nodes or nodes[node][1] != controller
                              or nodes[node][2] != profile))
                or profile not in identities or (recovery and recovery not in transitions)
                or (source and source not in override_slices)
                or expected_slice != (action_start, action_count)
                or not 1 <= role <= 7 or lifetime not in (1, 2, 3)
                or contextual not in (0, 1) or flags
                or reserved != (0 if contextual else 0xFFFF)):
            raise ValueError(f"{path}: independent import closure mismatch")

    for item in graph.records("tiredTranslations", "<HBB6H4B2H"):
        (stable, origin, authored, controller, profile, definition_id, recovery,
         fallback_controller, fallback_node, remove_candidate, remove_calm,
         cooldown, required, flags, reserved) = item
        definition = definitions.get(definition_id)
        if (origin not in (1, 2, 3) or authored not in (0, 1)
                or controller not in controller_ids or profile not in identities
                or definition is None or recovery not in transitions
                or remove_candidate != 1 or remove_calm != 1 or cooldown != 2
                or required != 1 or flags or reserved
                or definition[19] != 1 or definition[20] != origin
                or definition[21] != 1 or definition[5] != recovery):
            raise ValueError(f"{path}: independent tired translation closure mismatch")
        if authored:
            valid = not fallback_controller and not fallback_node and definition[10] == 2
        else:
            valid = (fallback_controller == controller and fallback_node in nodes
                     and nodes[fallback_node][1] == controller
                     and nodes[fallback_node][2] == profile
                     and definition[10] == 1 and definition[2] == controller
                     and definition[3] == fallback_node)
        if not valid:
            raise ValueError(f"{path}: independent tired fallback mismatch")

    dispatch = []
    for transition in transitions.values():
        definition = definitions[transition[1]]
        application = applicability[definition[6]]
        dispatch.append((transition, definition[2] or application[3]))
    for index, (left, left_controller) in enumerate(dispatch):
        for right, right_controller in dispatch[index + 1:]:
            if (left[13] == right[13] and left[9] == right[9] and left[10] & right[10]
                    and (not left_controller or not right_controller
                         or left_controller == right_controller)):
                raise ValueError(f"{path}: independent ambiguous transition dispatch")


def validate_direct_cutover_records(graph):
    path = graph.path
    semantic = {record[0]: record for record in graph.records("semanticIds", "<HBBHH")}
    spawn = {record[0]: record for record in graph.records("spawnPolicies", "<3H6B")}
    population = {record[0]: record for record in graph.records("populationPolicies", "<4H2B")}
    hooks = {record[0]: record for record in graph.records("hookSets", "<2H4B")}
    controllers = graph.records("controllers", "<7H10B")
    nodes = graph.records("controllerNodes", "<4HBBH")

    for stable, name, provenance, state, destination, minimum, maximum, hop, flags in spawn.values():
        if (stable != name or provenance not in semantic or semantic[provenance][1] != 1 \
                or state > 3 or destination > 16 or not 1 <= minimum <= maximum <= 8 \
                or hop > 64 or flags):
            raise ValueError(f"{path}: direct-cutover spawn configuration mismatch")
    for stable, name, group, provenance, limit, flags in population.values():
        if stable != name or group not in semantic or semantic[group][1] != 3 \
                or not provenance or limit > 10 or flags:
            raise ValueError(f"{path}: direct-cutover population configuration mismatch")
    for stable, name, help_call, pickup_entry, pickup_loop, flags in hooks.values():
        if stable != name or help_call > 1 or pickup_entry > 1 or pickup_loop != pickup_entry \
                or (help_call and pickup_entry) or flags:
            raise ValueError(f"{path}: direct-cutover hook configuration mismatch")
    node_cursor = 0
    for controller in controllers:
        stable, name, node_start, node_count, spawn_id, population_id, hook_id = controller[:7]
        local_nodes = nodes[node_start:node_start + node_count]
        if stable != name or node_start != node_cursor or not node_count \
                or spawn_id not in spawn or population_id not in population or hook_id not in hooks \
                or controller[15:] != (0, 0) \
                or any(not scalar_value_valid(5, field, value)
                       for field, value in enumerate(controller[7:14], 1)) \
                or len(local_nodes) != node_count or any(node[1] != stable for node in local_nodes) \
                or sum(bool(node[5] & 1) for node in local_nodes) != 1:
            raise ValueError(f"{path}: direct-cutover controller/configuration binding mismatch")
        node_cursor += node_count
    if node_cursor != len(nodes):
        raise ValueError(f"{path}: unclaimed controller nodes")

    definitions = {record[0]: record for record in graph.records("overrideDefinitions", "<8H20B")}
    owners = {record[0]: record for record in graph.records("owners", "<2H2B")}
    guards = graph.records("transitionGuards", "<HH4BHH")
    operations = graph.records("transitionOperations", "<7H4B")
    actions = graph.records("transitionActions", "<HHBBHH")
    recoveries = graph.records("recoveryActions", "<HHHBB")
    cursors = [0, 0, 0, 0]
    for transition_index, transition in enumerate(graph.records("transitions", "<9H4BH")):
        (stable, definition, owner, guard_start, guard_count, operation_start,
         operation_count, action_start, action_count, trigger, from_roles,
         recovery_start, recovery_count, priority) = transition
        if definition not in definitions or owner not in owners or not 1 <= trigger <= 13 \
                or not from_roles or from_roles & ~0x7F \
                or [guard_start, operation_start, action_start, recovery_start] != cursors:
            raise ValueError(f"{path}: direct-cutover transition header/slice mismatch")
        transition_guards = guards[guard_start:guard_start + guard_count]
        transition_operations = operations[operation_start:operation_start + operation_count]
        transition_actions = actions[action_start:action_start + action_count]
        transition_recoveries = recoveries[recovery_start:recovery_start + recovery_count]
        if len(transition_guards) != guard_count or len(transition_operations) != operation_count \
                or len(transition_actions) != action_count or len(transition_recoveries) != recovery_count:
            raise ValueError(f"{path}: direct-cutover transition slice escaped section")
        for guard in transition_guards:
            if guard[1] != stable or not 1 <= guard[2] <= 8 or guard[3] > 1 \
                    or guard[5] or guard[7]:
                raise ValueError(f"{path}: direct-cutover transition guard mismatch")
        for operation in transition_operations:
            kind = operation[7]
            if operation[1] != stable or not 1 <= kind <= 6 or operation[8] not in (1, 2) \
                    or operation[9] > 1 or operation[10] \
                    or (operation[2] and operation[2] not in definitions) \
                    or (operation[3] and operation[3] not in owners) \
                    or (operation[6] and kind not in (1, 2)):
                raise ValueError(f"{path}: direct-cutover transition operation mismatch")
        for action in transition_actions:
            if action[1] != stable or not 1 <= action[2] <= 4 or not 1 <= action[3] <= 8:
                raise ValueError(f"{path}: direct-cutover transition action mismatch")
        for recovery in transition_recoveries:
            if recovery[1] != stable or recovery[2] not in owners \
                    or not 1 <= recovery[3] <= 4 or recovery[4] not in (0, 1):
                raise ValueError(f"{path}: direct-cutover recovery action mismatch")
        if trigger == 2 and not any(guard[2] == 8 and guard[4] == trigger
                                    for guard in transition_guards):
            raise ValueError(f"{path}: stamina transition lacks exact system-route evidence")
        cursors = [guard_start + guard_count, operation_start + operation_count,
                   action_start + action_count, recovery_start + recovery_count]
    if cursors != [len(guards), len(operations), len(actions), len(recoveries)]:
        raise ValueError(f"{path}: unclaimed direct-cutover transition records")


def validate_wire(path, source):
    blob = path.read_bytes()
    if len(blob) < 216 or len(blob) > 0x3000:
        raise ValueError(f"{path}: independent size/cap mismatch")
    magic, version, header_size, size, flags, checksum, fingerprint = struct.unpack_from("<IHHIIII", blob)
    defines = {name: int(value, 0) for name, value in re.findall(
        r"^\s*#\s*define\s+(OVERWORLD_WILD_BEHAVIOR_DATA_(?:CHECKSUM|SCHEMA_FINGERPRINT))\s+(0[xX][0-9A-Fa-f]+|[0-9]+)(?:u)?\b",
        source.read_text(), re.MULTILINE)}
    scratch = bytearray(blob); scratch[16:20] = bytes(4)
    if (magic, version, header_size, size, flags) != (0x4F574244, 40, 216, len(blob), 6) \
            or checksum != defines["OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM"] \
            or fingerprint != defines["OVERWORLD_WILD_BEHAVIOR_DATA_SCHEMA_FINGERPRINT"] \
            or checksum != binascii.crc32(scratch) & 0xFFFFFFFF:
        raise ValueError(f"{path}: independent header/checksum mismatch")
    graph = Graph(blob, source, path)
    seen = set()
    for name, stride in SECTION_SPECS:
        if name == "overrideMembers": continue
        for record in graph.records(name, "<H" + "x" * (stride - 2)):
            if not record[0] or record[0] in seen: raise ValueError(f"{path}: independent stable-ID collision")
            seen.add(record[0])
    body_roles = {}
    for stable, role, count, values in graph.records("stateBodies", "<HBB28s"):
        if count != 28 or not 1 <= role <= 7 or not state_body_values_valid(values):
            raise ValueError(f"{path}: independent state-body invariant mismatch")
        body_roles[stable] = role
    identities = {record[0]: record for record in graph.records("profileIdentities", "<HHHBB")}
    semantic = {record[0]: record for record in graph.records("semanticIds", "<HBBHH")}
    if (any(record[1] not in body_roles or record[2] not in semantic
            or semantic[record[2]][1] != 1 for record in identities.values())
            or set(body_roles) != {record[1] for record in identities.values()}):
        raise ValueError(f"{path}: independent profile body/provenance reference mismatch")
    controller_ids = {record[0] for record in graph.records("controllers", "<7H10B")}
    node_records = graph.records("controllerNodes", "<4HBBH")
    nodes = {record[0]: record for record in node_records}
    for stable, controller, profile, custom, role, node_flags, reserved in node_records:
        if controller not in controller_ids or profile not in identities or not 1 <= role <= 7 or reserved:
            raise ValueError(f"{path}: independent controller node reference mismatch")
    for (stable, owner, controller, node, profile, recovery, source_id, action_start,
         action_count, truth, role, lifetime, import_flags, reserved) in \
            graph.records("importRecipes", "<10H4B"):
        if profile not in identities or (controller and controller not in controller_ids) \
                or (node and node not in nodes) or not 1 <= role <= 7:
            raise ValueError(f"{path}: independent import reference mismatch")
    validate_direct_cutover_records(graph)
    validate_graph_closure(
        graph, seen, body_roles, identities, semantic, controller_ids, nodes,
    )
    return graph


def scalar(value):
    return value.get("value", value) if isinstance(value, dict) else value


def decode_match(raw):
    group, species, terrain, minimum, maximum, shiny, behavior_class, _ = struct.unpack("<IH6B", raw)
    return group, species, terrain, minimum, maximum, shiny, behavior_class


def applies(match, context):
    group, species, terrain, minimum, maximum, shiny, behavior_class = match
    return (
        (species == 0 or species == context["species"])
        and (group == 0 or context["groupFlags"] & group)
        and (terrain == 0xFF or terrain == context["terrain"])
        and (minimum == 0 or context["level"] >= minimum)
        and (maximum == 0 or context["level"] <= maximum)
        and (shiny == 0xFF or shiny == context["shiny"])
        and (behavior_class == 0xFF or behavior_class == context["behaviorClass"])
    )


def normalize(profile):
    valid_kind = lambda value: value in (*range(0, 9), 10, 11)
    if not valid_kind(profile["chillState"]): profile["chillState"] = 1
    for field in ("chillAction", "movementStyle", "specialAction"):
        if not 0 <= profile[field] <= 7: profile[field] = 0
    if profile["alertSpecialAction"] > 2: profile["alertSpecialAction"] = 0
    profile["overworldLimit"] = min(profile["overworldLimit"], 12)
    profile["attentiveChaseBoostDistance"] = min(profile["attentiveChaseBoostDistance"], 32)
    profile["attentiveChaseBoostSpeed"] = min(profile["attentiveChaseBoostSpeed"], 4)
    profile["hopAllowNonCardinal"] = min(profile["hopAllowNonCardinal"], 1)
    profile["hopMaxDistance"] = max(profile["hopMaxDistance"], profile["hopMinDistance"])
    profile["ramAccelerationSteps"] = min(profile["ramAccelerationSteps"], 32)
    profile["chainMovementVariance"] = min(profile["chainMovementVariance"], 32)
    if profile["chainPauseAction"] > 2: profile["chainPauseAction"] = 0
    profile["attentiveCircleRadius"] = min(profile["attentiveCircleRadius"], 8)
    profile["attentiveContinueWhenArrived"] = min(profile["attentiveContinueWhenArrived"], 1)
    profile["attentiveAvoidPreviousTile"] = int(
        profile["attentiveState"] == 3 and profile["targetSelector"] != 1)
    if profile["chillTarget"] > 8: profile["chillTarget"] = 0
    if profile["targetSelector"] > 9: profile["targetSelector"] = 0
    if not valid_kind(profile["attentiveState"]): profile["attentiveState"] = 0
    if not valid_kind(profile["tiredState"]): profile["tiredState"] = 0
    if profile["chillState"] == 8:
        profile["tiredState"], profile["stamina"], profile["alertness"], profile["alertChance"] = 8, 1, 0, 0
    elif profile["tiredState"] == 8:
        profile["stamina"] = 1
    if (profile["attentiveState"] or profile["targetSelector"] or profile["movementStyle"] or profile["attentiveBattle"]) \
            and profile["tiredState"] and profile["stamina"] == 0:
        profile["stamina"] = 1
    if profile["tiredState"] and profile["tiredState"] != 8 and profile["restTime"] == 0: profile["restTime"] = 1
    profile["jumpLevel"] = min(profile["jumpLevel"], 2)
    if profile["spawnState"] > 3: profile["spawnState"] = 0
    if profile["alertState"] > 2: profile["alertState"] = 0
    if profile["alertEmote"] > 10 and profile["alertEmote"] != 0xFF: profile["alertEmote"] = 0xFF
    if profile["alertRange"] > 4: profile["alertRange"] = 0
    if profile["spawnDestination"] > 16: profile["spawnDestination"] = 0
    profile["spawnDestinationMinDistance"] = min(8, max(1, profile["spawnDestinationMinDistance"]))
    profile["spawnDestinationMaxDistance"] = min(8, max(1, profile["spawnDestinationMaxDistance"]))
    profile["spawnDestinationMaxDistance"] = max(profile["spawnDestinationMaxDistance"], profile["spawnDestinationMinDistance"])
    if profile["attentiveBattle"] > 4: profile["attentiveBattle"] = 0
    return profile


def apply_typed_operator(kind, field, operator, before, delta, bound):
    """Execute the closed typed modifier algebra over its wire-domain bounds."""
    if not operator_allowed(kind, field, operator):
        raise ValueError("operator is illegal for typed field")
    if kind == 11:
        if not 0 <= before <= 255 or bound:
            raise ValueError("candidate timer input/bound outside wire domain")
        if operator == 1:
            if not 0 <= delta <= 255:
                raise ValueError("candidate timer SET outside byte domain")
            return delta
        if not -32 <= delta <= 32:
            raise ValueError("candidate timer ADD outside -32..32")
        return min(64, max(0, before + delta))
    if not scalar_value_valid(kind, field, before):
        raise ValueError("typed operator input outside scalar domain")
    minimum, maximum = numeric_bounds(kind, field) if operator != 1 else (0, 255)
    if operator in SIGNED_DELTA_OPERATORS:
        if not -32 <= delta <= 32:
            raise ValueError("typed numeric delta outside -32..32")
    else:
        operand = delta & 0xFF
        if not scalar_value_valid(kind, field, operand):
            raise ValueError("typed operator operand outside scalar domain")
    if operator < 5 and bound:
        raise ValueError("non-compound operator has a bound")
    if operator >= 5 and not scalar_value_valid(kind, field, bound):
        raise ValueError("typed operator bound outside scalar domain")
    clamped_add = min(maximum, max(minimum, before + delta))
    if operator == 1: return delta & 0xFF
    if operator == 2: return clamped_add
    if operator == 3: return max(before, delta & 0xFF)
    if operator == 4: return min(before, delta & 0xFF)
    if operator == 5: return max(bound, clamped_add)
    if operator == 6: return min(bound, clamped_add)
    raise ValueError("unknown typed modifier operator")


class Resolver:
    def __init__(self, graph):
        bodies = {stable: list(values) for stable, role, count, values
                  in graph.records("stateBodies", "<HBB28s")}
        identities = {stable: body for stable, body, provenance, tag_a, tag_b
                      in graph.records("profileIdentities", "<HHHBB")}
        self.profile_values = {stable: list(bodies[body]) for stable, body in identities.items()}
        self.controllers = graph.records("controllers", "<7H10B")
        self.controller_index = {record[0]: index for index, record in enumerate(self.controllers)}
        nodes = graph.records("controllerNodes", "<4HBBH")
        self.graph_nodes = nodes
        self.nodes, self.node_by_id = {}, {}
        for stable, controller, profile, custom, role, flags, reserved in nodes:
            self.nodes[(controller, role)] = list(bodies[identities[profile]])
            self.node_by_id[stable] = (controller, role, profile)
        self.spawn = {record[0]: record for record in graph.records("spawnPolicies", "<3H6B")}
        self.population = {record[0]: record for record in graph.records("populationPolicies", "<4H2B")}
        semantic = {record[0]: record for record in graph.records("semanticIds", "<HBBHH")}
        self.population_key = {stable: semantic[record[2]][2] - 1
                               for stable, record in self.population.items()}
        self.hooks = {record[0]: record for record in graph.records("hookSets", "<2H4B")}
        self.pseudo_states, self.contextual_imports = {}, {}
        for (stable, owner, controller, node, profile, recovery, source_id, action_start,
             action_count, truth, role, lifetime, flags, reserved) in \
                graph.records("importRecipes", "<10H4B"):
            if flags == 1:
                self.pseudo_states[role] = list(bodies[identities[profile]])
            else:
                self.contextual_imports[(controller, source_id)] = {
                    "state": list(bodies[identities[profile]]), "role": role, "lifetime": lifetime,
                    "owner": owner, "recovery": recovery, "action_slice": (action_start, action_count),
                    "truth": truth,
                }
        self.static_actions = graph.records("overrideActions", "<HBB8s")
        self.generic = [(decode_match(raw), action, priority) for stable, raw, action, priority, reserved
                        in graph.records("genericAssignments", "<H12sHHH")]
        self.species = graph.records("speciesAssignments", "<4H")
        all_members = [record[0] for record in graph.records("overrideMembers", "<H")]
        all_actions = self.static_actions
        self.overrides = []
        for (stable, name, raw, member_start, member_count, action_start,
             action_count, target, order, _) in graph.records("overrideSources", "<HH12s4HBBH"):
            self.overrides.append({
                "stable": stable,
                "match": decode_match(raw), "members": all_members[member_start:member_start + member_count],
                "actions": all_actions[action_start:action_start + action_count], "target": target,
                "action_slice": (action_start, action_count), "order": order, "priority": _,
            })
        self.transitions = graph.records("transitions", "<9H4BH")
        self.guards = graph.records("transitionGuards", "<HH4BHH")
        self.operations = graph.records("transitionOperations", "<7H4B")
        self.transition_actions = graph.records("transitionActions", "<HHBBHH")
        self.recoveries = graph.records("recoveryActions", "<HHHBB")
        self.definitions = {record[0]: record for record in graph.records("overrideDefinitions", "<8H20B")}
        self.owners = {record[0]: record for record in graph.records("owners", "<2H2B")}
        self.applicability = {record[0]: record for record in graph.records("applicability", "<HHIHHBBH")}
        self.translations = graph.records("tiredTranslations", "<HBB6H4B2H")

    def multiplicity_allows(self, definition, existing_owners, new_owner):
        target = self.definitions[definition]
        any_owner = bool(existing_owners)
        same_owner = new_owner in existing_owners
        return bool((target[22] or not any_owner) and (target[23] or not same_owner))

    def transition_trace(self, transition):
        stable, definition, owner = transition[:3]
        guards = self.guards[transition[3]:transition[3] + transition[4]]
        operations = self.operations[transition[5]:transition[5] + transition[6]]
        actions = self.transition_actions[transition[7]:transition[7] + transition[8]]
        recovery = self.recoveries[transition[11]:transition[11] + transition[12]]
        definition_record = self.definitions[definition]
        applicability = self.applicability[definition_record[6]]
        return (stable, transition[9], transition[13], owner, self.owners[owner][2],
                tuple((item[2], item[4], item[6]) for item in guards),
                tuple((item[7], item[2], item[3], item[8]) for item in operations),
                tuple((item[2], item[3]) for item in actions),
                tuple((item[3], item[4]) for item in recovery), applicability[1])

    def typed_event_replay(self, include_events=False):
        """Execute candidate selection and every closed transition operation.

        This is intentionally independent of the legacy profile oracle.  It
        turns serialized selectors, applicability, precedence, multiplicity,
        guards, BUSY policy, owners, actions, timers, lifetimes, imports and
        tired translations into observable event/state sequences.
        """
        events = []
        controller_ids = tuple(record[0] for record in self.controllers)
        candidates = []
        for definition in self.definitions.values():
            app = self.applicability[definition[6]]
            owner = definition[4]
            owner_system = self.owners[owner][2] if owner else 0
            for controller in controller_ids:
                for role in range(1, 8):
                    flags, context_mask, app_controller, profile, app_role = app[1:6]
                    applies_now = (not flags & 2 or app_controller == controller) \
                        and (not flags & 8 or app_role == role)
                    selector_now = ((definition[10] == 2 and definition[11] == role)
                                    or (definition[10] == 1 and definition[2] == controller
                                        and self.node_by_id[definition[3]][1] == role))
                    if applies_now and selector_now:
                        candidates.append((controller, role, definition[9], definition[7], definition[0]))
                        events.append(("candidate", controller, role, definition[0], definition[8:26],
                                       app, owner_system))
        events.append(("selection", tuple(sorted(candidates))))

        for transition in sorted(self.transitions, key=lambda row: (row[13], row[0])):
            tid, candidate, owner = transition[:3]
            role = next(bit + 1 for bit in range(7) if transition[10] & (1 << bit))
            definition = self.definitions[candidate]
            stack = [{"definition": candidate, "owner": owner, "instance": candidate}]
            guards = self.guards[transition[3]:transition[3] + transition[4]]
            guard_results = []
            for guard in guards:
                kind, negate, payload, reference = guard[2], guard[3], guard[4], guard[6]
                result = (kind == 1 or (kind == 2 and role == payload)
                          or (kind == 3 and reference in self.node_by_id)
                          or (kind == 4 and any(item["owner"] == reference for item in stack))
                          or (kind == 5 and not any(item["owner"] == reference for item in stack))
                          or kind == 6
                          or (kind == 7 and payload == 100)
                          or (kind == 8 and payload == transition[9]))
                guard_results.append(not result if negate else result)
            before = tuple((item["definition"], item["owner"], item["instance"]) for item in stack)
            operation_events = []
            if all(guard_results):
                for operation in self.operations[transition[5]:transition[5] + transition[6]]:
                    _, _, did, op_owner, replacement, policy, instance, kind, busy, required, _ = operation
                    if busy == 1:
                        operation_events.append(("queue", kind, did, op_owner, instance))
                    if kind == 1:
                        target = self.definitions[did]
                        same_owner = [item for item in stack if item["definition"] == did and item["owner"] == op_owner]
                        any_owner = [item for item in stack if item["definition"] == did]
                        allowed = (target[22] or not any_owner) and (target[23] or not same_owner)
                        if allowed: stack.append({"definition": did, "owner": op_owner, "instance": instance})
                    elif kind == 2:
                        for item in stack:
                            if item["definition"] == did and item["owner"] == op_owner: item["definition"] = replacement
                    elif kind in (3, 4):
                        matched = [item for item in stack if item["definition"] == did and item["owner"] == op_owner]
                        if required and not matched: raise ValueError("required transition removal missed")
                        stack = [item for item in stack if item not in matched]
                    elif kind == 5:
                        stack = [item for item in stack if item["owner"] != op_owner]
                    elif kind == 6:
                        operation_events.append(("policy", policy))
                    operation_events.append(("commit", kind, did, op_owner, replacement, policy, instance, busy, required))
            after = tuple((item["definition"], item["owner"], item["instance"]) for item in stack)
            actions = tuple(self.transition_actions[transition[7]:transition[7] + transition[8]])
            recovery = tuple(self.recoveries[transition[11]:transition[11] + transition[12]])
            events.append(("transition", tid, transition[9], role, transition[13], tuple(zip(guards, guard_results)),
                           before, tuple(operation_events), after, actions, recovery,
                           definition[9], definition[12:19], self.owners[owner][2]))

        for (controller, source), recipe in sorted(self.contextual_imports.items()):
            start, count = recipe["action_slice"]
            events.append(("import", controller, source, recipe["role"], recipe["owner"],
                           self.owners[recipe["owner"]][2], recipe["recovery"], recipe["lifetime"],
                           recipe["truth"], tuple(self.static_actions[start:start + count]),
                           tuple(recipe["state"])))
        for row in self.translations:
            definition = self.definitions[row[5]]
            events.append(("translation", row, definition[2:26], tuple(self.profile_values[row[4]])))
        for policy, record in sorted(self.population.items()):
            events.append(("population", policy, self.population_key[policy], record[3], record[4]))
        for owner, record in sorted(self.owners.items()):
            events.append(("owner", owner, record[2], record[3]))
        for node, record in sorted(self.node_by_id.items()):
            controller, role, profile = record
            events.append(("node", node, controller, role, profile,
                           next(row[5] for row in self.graph_nodes if row[0] == node)))
        encoded = repr(events).encode("ascii")
        result = hashlib.sha256(encoded).hexdigest(), len(events)
        return result + (events,) if include_events else result

    @staticmethod
    def _state_into(profile, role, values):
        prefix = {1: "chill", 2: "attentive", 3: "tired"}[role]
        profile[prefix + "State"] = values[0]
        profile[{1: "chillAction", 2: "movementStyle", 3: "specialAction"}[role]] = values[1]
        if role != 3: profile[{1: "chillTarget", 2: "targetSelector"}[role]] = values[2]
        profile[prefix + "Speed"] = values[3]
        profile["range"], profile["jumpLevel"] = values[4], values[5]
        profile[prefix + "AllowedTile"], profile[prefix + "AllowedTile2"] = values[6], values[7]
        stem = "" if role == 1 else prefix
        for suffix, index in (("HopAllowNonCardinal", 8), ("HopMinDistance", 9), ("HopMaxDistance", 10),
                              ("HopPause", 11), ("TeleportTime", 14), ("TeleportPause", 15),
                              ("RamAccelerationSteps", 16), ("RamMaxSpeed", 17)):
            name = suffix[0].lower() + suffix[1:] if role == 1 else stem + suffix
            profile[name] = values[index]
        profile["hopTime"] = values[12]
        profile["attentiveHopSpinSpeed" if role == 2 else "hopSpinSpeed"] = values[13]
        if role == 2:
            for name, index in (("attentiveChaseBoostDistance", 18), ("attentiveChaseBoostSpeed", 19),
                                ("attentiveCircleRadius", 20), ("attentiveContinueWhenArrived", 21),
                                ("attentiveAvoidPreviousTile", 22), ("attentiveBattle", 26)):
                profile[name] = values[index]
        profile["chainPauseAction"], profile["chainMovementVariance"], profile["chainPauseVariance"] = values[23:26]
        profile["playerAdjacentDirectionMasks"] = values[27]

    def _base(self, class_index):
        controller = self.controllers[class_index]
        controller_id = controller[0]
        profile = {name: 0 for name in PROFILE_FIELDS}
        states = {role: list(self.nodes[(controller_id, role)]) for role in (1, 2, 3)}
        for role, values in states.items(): self._state_into(profile, role, values)
        for name, value in zip(("alertState", "alertEmote", "alertTime", "alertness", "alertRange",
                                "alertChance", "stamina", "restTime"), controller[7:15]):
            profile[name] = value
        spawn = self.spawn[controller[4]]
        for name, value in zip(("spawnState", "spawnDestination", "spawnDestinationMinDistance",
                                "spawnDestinationMaxDistance", "spawnHopTime"), spawn[3:8]): profile[name] = value
        profile["overworldLimit"] = self.population[controller[5]][4]
        profile["alertSpecialAction"] = self.hooks[controller[6]][2]
        return profile, states, list(controller[7:15]), list(spawn[3:8]), \
            (profile["overworldLimit"], self.population_key[controller[5]]), \
            list(self.hooks[controller[6]][2:5])

    def _assignment_class(self, action_index):
        stable, kind, flags, payload = self.static_actions[action_index]
        controller, zero0, zero1, zero2 = struct.unpack("<4H", payload)
        if kind != 1 or flags or zero0 or zero1 or zero2 or controller not in self.controller_index:
            raise ValueError("invalid assignment action escaped wire validation")
        return self.controller_index[controller]

    def classify(self, context):
        result, hits = 0, []
        for order, (match, action, priority) in enumerate(sorted(self.generic, key=lambda item: item[2]), 1):
            if applies(match, {**context, "behaviorClass": result}): result, hits = self._assignment_class(action), hits + [order]
        for order, (stable, species, action, priority) in enumerate(sorted(self.species, key=lambda item: item[3]), 3):
            if species == context["species"]: result, hits = self._assignment_class(action), hits + [order]
        return result, hits

    def resolve(self, context, incoming_class, forced=None, isolated=None):
        base = incoming_class if 0 <= incoming_class < 4 else 0
        if base == 3:
            profile = {name: 0 for name in PROFILE_FIELDS}
            states = {role: list(self.pseudo_states[role]) for role in (1, 2, 3)}
            controller_values = [0, 0xFF, 0, 0, 0, 0, 0, 0]
            spawn_values = [0, 0, 1, 5, 4]
            population_value, population_key, hook_value = 0, 3, [0, 0, 0]
        else:
            profile, states, controller_values, spawn_values, population_pair, hook_value = self._base(base)
            population_value, population_key = population_pair
        steps, limit = [], population_key
        if base != 3 or isolated is not None:
            selected_items = []
            for index, override in sorted(enumerate(self.overrides), key=lambda item: (item[1]["priority"], item[1]["order"])):
                natural = override["target"] != 0 and applies(override["match"], {**context, "behaviorClass": incoming_class}) \
                    and (override["target"] == 2 or context["species"] in override["members"])
                selected = (isolated == index) if isolated is not None else (natural or forced == index)
                if selected: selected_items.append((index, override, natural))
            fields_by_override = {index: [] for index, _, _ in selected_items}
            controller_id = self.controllers[base][0] if base < 3 else 0
            # Complete bindings resolve before modifiers; this preserves earlier
            # ordinary field folds while replacing only the authored state body.
            for binding_phase in (True, False):
              for index, override, natural in selected_items:
                import_recipe = self.contextual_imports.get((controller_id, override["stable"]))
                imported_state_role = ({6: 1, 4: 3}.get(import_recipe["role"], 0)
                                       if import_recipe is not None else 0)
                if (forced == index or isolated == index) and base < 3 and import_recipe is not None:
                    if not binding_phase:
                        if import_recipe["action_slice"] != override["action_slice"] or import_recipe["truth"] != 0xFFFF:
                            raise ValueError("semantic import source/action truth mismatch")
                        imported = import_recipe["state"]
                        states[imported_state_role][0] = imported[0]
                        if import_recipe["role"] == 6:
                            states[1][2] = imported[2]
                            states[1][3] = max(states[1][3], imported[3])
                            states[1][27] = imported[27]
                        else:
                            states[3][1] = imported[1]
                for _, kind, flags_value, payload in override["actions"]:
                    if (kind == 2) != binding_phase: continue
                    targets, operator, value, roles, typed_field, delta, bound = [], 1, 0, 0, 0, 0, 0
                    if kind == 2:
                        target_controller, node, profile, zero = struct.unpack("<4H", payload)
                        node_controller, role, _ = self.node_by_id[node]
                        if imported_state_role == role and (forced == index or isolated == index) and base < 3: continue
                        if base == 3:
                            if target_controller != self.controllers[0][0]: continue
                            states[role][0] = self.profile_values[profile][0]; targets = []
                        else:
                            if target_controller != controller_id: continue
                            if node_controller != controller_id: raise ValueError("bind-node controller mismatch")
                            states[role] = list(self.profile_values[profile]); targets = []
                    elif kind in (4, 5, 7):
                        typed_field, operator, delta, bound, roles, zero, target_controller = struct.unpack("<BBbBBBH", payload)
                        value = bound if operator in (5, 6) else delta
                        if target_controller and target_controller != controller_id: continue
                        selected_roles = [role for role in (1, 2, 3) if roles & (1 << (role - 1))]
                        if kind == 4 and (forced == index or isolated == index) and base < 3:
                            selected_roles = [role for role in selected_roles if role != imported_state_role]
                        if kind == 4: targets = [(states[role], typed_field) for role in selected_roles]
                        elif kind == 5: targets = [(controller_values, typed_field - 1)]
                        elif kind == 7: targets = [(spawn_values, typed_field - 1)]
                    elif kind == 8:
                        policy_id, zero0, zero1, zero2 = struct.unpack("<4H", payload)
                        policy = self.population[policy_id]
                        population_value, limit = policy[4], self.population_key[policy_id]
                        targets = []; operator = typed_field = roles = 0
                    elif kind == 10:
                        hook_id, zero0, zero1, zero2 = struct.unpack("<4H", payload)
                        hook_value = list(self.hooks[hook_id][2:5]); targets = []
                    elif kind == 11:
                        target_controller, node, operator, value, zero = struct.unpack("<HHBBH", payload)
                        if target_controller != (self.controllers[0][0] if base == 3 else controller_id): continue
                        targets = [(controller_values, 7)]; roles = 4; typed_field = 1
                        delta = value if operator == 1 or value < 128 else value - 256
                    else: raise ValueError("closed static action escaped validation")
                    for container, field_index in targets:
                        before = container[field_index]
                        container[field_index] = apply_typed_operator(
                            kind, typed_field, operator, before, delta, bound)
                    fields_by_override[index].append((kind, typed_field, roles))
            steps = [(index, tuple(fields_by_override[index]), natural, forced == index)
                     for index, override, natural in selected_items]
        profile = {name: 0 for name in PROFILE_FIELDS}
        for role, values in states.items(): self._state_into(profile, role, values)
        for name, value in zip(("alertState", "alertEmote", "alertTime", "alertness", "alertRange",
                                "alertChance", "stamina", "restTime"), controller_values): profile[name] = value
        for name, value in zip(("spawnState", "spawnDestination", "spawnDestinationMinDistance",
                                "spawnDestinationMaxDistance", "spawnHopTime"), spawn_values): profile[name] = value
        profile["overworldLimit"] = population_value
        profile["alertSpecialAction"] = 2 if hook_value[1] and hook_value[2] else (1 if hook_value[0] else 0)
        return (profile if base == 3 and isolated is None else normalize(profile)), limit, steps


def verify_snapshot_freshness(event_digest):
    if EXPECTED_TYPED_EVENT_DIGEST and event_digest != EXPECTED_TYPED_EVENT_DIGEST:
        raise ValueError(f"typed event snapshot changed: {event_digest}")


def verify(blob, source, model_path=CANONICAL_MODEL, check_snapshot_digest=True, report=True):
    """Production structural verification for any valid authored V40 catalog."""
    graph = validate_wire(blob, source)
    if report:
        print(
            f"independent authored-graph structure: {len(graph.blob)} bytes; "
            f"{graph.sections['profileIdentities'][1]} profiles; "
            f"{graph.sections['controllers'][1]} controllers; "
            f"{graph.sections['transitions'][1]} transitions"
        )
    return graph


def verify_golden_baseline(
    blob, source, model_path=CANONICAL_MODEL, check_snapshot_digest=True, report=True,
):
    graph = validate_wire(blob, source)
    model = json.loads(model_path.read_text())
    if (model.get("schema") != "overworld-wild-behavior-model-v40"
            or model.get("modelVersion") != 40):
        raise ValueError("canonical authored model header is invalid")
    resolver = Resolver(graph)
    first_body = graph.records("stateBodies", "<HBB28s")[0]
    if first_body[3][3] != 1:
        raise ValueError("canonical base state changed field chillSpeed")
    first_state_modifier = next(
        record for record in graph.records("overrideActions", "<HBB8s")
        if record[0] == 0x6004
    )
    if first_state_modifier[3][4] != 2:
        raise ValueError("canonical state modifier changed field chillSpeed")
    if first_state_modifier[3][2] != 2:
        raise ValueError("canonical state modifier changed field attentiveSpeed")
    expected_population = [
        (item["stableId"], item["nameId"], item["populationGroupId"],
         item["provenanceId"], item["limit"], item["flags"])
        for item in model["populationPolicies"]
    ]
    if graph.records("populationPolicies", "<4H2B") != expected_population:
        raise ValueError("population policy differs from canonical authored model")

    # Keep an independently observable end-to-end catalog fixture without
    # retaining a second, legacy model of the complete graph.
    context = {"species": 56, "groupFlags": 0, "level": 1,
               "terrain": 0, "shiny": 0}
    mankey_class, _ = resolver.classify(context)
    mankey_profile, _, _ = resolver.resolve(context, mankey_class)
    fixture = {"attentiveState": 3, "movementStyle": 2, "targetSelector": 8,
               "spawnDestination": 1, "hopTime": 6, "overworldLimit": 1,
               "alertSpecialAction": 2, "specialAction": 1}
    if any(mankey_profile[name] != value for name, value in fixture.items()):
        raise ValueError("Mankey canopy hopper/throw fixture changed")
    transitions = graph.records("transitions", "<9H4BH")
    definitions = graph.records("overrideDefinitions", "<8H20B")
    imports = graph.records("importRecipes", "<10H4B")
    translations = graph.records("tiredTranslations", "<HBB6H4B2H")
    event_digest, event_count = resolver.typed_event_replay()
    if check_snapshot_digest:
        verify_snapshot_freshness(event_digest)
    canonical_imports = {(record[10], record[1], record[5], record[11], record[6])
                         for record in imports if record[12] == 0}
    expected_imports = {(4, 0x810A, 0xA00F, 2, 0x500A),
                        (5, 0x8109, 0, 1, 0), (6, 0x810B, 0xA011, 3, 0x500B)}
    if (len(resolver.contextual_imports) != 9 or len(transitions) != 26 or len(definitions) != 19
            or event_count < 80 or canonical_imports != expected_imports
            or any((row[2] and (row[7] or row[8] or resolver.definitions[row[5]][10] != 2))
                   or (not row[2] and resolver.definitions[row[5]][10] != 1) for row in translations)):
        raise ValueError("typed import/tired/transition execution fixture changed")
    if report:
        print(f"independent canonical authored-graph replay: 115 assignments; "
              f"{event_count} typed events; digest={event_digest}")


def mutation_semantic_outcome(label, resolver):
    events = resolver.typed_event_replay(include_events=True)[2]
    selection = next(event[1] for event in events if event[0] == "selection")
    transition = next(event for event in events if event[0] == "transition" and event[1] == 0xA001)
    if label == "definition-priority":
        candidates = [item for item in selection if item[:3] == (0x3001, 2, 1)]
        return tuple(item[4] for item in candidates)
    if label == "definition-multiplicity":
        return (resolver.definitions[0x7001][22],
                resolver.multiplicity_allows(0x7001, (0x8103,), 0x8102))
    if label == "applicability":
        return sum(event[0] == "candidate" and event[3] == 0x7001 for event in events)
    if label == "transition-from-role":
        return transition[3], tuple(result for _guard, result in transition[5]), len(transition[7])
    if label == "transition-dispatch-priority": return transition[4]
    if label == "transition-guard":
        guard, result = transition[5][0]
        return guard[2], guard[4], result
    if label == "transition-operation":
        commits = tuple(item[1] for item in transition[7] if item[0] == "commit")
        return commits, len(transition[8])
    if label == "transition-busy":
        commits = tuple(item[7] for item in transition[7] if item[0] == "commit")
        return any(item[0] == "queue" for item in transition[7]), commits
    if label == "owner-taxonomy": return resolver.owners[0x8102][2]
    if label == "definition-channel":
        return tuple(sorted({item[2] for item in selection if item[4] == 0x7001}))
    if label == "definition-map-lifetime": return transition[12]
    if label == "stamina-timer-source": return resolver.definitions[0x7004][15]
    if label == "hidden-timer-policy": return resolver.definitions[0x7004][16]
    if label == "active-optional-flag":
        return next(event[5] for event in events if event[0] == "node" and event[1] == 0x3102)
    raise ValueError(f"missing semantic observer for {label}")


def verify_mutation_detection(blob, source, model_path):
    original = blob.read_bytes()
    base_graph = Graph(original, source, blob)
    base_resolver = Resolver(base_graph)
    fixtures = []
    action_offset, _, stride = base_graph.sections["overrideActions"]
    action_records = base_graph.records("overrideActions", "<HBB8s")
    state_action = next(index for index, record in enumerate(action_records) if record[1] == 4)
    action = bytearray(original); action[action_offset + state_action * stride + 8] ^= 1; fixtures.append(("role-mask", action))
    body_offset, _, _ = base_graph.sections["stateBodies"]
    body = bytearray(original); body[body_offset + 4 + 3] += 1; fixtures.append(("state-body", body))
    value = bytearray(original); value[action_offset + state_action * stride + 6] ^= 1; fixtures.append(("typed-value", value))
    definition_offset, _, definition_stride = base_graph.sections["overrideDefinitions"]
    priority = bytearray(original); priority[definition_offset + 14] ^= 1; fixtures.append(("definition-priority", priority))
    multiplicity = bytearray(original); multiplicity[definition_offset + 30] ^= 1; fixtures.append(("definition-multiplicity", multiplicity))
    selector = bytearray(original); selector[definition_offset + 10 * definition_stride + 18] = 2
    fixtures.append(("exact-selector-discriminant", selector))
    application_offset, _, _ = base_graph.sections["applicability"]
    application = bytearray(original); application[application_offset + 2] ^= 2; fixtures.append(("applicability", application))
    transition_offset, _, _ = base_graph.sections["transitions"]
    from_role = bytearray(original); from_role[transition_offset + 19] ^= 1; fixtures.append(("transition-from-role", from_role))
    dispatch = bytearray(original); dispatch[transition_offset + 22] ^= 1; fixtures.append(("transition-dispatch-priority", dispatch))
    guard_offset, _, _ = base_graph.sections["transitionGuards"]
    guard = bytearray(original); guard[guard_offset + 4] = 1; guard[guard_offset + 6] = 0
    struct.pack_into("<H", guard, guard_offset + 8, 0); fixtures.append(("transition-guard", guard))
    operation_offset, _, _ = base_graph.sections["transitionOperations"]
    operation = bytearray(original); operation[operation_offset + 14] = 4
    fixtures.append(("transition-operation", operation))
    busy = bytearray(original); busy[operation_offset + 15] = 2; fixtures.append(("transition-busy", busy))
    import_offset, _, import_stride = base_graph.sections["importRecipes"]
    lifetime = bytearray(original); lifetime[import_offset + 21] = 2; fixtures.append(("import-lifetime", lifetime))
    owner_offset, _, _ = base_graph.sections["owners"]
    owner = bytearray(original); owner[owner_offset + 4] = 0; fixtures.append(("owner-taxonomy", owner))
    import_offset, _, import_stride = base_graph.sections["importRecipes"]
    node_offset, _, node_stride = base_graph.sections["controllerNodes"]
    channel = bytearray(original); channel[definition_offset + 17] = 2; fixtures.append(("definition-channel", channel))
    map_life = bytearray(original); map_life[definition_offset + 20] = 1; fixtures.append(("definition-map-lifetime", map_life))
    timer_source = bytearray(original); timer_source[definition_offset + 3 * definition_stride + 23] = 1
    fixtures.append(("stamina-timer-source", timer_source))
    hidden = bytearray(original); hidden[definition_offset + 3 * definition_stride + 24] = 2
    fixtures.append(("hidden-timer-policy", hidden))
    carried_owner = bytearray(original); struct.pack_into("<H", carried_owner, import_offset + 2, 0x810B)
    fixtures.append(("carried-owner", carried_owner))
    carried_recovery = bytearray(original); struct.pack_into("<H", carried_recovery, import_offset + 10, 0xA001)
    fixtures.append(("carried-recovery", carried_recovery))
    population_offset, _, population_stride = base_graph.sections["populationPolicies"]
    population_groups = bytearray(original)
    group0 = struct.unpack_from("<H", original, population_offset + 4)[0]
    group1 = struct.unpack_from("<H", original, population_offset + population_stride + 4)[0]
    struct.pack_into("<H", population_groups, population_offset + 4, group1)
    struct.pack_into("<H", population_groups, population_offset + population_stride + 4, group0)
    fixtures.append(("population-group-provenance", population_groups))
    active_optional = bytearray(original); active_optional[node_offset + node_stride + 9] = 2
    fixtures.append(("active-optional-flag", active_optional))
    expected_errors = {
        "role-mask": "field chillSpeed", "state-body": "field chillSpeed",
        "typed-value": "field attentiveSpeed",
        "exact-selector-discriminant": "definition domain/reference mismatch",
        "applicability": "applicability mismatch",
        "transition-operation": "direct-cutover transition operation mismatch",
        "import-lifetime": "typed import/tired/transition execution fixture",
        "carried-owner": "typed import/tired/transition execution fixture",
        "carried-recovery": "typed import/tired/transition execution fixture",
        "owner-taxonomy": "owner mismatch",
        "population-group-provenance": "population policy differs from canonical authored model",
    }
    expected_outcomes = {
        "definition-priority": (0x7002, 0x7003, 0x7001),
        "definition-multiplicity": (1, True),
        "transition-from-role": (2, (False,), 0),
        "transition-dispatch-priority": 0x2001,
        "transition-guard": (1, 0, True),
        "transition-busy": (False, (2,)),
        "definition-channel": (2,),
        "definition-map-lifetime": (1, 1, 0, 0, 0, 0, 0),
        "stamina-timer-source": 1,
        "hidden-timer-policy": 2,
        "active-optional-flag": 2,
    }
    if set(expected_errors) | set(expected_outcomes) != {label for label, _ in fixtures}:
        raise ValueError("mutation fixture expectations are incomplete or duplicated")
    for label, raw in fixtures:
        raw[16:20] = b"\0\0\0\0"
        checksum = binascii.crc32(raw) & 0xFFFFFFFF
        struct.pack_into("<I", raw, 16, checksum)
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            mutated, mutated_source = temp / "mutated.bin", temp / "mutated.h"
            mutated.write_bytes(raw)
            mutated_source.write_text(re.sub(
                r"(#define OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM )0x[0-9A-Fa-f]+u",
                rf"\g<1>0x{checksum:08X}u", source.read_text()))
            try:
                verify_golden_baseline(
                    mutated, mutated_source, model_path,
                    check_snapshot_digest=False, report=False,
                )
            except ValueError as error:
                expected = expected_errors.get(label)
                if expected is None or expected not in str(error):
                    raise ValueError(f"resealed {label} raised wrong semantic category: {error}") from error
                continue
        expected = expected_outcomes.get(label)
        mutated_resolver = Resolver(Graph(bytes(raw), source, label))
        actual = mutation_semantic_outcome(label, mutated_resolver)
        baseline = mutation_semantic_outcome(label, base_resolver)
        if actual != expected or actual == baseline:
            raise ValueError(
                f"resealed {label} semantic outcome {actual!r}; expected {expected!r}; baseline {baseline!r}")
    print(f"independent authored-graph mutation semantics: {len(fixtures)} fixtures; "
          f"{len(expected_errors)} invariant categories; {len(expected_outcomes)} explicit outcomes; "
          "snapshot digest excluded")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blob", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "include" / "overworld_wild_behavior_data.h")
    parser.add_argument("--model", type=Path, default=CANONICAL_MODEL)
    parser.add_argument("--golden-baseline", action="store_true")
    parser.add_argument("--mutation-self-test", action="store_true")
    args = parser.parse_args()
    verify(args.blob, args.source, args.model)
    if args.golden_baseline:
        verify_golden_baseline(args.blob, args.source, args.model)
    if args.mutation_self_test:
        if not args.golden_baseline:
            raise ValueError("mutation self-test requires --golden-baseline")
        verify_mutation_detection(args.blob, args.source, args.model)


if __name__ == "__main__":
    main()
