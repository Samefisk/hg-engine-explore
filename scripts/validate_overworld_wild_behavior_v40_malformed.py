#!/usr/bin/env python3
"""Permanent host/production-validator differential corpus for OWBD v40."""

from __future__ import annotations

import argparse
import binascii
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from overworld_wild_behavior_v40_validator import SECTION_SPECS, validate_v40_owbd
from resolve_overworld_wild_behavior_v40 import apply_typed_operator
from validate_overworld_wild_behavior_v40_projection import expected_projection

CHECKSUM_OFFSET = 16
SECTION = {name: index for index, (name, _, _) in enumerate(SECTION_SPECS)}


def section(blob, name):
    return struct.unpack_from("<IHH", blob, 24 + SECTION[name] * 8)


def record(blob, name, index=0):
    offset, count, stride = section(blob, name)
    if not 0 <= index < count:
        raise ValueError(f"fixture index {index} outside {name}")
    return offset + index * stride


def seal(blob):
    blob[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4] = b"\0" * 4
    checksum = binascii.crc32(blob) & 0xFFFFFFFF
    struct.pack_into("<I", blob, CHECKSUM_OFFSET, checksum)
    return checksum


def put8(section_name, relative, value, index=0):
    return lambda blob: blob.__setitem__(record(blob, section_name, index) + relative, value)


def put16(section_name, relative, value, index=0):
    return lambda blob: struct.pack_into("<H", blob, record(blob, section_name, index) + relative, value)


def correlated_spawn(blob):
    base = record(blob, "spawnPolicies")
    blob[base + 8], blob[base + 9] = 7, 2


def correlated_exact_selector(blob):
    base = record(blob, "overrideDefinitions", 10)
    struct.pack_into("<H", blob, base + 4, 0x3001)
    struct.pack_into("<H", blob, base + 6, 0x3108)  # node belongs to controller 0x3002


def correlated_translation(blob):
    base = record(blob, "tiredTranslations")
    struct.pack_into("<H", blob, base + 4, 0x3002)
    struct.pack_into("<H", blob, base + 12, 0x3002)
    struct.pack_into("<H", blob, base + 14, 0x310E)  # valid node, wrong semantic/controller arm


def correlated_import(blob):
    base = record(blob, "importRecipes")
    struct.pack_into("<H", blob, base + 4, 0x3002)
    struct.pack_into("<H", blob, base + 6, 0x3101)


def correlated_missing_stamina_owner(blob):
    base = record(blob, "overrideDefinitions", 3)
    struct.pack_into("<H", blob, base + 8, 0)
    blob[base + 29] = 0


def correlated_duplicate_import(blob):
    source = record(blob, "importRecipes", 0)
    destination = record(blob, "importRecipes", 3)
    blob[destination:destination + 24] = blob[source:source + 24]


def correlated_duplicate_base(blob):
    base = record(blob, "controllerNodes", 1)
    blob[base + 9] = 1


def correlated_orphan_owner(blob):
    for section_name, relative in (
        ("overrideDefinitions", 8), ("transitions", 4),
        ("transitionOperations", 6), ("recoveryActions", 4),
        ("importRecipes", 2),
    ):
        offset, count, stride = section(blob, section_name)
        for index in range(count):
            location = offset + index * stride + relative
            if struct.unpack_from("<H", blob, location)[0] == 0x8102:
                struct.pack_into("<H", blob, location, 0x8103)
    offset, count, stride = section(blob, "transitionGuards")
    for index in range(count):
        location = offset + index * stride
        if blob[location + 4] in (4, 5) and struct.unpack_from("<H", blob, location + 8)[0] == 0x8102:
                struct.pack_into("<H", blob, location + 8, 0x8103)


