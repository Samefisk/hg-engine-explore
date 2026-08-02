#!/usr/bin/env python3
"""Exhaustive host validator for the compact authored-source OWBD v40."""

from __future__ import annotations

import binascii
import re
import struct
from pathlib import Path

from overworld_wild_behavior_v40_field_metadata import (
    SIGNED_DELTA_OPERATORS,
    operator_allowed,
    scalar_value_valid,
    state_body_values_valid,
)

MAGIC = 0x4F574244
HEADER_SIZE = 216
CHECKSUM_OFFSET = 16
SECTION_SPECS = (
    ("stateBodies", "OWBD_STATE_BODY_COUNT", 32),
    ("profileIdentities", "OWBD_PROFILE_IDENTITY_COUNT", 8),
    ("controllers", "OWBD_CONTROLLER_COUNT", 24),
    ("controllerNodes", "OWBD_CONTROLLER_NODE_COUNT", 12),
    ("sourceClassProfiles", "OWBD_CLASS_PROFILE_COUNT", 72),
    ("genericAssignments", "OWBD_CLASS_RULE_COUNT", 20),
    ("speciesAssignments", "OWBD_SPECIES_CLASS_RULE_COUNT", 8),
    ("overrideSources", "OWBD_OVERRIDE_SOURCE_COUNT", 28),
    ("overrideMembers", "OWBD_OVERRIDE_MEMBER_COUNT", 2),
    ("overrideActions", "OWBD_OVERRIDE_ACTION_COUNT", 12),
    ("spawnPolicies", "OWBD_SPAWN_POLICY_COUNT", 12),
    ("populationPolicies", "OWBD_POPULATION_POLICY_COUNT", 10),
    ("hookSets", "OWBD_HOOK_SET_COUNT", 8),
    ("owners", "OWBD_OWNER_COUNT", 6),
    ("overrideDefinitions", "OWBD_OVERRIDE_DEFINITION_COUNT", 36),
    ("transitions", "OWBD_TRANSITION_COUNT", 24),
    ("transitionGuards", "OWBD_TRANSITION_GUARD_COUNT", 12),
    ("transitionOperations", "OWBD_TRANSITION_OPERATION_COUNT", 18),
    ("transitionActions", "OWBD_TRANSITION_ACTION_COUNT", 10),
    ("recoveryActions", "OWBD_RECOVERY_ACTION_COUNT", 8),
    ("importRecipes", "OWBD_IMPORT_RECIPE_COUNT", 24),
    ("applicability", "OWBD_APPLICABILITY_COUNT", 16),
    ("tiredTranslations", "OWBD_TIRED_TRANSLATION_COUNT", 24),
    ("semanticIds", "OWBD_SEMANTIC_ID_COUNT", 8),
)
STABLE_SECTIONS = {name for name, _, _ in SECTION_SPECS} - {
    "sourceClassProfiles", "overrideMembers"
}
DEFINE = re.compile(r"^\s*#\s*define\s+(\w+)\s+(0[xX][0-9A-Fa-f]+|[0-9]+)(?:u)?\b", re.MULTILINE)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_defines(path):
    return {name: int(value, 0) for name, value in DEFINE.findall(path.read_text())}


def crc32(blob):
    scratch = bytearray(blob)
    scratch[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4] = b"\0\0\0\0"
    return binascii.crc32(scratch) & 0xFFFFFFFF


class Graph:
    def __init__(self, blob, source, path):
        self.blob, self.path = blob, path
        self.defines = source_defines(source)
        self.sections = {}
        for index, (name, symbol, stride) in enumerate(SECTION_SPECS):
            offset, count, actual_stride = struct.unpack_from("<IHH", blob, 24 + index * 8)
            require(count == self.defines[symbol] and actual_stride == stride,
                    f"{path}: {name} count/stride mismatch")
            self.sections[name] = (offset, count, stride)

    def records(self, name, fmt):
        offset, count, stride = self.sections[name]
        require(struct.calcsize(fmt) == stride, f"{self.path}: internal {name} format mismatch")
        return [struct.unpack_from(fmt, self.blob, offset + index * stride) for index in range(count)]

    def ids(self, name):
        values = [record[0] for record in self.records(name, "<H" + "x" * (self.sections[name][2] - 2))]
        require(all(values) and len(values) == len(set(values)), f"{self.path}: {name} stable IDs invalid")
        return set(values)


