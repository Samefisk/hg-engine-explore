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

from overworld_wild_behavior_v39_frozen import FROZEN, load_frozen
from overworld_wild_behavior_v40_field_metadata import (
    SIGNED_DELTA_OPERATORS,
    numeric_bounds,
    operator_allowed,
    scalar_value_valid,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TYPED_EVENT_DIGEST = "1f57fc0f2996f8c25d1838db27e895cda1ce63a15b24d080847f923041238701"

# Deliberately duplicated frozen decode vocabulary.  The parity executor must
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
    ("stateBodies", 58, 32), ("profileIdentities", 58, 8),
    ("controllers", 3, 24), ("controllerNodes", 21, 12),
    ("sourceClassProfiles", 4, 72), ("genericAssignments", 2, 20),
    ("speciesAssignments", 113, 8), ("overrideSources", 11, 28),
    ("overrideMembers", 155, 2), ("overrideActions", 207, 12),
    ("spawnPolicies", 3, 12), ("populationPolicies", 6, 10),
    ("hookSets", 3, 8), ("owners", 10, 6),
    ("overrideDefinitions", 19, 36), ("transitions", 26, 24),
    ("transitionGuards", 26, 12), ("transitionOperations", 53, 18),
    ("transitionActions", 41, 10), ("recoveryActions", 15, 8),
    ("importRecipes", 12, 24), ("applicability", 19, 16),
    ("tiredTranslations", 18, 24),
    ("semanticIds", 16, 8),
)


class Graph:
    def __init__(self, blob, source, path):
        self.blob, self.path, self.sections = blob, path, {}
        cursor = 216
        for index, (name, expected_count, expected_stride) in enumerate(SECTION_SPECS):
            offset, count, stride = struct.unpack_from("<IHH", blob, 24 + index * 8)
            if (offset, count, stride) != (cursor, expected_count, expected_stride):
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
    for index, controller in enumerate(controllers):
        stable, name, node_start, node_count, spawn_id, population_id, hook_id = controller[:7]
        if stable != name or node_start != index * 7 or node_count != 7 \
                or spawn_id not in spawn or population_id not in population or hook_id not in hooks \
                or controller[15:] != (0, 0) \
                or any(not scalar_value_valid(5, field, value)
                       for field, value in enumerate(controller[7:14], 1)) \
                or any(node[1] != stable for node in nodes[node_start:node_start + node_count]):
            raise ValueError(f"{path}: direct-cutover controller/configuration binding mismatch")

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
                or not from_roles or from_roles & ~0x7F or not priority \
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
                    or recovery[3] not in (1, 2) or recovery[4] != 1:
                raise ValueError(f"{path}: direct-cutover recovery action mismatch")
        if trigger == 2 and not any(guard[2] == 8 and guard[4] == trigger
                                    for guard in transition_guards):
            raise ValueError(f"{path}: stamina transition lacks exact system-route evidence")
        if transition_index >= 17 and (trigger != 3 or from_roles != 0x40 \
                or guard_count != 1 or transition_guards[0][2:5] != (6, 0, 3) \
                or action_count != 2 or recovery_count != 1):
            raise ValueError(f"{path}: exact tired cutover transition topology mismatch")
        cursors = [guard_start + guard_count, operation_start + operation_count,
                   action_start + action_count, recovery_start + recovery_count]
    if cursors != [len(guards), len(operations), len(actions), len(recoveries)]:
        raise ValueError(f"{path}: unclaimed direct-cutover transition records")


def validate_wire(path, source):
    blob = path.read_bytes()
    if len(blob) != 11636: raise ValueError(f"{path}: independent exact size mismatch")
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
    for name, _, stride in SECTION_SPECS:
        if name in ("sourceClassProfiles", "overrideMembers"): continue
        for record in graph.records(name, "<H" + "x" * (stride - 2)):
            if not record[0] or record[0] in seen: raise ValueError(f"{path}: independent stable-ID collision")
            seen.add(record[0])
    body_roles = {}
    for stable, role, count, values in graph.records("stateBodies", "<HBB28s"):
        if count != 28 or values[22] != int(role == 2 and values[0] == 3 and values[2] != 1):
            raise ValueError(f"{path}: independent derived state-body invariant mismatch")
        body_roles[stable] = role
    identities = {record[0]: record for record in graph.records("profileIdentities", "<HHHBB")}
    semantic = {record[0]: record for record in graph.records("semanticIds", "<HBBHH")}
    if any(semantic[record[2]][1:3] != (1, body_roles[record[1]]) for record in identities.values()):
        raise ValueError(f"{path}: independent profile provenance/body-role mismatch")
    controller_ordinals = {record[0]: index + 1 for index, record in enumerate(
        graph.records("controllers", "<7H10B"))}
    node_records = graph.records("controllerNodes", "<4HBBH")
    nodes = {record[0]: record for record in node_records}
    for stable, controller, profile, custom, role, node_flags, reserved in node_records:
        tag_a, tag_b = identities[profile][3:5]
        expected_tag = {4: 13, 5: 14, 6: 12, 7: 15}.get(role)
        if expected_tag is not None and (tag_a, tag_b) != (
                expected_tag, 0 if role == 5 else controller_ordinals[controller]):
            raise ValueError(f"{path}: independent contextual node tag mismatch")
    for (stable, owner, controller, node, profile, recovery, source_id, action_start,
         action_count, truth, role, lifetime, import_flags, reserved) in \
            graph.records("importRecipes", "<10H4B"):
        if import_flags == 0:
            node_record = nodes[node]
            tag_a, tag_b = identities[profile][3:5]
            if (node_record[1], node_record[2], node_record[4]) != (controller, profile, role) \
                    or (tag_a, tag_b) != ({4: 13, 5: 14, 6: 12}[role],
                                          0 if role == 5 else controller_ordinals[controller]):
                raise ValueError(f"{path}: independent contextual import mismatch")
            expected_owner, expected_recovery, expected_lifetime, expected_source = {
                4: (0x810A, 0xA00F, 2, 0x500A),
                5: (0x8109, 0, 1, 0),
                6: (0x810B, 0xA011, 3, 0x500B),
            }[role]
            if owner != expected_owner:
                raise ValueError(f"{path}: independent contextual import owner mismatch")
            if recovery != expected_recovery:
                raise ValueError(f"{path}: independent contextual import recovery mismatch")
            if lifetime != expected_lifetime:
                raise ValueError(f"{path}: independent contextual import lifetime mismatch")
            if source_id != expected_source:
                raise ValueError(f"{path}: independent contextual import source mismatch")
    validate_direct_cutover_records(graph)
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