def mutate_modifier_action(blob, kind, field, operator, delta, bound=0):
    offset, count, stride = section(blob, "overrideActions")
    for index in range(count):
        action = offset + index * stride
        if blob[action + 2] == kind:
            blob[action + 4] = field
            blob[action + 5] = operator
            struct.pack_into("<b", blob, action + 6, delta)
            blob[action + 7] = bound
            return
    raise ValueError(f"fixture has no modifier action kind {kind}")


def mutate_timer_action(blob, operator, operand):
    offset, count, stride = section(blob, "overrideActions")
    for index in range(count):
        action = offset + index * stride
        if blob[action + 2] == 11:
            blob[action + 8] = operator
            blob[action + 9] = operand & 0xFF
            return
    raise ValueError("fixture has no candidate-timer action")


def candidate_timer_targets_active_node(blob):
    node_offset, node_count, node_stride = section(blob, "controllerNodes")
    active_by_controller = {}
    for index in range(node_count):
        node = node_offset + index * node_stride
        controller = struct.unpack_from("<H", blob, node + 2)[0]
        if blob[node + 8] == 2:
            active_by_controller[controller] = struct.unpack_from("<H", blob, node)[0]
    action_offset, action_count, action_stride = section(blob, "overrideActions")
    for index in range(action_count):
        action = action_offset + index * action_stride
        if blob[action + 2] == 11:
            controller = struct.unpack_from("<H", blob, action + 4)[0]
            struct.pack_into("<H", blob, action + 6, active_by_controller[controller])
            return
    raise ValueError("fixture has no candidate-timer action")


def bound_override_profile_has_zero_behavior(blob):
    identity_offset, identity_count, identity_stride = section(blob, "profileIdentities")
    body_offset, body_count, body_stride = section(blob, "stateBodies")
    node_offset, node_count, node_stride = section(blob, "controllerNodes")
    bound_profiles = {
        struct.unpack_from("<H", blob, node_offset + index * node_stride + 4)[0]
        for index in range(node_count)
    }
    action_offset, action_count, action_stride = section(blob, "overrideActions")
    for action_index in range(action_count):
        action = action_offset + action_index * action_stride
        if blob[action + 2] != 2:
            continue
        profile = struct.unpack_from("<H", blob, action + 8)[0]
        if profile in bound_profiles:
            continue
        body = next(
            struct.unpack_from("<H", blob, identity_offset + index * identity_stride + 2)[0]
            for index in range(identity_count)
            if struct.unpack_from("<H", blob, identity_offset + index * identity_stride)[0] == profile
        )
        for body_index in range(body_count):
            location = body_offset + body_index * body_stride
            if struct.unpack_from("<H", blob, location)[0] == body:
                blob[location + 4] = 0
                blob[location + 26] = 0
                return
    raise ValueError("fixture has no override-only bound profile")


def replace_uses_wrong_replacement_owner(blob):
    operation = record(blob, "transitionOperations", 0)
    struct.pack_into("<H", blob, operation + 8, 0x7004)
    blob[operation + 14] = 2


def owner_only_in_non_transition_record(blob):
    offset, count, stride = section(blob, "transitions")
    for index in range(count):
        location = offset + index * stride + 4
        if struct.unpack_from("<H", blob, location)[0] == 0x8102:
            struct.pack_into("<H", blob, location, 0x8103)