def match_valid(raw):
    group, species, terrain, minimum, maximum, shiny, behavior_class, pad = struct.unpack("<IH6B", raw)
    return pad == 0 and terrain in (*range(4), 0xFF) and shiny in (0, 1, 0xFF) \
        and behavior_class in (0, 1, 2, 3, 0xFD, 0xFF) \
        and (minimum == 0 or maximum == 0 or minimum <= maximum)


def action_value_valid(field, operation, signed_value):
    value = signed_value & 0xFF
    if operation == 2:
        return -32 <= signed_value <= 32
    maxima = {
        0: 11, 5: 11, 7: 11, 1: 2, 9: 4, 10: 4, 11: 4, 12: 32, 13: 2,
        15: 3, 16: 7, 21: 7, 17: 8, 18: 4, 19: 15, 20: 9, 22: 100,
        23: 16, 24: 4, 25: 3, 32: 3, 26: 1, 45: 1, 53: 1, 68: 1,
        27: 64, 28: 64, 46: 64, 47: 64, 54: 64, 55: 64, 33: 12,
        38: 2, 39: 15, 40: 15, 41: 15, 42: 15, 43: 15, 44: 15,
        61: 64, 65: 64, 62: 32, 70: 32, 63: 4, 64: 15, 66: 15, 67: 8,
    }
    if field == 2:
        return value <= 10 or value == 0xFF
    if field in (9, 10, 11):
        return 1 <= value <= 4
    if field in (34, 35):
        return 1 <= value <= 8
    return field not in maxima or value <= maxima[field]


def state_values_valid(values):
    return state_body_values_valid(values)


def static_value_valid(kind, field, value):
    return scalar_value_valid(kind, field, value)


def claim_slices(records, total, start_index, count_index, label, path, base=0):
    claims = [0] * total
    cursor = base
    for record in records:
        start, count = record[start_index], record[count_index]
        require(start == cursor and count <= total - start, f"{path}: {label} slice out of range/order")
        for index in range(start, start + count): claims[index] += 1
        cursor += count
    require(cursor == total, f"{path}: {label} slices do not cover section")
    require(all(value == 0 for value in claims[:base]) and all(value == 1 for value in claims[base:]),
            f"{path}: orphan/multiply claimed {label}")