def expected_profile(oracle, effective_id):
    profile = {name: scalar(value) for name, value in oracle["effectiveProfiles"][effective_id]["legacyProfile"].items()}
    profile["attentiveAvoidPreviousTile"] = int(
        profile["attentiveState"] == 3 and profile["targetSelector"] != 1)
    return profile


def compare_profile(actual, expected, label):
    for field in PROFILE_FIELDS:
        if field in DEAD_DIAGNOSTIC_FIELDS: continue
        if actual[field] != expected[field]:
            raise ValueError(f"{label}: field {field}: v40={actual[field]} frozen={expected[field]}")


def context_input(record):
    return {"species": scalar(record["species"]), "groupFlags": record.get("groupFlags", 0),
            "level": record.get("level", 1), "terrain": scalar(record.get("terrain", 0)),
            "shiny": int(record.get("shiny", False))}


def verify_snapshot_freshness(event_digest):
    if EXPECTED_TYPED_EVENT_DIGEST and event_digest != EXPECTED_TYPED_EVENT_DIGEST:
        raise ValueError(f"typed event snapshot changed: {event_digest}")


def verify(blob, source, frozen=FROZEN, check_snapshot_digest=True, report=True):
    graph = validate_wire(blob, source)
    oracle = load_frozen(frozen)
    if (len(oracle["classRules"]), len(oracle["effectiveProfiles"]), len(oracle["resolutionStacks"])) != (115, 67, 296):
        raise ValueError("frozen assignment/effective-profile/resolution-stack counts changed")
    resolver = Resolver(graph)
    source_profiles = graph.records("sourceClassProfiles", "<72B")
    expected_sources = [tuple(scalar(item["sourceProfile"][field]) for field in PROFILE_FIELDS)
                        for item in oracle["classProfiles"]]
    if source_profiles != expected_sources:
        raise ValueError("transitional source-profile projection differs from frozen authored source")
    natural_by_id = {record["id"]: record for record in oracle["contexts"]}
    checked = 0
    for record in oracle["contexts"]:
        context = context_input(record)
        behavior, hits = resolver.classify(context)
        if behavior != record["behaviorClass"]: raise ValueError(f"{record['id']}: class mismatch")
        actual, limit, steps = resolver.resolve(context, behavior)
        compare_profile(actual, expected_profile(oracle, record["effectiveProfileId"]), record["id"])
        if limit != scalar(record["behaviorLimitKey"]): raise ValueError(f"{record['id']}: limit provenance mismatch")
        expected_steps = oracle["resolutionStacks"][record["resolutionStackId"]]
        expected_overrides = [step["overrideIndex"] for step in expected_steps if step["kind"] == "override"]
        if [step[0] for step in steps] != expected_overrides or expected_steps[0]["classRuleOrders"] != hits:
            raise ValueError(f"{record['id']}: ordered provenance mismatch")
        checked += 1
    for record in oracle["contextualForcedProbes"]:
        natural = natural_by_id.get(record["naturalContextId"])
        context = context_input(natural) if natural is not None else {
            "species": 0, "groupFlags": 0, "level": 1, "terrain": 0, "shiny": 0,
        }
        actual, limit, _ = resolver.resolve(context, record["classIndex"], forced=record["forcedOverrideIndex"])
        compare_profile(actual, expected_profile(oracle, record["effectiveProfileId"]),
                        (record["naturalContextId"] or "picked-up") + "/follower")
        if limit != scalar(record["behaviorLimitKey"]): raise ValueError("follower limit mismatch")
        checked += 1
    for record in oracle["isolatedOverrideProbes"]:
        context = {"species": 0, "groupFlags": 0, "level": 1, "terrain": 0, "shiny": 0}
        actual, limit, _ = resolver.resolve(context, record["classIndex"], isolated=record["overrideProfileOrder"] - 1)
        compare_profile(actual, expected_profile(oracle, record["effectiveProfileId"]), "isolated")
        if limit != scalar(record["behaviorLimitKey"]): raise ValueError("isolated limit mismatch")
        checked += 1
    record = oracle["dormantContextProbes"][0]
    context = {"species": 0, "groupFlags": 0, "level": 1, "terrain": 0, "shiny": 0}
    actual, limit, _ = resolver.resolve(context, record["incomingBehaviorClass"], forced=record["overrideOrder"] - 1)
    compare_profile(actual, expected_profile(oracle, record["effectiveProfileId"]), "forced-asleep")
    if limit != scalar(record["behaviorLimitKey"]): raise ValueError("forced-asleep limit mismatch")
    checked += 1
    if checked != 22443: raise ValueError(f"case count {checked} != 22443")
    mankey = next(record for record in oracle["contexts"]
                  if record["id"] == "SPECIES_MANKEY/L1/OW_WILD_SPAWN_TERRAIN_LAND/S0")
    mankey_profile, _, _ = resolver.resolve(context_input(mankey), mankey["behaviorClass"])
    fixture = {"attentiveState": 3, "movementStyle": 2, "targetSelector": 8,
               "spawnDestination": 1, "hopTime": 6, "overworldLimit": 1,
               "alertSpecialAction": 2, "specialAction": 1}
    if any(mankey_profile[name] != value for name, value in fixture.items()):
        raise ValueError("Mankey canopy hopper/throw fixture changed")
    follower_effective = {record["effectiveProfileId"] for record in oracle["contextualForcedProbes"]}
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
    if (len(follower_effective) != 17 or len(transitions) != 26 or len(definitions) != 19
            or event_count < 80 or canonical_imports != expected_imports
            or any((row[2] and (row[7] or row[8] or resolver.definitions[row[5]][10] != 2))
                   or (not row[2] and resolver.definitions[row[5]][10] != 1) for row in translations)):
        raise ValueError("typed import/tired/transition execution fixture changed")
    if report:
        print(f"independent authored-graph parity: {checked} frozen cases; 115 assignments; "
              f"67 conclusions; 296 stacks; {event_count} typed events; digest={event_digest}")


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