OPERATOR_CASES = tuple(
    (target, kind, field, operator, before, delta, bound, expected)
    for target, kind, field, rows in (
        ("state-speed", 4, 3, ((1, 2, 4, 0, 4), (2, 3, 2, 0, 4),
                               (3, 2, 4, 0, 4), (4, 3, 2, 0, 2),
                               (5, 2, -1, 3, 3), (6, 2, 3, 3, 3))),
        ("controller-alert-chance", 5, 6,
         ((1, 20, 75, 0, 75), (2, 20, -1, 0, 19), (2, 95, 10, 0, 100),
          (3, 20, 75, 0, 75), (4, 80, 25, 0, 25),
          (5, 10, -20, 30, 30), (6, 90, 20, 70, 70))),
        ("spawn-hop-time", 7, 5, ((1, 2, 7, 0, 7), (2, 20, -1, 0, 19),
                                      (2, 7, 3, 0, 10),
                                      (3, 2, 6, 0, 6), (4, 6, 3, 0, 3),
                                      (5, 2, -5, 4, 4), (6, 7, 4, 5, 5))),
        ("candidate-timer", 11, 1,
         ((1, 20, 0, 0, 0), (1, 20, 255, 0, 255), (2, 20, -1, 0, 19))),
        ("state-range", 4, 4, ((1, 32, 64, 0, 64),)),
        ("state-hop-min", 4, 9, ((1, 1, 0, 0, 0),)),
        ("state-hop-max", 4, 10, ((1, 1, 12, 0, 12),)),
        ("state-hop-pause", 4, 11, ((1, 40, 255, 0, 255),)),
        ("state-teleport-pause", 4, 15, ((1, 30, 255, 0, 255),)),
        ("state-ram-max", 4, 17, ((1, 4, 255, 0, 255),)),
        ("state-chain-pause", 4, 25, ((1, 0, 255, 0, 255),)),
        ("controller-alertness", 5, 4, ((1, 14, 64, 0, 64),)),
        ("controller-alert-range", 5, 5, ((1, 3, 5, 0, 5),)),
        ("state-target", 4, 2, ((1, 6, 9, 0, 9),)),
        ("state-allowed-tile", 4, 6, ((1, 0, 15, 0, 15),)),
        ("state-battle-trigger", 4, 26, ((1, 0, 2, 0, 2),)),
        ("population-limit", 9, 1, ((1, 4, 10, 0, 10),)),
    )
    for operator, before, delta, bound, expected in rows
)


def operator_conformance(target):
    executed = 0
    seen_operators = set()
    for label, kind, field, operator, before, delta, bound, expected in OPERATOR_CASES:
        actual = apply_typed_operator(kind, field, operator, before, delta, bound)
        if actual != expected:
            raise SystemExit(f"Python operator mismatch: {label}/{operator}: {actual} != {expected}")
        completed = subprocess.run(
            [target, "--operator", str(kind), str(field), str(operator),
             str(before), str(delta), str(bound)],
            check=True, text=True, stdout=subprocess.PIPE)
        c_actual = int(completed.stdout.strip())
        if c_actual != expected:
            raise SystemExit(f"C operator mismatch: {label}/{operator}: {c_actual} != {expected}")
        executed += 1
        seen_operators.add(operator)
    if executed != 36 or seen_operators != set(range(1, 7)):
        raise SystemExit("six-operator conformance coverage is incomplete")