def validate_v40_owbd(path: Path, source: Path) -> None:
    blob = path.read_bytes()
    defines = source_defines(source)
    require(len(blob) >= HEADER_SIZE, f"{path}: truncated header")
    magic, version, header_size, blob_size, flags, checksum, fingerprint = struct.unpack_from("<IHHIIII", blob)
    require(magic == MAGIC and version == 40 and header_size == HEADER_SIZE, f"{path}: header identity mismatch")
    require(blob_size == len(blob) == defines["OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE"], f"{path}: exact size mismatch")
    require(blob_size <= defines["OVERWORLD_WILD_BEHAVIOR_DATA_MAX_SIZE"] == 0x3000, f"{path}: authored cap mismatch")
    require(flags == 6 and fingerprint == defines["OVERWORLD_WILD_BEHAVIOR_DATA_SCHEMA_FINGERPRINT"], f"{path}: flags/fingerprint mismatch")
    require(checksum == defines["OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM"] == crc32(blob), f"{path}: checksum mismatch")
    graph = Graph(blob, source, path)

    cursor = HEADER_SIZE
    for name, _, _ in SECTION_SPECS:
        offset, count, stride = graph.sections[name]
        require(offset == cursor and offset % 4 == 0 and count <= (len(blob) - offset) // stride,
                f"{path}: {name} offset/range invalid")
        cursor += count * stride
        aligned = (cursor + 3) & ~3
        require(blob[cursor:aligned] == b"\0" * (aligned - cursor), f"{path}: nonzero alignment padding")
        cursor = aligned
    require(cursor == len(blob), f"{path}: unclaimed bytes/gap")

    ids = {}
    global_ids = set()
    for name in STABLE_SECTIONS:
        ids[name] = graph.ids(name)
        require(not global_ids.intersection(ids[name]), f"{path}: global stable-ID collision in {name}")
        global_ids.update(ids[name])

    semantic = {}
    for index, (stable, kind, ordinal, reserved, reserved2) in enumerate(graph.records("semanticIds", "<HBBHH")):
        expected_kind = 1 if index < 7 else 2 if index < 10 else 3
        expected_ordinal = (index + 1 if index < 7 else index - 6 if index < 10
                            else (1, 2, 3, 6, 7, 11)[index - 10])
        require(kind == expected_kind and ordinal == expected_ordinal and reserved == reserved2 == 0,
                f"{path}: semantic ID {stable} invalid")
        semantic[stable] = (kind, ordinal)

    bodies = {}
    for stable, role, count, values in graph.records("stateBodies", "<HBB28s"):
        require(1 <= role <= 7 and count == 28 and state_values_valid(values),
                f"{path}: body {stable} role/count/tail invalid")
        require(values[22] == int(role == 2 and values[0] == 3 and values[2] != 1),
                f"{path}: body {stable} derived avoidPreviousTile invalid")
        bodies[stable] = (role, values)
    identities = {}
    for stable, body, provenance, tag_a, tag_b in graph.records("profileIdentities", "<HHHBB"):
        require(body in ids["stateBodies"] and semantic.get(provenance) == (1, bodies[body][0]),
                f"{path}: identity {stable} body/provenance dangling")
        require(((tag_a == 0 and tag_b == 0)
                 or (1 <= tag_a <= 13 and 1 <= tag_b <= 3)
                 or (tag_a == 14 and tag_b == 0)
                 or (tag_a == 15 and 1 <= tag_b <= 3)),
                f"{path}: identity {stable} role/tag mismatch")
        identities[stable] = (body, provenance, tag_a, tag_b)

    nodes = graph.records("controllerNodes", "<4HBBH")
    controllers = graph.records("controllers", "<7H10B")
    claim_slices(controllers, len(nodes), 2, 3, "controller node", path)
    node_roles = {}
    controller_ordinals = {record[0]: index + 1 for index, record in enumerate(controllers)}
    for stable, controller, profile, custom, role, flags_value, reserved in nodes:
        tag_a, tag_b = identities[profile][2:4]
        expected_system_tag = {4: 13, 5: 14, 6: 12, 7: 15}.get(role)
        require(controller in ids["controllers"] and profile in ids["profileIdentities"]
                and 1 <= role <= 7 and not flags_value & ~7 and reserved == 0
                and flags_value == ({1: 1, 2: 0, 3: 0, 4: 2, 5: 2, 6: 2, 7: 6}[role])
                and ((role == 7) == (semantic.get(custom, (0,))[0] == 2))
                and bodies[identities[profile][0]][0] == role
                and bodies[identities[profile][0]][1][0] != 0,
                f"{path}: node {stable} invalid")
        if expected_system_tag:
            require(tag_a == expected_system_tag
                    and tag_b == (0 if role == 5 else controller_ordinals[controller]),
                    f"{path}: node {stable} contextual identity tag mismatch")
        node_roles.setdefault(controller, set())
        require(role not in node_roles[controller], f"{path}: duplicate controller semantic role")
        node_roles[controller].add(role)
    for record in controllers:
        stable = record[0]
        require(record[1] == stable and record[4] in ids["spawnPolicies"] and record[5] in ids["populationPolicies"]
                and record[6] in ids["hookSets"]
                and all(scalar_value_valid(5, field, record[6 + field]) for field in range(1, 8))
                and record[14] <= 255 and record[15] == record[16] == 0,
                f"{path}: controller {stable} invalid")
        start, count = record[2:4]
        require(all(nodes[index][1] == stable for index in range(start, start + count)),
                f"{path}: controller {stable} node backlink mismatch")
        base_nodes = [nodes[index] for index in range(start, start + count) if nodes[index][5] & 1]
        require(len(base_nodes) == 1 and base_nodes[0][4] == 1 and base_nodes[0][5] == 1,
                f"{path}: controller {stable} base-node flags invalid")

    generic = graph.records("genericAssignments", "<H12sHHH")
    species = graph.records("speciesAssignments", "<4H")
    require(all(match_valid(record[1]) and record[2] < 3
            and record[3] == 0x1001 + index and record[4] == 0 for index, record in enumerate(generic)),
            f"{path}: generic assignments invalid")
    require(len({record[1] for record in species}) == len(species)
            and all(record[1] and record[2] < 3 and record[3] == 0x2003 + index
                    for index, record in enumerate(species)),
            f"{path}: species assignments invalid")

    overrides = graph.records("overrideSources", "<HH12s4HBBH")
    members = graph.records("overrideMembers", "<H")
    actions = graph.records("overrideActions", "<HBB8s")
    claim_slices(overrides, len(members), 3, 4, "override member", path)
    claim_slices(overrides, len(actions), 5, 6, "override action", path, base=3)
    require([record[8] for record in overrides] == list(range(1, 12)), f"{path}: override order changed")
    for stable, name, match, member_start, member_count, action_start, action_count, target, order, reserved in overrides:
        require(name == stable and match_valid(match) and target in (0, 1, 2) and reserved == 0x4000 + order - 1
                and ((target == 1 and member_count) or target in (0, 2)), f"{path}: override {stable} invalid")
        local = [members[index][0] for index in range(member_start, member_start + member_count)]
        require(all(local) and len(local) == len(set(local)), f"{path}: override {stable} members invalid")
    def node_binding(controller, node, profile=0, unbind=False, semantic_role=0):
        item = next((row for row in nodes if row[0] == node), None)
        if (item is None or item[1] != controller or (unbind and item[5] & 1)
                or (semantic_role and item[4] != semantic_role)):
            return False
        if not profile:
            return True
        if profile not in identities:
            return False
        body = bodies[identities[profile][0]]
        return body[0] == item[4] and body[1][0] != 0

    assignment_controllers = []
    for index, (stable, kind, flags_value, payload) in enumerate(actions):
        require(flags_value == 0 and 1 <= kind <= 11, f"{path}: static action {stable} tag invalid")
        if kind == 1:
            controller, zero0, zero1, zero2 = struct.unpack("<4H", payload)
            require(index < 3 and controller in ids["controllers"] and zero0 == zero1 == zero2 == 0,
                    f"{path}: assignment action {stable} invalid")
            assignment_controllers.append(controller)
        elif kind in (2, 3):
            controller, node, profile, zero = struct.unpack("<4H", payload)
            require(index >= 3 and node_binding(controller, node, profile, kind == 3)
                    and zero == 0 and ((kind == 2 and profile) or (kind == 3 and profile == 0)),
                    f"{path}: node action {stable} invalid")
        elif kind in (4, 5, 7, 9):
            field, operator, delta, bound, roles, zero, controller = struct.unpack("<BBbBBBH", payload)
            require(index >= 3 and operator_allowed(kind, field, operator) and zero == 0
                    and ((operator in (5, 6)) or bound == 0)
                    and ((-32 <= delta <= 32) if operator in SIGNED_DELTA_OPERATORS
                         else static_value_valid(kind, field, delta & 0xFF))
                    and (operator not in (5, 6) or static_value_valid(kind, field, bound))
                    and (not controller or controller in ids["controllers"]),
                    f"{path}: modifier action {stable} common payload invalid")
            if kind == 4:
                require(1 <= field <= 27 and field != 22 and roles and not roles & ~7,
                        f"{path}: state modifier {stable} invalid")
            elif kind == 5:
                require(1 <= field <= 7 and roles == controller == 0,
                        f"{path}: controller modifier {stable} invalid")
            elif kind == 7:
                require(1 <= field <= 5 and roles == controller == 0,
                        f"{path}: spawn patch {stable} invalid")
            else:
                require(field == 1 and roles == controller == 0,
                        f"{path}: population patch {stable} invalid")
        elif kind in (6, 8, 10):
            reference, zero0, zero1, zero2 = struct.unpack("<4H", payload)
            section_name = {6: "spawnPolicies", 8: "populationPolicies", 10: "hookSets"}[kind]
            require(index >= 3 and reference in ids[section_name] and zero0 == zero1 == zero2 == 0,
                    f"{path}: policy binding action {stable} invalid")
        else:
            controller, node, operator, value, zero = struct.unpack("<HHBBH", payload)
            signed_value = value if value < 128 else value - 256
            require(index >= 3 and node_binding(controller, node, unbind=True, semantic_role=3)
                    and operator_allowed(11, 1, operator)
                    and (operator == 1 or -32 <= signed_value <= 32) and zero == 0,
                    f"{path}: timer action {stable} invalid")
    require(len(assignment_controllers) == 3
            and all(assignment_controllers[record[2]] in ids["controllers"] for record in generic + species),
            f"{path}: assignment action coverage invalid")

    for stable, name, provenance, spawn_state, destination, minimum, maximum, hop, flags_value in graph.records("spawnPolicies", "<3H6B"):
        require(name == stable and semantic.get(provenance, (0,))[0] == 1
                and all(scalar_value_valid(7, field, value) for field, value in enumerate(
                    (spawn_state, destination, minimum, maximum, hop), 1))
                and minimum <= maximum and flags_value == 0,
                f"{path}: spawn policy {stable} invalid")
    groups = {}
    population_records = graph.records("populationPolicies", "<4H2B")
    expected_population_keys = (1, 2, 3, 6, 7, 11)
    expected_override_provenance = (None, None, None, 0x5002, 0x5003, 0x5007)
    for policy_index, (stable, name, group, provenance, limit, flags_value) in enumerate(population_records):
        expected_provenance = expected_override_provenance[policy_index]
        require(name == stable and semantic.get(group) == (3, expected_population_keys[policy_index])
                and ((semantic.get(provenance) == (1, policy_index + 1)) if policy_index < 3
                     else provenance == expected_provenance)
                and scalar_value_valid(9, 1, limit) and flags_value == 0,
                f"{path}: population {stable} invalid")
        require(group not in groups or groups[group] == limit, f"{path}: population group conflict")
        groups[group] = limit
    for stable, name, help_call, pickup_entry, pickup_loop, flags_value in graph.records("hookSets", "<2H4B"):
        require(name == stable and help_call in (0, 1) and pickup_entry in (0, 1)
                and pickup_loop in (0, 1) and pickup_entry == pickup_loop
                and not (help_call and pickup_entry) and flags_value == 0,
                f"{path}: hook {stable} invalid")
    owner_records = graph.records("owners", "<2H2B")
    require(tuple(record[0] for record in owner_records) == tuple(range(0x8102, 0x810C)),
            f"{path}: live owner registry is not canonical")
    for stable, name, system_owned, flags_value in owner_records:
        require(name == stable and system_owned in (0, 1) and flags_value == 0, f"{path}: owner {stable} invalid")

    applications = {}
    for stable, flags_value, context_mask, controller, profile, role, reserved0, reserved in \
            graph.records("applicability", "<HHIHHBBH"):
        require(flags_value and not flags_value & ~0xF and reserved0 == reserved == 0,
                f"{path}: applicability {stable} flags/reserved invalid")
        require(bool(flags_value & 1) == bool(context_mask)
                and ((flags_value & 2 and controller in ids["controllers"]) or (not flags_value & 2 and controller == 0))
                and ((flags_value & 4 and profile in ids["profileIdentities"]) or (not flags_value & 4 and profile == 0))
                and ((flags_value & 8 and 1 <= role <= 7) or (not flags_value & 8 and role == 0)),
                f"{path}: applicability {stable} tagged selector invalid")
        applications[stable] = (flags_value, context_mask, controller, profile, role)

    definitions = {}
    node_owner = {record[0]: record[1] for record in nodes}
    for record in graph.records("overrideDefinitions", "<8H20B"):
        stable, name, controller, node, owner, recovery, applicability, priority = record[:8]
        tags = record[8:]
        (kind, channel, selector, role, map_life, battle_life, clock, source_kind, hidden,
         recovery_policy, timer, has_origin, origin, has_owner, allow_owners, allow_instances,
         authored_bound, flags_value, reserved0, reserved1) = tags
        require(name == stable and applicability in applications and priority <= 0xFF
                and kind in (1, 2) and channel <= 5 and selector in (1, 2)
                and map_life in (1, 2, 3) and battle_life in (1, 2, 3) and clock <= 2
                and source_kind <= 3 and hidden <= 3 and recovery_policy <= 1 and has_origin <= 1
                and has_owner <= 1 and allow_owners <= 1 and allow_instances <= 1 and authored_bound <= 1
                and flags_value <= 1 and reserved0 == reserved1 == 0,
                f"{path}: definition {stable} scalar/tag invalid")
        require(bool(has_owner) == bool(owner)
                and (not has_owner or owner in ids["owners"]),
                f"{path}: definition {stable} required-owner tag noncanonical")
        require(kind != 1 or not (applications[applicability][0] & (4 | 8)),
                f"{path}: state candidate {stable} self-gates on mutable output")
        if selector == 2:
            require(controller == node == 0 and 1 <= role <= 7,
                    f"{path}: semantic definition {stable} selector payload invalid")
        else:
            require(controller in ids["controllers"] and node in node_owner and node_owner[node] == controller and role == 0,
                    f"{path}: exact definition {stable} selector payload invalid")
            require(applications[applicability][2] == controller,
                    f"{path}: exact definition {stable} applicability controller mismatch")
        require((clock == 0) == (source_kind == 0) == (timer == 0)
                and (hidden == 0 or source_kind != 0)
                and bool(recovery_policy) == bool(recovery), f"{path}: definition {stable} timer/recovery tags invalid")
        require((has_origin != 0) == (origin != 0), f"{path}: definition {stable} origin tag noncanonical")
        if origin:
            require(origin in (1, 2, 3) and has_owner
                    and owner == {1: 0x8107, 2: 0x8106, 3: 0x8108}[origin]
                    and recovery in ids["transitions"], f"{path}: tired definition {stable} pairing invalid")
        elif owner:
            require(stable == 0x7004 and has_owner and owner == 0x8105
                    and selector == 2 and role == 3,
                    f"{path}: generated stamina owner pairing invalid")
        elif stable == 0x7004:
            require(False, f"{path}: generated stamina owner authorization missing")
        elif recovery:
            require(recovery in ids["transitions"], f"{path}: definition {stable} recovery dangling")
        if selector == 1:
            require(bool(flags_value) == bool(origin) and authored_bound == 0,
                    f"{path}: exact tired wrapper flags invalid")
        definitions[stable] = record
    application_claims = [record[6] for record in definitions.values()]
    require(set(application_claims) == set(applications) and len(application_claims) == len(set(application_claims)),
            f"{path}: applicability records are orphaned or multiply claimed")

    transitions = graph.records("transitions", "<9H4BH")
    guards = graph.records("transitionGuards", "<HH4BHH")
    operations = graph.records("transitionOperations", "<7H4B")
    typed_actions = graph.records("transitionActions", "<HHBBHH")
    recoveries = graph.records("recoveryActions", "<HHHBB")
    claim_slices(transitions, len(guards), 3, 4, "transition guard", path)
    claim_slices(transitions, len(operations), 5, 6, "transition operation", path)
    claim_slices(transitions, len(typed_actions), 7, 8, "transition action", path)
    recovery_claims = [0] * len(recoveries)
    recovery_cursor = 0
    for record in transitions:
        stable, definition, owner = record[:3]
        require(definition in definitions
                and (definitions[definition][4] == 0 or owner == definitions[definition][4])
                and owner in ids["owners"] and 1 <= record[9] <= 13
                and record[10] and not record[10] & ~0x7F
                and record[13] == (0x2000 + record[3] if stable < 0xA012 else 0x3000 + stable - 0xA012),
                f"{path}: transition {stable} invalid")
        start, count = record[11:13]
        require(start == recovery_cursor and count <= len(recoveries) - start, f"{path}: recovery slice invalid")
        for index in range(start, start + count): recovery_claims[index] += 1
        recovery_cursor += count
    require(all(value == 1 for value in recovery_claims), f"{path}: orphan recovery")
    for definition, record in definitions.items():
        recovery = record[5]
        if recovery:
            route = next((item for item in transitions if item[0] == recovery), None)
            require(route is not None and route[1] == definition
                    and (record[4] == 0 or route[2] == record[4]),
                    f"{path}: definition {definition} recovery backlink mismatch")
    for stable, transition, kind, negate, payload, reserved0, reference, reserved in guards:
        require(transition in ids["transitions"] and 1 <= kind <= 8 and negate <= 1
                and reserved0 == reserved == 0, f"{path}: guard {stable} invalid")
        if kind == 1: require(payload == reference == 0, f"{path}: always guard payload invalid")
        elif kind == 2: require(1 <= payload <= 7 and reference == 0, f"{path}: role guard payload invalid")
        elif kind == 3: require(payload == 0 and reference in ids["controllerNodes"], f"{path}: node guard payload invalid")
        elif kind in (4, 5): require(payload == 0 and reference in ids["owners"], f"{path}: owner guard payload invalid")
        elif kind == 6: require(1 <= payload <= 3 and reference == 0, f"{path}: timer guard payload invalid")
        elif kind == 7: require(payload <= 100 and reference == 0, f"{path}: chance guard payload invalid")
        elif kind == 8: require(1 <= payload <= 13 and reference == 0, f"{path}: system guard payload invalid")
    for stable, transition, definition, owner, replacement, policy, instance, kind, busy, required, reserved in operations:
        require(transition in ids["transitions"] and 1 <= kind <= 6 and busy in (1, 2)
                and required <= 1 and reserved == 0, f"{path}: operation {stable} invalid")
        if kind in (1, 3, 4):
            require(definition in definitions and owner in ids["owners"]
                    and (definitions[definition][4] == 0 or owner == definitions[definition][4])
                    and not replacement and not policy
                    and instance == definition and required == (kind == 3), f"{path}: operation ref/payload invalid")
        elif kind == 2:
            require(definition in definitions and owner in ids["owners"]
                    and (definitions[definition][4] == 0 or owner == definitions[definition][4])
                    and replacement in definitions
                    and (definitions[replacement][4] == 0 or owner == definitions[replacement][4])
                    and not policy and instance == definition and not required, f"{path}: replace payload invalid")
        elif kind == 5:
            require(not definition and owner in ids["owners"] and not replacement and not policy and not instance and not required,
                    f"{path}: remove-owner payload invalid")
        else:
            require(not definition and not owner and not replacement and policy and not instance and not required,
                    f"{path}: policy payload invalid")
    for stable, transition, phase, kind, reference, payload in typed_actions:
        require(transition in ids["transitions"] and phase in (1, 2, 3, 4) and 1 <= kind <= 8
                and reference == payload == 0, f"{path}: typed action {stable} invalid")
    for stable, transition, owner, kind, required in recoveries:
        require(transition in ids["transitions"] and owner in ids["owners"] and 1 <= kind <= 4 and required <= 1,
                f"{path}: recovery {stable} invalid")
    for transition in transitions:
        tid = transition[0]
        require(all(record[1] == tid for record in guards[transition[3]:transition[3] + transition[4]])
                and all(record[1] == tid for record in operations[transition[5]:transition[5] + transition[6]])
                and all(record[1] == tid for record in typed_actions[transition[7]:transition[7] + transition[8]])
                and all(record[1] == tid and record[2] == transition[2]
                        for record in recoveries[transition[11]:transition[11] + transition[12]]),
                f"{path}: transition {tid} child backlink mismatch")
    override_by_id = {record[0]: record for record in overrides}
    import_keys = set()
    imports = graph.records("importRecipes", "<10H4B")
    for (stable, owner, controller, node, profile, recovery, source_id, action_start,
         action_count, truth_vector, role, lifetime, flags_value, reserved) in \
            imports:
        require(owner in ids["owners"] and profile in ids["profileIdentities"] and 1 <= role <= 6
                and lifetime in (1, 2, 3) and flags_value in (0, 1) and reserved == 0
                and (recovery == 0 or recovery in ids["transitions"]), f"{path}: import {stable} invalid")
        if flags_value == 0:
            require(controller in ids["controllers"] and node in node_owner and node_owner[node] == controller
                    and 4 <= role <= 6, f"{path}: contextual import {stable} selector invalid")
            node_record = next(item for item in nodes if item[0] == node)
            expected_tag = {4: 13, 5: 14, 6: 12}[role]
            require(node_record[4] == role and node_record[2] == profile
                    and bodies[identities[profile][0]][0] == role,
                    f"{path}: contextual import {stable} role/profile/node mismatch")
            require(identities[profile][2:] == (expected_tag, 0 if role == 5 else controller_ordinals[controller]),
                    f"{path}: contextual import {stable} profile context tag mismatch")
            expected = {
                4: (0x810A, 0xA00F, 2, 0x500A),
                5: (0x8109, 0, 1, 0),
                6: (0x810B, 0xA011, 3, 0x500B),
            }[role]
            require((owner, recovery, lifetime, source_id) == expected and truth_vector == 0xFFFF,
                    f"{path}: contextual import {stable} canonical owner/recovery/source invalid")
            if source_id:
                source = override_by_id.get(source_id)
                require(source is not None and (action_start, action_count) == source[5:7],
                        f"{path}: contextual import {stable} source action slice mismatch")
            else:
                require(action_start == action_count == 0,
                        f"{path}: carried import {stable} has inactive source payload")
        else:
            require(owner == 0x8109 and controller == node == recovery == source_id == 0
                    and action_start == action_count == truth_vector == 0 and lifetime == 1
                    and role in (1, 2, 3)
                    and bodies[identities[profile][0]][0] == role,
                    f"{path}: pseudo-class import {stable} invalid")
        require((flags_value, controller, role) not in import_keys, f"{path}: duplicate import recipe")
        import_keys.add((flags_value, controller, role))
    require(len(import_keys) == 12, f"{path}: contextual import coverage invalid")

    translations = graph.records("tiredTranslations", "<HBB6H4B2H")
    translation_keys = set()
    for (stable, origin, authored_bound, destination_controller, profile, definition, recovery,
         fallback_controller, fallback_node, timer_operator, timer_source, map_life, battle_life,
         flags_value, reserved) in translations:
        require(origin in (1, 2, 3) and authored_bound in (0, 1)
                and destination_controller in ids["controllers"] and profile in identities and definition in definitions
                and recovery in ids["transitions"] and timer_operator == 1
                and timer_source == 1
                and map_life == 2 and battle_life == 1 and flags_value == reserved == 0,
                f"{path}: tired translation {stable} scalar/reference invalid")
        body = bodies[identities[profile][0]]
        definition_record = definitions[definition]
        require(definition_record[19] == 1 and definition_record[20] == origin
                and definition_record[5] == recovery, f"{path}: tired translation {stable} origin/backlink invalid")
        if authored_bound:
            require(body[0] == 3 and definition_record[10] == 2 and definition_record[11] == 3
                    and definition_record[2] == definition_record[3] == 0
                    and fallback_controller == fallback_node == 0,
                    f"{path}: authored tired translation must use portable semantic origin")
        else:
            expected_node = next(node[0] for node in nodes if node[1] == destination_controller and node[4] == 7)
            require(body[0] == 7 and fallback_controller == destination_controller
                    and fallback_node == expected_node and node_owner[fallback_node] == destination_controller
                    and definition_record[10] == 1 and definition_record[2] == destination_controller
                    and definition_record[3] == expected_node and definition_record[24] == 0,
                    f"{path}: absent tired translation exact fallback invalid")
        require((origin, destination_controller, authored_bound) not in translation_keys,
                f"{path}: duplicate tired translation")
        translation_keys.add((origin, destination_controller, authored_bound))
    require(len(translation_keys) == 18 and {key[0] for key in translation_keys} == {1, 2, 3},
            f"{path}: tired translation coverage invalid")

    owner_references = {record[4] for record in definitions.values() if record[4]}
    owner_references.update(record[2] for record in transitions)
    owner_references.update(record[6] for record in guards if record[2] in (4, 5))
    owner_references.update(record[3] for record in operations if record[3])
    owner_references.update(record[2] for record in recoveries)
    owner_references.update(record[1] for record in imports)
    require(owner_references == ids["owners"],
            f"{path}: owner records are orphaned or outside inbound-reference closure")

    # Current-runtime adapter source is closed and stays below the proven v39 cap.
    for profile in graph.records("sourceClassProfiles", "<72B"):
        require(all(1 <= profile[index] <= 4 for index in (9, 10, 11)), f"{path}: source profile speed invalid")


__all__ = ["validate_v40_owbd", "SECTION_SPECS"]