def verify_mutation_detection(blob, source, frozen):
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
    derived = bytearray(original); derived[body_offset + 4 + 22] ^= 1; fixtures.append(("derived-field", derived))
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
    contextual = bytearray(original)
    replacement_profile = struct.unpack_from("<H", original, import_offset + 4 * import_stride + 8)[0]
    struct.pack_into("<H", contextual, import_offset + import_stride + 8, replacement_profile)
    struct.pack_into("<H", contextual, node_offset + 4 * node_stride + 4, replacement_profile)
    fixtures.append(("contextual-import-profile", contextual))
    source_offset, _, _ = base_graph.sections["sourceClassProfiles"]
    source_profile = bytearray(original); source_profile[source_offset] ^= 1
    fixtures.append(("transitional-source-profile", source_profile))
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
    identity_offset, _, identity_stride = base_graph.sections["profileIdentities"]
    provenance = bytearray(original); struct.pack_into("<H", provenance, identity_offset + 4, 0x9002)
    fixtures.append(("identity-provenance-role", provenance))
    active_optional = bytearray(original); active_optional[node_offset + node_stride + 9] = 2
    fixtures.append(("active-optional-flag", active_optional))
    expected_errors = {
        "role-mask": "field chillSpeed", "state-body": "field chillSpeed",
        "typed-value": "field attentiveSpeed", "derived-field": "derived state-body invariant",
        "exact-selector-discriminant": "typed import/tired/transition execution fixture",
        "transition-operation": "direct-cutover transition operation mismatch",
        "import-lifetime": "contextual import lifetime mismatch",
        "contextual-import-profile": "contextual node tag mismatch",
        "transitional-source-profile": "source-profile projection differs",
        "carried-owner": "contextual import owner mismatch",
        "carried-recovery": "contextual import recovery mismatch",
        "population-group-provenance": "limit provenance mismatch",
        "identity-provenance-role": "profile provenance/body-role mismatch",
    }
    expected_outcomes = {
        "definition-priority": (0x7002, 0x7003, 0x7001),
        "definition-multiplicity": (1, True),
        "applicability": 0,
        "transition-from-role": (2, (False,), 0),
        "transition-dispatch-priority": 0x2001,
        "transition-guard": (1, 0, True),
        "transition-busy": (False, (2,)),
        "owner-taxonomy": 0,
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
                verify(mutated, mutated_source, frozen, check_snapshot_digest=False, report=False)
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
    parser.add_argument("--frozen", type=Path, default=FROZEN)
    parser.add_argument("--mutation-self-test", action="store_true")
    args = parser.parse_args()
    verify(args.blob, args.source, args.frozen)
    if args.mutation_self_test:
        verify_mutation_detection(args.blob, args.source, args.frozen)


if __name__ == "__main__":
    main()