def corpus(valid, count=5000):
    explicit = [
        ("header-magic", lambda b: struct.pack_into("<I", b, 0, 0)),
        ("header-version", lambda b: struct.pack_into("<H", b, 4, 41)),
        ("header-size", lambda b: struct.pack_into("<H", b, 6, 212)),
        ("header-flags", lambda b: struct.pack_into("<I", b, 12, 0xFFFFFFFF)),
        ("header-fingerprint", lambda b: struct.pack_into("<I", b, 20, 0)),
        ("section-offset-overlap", lambda b: struct.pack_into("<I", b, 24 + SECTION["profileIdentities"] * 8,
                                                               section(b, "stateBodies")[0])),
        ("section-count", lambda b: struct.pack_into("<H", b, 24 + SECTION["owners"] * 8 + 4, 9)),
        ("section-stride", lambda b: struct.pack_into("<H", b, 24 + SECTION["overrideActions"] * 8 + 6, 10)),
        ("body-kind-zero", put8("stateBodies", 4, 0)),
        ("body-derived", put8("stateBodies", 26, 1)),
        ("body-role-zero", put8("stateBodies", 2, 0)),
        ("body-count", put8("stateBodies", 3, 27)),
        ("body-boolean", put8("stateBodies", 12, 2)),
        ("body-target-gap", put8("stateBodies", 6, 7)),
        ("body-allowed-tile-gap", put8("stateBodies", 10, 6)),
        ("body-battle-trigger-gap", put8("stateBodies", 30, 3)),
        ("body-hop-distance-high", put8("stateBodies", 14, 13)),
        ("body-range-high", put8("stateBodies", 8, 65)),
        ("state-locomotion-add", lambda b: mutate_modifier_action(b, 4, 1, 2, 1)),
        ("state-target-gap", lambda b: mutate_modifier_action(b, 4, 2, 1, 7)),
        ("state-allowed-tile-gap", lambda b: mutate_modifier_action(b, 4, 6, 1, 6)),
        ("state-battle-trigger-gap", lambda b: mutate_modifier_action(b, 4, 26, 1, 3)),
        ("candidate-timer-at-least", lambda b: mutate_timer_action(b, 3, 4)),
        ("candidate-timer-active-node", candidate_timer_targets_active_node),
        ("bound-override-profile-zero-behavior", bound_override_profile_has_zero_behavior),
        ("node-profile-role", put16("controllerNodes", 4, 0x2202)),
        ("node-active-optional", put8("controllerNodes", 9, 2, 1)),
        ("node-flags-unknown", put8("controllerNodes", 9, 0x80)),
        ("node-padding", put16("controllerNodes", 10, 1)),
        ("controller-alert-state", put8("controllers", 14, 3)),
        ("controller-alertness-high", put8("controllers", 17, 65)),
        ("controller-alert-range-high", put8("controllers", 18, 6)),
        ("controller-reserved", put8("controllers", 22, 1)),
        ("static-action-kind", put8("overrideActions", 2, 0, 3)),
        ("static-action-flags", put8("overrideActions", 3, 1, 3)),
        ("modifier-operator", put8("overrideActions", 5, 7, 10)),
        ("modifier-inactive-bound", put8("overrideActions", 7, 1, 10)),
        ("modifier-reserved", put8("overrideActions", 9, 1, 10)),
        ("exact-wrapper-flags", put8("overrideDefinitions", 33, 0, 10)),
        ("definition-channel", put8("overrideDefinitions", 17, 6)),
        ("definition-selector", put8("overrideDefinitions", 18, 0)),
        ("definition-map-lifetime", put8("overrideDefinitions", 20, 4)),
        ("definition-owner-boolean", put8("overrideDefinitions", 29, 2)),
        ("definition-multiplicity", put8("overrideDefinitions", 30, 2)),
        ("duplicate-import", correlated_duplicate_import),
        ("import-profile", put16("importRecipes", 8, 0x2206)),
        ("import-node", put16("importRecipes", 6, 0x3105)),
        ("import-owner", put16("importRecipes", 2, 0x810B)),
        ("import-recovery", put16("importRecipes", 10, 0xA001)),
        ("import-source", put16("importRecipes", 12, 0x500A, 1)),
        ("import-action-slice", put16("importRecipes", 14, 0, 1)),
        ("import-truth", put16("importRecipes", 18, 0, 1)),
        ("import-flags", put8("importRecipes", 22, 2)),
        ("import-padding", put8("importRecipes", 23, 1)),
        ("owner-boolean", put8("owners", 4, 2)),
        ("owner-inbound-closure", correlated_orphan_owner),
        ("applicability-flags", put16("applicability", 2, 0xFF)),
        ("applicability-controller", put16("applicability", 8, 0x3002, 10)),
        ("applicability-padding", put8("applicability", 13, 1)),
        ("spawn-distance", correlated_spawn),
        ("spawn-state", put8("spawnPolicies", 6, 4)),
        ("spawn-flags", put8("spawnPolicies", 11, 1)),
        ("population-group-zero", put16("populationPolicies", 4, 0)),
        ("population-provenance", put16("populationPolicies", 6, 0x9002)),
        ("population-limit", put8("populationPolicies", 8, 13)),
        ("transition-slice", put16("transitions", 14, 0, 1)),
        ("transition-trigger", put8("transitions", 18, 0)),
        ("transition-from-role", put8("transitions", 19, 0)),
        ("guard-discriminant", put8("transitionGuards", 4, 9)),
        ("guard-negate", put8("transitionGuards", 5, 2)),
        ("operation-discriminant", put8("transitionOperations", 14, 7)),
        ("operation-busy", put8("transitionOperations", 15, 3)),
        ("replace-wrong-replacement-owner", replace_uses_wrong_replacement_owner),
        ("recovery-kind", put8("recoveryActions", 6, 5)),
        ("recovery-required", put8("recoveryActions", 7, 2)),
        ("tired-backlink", correlated_translation),
        ("tired-origin", put8("tiredTranslations", 2, 4)),
        ("tired-bound", put8("tiredTranslations", 3, 2)),
        ("tired-timer-source", put8("tiredTranslations", 17, 3)),
        ("semantic-ordinal", put8("semanticIds", 3, 0)),
        ("semantic-kind", put8("semanticIds", 2, 4)),
    ]
    cases = {}
    for label, mutate in explicit:
        blob = bytearray(valid); mutate(blob); seal(blob); cases[label] = bytes(blob)

    # Each remaining case is a standalone, independently expected collision:
    # one stable record receives another live stable ID.  No masking noise or
    # compound defect is used, and every byte string is unique.
    stable_locations = []
    for name, _, stride in SECTION_SPECS:
        if name in ("sourceClassProfiles", "overrideMembers"): continue
        offset, records, actual_stride = section(valid, name)
        if actual_stride != stride: raise ValueError(f"fixture stride mismatch for {name}")
        stable_locations.extend((name, index, offset + index * stride) for index in range(records))
    pair = 1
    while len(cases) < count:
        for target_index, (name, record_index, location) in enumerate(stable_locations):
            donor = stable_locations[(target_index + pair) % len(stable_locations)][2]
            if donor == location: continue
            blob = bytearray(valid)
            blob[location:location + 2] = valid[donor:donor + 2]
            seal(blob)
            cases[f"stable-collision-{pair:02d}-{name}-{record_index:03d}"] = bytes(blob)
            if len(cases) == count: return cases
        pair += 1
    return cases


def accepted_corpus(valid):
    """Standalone schema-valid changes whose semantic effect belongs to replay."""
    mutations = {
        "definition-priority": put16("overrideDefinitions", 14, 199),
        "definition-multiplicity": put8("overrideDefinitions", 30, 1),
        "transition-from-role": put8("transitions", 19, 0x7E),
        "operation-busy-queue": put8("transitionOperations", 15, 2),
        "owner-system-flag": put8("owners", 4, 0),
        "controller-alert-chance": put8("controllers", 19, 99),
        "spawn-hop-time": put8("spawnPolicies", 10, 63),
        "controller-negative-add": lambda b: mutate_modifier_action(b, 5, 6, 2, -1),
        "spawn-negative-add": lambda b: mutate_modifier_action(b, 7, 3, 2, -1),
        "candidate-timer-set-zero": lambda b: mutate_timer_action(b, 1, 0),
        "candidate-timer-set-255": lambda b: mutate_timer_action(b, 1, 255),
        "candidate-timer-add-negative": lambda b: mutate_timer_action(b, 2, -1),
        "body-hop-min-zero": put8("stateBodies", 13, 0),
        "body-hop-max-twelve": put8("stateBodies", 14, 12),
        "body-hop-pause-255": put8("stateBodies", 15, 255),
        "body-teleport-pause-255": put8("stateBodies", 19, 255),
        "body-ram-max-255": put8("stateBodies", 21, 255),
        "body-chain-pause-255": put8("stateBodies", 29, 255),
        "body-movement-range-64": put8("stateBodies", 8, 64),
        "body-target-member-nine": put8("stateBodies", 6, 9),
        "body-allowed-tile-none": put8("stateBodies", 10, 15),
        "body-battle-trigger-two": put8("stateBodies", 30, 2),
        "controller-alertness-64": put8("controllers", 17, 64),
        "controller-alert-range-five": put8("controllers", 18, 5),
        "owner-non-transition-reference": owner_only_in_non_transition_record,
    }
    cases = {}
    for label, mutate in mutations.items():
        blob = bytearray(valid); mutate(blob); seal(blob); cases[label] = bytes(blob)
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blob", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("include/overworld_wild_behavior_data.h"))
    parser.add_argument("--target-validator", type=Path)
    parser.add_argument("--count", type=int, default=5000)
    args = parser.parse_args()
    valid = args.blob.read_bytes()
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        target = args.target_validator
        if target is None:
            compiler = shutil.which("clang") or shutil.which("cc")
            if compiler is None:
                raise SystemExit("no host C compiler for production-validator parity")
            target = tmp / "owbd-target-validator"
            subprocess.run([compiler, "-std=c99", "-O2", "-DOWBD_VALIDATION_TEST_ALLOW_DYNAMIC_CHECKSUM",
                            str(Path(__file__).with_name("overworld_wild_behavior_v40_target_validator.c")),
                            "-o", target], check=True)
        valid_path, projection_path = tmp / "valid.bin", tmp / "projection.bin"
        valid_path.write_bytes(valid)
        validate_v40_owbd(valid_path, args.source)
        if subprocess.run([target, valid_path], check=False).returncode != 0:
            raise SystemExit("production validator rejected valid blob")
        operator_conformance(target)
        if (subprocess.run([target, valid_path, projection_path], check=False).returncode != 0
                or projection_path.read_bytes() != expected_projection()):
            raise SystemExit("production runtime projection differs from frozen v39 source")
        for name, blob in accepted_corpus(valid).items():
            path, source = tmp / f"accepted-{name}.bin", tmp / f"accepted-{name}.h"
            path.write_bytes(blob)
            checksum = struct.unpack_from("<I", blob, CHECKSUM_OFFSET)[0]
            source.write_text(re.sub(r"(#define OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM )0x[0-9A-Fa-f]+u",
                                     rf"\g<1>0x{checksum:08X}u", args.source.read_text()))
            try:
                validate_v40_owbd(path, source)
                host_valid = True
            except (ValueError, KeyError, IndexError, struct.error):
                host_valid = False
            target_valid = subprocess.run([target, path], check=False).returncode == 0
            if not host_valid or not target_valid:
                raise SystemExit(f"validator accepted-case parity failure: {name}: host={host_valid} target={target_valid}")
        for name, blob in corpus(valid, args.count).items():
            path, source = tmp / f"{name}.bin", tmp / f"{name}.h"
            path.write_bytes(blob)
            checksum = struct.unpack_from("<I", blob, CHECKSUM_OFFSET)[0]
            source.write_text(re.sub(r"(#define OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM )0x[0-9A-Fa-f]+u",
                                     rf"\g<1>0x{checksum:08X}u", args.source.read_text()))
            try:
                validate_v40_owbd(path, source)
                host_valid = True
            except (ValueError, KeyError, IndexError, struct.error):
                host_valid = False
            target_valid = subprocess.run([target, path], check=False).returncode == 0
            if host_valid != target_valid or host_valid:
                raise SystemExit(f"validator parity failure: {name}: host={host_valid} target={target_valid}")
    print(f"validator parity: valid/projection + {len(accepted_corpus(valid))} structured variants accepted; "
          f"{args.count} deterministic malformed mutations rejected identically; "
          f"{len(OPERATOR_CASES)} typed operator executions cover all six operators")


if __name__ == "__main__":
    main()
