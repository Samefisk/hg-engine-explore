#!/usr/bin/env python3
"""Validate generated overworld-wild code-addon blob metadata."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path
from typing import Optional


OWBD_MAGIC = 0x4F574244
OWBD_HEADER_SIZE = 84
OWBD_PROFILE_SIZE = 80
OWBD_CLASS_RULE_SIZE = 16
OWBD_SPECIES_RULE_SIZE = 4
OWBD_OVERRIDE_PROFILE_SIZE = 228
OWBD_OVERRIDE_MEMBER_SIZE = 2
OWBD_CONDITION_ENTRY_SIZE = 48
OWBD_CONDITION_TERRAIN_MASK_ALLOWED = 0x03FF
OWBD_CONDITION_MOVEMENT_SPEED_MAX = 32
OWBD_CONDITION_MAX_ENTRIES = 65535
OWBD_PROFILE_KIND_NORMAL = 0
OWBD_PROFILE_KIND_CONDITIONAL = 1
OWBD_CONDITION_SUBJECT_APPLICATION_NONE = 0xFF
OWBD_CONDITION_TERRAIN_SPEED = 2
OWBD_CONDITION_TARGET_CANNOT_SEE_SUBJECT = 3
OWBD_CONDITION_ACTOR_FACTS = 4
OWBD_CONDITION_PLAYER_DAMAGED = 5
OWBD_CONDITION_SUBJECT_DAMAGED = 6
OWBD_CONDITION_PLAYER_NOTICED = 0
OWBD_CONDITION_FACT_MASK_ALLOWED = 0x3F
OWBD_CONDITION_OPTIONS_SIZE = 18
OWBD_CONDITION_WHILE_TRUE = 0
OWBD_CONDITION_TIMED = 1
OWBD_CONDITION_UNTIL_CRASH = 2
OWBD_CONDITION_TARGET_NONE = 0
OWBD_CONDITION_TARGET_PLAYER = 1
OWBD_CONDITION_TARGET_ACTOR = 2
OWBD_CONDITION_TARGET_ROLE_MASK = 0x03
OWBD_CONDITION_RANGE_VISION_CURRENT = 5
OWBD_CONDITION_RANGE_VISION_CUSTOM = 6
OWBD_VISION_OPTIONS_FORWARD_90 = 1
OWBD_VISION_OPTIONS_FORWARD_LINE = 2
OWBD_VISION_OPTIONS_CARDINAL_LINES = 3
OWBD_VISION_OPTIONS_ADJACENT_AWARENESS = 4
OWBD_VISION_OPTIONS_SAME_TILE_AWARENESS = 8
OWBD_CHILL_ACTION_OFFSET = 12
OWBD_CHILL_ACTION_FIELD_BIT = 1 << 12
OWBD_LOCOMOTION_MAX = 12
OWBD_SURFACE_MODEL_SIZE = 6
OWBD_SURFACE_INSTANCE_SIZE = 8
OWBD_SURFACE_TEMPLATE_SIZE = 2
OWBD_MASK_ALLOWED = 0x3FFFFFFF
# Cargo uses bits26/27 in v90, extra Hops28/29 in v91, Hop effects30/31 in v92.
OWBD_MASK2_ALLOWED = 0xFFFFFFFF
OWBD_CHAIN_HOP_EXTRA_HOPS_FIELD_BIT = 1 << 28
OWBD_CHAIN_HOP_EXTRA_CHANCE_FIELD_BIT = 1 << 29
OWBD_CHAIN_HOP_EXTRA_CHANCE_OFFSET = 43
OWBD_CONTROLLER_OPTIONS_OFFSET = 42
OWBD_CONTROLLER_OPTIONS_ALLOWED = 0xFF
OWBD_MASK3_ALLOWED = 0xFFFFFFFF
OWBD_RELATIVE_MASK_ALLOWED = 0x05F000F8
OWBD_RELATIVE_MASK2_ALLOWED = 0x1F8F
OWBD_RELATIVE_MASK3_ALLOWED = 0x0D40F8F3
OWBD_BOUNDED_MASK_ALLOWED = 0x01C00080
OWBD_BOUNDED_MASK2_ALLOWED = 0x1F84
OWBD_BOUNDED_MASK3_ALLOWED = 0x0D40F8F3
# Divide reuses both bound bits without relative; no record bytes are added.
OWBD_DIVIDE_MASK_ALLOWED = 0x05F000E8
OWBD_DIVIDE_MASK2_ALLOWED = 0x00001F8F
OWBD_DIVIDE_MASK3_ALLOWED = 0x0D40F8F7
# Compact data fields are stored in the same order as the mask bits.
OWBD_OPERATOR_FIELD_PROFILE_OFFSETS = tuple(
    69 if index in (70, 71) else 63 if index == 69 else 64 if index == 68
    else index if index < 34 else index + 2 if index < 52 else index + 4
    for index in range(72)
)
OWBD_OPERATOR_FIELD_MAXIMUMS = (
    0, 0, 0, 255, 64, 64, 64, 32, 64, 0, 0, 0, 0, 0, 0, 0, 100, 0, 0,
    0, 12, 12, 255, 64, 255, 0, 10, 8, 8, 32, 255, 0, 0, 0, 64, 32, 32,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 255, 32, 0, 0, 0, 8, 8, 8, 32,
    5, 0, 0, 0, 0, 0, 0, 255, 32, 32, 33, 32, 32, 0, 0,
)
OWBD_BOUNDED_FIELD_MAXIMUMS = (
    0, 0, 0, 0, 0, 0, 0, 32, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 255, 64, 255, 0, 0, 0, 0, 32, 0, 0, 0, 0, 64, 32, 32,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 255, 32, 0, 0, 0, 8, 8, 8, 32,
    5, 0, 0, 0, 0, 0, 0, 255, 32, 32, 0, 32, 32, 0, 0,
)
OWBD_OVERRIDE_PROFILE_VALUE_OFFSET = 32
OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET = 148
OWBD_ALLOWED_TERRAIN_ALL = 0x7FF
OWBD_ALLOWED_TERRAIN_VALUE_OFFSET = 32
OWBD_ALLOWED_TERRAIN_OVERRIDE_OFFSET = 34
OWBD_ALLOWED_TERRAIN_FIELD_BITS = (1 << 5) | (1 << 6)
OWBD_TILES_TO_ACCELERATE_OFFSET = 50
OWBD_MAX_WALK_SPEED_OFFSET = 51
OWBD_SPAWN_DESTINATION_VALUE_OFFSET = 52
OWBD_SPAWN_DESTINATION_OVERRIDE_OFFSET = 54
OWBD_MOVEMENT_DIRECTIONS_OFFSET = 19
OWBD_MOVEMENT_DIRECTIONS_FIELD_BIT = 1 << 19
OWBD_MOVEMENT_DIRECTIONS_MAX = 2
OWBD_TILES_TO_ACCELERATE_FIELD_BIT = 1 << 6
OWBD_MAX_WALK_SPEED_FIELD_BIT = 1 << 7
OWBD_SPAWN_DESTINATION_FIELD_BITS = (1 << 8) | (1 << 9)
OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_OFFSET = 56
OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_FIELD_BIT = 1 << 10
OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET = 57
OWBD_CHAIN_REPOSITION_JUMP_COUNT_FIELD_BIT = 1 << 11
OWBD_HOP_SWAY_WIDTH_OFFSET = 58
OWBD_HOP_SWAY_WIDTH_FIELD_BIT = 1 << 12
OWBD_SPAWN_HOP_SWAY_WIDTH_OFFSET = 59
OWBD_SPAWN_HOP_SWAY_WIDTH_FIELD_BIT = 1 << 13
OWBD_CHAIN_REPOSITION_SPEED_OFFSET = 60
OWBD_CHAIN_REPOSITION_SPEED_FIELD_BIT = 1 << 14
OWBD_CHAIN_REPOSITION_DISTANCE_OFFSET = 61
OWBD_CHAIN_REPOSITION_DISTANCE_FIELD_BIT = 1 << 15
OWBD_CHAIN_REPOSITION_DUST_OFFSET = 62
OWBD_CHAIN_REPOSITION_DUST_FIELD_BIT = 1 << 16
OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_OFFSET = 63
OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_FIELD_BIT = 1 << 17
OWBD_WALK_PAUSE_VARIANCE_OFFSET = 63
OWBD_WALK_PAUSE_VARIANCE_FIELD_BIT = 1 << 27
OWBD_WALK_PAUSE_VARIANCE_SHIFT = 1
OWBD_WALK_PAUSE_VARIANCE_MASK = 0xFE
OWBD_CHAIN_PAUSE_ACTION_OFFSET = 31
OWBD_CHAIN_PAUSE_ACTION_FIELD_BIT = 1 << 4
OWBD_CHAIN_PAUSE_ACTION_MAX = 7
OWBD_CHAIN_PAUSE_RANDOM_CHOICE = 1 << 7
OWBD_CHAIN_PAUSE_CHOICE_MASK = 0x7F
OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_OFFSET = 64
OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_FIELD_BIT = 1 << 18
OWBD_WALK_OPTIONS_OFFSET = 65
OWBD_WALK_OPTIONS_FIELD_BIT = 1 << 19
OWBD_WANDER_STRAIGHT_CHANCE_OFFSET = 66
OWBD_WANDER_STRAIGHT_CHANCE_FIELD_BIT = 1 << 20
OWBD_CHAIN_PAUSE_ACTION_CHANCE_OFFSET = 67
OWBD_CHAIN_PAUSE_ACTION_CHANCE_FIELD_BIT = 1 << 21
OWBD_WALK_PAUSE_OFFSET = 68
OWBD_WALK_PAUSE_FIELD_BIT = 1 << 22
OWBD_TILES_BEFORE_TURN_SKID_OFFSET = 69
OWBD_TILES_BEFORE_TURN_SKID_FIELD_BIT = 1 << 23
OWBD_TILES_BEFORE_TURN_SKID_MASK = 0x3F
OWBD_STOP_SKID_FIELD_BIT = 1 << 28
OWBD_STOP_SKID_MASK = 0x80
OWBD_PLAN_TURN_SKID_PATH_FIELD_BIT = 1 << 29
OWBD_PLAN_TURN_SKID_PATH_MASK = 0x40
OWBD_WALK_STOMP_TIME_OFFSET = 70
OWBD_WALK_STOMP_TIME_FIELD_BIT = 1 << 24
OWBD_WALK_ACCELERATION_STEP_OFFSET = 71
OWBD_WALK_ACCELERATION_STEP_FIELD_BIT = 1 << 25
OWBD_WALK_ACCELERATION_LINEAR_SPEED = 34
OWBD_ATTACKING_OFFSET = 72
OWBD_ATTACKING_FIELD_BIT = 1 << 15
OWBD_COLLISION_DAMAGE_OFFSET = 74
OWBD_COLLISION_DAMAGE_FIELD_BIT = 1 << 31
OWBD_ON_REACH_ACTION_OFFSET = 75
OWBD_ON_REACH_ACTION_FIELD_BIT = 1 << 16
OWBD_THROW_MAX_RANGE_OFFSET = 76
OWBD_THROW_MAX_RANGE_FIELD_BIT = 1 << 17
OWBD_THROW_WINDUP_FRAMES_OFFSET = 77
OWBD_THROW_WINDUP_FRAMES_FIELD_BIT = 1 << 18
OWBD_THROW_RECOVERY_FRAMES_OFFSET = 78
OWBD_THROW_RECOVERY_FRAMES_FIELD_BIT = 1 << 19
OWBD_KNOCKBACK_OFFSET = 79
OWBD_KNOCKBACK_TYPE_FIELD_BIT = 1 << 20
OWBD_KNOCKBACK_DISTANCE_FIELD_BIT = 1 << 21
OWBD_KNOCKBACK_TYPE_MASK = 0x03
OWBD_KNOCKBACK_DISTANCE_SHIFT = 2
OWBD_KNOCKBACK_DISTANCE_MASK = 0x1C
OWBD_WALK_TIME_VARIANCE_OFFSET = 64
OWBD_WALK_TIME_VARIANCE_FIELD_BIT = 1 << 26
OWBD_WALK_TIME_VARIANCE_SHIFT = 1
OWBD_WALK_TIME_VARIANCE_MASK = 0xFE
OWBD_WALK_SWAY_WIDTH_SHIFT = 1
OWBD_WALK_SWAY_WIDTH_MASK = 0x0E
OWBD_WALK_SWAY_WIDTH_MAX = 7
OWBD_WALK_OPTIONS_RESERVED_MASK = 0x00
OWBD_WALK_CRASH_SOUND_MASK = 0x10
OWBD_WALK_CRASH_SOUND_SHIFT = 4
OWBD_WALK_FACING_MASK = 0xC0
OWBD_SPAWN_DESTINATION_OFFSET = 17
OWBD_SPAWN_DESTINATION_MAX = 20
OWBD_SURFACE_TYPE_FLOWERBED = 3
OWBD_SURFACE_TYPE_CANOPY = 4
OWBD_SURFACE_TYPE_COUNT = 5
OWBD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND = 0x1F
OWBD_SURFACE_CANOPY_HEIGHT_OFFSET_Q4 = 0x3158


def owbd_operator_field_value(blob: bytes, profile_base: int, field_index: int,
                              version: int = 0) -> int:
    value = blob[profile_base + OWBD_OPERATOR_FIELD_PROFILE_OFFSETS[field_index]]
    if version >= 91 and field_index == 53:
        return value & 0x0F
    if field_index in (59, 60):
        return value & 1
    if field_index == 68:
        return (value & OWBD_WALK_TIME_VARIANCE_MASK) >> OWBD_WALK_TIME_VARIANCE_SHIFT
    if field_index == 69:
        return (value & OWBD_WALK_PAUSE_VARIANCE_MASK) >> OWBD_WALK_PAUSE_VARIANCE_SHIFT
    if field_index == 65:
        return value & OWBD_TILES_BEFORE_TURN_SKID_MASK
    if field_index == 70:
        return 1 if value & OWBD_STOP_SKID_MASK else 0
    if field_index == 71:
        return 1 if value & OWBD_PLAN_TURN_SKID_PATH_MASK else 0
    return value

OWED_MAGIC = 0x4F574544
OWED_VERSION = 2
OWED_HEADER_SIZE = 32
OWED_DIRECTORY_ENTRY_SIZE = 12
OWED_SECTION_MASK_ALL = 0xFF

ENCOUNTER_DATA_SIZE = 196
SPECIES_MASK = 0x7FF
OWED_CHECKSUM_OFFSET = 24

OWED_SECTIONS = (
    (1 << 0, 8, 12),
    (1 << 1, 20, 24),
    (1 << 2, 44, 24),
    (1 << 3, 68, 24),
    (1 << 4, 100, 20),
    (1 << 5, 128, 20),
    (1 << 6, 148, 20),
    (1 << 7, 168, 20),
)

DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\b", re.MULTILINE)
INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def valid_on_reach_options(value: int, version: int) -> bool:
    # v92 keeps pickup in bit0 and a separate four-choice cry chance in6..7.
    return value & 0x3E == 0 if version >= 92 else value <= 1


def valid_chain_pause_action(value: int) -> bool:
    return value <= OWBD_CHAIN_PAUSE_ACTION_MAX or (
        value & OWBD_CHAIN_PAUSE_RANDOM_CHOICE != 0
        and value & OWBD_CHAIN_PAUSE_CHOICE_MASK != 0
    )


def read_define(source: Path, symbol: str) -> int:
    definitions: dict[str, str] = {}
    visited: set[Path] = set()

    def collect(path: Path) -> None:
        path = path.resolve()
        if path in visited or not path.exists():
            return
        visited.add(path)
        text = path.read_text()
        definitions.update(DEFINE_RE.findall(text))
        for include in INCLUDE_RE.findall(text):
            collect(path.parent / include)

    def resolve(name: str, resolving: set[str]) -> int:
        require(name in definitions, f"{source}: could not find #define {name}")
        require(name not in resolving, f"{source}: recursive #define {name}")
        value = definitions[name]
        if value.isdigit():
            return int(value, 10)
        return resolve(value, resolving | {name})

    collect(source)
    return resolve(symbol, set())


def range_end(path: Path, name: str, offset: int, count: int, element_size: int, blob_size: int, alignment: int, minimum_offset: int) -> int:
    require(element_size != 0, f"{path}: {name} has zero element size")
    require(offset >= minimum_offset, f"{path}: {name} starts before payload")
    require(offset % alignment == 0, f"{path}: {name} has bad alignment")
    size = count * element_size
    require(offset <= blob_size and size <= blob_size - offset, f"{path}: {name} extends past blob size")
    return offset + size


def narc_member_count(path: Path) -> int:
    blob = path.read_bytes()
    fat_offset = blob.find(b"BTAF")
    require(fat_offset >= 0 and fat_offset + 12 <= len(blob), f"{path}: missing BTAF chunk")
    return struct.unpack_from("<I", blob, fat_offset + 8)[0]


def read_narc_members(path: Path) -> list[bytes]:
    blob = path.read_bytes()
    fat_offset = blob.find(b"BTAF")
    require(fat_offset >= 0 and fat_offset + 12 <= len(blob), f"{path}: missing BTAF chunk")
    member_count = struct.unpack_from("<I", blob, fat_offset + 8)[0]
    entries_offset = fat_offset + 12
    require(entries_offset + member_count * 8 <= len(blob), f"{path}: truncated FAT entries")

    data_offset = blob.find(b"GMIF")
    require(data_offset >= 0 and data_offset + 8 <= len(blob), f"{path}: missing GMIF chunk")
    data_start = data_offset + 8
    members = []
    for member_index in range(member_count):
        start, end = struct.unpack_from("<II", blob, entries_offset + member_index * 8)
        require(start <= end and data_start + end <= len(blob), f"{path}: bad FAT range for member {member_index}")
        members.append(blob[data_start + start:data_start + end])
    return members


def owed_checksum(blob: bytes) -> int:
    scratch = bytearray(blob)
    struct.pack_into("<I", scratch, OWED_CHECKSUM_OFFSET, 0)
    return sum(scratch) & 0xFFFFFFFF


def owed_any_species(slots: bytes) -> bool:
    require(len(slots) % 2 == 0, "OWED species table has odd byte length")
    for offset in range(0, len(slots), 2):
        species = struct.unpack_from("<H", slots, offset)[0] & SPECIES_MASK
        if species != 0:
            return True
    return False


def owed_any_slot_species(slots: bytes) -> bool:
    require(len(slots) % 4 == 0, "OWED slot table has odd byte length")
    for offset in range(0, len(slots), 4):
        species = struct.unpack_from("<H", slots, offset + 2)[0] & SPECIES_MASK
        if species != 0:
            return True
    return False


def owed_section_is_present(data: bytes, mask: int, offset: int, size: int, land_has_species: bool) -> bool:
    section = data[offset:offset + size]
    if not any(section):
        return False
    if mask == 1:
        return land_has_species
    if mask in (2, 4, 8):
        return owed_any_species(section)
    return owed_any_slot_species(section)


def encode_sparse_record(data: bytes) -> bytes:
    require(len(data) >= ENCOUNTER_DATA_SIZE, "encounter member is smaller than expected")
    data = data[:ENCOUNTER_DATA_SIZE]
    land_has_species = (
        owed_any_species(data[20:44])
        or owed_any_species(data[44:68])
        or owed_any_species(data[68:92])
    )
    section_mask = 0
    payload = bytearray()
    for mask, offset, size in OWED_SECTIONS:
        if owed_section_is_present(data, mask, offset, size, land_has_species):
            section_mask |= mask
            payload.extend(data[offset:offset + size])
    return bytes((data[3], data[4], data[5], section_mask)) + bytes(payload)


def decode_sparse_record(path: Path, record: bytes) -> bytes:
    require(len(record) >= 4, f"{path}: OWED record is smaller than header")
    section_mask = record[3]
    require((section_mask & ~OWED_SECTION_MASK_ALL) == 0, f"{path}: OWED record has invalid section mask")
    decoded = bytearray(ENCOUNTER_DATA_SIZE)
    decoded[3] = record[0]
    decoded[4] = record[1]
    decoded[5] = record[2]

    record_offset = 4
    for mask, target_offset, size in OWED_SECTIONS:
        if (section_mask & mask) == 0:
            continue
        require(record_offset + size <= len(record), f"{path}: OWED record section extends past payload")
        decoded[target_offset:target_offset + size] = record[record_offset:record_offset + size]
        record_offset += size

    require(record_offset == len(record), f"{path}: OWED record has trailing bytes")
    return bytes(decoded)


def validate_owbd(path: Path, source: Path) -> None:
    blob = path.read_bytes()
    expected_version = read_define(source, "OVERWORLD_WILD_BEHAVIOR_DATA_VERSION")
    expected_class_profile_count = read_define(source, "OWBD_CLASS_PROFILE_COUNT")
    expected_class_rule_count = read_define(source, "OWBD_CLASS_RULE_COUNT")
    expected_species_rule_count = read_define(source, "OWBD_SPECIES_CLASS_RULE_COUNT")
    expected_override_profile_count = read_define(source, "OWBD_OVERRIDE_PROFILE_COUNT")
    expected_override_member_count = read_define(source, "OWBD_OVERRIDE_MEMBER_COUNT")
    expected_condition_entry_count = read_define(source, "OWBD_CONDITION_ENTRY_COUNT")
    expected_surface_model_count = read_define(source, "OWBD_SURFACE_MODEL_COUNT")
    expected_surface_instance_count = read_define(source, "OWBD_SURFACE_INSTANCE_COUNT")
    expected_surface_template_count = read_define(source, "OWBD_SURFACE_TEMPLATE_COUNT")
    require(len(blob) >= OWBD_HEADER_SIZE, f"{path}: truncated OWBD header")
    fields = struct.unpack_from(
        "<IHHI IHH IHH IHH IHH IHH IHH IHH IHH IHH",
        blob,
        0,
    )
    (
        magic,
        version,
        header_size,
        blob_size,
        class_profiles_offset,
        class_profile_count,
        class_profile_size,
        class_rules_offset,
        class_rule_count,
        class_rule_size,
        species_rules_offset,
        species_rule_count,
        species_rule_size,
        override_profiles_offset,
        override_profile_count,
        override_profile_size,
        override_members_offset,
        override_member_count,
        override_member_size,
        condition_entries_offset,
        condition_entry_count,
        condition_entry_size,
        surface_models_offset,
        surface_model_count,
        surface_model_size,
        surface_instances_offset,
        surface_instance_count,
        surface_instance_size,
        surface_templates_offset,
        surface_template_count,
        surface_template_size,
    ) = fields

    require(magic == OWBD_MAGIC, f"{path}: bad OWBD magic")
    require(version == expected_version, f"{path}: bad OWBD version")
    require(header_size == OWBD_HEADER_SIZE, f"{path}: bad OWBD header size")
    require(blob_size == len(blob), f"{path}: OWBD blob size does not match file size")
    require(class_profile_count == expected_class_profile_count, f"{path}: bad class profile count")
    require(class_rule_count == expected_class_rule_count, f"{path}: bad class rule count")
    require(species_rule_count == expected_species_rule_count, f"{path}: bad species class rule count")
    require(override_profile_count == expected_override_profile_count, f"{path}: bad override profile count")
    require(override_member_count == expected_override_member_count, f"{path}: bad override member count")
    require(condition_entry_count == expected_condition_entry_count, f"{path}: bad condition entry count")
    require(condition_entry_count <= OWBD_CONDITION_MAX_ENTRIES, f"{path}: too many condition entries")
    require(surface_model_count == expected_surface_model_count, f"{path}: bad surface model count")
    require(surface_instance_count == expected_surface_instance_count, f"{path}: bad surface instance count")
    require(surface_template_count == expected_surface_template_count, f"{path}: bad surface template count")
    require(surface_template_count <= 256, f"{path}: surface templates exceed byte-addressable range")
    require(class_profile_size == OWBD_PROFILE_SIZE, f"{path}: bad class profile element size")
    require(class_rule_size == OWBD_CLASS_RULE_SIZE, f"{path}: bad class rule element size")
    require(species_rule_size == OWBD_SPECIES_RULE_SIZE, f"{path}: bad species class rule element size")
    require(override_profile_size == OWBD_OVERRIDE_PROFILE_SIZE, f"{path}: bad override profile element size")
    require(override_member_size == OWBD_OVERRIDE_MEMBER_SIZE, f"{path}: bad override member element size")
    require(condition_entry_size == OWBD_CONDITION_ENTRY_SIZE, f"{path}: bad condition entry element size")
    require(surface_model_size == OWBD_SURFACE_MODEL_SIZE, f"{path}: bad surface model element size")
    require(surface_instance_size == OWBD_SURFACE_INSTANCE_SIZE, f"{path}: bad surface instance element size")
    require(surface_template_size == OWBD_SURFACE_TEMPLATE_SIZE, f"{path}: bad surface template element size")

    class_profiles_end = range_end(path, "classProfiles", class_profiles_offset, class_profile_count, class_profile_size, blob_size, 2, header_size)
    class_rules_end = range_end(path, "classRules", class_rules_offset, class_rule_count, class_rule_size, blob_size, 4, class_profiles_end)
    species_rules_end = range_end(path, "speciesClassRules", species_rules_offset, species_rule_count, species_rule_size, blob_size, 2, class_rules_end)
    override_profiles_end = range_end(path, "overrideProfiles", override_profiles_offset, override_profile_count, override_profile_size, blob_size, 4, species_rules_end)
    for index in range(class_profile_count):
        profile_offset = class_profiles_offset + index * class_profile_size
        if version >= 89:
            require(blob[profile_offset + OWBD_CONTROLLER_OPTIONS_OFFSET]
                    & ~(OWBD_CONTROLLER_OPTIONS_ALLOWED if version >= 90 else 0x03) == 0,
                    f"{path}: class profile {index} has undefined controller-option bits")
        if version >= 90:
            require((blob[profile_offset + OWBD_CONTROLLER_OPTIONS_OFFSET] >> 2) & 15 != 0,
                    f"{path}: class profile {index} Cargo target check interval must be 1..15")
        require(blob[profile_offset + 8] <= 127,
                f"{path}: class profile {index} one-turn skid time must be 0..127")
        require(
            blob[profile_offset + OWBD_ATTACKING_OFFSET] <= 1
            and blob[profile_offset + OWBD_COLLISION_DAMAGE_OFFSET] <= 50
            and (blob[profile_offset + OWBD_KNOCKBACK_OFFSET]
                 & OWBD_KNOCKBACK_TYPE_MASK) <= 2
            and 1 <= (blob[profile_offset + OWBD_KNOCKBACK_OFFSET]
                      & OWBD_KNOCKBACK_DISTANCE_MASK)
                      >> OWBD_KNOCKBACK_DISTANCE_SHIFT <= 7,
            f"{path}: class profile {index} has an invalid collision attack",
        )
        require(
            blob[profile_offset + OWBD_CHILL_ACTION_OFFSET] <= OWBD_LOCOMOTION_MAX,
            f"{path}: class profile {index} has an invalid locomotion",
        )
        require(
            valid_on_reach_options(blob[profile_offset + OWBD_ON_REACH_ACTION_OFFSET], version)
            and 1 <= blob[profile_offset + OWBD_THROW_MAX_RANGE_OFFSET] <= 8,
            f"{path}: class profile {index} has invalid throw settings",
        )
        require(
            blob[profile_offset + OWBD_MOVEMENT_DIRECTIONS_OFFSET]
                <= OWBD_MOVEMENT_DIRECTIONS_MAX,
            f"{path}: class profile {index} has an invalid movement-direction mode",
        )
        require(
            1 <= blob[profile_offset + 15] <= 0xF,
            f"{path}: class profile {index} Next-to-player side mask must be between 1 and 15",
        )
        require(
            1 <= blob[profile_offset + 7] <= 32,
            f"{path}: class profile {index} Chill Walk time must be between 1 and 32 frames",
        )
        require(
            1 <= blob[profile_offset + OWBD_TILES_TO_ACCELERATE_OFFSET] <= 255,
            f"{path}: class profile {index} acceleration interval must be between 1 and 255",
        )
        require(
            1 <= blob[profile_offset + OWBD_MAX_WALK_SPEED_OFFSET] <= 32,
            f"{path}: class profile {index} fastest Walk time must be between 1 and 32 frames",
        )
        require(
            blob[profile_offset + OWBD_MAX_WALK_SPEED_OFFSET] <= blob[profile_offset + 7],
            f"{path}: class profile {index} fastest Walk time is slower than its base Walk time",
        )
        require(
            blob[profile_offset + OWBD_SPAWN_DESTINATION_OFFSET] <= OWBD_SPAWN_DESTINATION_MAX,
            f"{path}: class profile {index} has an invalid spawn destination",
        )
        require(
            (blob[profile_offset + OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_OFFSET] & 1) <= 1,
            f"{path}: class profile {index} has an invalid vertical-obstacle hop policy",
        )
        require(
            1 <= (blob[profile_offset + OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET]
                  & (0x0F if version >= 91 else 0xFF)) <= 8,
            f"{path}: class profile {index} reposition-jump count must be between 1 and 8",
        )
        if version >= 91:
            packed_count = blob[profile_offset + OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET]
            require((version >= 92 or packed_count & 0xC0 == 0)
                    and (packed_count >> 4) & 3 <= 2,
                    f"{path}: class profile {index} extra in-place Hops must be 0..2")
            require(blob[profile_offset + OWBD_CHAIN_HOP_EXTRA_CHANCE_OFFSET] >> 1 <= 100,
                    f"{path}: class profile {index} extra in-place Hop chance must be 0..100")
        require(
            blob[profile_offset + OWBD_HOP_SWAY_WIDTH_OFFSET] <= 8,
            f"{path}: class profile {index} horizontal sway must be between 0 and 8",
        )
        require(
            blob[profile_offset + OWBD_SPAWN_HOP_SWAY_WIDTH_OFFSET] <= 8,
            f"{path}: class profile {index} spawn horizontal sway must be between 0 and 8",
        )
        require(
            1 <= blob[profile_offset + OWBD_CHAIN_REPOSITION_SPEED_OFFSET] <= 32,
            f"{path}: class profile {index} reposition Walk time must be between 1 and 32 frames",
        )
        require(
            1 <= blob[profile_offset + OWBD_CHAIN_REPOSITION_DISTANCE_OFFSET] <= 5,
            f"{path}: class profile {index} reposition distance must be between 1 and 5",
        )
        for option_offset, option_name in (
            (OWBD_CHAIN_REPOSITION_DUST_OFFSET, "dust"),
            (OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_OFFSET, "cardinal-direction"),
            (OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_OFFSET, "diagonal-direction"),
        ):
            option_value = blob[profile_offset + option_offset]
            if option_offset in (
                OWBD_CHAIN_REPOSITION_DUST_OFFSET,
                OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_OFFSET,
                OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_OFFSET,
            ):
                option_value &= 1
            require(
                option_value <= 1,
                f"{path}: class profile {index} has an invalid reposition {option_name} option",
            )
        walk_options = blob[profile_offset + OWBD_WALK_OPTIONS_OFFSET]
        require(
            (walk_options & OWBD_WALK_OPTIONS_RESERVED_MASK) == 0
            and ((walk_options & OWBD_WALK_SWAY_WIDTH_MASK)
                 >> OWBD_WALK_SWAY_WIDTH_SHIFT) <= OWBD_WALK_SWAY_WIDTH_MAX
            and ((walk_options & OWBD_WALK_CRASH_SOUND_MASK)
                 >> OWBD_WALK_CRASH_SOUND_SHIFT) <= 1
            and (walk_options & OWBD_WALK_FACING_MASK) != OWBD_WALK_FACING_MASK,
            f"{path}: class profile {index} has invalid Walk options",
        )
        require(
            (blob[profile_offset + OWBD_TILES_BEFORE_TURN_SKID_OFFSET]
             & OWBD_TILES_BEFORE_TURN_SKID_MASK) <= 32,
            f"{path}: class profile {index} turn-skid buildup must be between 0 and 32",
        )
        require(
            blob[profile_offset + OWBD_WALK_STOMP_TIME_OFFSET] <= 32,
            f"{path}: class profile {index} stomp time must be 0 (off) or 1..32 frames",
        )
        require(
            blob[profile_offset + OWBD_WALK_ACCELERATION_STEP_OFFSET]
                <= OWBD_WALK_ACCELERATION_LINEAR_SPEED,
            f"{path}: class profile {index} acceleration must be 0 (none), 1..32 frames, 33 (/2), or 34 (Linear speed)",
        )
        require(
            (blob[profile_offset + OWBD_WALK_TIME_VARIANCE_OFFSET]
             & OWBD_WALK_TIME_VARIANCE_MASK) >> OWBD_WALK_TIME_VARIANCE_SHIFT <= 32,
            f"{path}: class profile {index} Walk time variance must be between 0 and 32 frames",
        )
        require(
            (blob[profile_offset + OWBD_WALK_PAUSE_VARIANCE_OFFSET]
             & OWBD_WALK_PAUSE_VARIANCE_MASK) >> OWBD_WALK_PAUSE_VARIANCE_SHIFT <= 32,
            f"{path}: class profile {index} Walk pause variance must be between 0 and 32 frames",
        )
        require(
            valid_chain_pause_action(
                blob[profile_offset + OWBD_CHAIN_PAUSE_ACTION_OFFSET]
            ),
            f"{path}: class profile {index} chain pause action is invalid",
        )
        require(
            (struct.unpack_from("<H", blob, profile_offset + OWBD_ALLOWED_TERRAIN_VALUE_OFFSET)[0]
             | struct.unpack_from("<H", blob, profile_offset + OWBD_ALLOWED_TERRAIN_OVERRIDE_OFFSET)[0])
            & ~OWBD_ALLOWED_TERRAIN_ALL == 0,
            f"{path}: class profile {index} has undefined terrain-policy bits",
        )
        require(
            (struct.unpack_from("<H", blob, profile_offset + OWBD_SPAWN_DESTINATION_VALUE_OFFSET)[0]
             | struct.unpack_from("<H", blob, profile_offset + OWBD_SPAWN_DESTINATION_OVERRIDE_OFFSET)[0])
            & ~OWBD_ALLOWED_TERRAIN_ALL == 0,
            f"{path}: class profile {index} has undefined spawn-destination-policy bits",
        )
    profile_condition_slices = []
    for index in range(override_profile_count):
        profile_offset = override_profiles_offset + index * override_profile_size
        profile_kind, condition_start, condition_count = struct.unpack_from(
            "<BBB",
            blob,
            profile_offset + 17,
        )
        require(
            profile_kind in (OWBD_PROFILE_KIND_NORMAL, OWBD_PROFILE_KIND_CONDITIONAL),
            f"{path}: override profile {index} has an invalid profile kind",
        )
        require(
            condition_start <= condition_entry_count
            and condition_count <= condition_entry_count - condition_start,
            f"{path}: override profile {index} condition slice is out of range",
        )
        if profile_kind == OWBD_PROFILE_KIND_NORMAL:
            require(
                condition_count == 0,
                f"{path}: normal override profile {index} owns conditions",
            )
        else:
            require(
                condition_count != 0,
                f"{path}: conditional override profile {index} has no conditions",
            )
        profile_condition_slices.append(
            (profile_kind, condition_start, condition_count)
        )
        mask, mask2, mask3 = struct.unpack_from("<III", blob, profile_offset + 20)
        if version >= 92:
            for value_offset in (OWBD_OVERRIDE_PROFILE_VALUE_OFFSET, OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET):
                require(valid_on_reach_options(blob[profile_offset + value_offset
                        + OWBD_ON_REACH_ACTION_OFFSET], version),
                        f"{path}: override profile {index} has undefined on-reach option bits")
        if version >= 89:
            for value_offset in (OWBD_OVERRIDE_PROFILE_VALUE_OFFSET, OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET):
                require(blob[profile_offset + value_offset + OWBD_CONTROLLER_OPTIONS_OFFSET]
                        & ~(OWBD_CONTROLLER_OPTIONS_ALLOWED if version >= 90 else 0x03) == 0,
                        f"{path}: override profile {index} has undefined controller-option bits")
        if version >= 90 and mask2 & (1 << 26):
            require((blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                          + OWBD_CONTROLLER_OPTIONS_OFFSET] >> 2) & 15 != 0,
                    f"{path}: override profile {index} Cargo target check interval must be 1..15")
        if mask2 & OWBD_ATTACKING_FIELD_BIT:
            require(
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_ATTACKING_OFFSET] <= 1,
                f"{path}: override profile {index} has an invalid attacking value",
            )
        if mask2 & OWBD_KNOCKBACK_TYPE_FIELD_BIT:
            require(
                (blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_KNOCKBACK_OFFSET] & OWBD_KNOCKBACK_TYPE_MASK) <= 2,
                f"{path}: override profile {index} has an invalid knockback type",
            )
        if mask2 & OWBD_KNOCKBACK_DISTANCE_FIELD_BIT:
            require(
                1 <= (blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_KNOCKBACK_OFFSET] & OWBD_KNOCKBACK_DISTANCE_MASK)
                    >> OWBD_KNOCKBACK_DISTANCE_SHIFT <= 7,
                f"{path}: override profile {index} has an invalid knockback distance",
            )
        if mask3 & OWBD_COLLISION_DAMAGE_FIELD_BIT:
            require(
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_COLLISION_DAMAGE_OFFSET] <= 50,
                f"{path}: override profile {index} has invalid collision damage",
            )
        require(blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + 8] <= 127,
                f"{path}: override profile {index} one-turn skid time must be 0..127")
        relative_mask, relative_mask2, relative_mask3 = struct.unpack_from("<III", blob, profile_offset + 112)
        at_least_mask, at_least_mask2, at_least_mask3 = struct.unpack_from("<III", blob, profile_offset + 124)
        at_most_mask, at_most_mask2, at_most_mask3 = struct.unpack_from("<III", blob, profile_offset + 136)
        divide_masks = tuple(a & b for a, b in zip(
            (at_least_mask, at_least_mask2, at_least_mask3),
            (at_most_mask, at_most_mask2, at_most_mask3)))
        operator_mask = relative_mask | at_least_mask | at_most_mask
        if mask & OWBD_CHILL_ACTION_FIELD_BIT:
            require(
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_CHILL_ACTION_OFFSET]
                    <= OWBD_LOCOMOTION_MAX,
                f"{path}: override profile {index} exact locomotion is invalid",
            )
        if mask & OWBD_MOVEMENT_DIRECTIONS_FIELD_BIT:
            require(
                blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_MOVEMENT_DIRECTIONS_OFFSET
                ] <= OWBD_MOVEMENT_DIRECTIONS_MAX,
                f"{path}: override profile {index} has an invalid movement-direction mode",
            )
        if (mask & (1 << 7)) and not (operator_mask & (1 << 7)):
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + 7] <= 32,
                f"{path}: override profile {index} exact Chill Walk time must be between 1 and 32 frames",
            )
        if mask & (1 << 15):
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + 15] <= 0xF,
                f"{path}: override profile {index} Next-to-player side mask must be between 1 and 15",
            )
        operator_mask3 = relative_mask3 | at_least_mask3 | at_most_mask3
        if mask3 & OWBD_TILES_TO_ACCELERATE_FIELD_BIT \
                and not operator_mask3 & OWBD_TILES_TO_ACCELERATE_FIELD_BIT:
            # This byte can inherit Linear speed from another profile. Validate
            # its stored frame range; the resolver still clamps legacy tiles.
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_TILES_TO_ACCELERATE_OFFSET] <= 255,
                f"{path}: override profile {index} exact acceleration interval must be between 1 and 255",
            )
        if mask3 & OWBD_MAX_WALK_SPEED_FIELD_BIT \
                and not operator_mask3 & OWBD_MAX_WALK_SPEED_FIELD_BIT:
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_MAX_WALK_SPEED_OFFSET] <= 32,
                f"{path}: override profile {index} exact fastest Walk time must be between 1 and 32 frames",
            )
        if mask & (1 << OWBD_SPAWN_DESTINATION_OFFSET):
            require(
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_SPAWN_DESTINATION_OFFSET]
                <= OWBD_SPAWN_DESTINATION_MAX,
                f"{path}: override profile {index} has an invalid spawn destination",
            )
        require((mask & ~OWBD_MASK_ALLOWED) == 0, f"{path}: override profile {index} mask has undefined bits")
        allowed_mask2 = (OWBD_MASK2_ALLOWED if version >= 92 else 0x3FFFFFFF
                         if version >= 91 else 0xFFFFFFF
                         if version >= 90 else 0x3FFFFFF if version >= 89 else 0x1FFFFFF)
        require((mask2 & ~allowed_mask2) == 0, f"{path}: override profile {index} mask2 has undefined bits")
        if version >= 91 and mask2 & OWBD_CHAIN_HOP_EXTRA_HOPS_FIELD_BIT:
            require((blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                          + OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET] >> 4) & 3 <= 2,
                    f"{path}: override profile {index} extra in-place Hops must be 0..2")
        if version >= 91 and mask2 & OWBD_CHAIN_HOP_EXTRA_CHANCE_FIELD_BIT:
            require(blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                         + OWBD_CHAIN_HOP_EXTRA_CHANCE_OFFSET] >> 1 <= 100,
                    f"{path}: override profile {index} extra in-place Hop chance must be 0..100")
        if mask2 & OWBD_ON_REACH_ACTION_FIELD_BIT:
            require(
                valid_on_reach_options(blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_ON_REACH_ACTION_OFFSET], version),
                f"{path}: override profile {index} has an invalid on-reach action",
            )
        if mask2 & OWBD_THROW_MAX_RANGE_FIELD_BIT:
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_THROW_MAX_RANGE_OFFSET] <= 8,
                f"{path}: override profile {index} has an invalid throw range",
            )
        if mask2 & OWBD_CHAIN_PAUSE_ACTION_FIELD_BIT:
            require(
                valid_chain_pause_action(blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_CHAIN_PAUSE_ACTION_OFFSET
                ]),
                f"{path}: override profile {index} chain pause action is invalid",
            )
        require(
            (mask2 & OWBD_ALLOWED_TERRAIN_FIELD_BITS) in (0, OWBD_ALLOWED_TERRAIN_FIELD_BITS),
            f"{path}: override profile {index} must update both terrain-policy fields together",
        )
        require(
            (struct.unpack_from("<H", blob, profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_ALLOWED_TERRAIN_VALUE_OFFSET)[0]
             | struct.unpack_from("<H", blob, profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_ALLOWED_TERRAIN_OVERRIDE_OFFSET)[0])
            & ~OWBD_ALLOWED_TERRAIN_ALL == 0,
            f"{path}: override profile {index} has undefined terrain-policy bits",
        )
        require((mask3 & ~OWBD_MASK3_ALLOWED) == 0, f"{path}: override profile {index} mask3 has undefined bits")
        if mask3 & OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_FIELD_BIT:
            require(
                (blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_OFFSET] & 1) <= 1,
                f"{path}: override profile {index} has an invalid vertical-obstacle hop policy",
            )
        if mask3 & OWBD_CHAIN_REPOSITION_JUMP_COUNT_FIELD_BIT \
                and not operator_mask3 & OWBD_CHAIN_REPOSITION_JUMP_COUNT_FIELD_BIT:
            require(
                1 <= (blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                           + OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET]
                      & (0x0F if version >= 91 else 0xFF)) <= 8,
                f"{path}: override profile {index} exact reposition-jump count must be between 1 and 8",
            )
        if mask3 & OWBD_HOP_SWAY_WIDTH_FIELD_BIT \
                and not operator_mask3 & OWBD_HOP_SWAY_WIDTH_FIELD_BIT:
            require(
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_HOP_SWAY_WIDTH_OFFSET] <= 8,
                f"{path}: override profile {index} exact horizontal sway must be between 0 and 8",
            )
        if mask3 & OWBD_SPAWN_HOP_SWAY_WIDTH_FIELD_BIT \
                and not operator_mask3 & OWBD_SPAWN_HOP_SWAY_WIDTH_FIELD_BIT:
            require(
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_SPAWN_HOP_SWAY_WIDTH_OFFSET] <= 8,
                f"{path}: override profile {index} exact spawn horizontal sway must be between 0 and 8",
            )
        if mask3 & OWBD_CHAIN_REPOSITION_SPEED_FIELD_BIT \
                and not operator_mask3 & OWBD_CHAIN_REPOSITION_SPEED_FIELD_BIT:
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_CHAIN_REPOSITION_SPEED_OFFSET] <= 32,
                f"{path}: override profile {index} exact reposition Walk time must be between 1 and 32 frames",
            )
        if mask3 & OWBD_CHAIN_REPOSITION_DISTANCE_FIELD_BIT \
                and not operator_mask3 & OWBD_CHAIN_REPOSITION_DISTANCE_FIELD_BIT:
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_CHAIN_REPOSITION_DISTANCE_OFFSET] <= 5,
                f"{path}: override profile {index} exact reposition distance must be between 1 and 5",
            )
        if mask3 & OWBD_WALK_OPTIONS_FIELD_BIT:
            walk_options = blob[
                profile_offset
                + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                + OWBD_WALK_OPTIONS_OFFSET
            ]
            require(
                (walk_options & OWBD_WALK_OPTIONS_RESERVED_MASK) == 0
                and ((walk_options & OWBD_WALK_SWAY_WIDTH_MASK)
                     >> OWBD_WALK_SWAY_WIDTH_SHIFT) <= OWBD_WALK_SWAY_WIDTH_MAX
                and ((walk_options & OWBD_WALK_CRASH_SOUND_MASK)
                     >> OWBD_WALK_CRASH_SOUND_SHIFT) <= 1
                and (walk_options & OWBD_WALK_FACING_MASK) != OWBD_WALK_FACING_MASK,
                f"{path}: override profile {index} has invalid Walk options",
            )
        if mask3 & OWBD_TILES_BEFORE_TURN_SKID_FIELD_BIT \
                and not operator_mask3 & OWBD_TILES_BEFORE_TURN_SKID_FIELD_BIT:
            require(
                (blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_TILES_BEFORE_TURN_SKID_OFFSET
                ] & OWBD_TILES_BEFORE_TURN_SKID_MASK) <= 32,
                f"{path}: override profile {index} turn-skid buildup must be between 0 and 32",
            )
        if mask3 & OWBD_WALK_STOMP_TIME_FIELD_BIT \
                and not operator_mask3 & OWBD_WALK_STOMP_TIME_FIELD_BIT:
            require(
                blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_WALK_STOMP_TIME_OFFSET
                ] <= 32,
                f"{path}: override profile {index} exact stomp time must be 0 (off) or 1..32 frames",
            )
        if mask3 & OWBD_WALK_ACCELERATION_STEP_FIELD_BIT:
            maximum = 33 if operator_mask3 & OWBD_WALK_ACCELERATION_STEP_FIELD_BIT \
                else OWBD_WALK_ACCELERATION_LINEAR_SPEED
            require(
                blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_WALK_ACCELERATION_STEP_OFFSET
                ] <= maximum,
                f"{path}: override profile {index} acceleration exceeds {maximum}; Linear speed (34) requires an exact replacement",
            )
        if mask3 & OWBD_WALK_TIME_VARIANCE_FIELD_BIT \
                and not operator_mask3 & OWBD_WALK_TIME_VARIANCE_FIELD_BIT:
            require(
                ((blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_WALK_TIME_VARIANCE_OFFSET
                ] & OWBD_WALK_TIME_VARIANCE_MASK)
                 >> OWBD_WALK_TIME_VARIANCE_SHIFT) <= 32,
                f"{path}: override profile {index} exact Walk time variance must be between 0 and 32 frames",
            )
        if mask3 & OWBD_WALK_PAUSE_VARIANCE_FIELD_BIT \
                and not operator_mask3 & OWBD_WALK_PAUSE_VARIANCE_FIELD_BIT:
            require(
                ((blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_WALK_PAUSE_VARIANCE_OFFSET
                ] & OWBD_WALK_PAUSE_VARIANCE_MASK)
                 >> OWBD_WALK_PAUSE_VARIANCE_SHIFT) <= 32,
                f"{path}: override profile {index} exact Walk pause variance must be between 0 and 32 frames",
            )
        for chance_bit, chance_offset, chance_name in (
            (OWBD_WANDER_STRAIGHT_CHANCE_FIELD_BIT, OWBD_WANDER_STRAIGHT_CHANCE_OFFSET, "Wander straight"),
            (OWBD_CHAIN_PAUSE_ACTION_CHANCE_FIELD_BIT, OWBD_CHAIN_PAUSE_ACTION_CHANCE_OFFSET, "chain pause action"),
        ):
            if mask3 & chance_bit and not operator_mask3 & chance_bit:
                require(
                    blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + chance_offset] <= 100,
                    f"{path}: override profile {index} {chance_name} chance must be between 0 and 100",
                )
        for option_bit, option_offset, option_name in (
            (OWBD_CHAIN_REPOSITION_DUST_FIELD_BIT, OWBD_CHAIN_REPOSITION_DUST_OFFSET, "dust"),
            (OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_FIELD_BIT, OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_OFFSET, "cardinal-direction"),
            (OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_FIELD_BIT, OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_OFFSET, "diagonal-direction"),
        ):
            if mask3 & option_bit:
                option_value = blob[
                    profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + option_offset
                ]
                if option_bit in (
                    OWBD_CHAIN_REPOSITION_ALLOW_CARDINAL_FIELD_BIT,
                    OWBD_CHAIN_REPOSITION_ALLOW_DIAGONAL_FIELD_BIT,
                ):
                    option_value &= 1
                require(
                    option_value <= 1,
                    f"{path}: override profile {index} has an invalid reposition {option_name} option",
                )
        require(
            (mask3 & OWBD_SPAWN_DESTINATION_FIELD_BITS) in (0, OWBD_SPAWN_DESTINATION_FIELD_BITS),
            f"{path}: override profile {index} must update both spawn-destination-policy fields together",
        )
        require(
            (struct.unpack_from("<H", blob, profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_SPAWN_DESTINATION_VALUE_OFFSET)[0]
             | struct.unpack_from("<H", blob, profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_SPAWN_DESTINATION_OVERRIDE_OFFSET)[0])
            & ~OWBD_ALLOWED_TERRAIN_ALL == 0,
            f"{path}: override profile {index} has undefined spawn-destination-policy bits",
        )
        require((relative_mask & ~mask) == 0, f"{path}: override profile {index} relative mask is not active")
        require((relative_mask2 & ~mask2) == 0, f"{path}: override profile {index} relative mask2 is not active")
        require((relative_mask3 & ~mask3) == 0, f"{path}: override profile {index} relative mask3 is not active")
        require((relative_mask & ~OWBD_RELATIVE_MASK_ALLOWED) == 0, f"{path}: override profile {index} has a non-numeric relative field")
        require((relative_mask2 & ~OWBD_RELATIVE_MASK2_ALLOWED) == 0, f"{path}: override profile {index} has a non-numeric relative field in mask2")
        require((relative_mask3 & ~OWBD_RELATIVE_MASK3_ALLOWED) == 0, f"{path}: override profile {index} has a non-numeric relative field in mask3")
        field_index = 0
        for operator_mask, width in zip((relative_mask, relative_mask2, relative_mask3), (27, 15, 29)):
            for bit in range(width):
                if operator_mask & (1 << bit):
                    value = owbd_operator_field_value(
                        blob,
                        profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET,
                        field_index,
                        version,
                    )
                    invalid_minimum = 0x40 if field_index in (68, 69) else 0x80
                    require(value != invalid_minimum, f"{path}: override profile {index} relative delta uses its invalid minimum")
                field_index += 1
        for operator_name, operator_masks in (
            ("at-least", (at_least_mask, at_least_mask2, at_least_mask3)),
            ("at-most", (at_most_mask, at_most_mask2, at_most_mask3)),
        ):
            for word, (operator_mask, active_mask, numeric_mask, divide_mask) in enumerate(zip(
                operator_masks,
                (mask, mask2, mask3),
                (OWBD_BOUNDED_MASK_ALLOWED, OWBD_BOUNDED_MASK2_ALLOWED, OWBD_BOUNDED_MASK3_ALLOWED),
                divide_masks,
            ), 1):
                operator_mask &= ~divide_mask
                require((operator_mask & ~active_mask) == 0, f"{path}: override profile {index} {operator_name} mask{word} is not active")
                require((operator_mask & ~numeric_mask) == 0, f"{path}: override profile {index} has a non-numeric {operator_name} field in mask{word}")
            field_index = 0
            for operator_mask, compound_word, divide_mask, width in zip(
                operator_masks,
                (relative_mask, relative_mask2, relative_mask3),
                divide_masks,
                (27, 15, 29),
            ):
                operator_mask &= ~divide_mask
                for bit in range(width):
                    if operator_mask & (1 << bit):
                        maximum = OWBD_BOUNDED_FIELD_MAXIMUMS[field_index]
                        value_base = (
                            OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET
                            if compound_word & (1 << bit)
                            else OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                        )
                        value = owbd_operator_field_value(
                            blob,
                            profile_offset + value_base,
                            field_index,
                            version,
                        )
                        require(value <= maximum, f"{path}: override profile {index} {operator_name} threshold exceeds field maximum")
                        if field_index in (7, 48, 49, 53, 56, 57):
                            require(value != 0, f"{path}: override profile {index} positive field bound must be at least 1")
                    field_index += 1
        field_index = 0
        for word, (relative_word, divide_word, active_word, allowed_word, width) in enumerate(zip(
            (relative_mask, relative_mask2, relative_mask3),
            divide_masks, (mask, mask2, mask3),
            (OWBD_DIVIDE_MASK_ALLOWED, OWBD_DIVIDE_MASK2_ALLOWED, OWBD_DIVIDE_MASK3_ALLOWED),
            (27, 15, 29),
        ), 1):
            require(not divide_word & relative_word, f"{path}: override profile {index} divide overlaps relative mask{word}")
            require(not divide_word & ~active_word, f"{path}: override profile {index} divide mask{word} is not active")
            require(not divide_word & ~allowed_word, f"{path}: override profile {index} has a non-numeric divide field in mask{word}")
            for bit in range(width):
                if divide_word & (1 << bit):
                    divisor = owbd_operator_field_value(blob,
                        profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET, field_index, version)
                    require(1 <= divisor <= 127,
                        f"{path}: override profile {index} divide divisor must be between 1 and 127")
                field_index += 1
    override_members_end = range_end(path, "overrideMembers", override_members_offset, override_member_count, override_member_size, blob_size, 2, override_profiles_end)
    condition_entries_end = range_end(path, "conditionEntries", condition_entries_offset, condition_entry_count, condition_entry_size, blob_size, 4, override_members_end)
    condition_ids = set()
    covered_entries = set()
    for profile_index, (profile_kind, condition_start, condition_count) in enumerate(profile_condition_slices):
        if profile_kind != OWBD_PROFILE_KIND_CONDITIONAL:
            continue
        for entry_index in range(condition_start, condition_start + condition_count):
            require(
                entry_index not in covered_entries,
                f"{path}: condition entry {entry_index} is owned by two profiles",
            )
            covered_entries.add(entry_index)
            application_index = blob[
                condition_entries_offset
                + entry_index * condition_entry_size
                + 34
            ]
            require(
                application_index == (profile_index if profile_index < 255 else 0xFF),
                f"{path}: condition entry {entry_index} names the wrong application",
            )
    require(
        len(covered_entries) == condition_entry_count,
        f"{path}: a condition entry has no conditional-profile owner",
    )
    condition_mirrors = []
    for index in range(condition_entry_count):
        offset = condition_entries_offset + index * condition_entry_size
        (
            terrain_mask,
            terrain_override_mask,
            duration_frames,
            cooldown_frames,
            subject_member_start,
            subject_member_count,
            target_member_start,
            target_member_count,
            condition_id,
        ) = struct.unpack_from("<9H", blob, offset + 16)
        (
            application_index,
            subject_mode,
            subject_application_index,
            kind,
            activation_mode,
            target_kind,
            target_role_mask,
            target_selection,
            range_kind,
            range_length,
            chance_percent,
            min_speed,
            max_speed,
        ) = struct.unpack_from("<13B", blob, offset + 34)
        require(condition_id != 0xFFFF and condition_id not in condition_ids, f"{path}: condition entry {index} has an invalid or duplicate id")
        condition_ids.add(condition_id)
        condition_mirrors.append((application_index, subject_application_index))
        require(application_index == 0xFF or application_index < override_profile_count, f"{path}: condition entry {index} has an invalid application mirror")
        require(subject_mode in (1, 2), f"{path}: condition entry {index} has an invalid subject mode")
        require(subject_application_index == OWBD_CONDITION_SUBJECT_APPLICATION_NONE or subject_application_index < override_profile_count, f"{path}: condition entry {index} has an invalid subject application mirror")
        require(subject_member_start <= override_member_count and subject_member_count <= override_member_count - subject_member_start, f"{path}: condition entry {index} subject members are out of range")
        require(target_member_start <= override_member_count and target_member_count <= override_member_count - target_member_start, f"{path}: condition entry {index} target members are out of range")
        require(kind <= OWBD_CONDITION_SUBJECT_DAMAGED, f"{path}: condition entry {index} has an invalid condition kind")
        require(activation_mode in (OWBD_CONDITION_WHILE_TRUE, OWBD_CONDITION_TIMED, OWBD_CONDITION_UNTIL_CRASH), f"{path}: condition entry {index} has an invalid activation mode")
        if activation_mode == OWBD_CONDITION_WHILE_TRUE:
            require(duration_frames == 0 and cooldown_frames == 0, f"{path}: while-true condition entry {index} has timers")
        elif activation_mode == OWBD_CONDITION_TIMED:
            require(duration_frames != 0, f"{path}: timed condition entry {index} has no duration")
        else:
            require(duration_frames == 0, f"{path}: until-crash condition entry {index} has a duration")
        require(target_kind <= OWBD_CONDITION_TARGET_ACTOR, f"{path}: condition entry {index} has an invalid target kind")
        require((target_role_mask & ~OWBD_CONDITION_TARGET_ROLE_MASK) == 0, f"{path}: condition entry {index} has invalid target roles")
        require(chance_percent <= 100, f"{path}: condition entry {index} has an invalid chance")
        if kind != OWBD_CONDITION_TERRAIN_SPEED:
            require(
                (terrain_mask | terrain_override_mask) & ~OWBD_CONDITION_FACT_MASK_ALLOWED == 0
                and (terrain_mask & terrain_override_mask) == 0,
                f"{path}: condition entry {index} has invalid actor facts",
            )
        if kind == OWBD_CONDITION_ACTOR_FACTS:
            require(
                (target_kind == OWBD_CONDITION_TARGET_NONE
                 and target_role_mask == 0 and target_member_count == 0
                 or version >= 87 and target_kind == OWBD_CONDITION_TARGET_ACTOR
                 and target_role_mask != 0 and target_selection == 0)
                and activation_mode == OWBD_CONDITION_WHILE_TRUE
                and range_kind == 0
                and range_length == 0
                and chance_percent == 100
                and min_speed == 0
                and max_speed == 0
                and (terrain_mask | terrain_override_mask) != 0,
                f"{path}: actor-facts condition entry {index} has invalid fields",
            )
        elif kind == OWBD_CONDITION_PLAYER_DAMAGED:
            require(
                target_kind == OWBD_CONDITION_TARGET_ACTOR and target_role_mask != 0
                and target_selection == 0 and activation_mode == OWBD_CONDITION_WHILE_TRUE
                and range_kind == 0 and range_length == 0 and chance_percent == 100
                and min_speed == 0 and max_speed == 0,
                f"{path}: player-damaged condition entry {index} has invalid fields",
            )
        elif kind == OWBD_CONDITION_SUBJECT_DAMAGED:
            require(
                target_kind in (OWBD_CONDITION_TARGET_NONE, OWBD_CONDITION_TARGET_PLAYER)
                and target_role_mask == 0 and target_member_count == 0
                and target_selection == 0 and range_kind == 0 and range_length == 0
                and chance_percent == 100 and min_speed == 0 and max_speed == 0,
                f"{path}: subject-damaged condition entry {index} has invalid fields",
            )
        elif kind == OWBD_CONDITION_TERRAIN_SPEED:
            require(target_kind == OWBD_CONDITION_TARGET_NONE, f"{path}: terrain condition entry {index} has a target")
            require((terrain_mask & ~OWBD_CONDITION_TERRAIN_MASK_ALLOWED) == 0, f"{path}: condition entry {index} enables an unknown terrain")
            require((terrain_override_mask & ~OWBD_CONDITION_TERRAIN_MASK_ALLOWED) == 0, f"{path}: condition entry {index} explicitly sets an unknown terrain")
            require((terrain_mask & ~terrain_override_mask) == 0, f"{path}: condition entry {index} enables a terrain that is not explicit")
            require(min_speed <= OWBD_CONDITION_MOVEMENT_SPEED_MAX and max_speed <= OWBD_CONDITION_MOVEMENT_SPEED_MAX, f"{path}: condition entry {index} has an invalid Walk-time bound")
            require(min_speed == 0 or max_speed == 0 or min_speed <= max_speed, f"{path}: condition entry {index} Walk-time range is reversed")
            require(terrain_override_mask != 0 or min_speed != 0 or max_speed != 0, f"{path}: condition entry {index} has no condition")
        else:
            require(target_kind in (OWBD_CONDITION_TARGET_PLAYER, OWBD_CONDITION_TARGET_ACTOR), f"{path}: notice condition entry {index} has no target")
            require(1 <= range_kind <= OWBD_CONDITION_RANGE_VISION_CUSTOM, f"{path}: condition entry {index} has an invalid range")
            if range_kind == OWBD_CONDITION_RANGE_VISION_CURRENT:
                require(range_length == 0 and min_speed == 0, f"{path}: current-Vision condition entry {index} has custom values")
            elif range_kind == OWBD_CONDITION_RANGE_VISION_CUSTOM:
                require(1 <= range_length <= 32, f"{path}: custom-Vision condition entry {index} has an invalid range")
                require(
                    (min_speed & ~(OWBD_VISION_OPTIONS_SAME_TILE_AWARENESS
                        if version >= 88 else 0)) in (
                        OWBD_VISION_OPTIONS_FORWARD_90,
                        OWBD_VISION_OPTIONS_FORWARD_90
                        | OWBD_VISION_OPTIONS_ADJACENT_AWARENESS,
                        OWBD_VISION_OPTIONS_FORWARD_LINE,
                        OWBD_VISION_OPTIONS_CARDINAL_LINES,
                        OWBD_VISION_OPTIONS_CARDINAL_LINES | OWBD_VISION_OPTIONS_ADJACENT_AWARENESS,
                        OWBD_VISION_OPTIONS_FORWARD_LINE
                        | OWBD_VISION_OPTIONS_ADJACENT_AWARENESS,
                    ),
                    f"{path}: custom-Vision condition entry {index} has invalid options",
                )
            else:
                require(range_length <= 0xFF and min_speed == 0, f"{path}: condition entry {index} has invalid legacy range values")
            require(max_speed == 0, f"{path}: notice condition entry {index} has a movement-speed value")
            if target_kind == OWBD_CONDITION_TARGET_ACTOR:
                require(target_role_mask != 0 and target_selection == 0, f"{path}: actor target condition entry {index} has an invalid selector")
            else:
                require(target_role_mask == 0 and target_member_count == 0, f"{path}: player target condition entry {index} has actor selector data")
    surface_models_end = range_end(path, "surfaceModels", surface_models_offset, surface_model_count, surface_model_size, blob_size, 2, condition_entries_end)
    surface_instances_end = range_end(path, "surfaceInstances", surface_instances_offset, surface_instance_count, surface_instance_size, blob_size, 2, surface_models_end)
    surface_templates_end = range_end(path, "surfaceTemplates", surface_templates_offset, surface_template_count, surface_template_size, blob_size, 1, surface_instances_end)
    padded_surface_end = (surface_templates_end + 3) & ~3
    if version >= 86:
        options_stride = OWBD_CONDITION_OPTIONS_SIZE if version >= 95 else 12
        options_size = max(1, condition_entry_count) * options_stride if version >= 87 else 0
        tail_base = padded_surface_end + 4 + options_size
        require(tail_base <= blob_size, f"{path}: truncated cooldown tint/condition options tail")
        if version < 93:
            require(tail_base == blob_size, f"{path}: bad cooldown tint/condition options tail size")
        rest_enabled = struct.unpack_from("<I", blob, padded_surface_end)[0]
        conditional_mask = sum(1 << index for index, entry in enumerate(profile_condition_slices)
                               if index < 32 and entry[0] == OWBD_PROFILE_KIND_CONDITIONAL)
        require(rest_enabled & ~conditional_mask == 0,
                f"{path}: cooldown tint tail references a nonconditional application")
        if version >= 87:
            options_base = padded_surface_end + 4
            for index in range(condition_entry_count):
                (role_mask, capture, lifetime, bind_only, duration, uses_binding,
                 reachable, distance, height, failure, _retry) = struct.unpack_from(
                    "<4BH6B", blob, options_base + index * options_stride)
                require(
                    role_mask & ~7 == 0 and capture <= 2 and uses_binding <= 3
                    and lifetime <= 1 and bind_only <= 1 and reachable <= 1
                    and distance <= 8 and height <= 64 and failure <= 1
                    and (not reachable or distance != 0)
                    and (not bind_only or capture != 0)
                    and (uses_binding != 3 or capture == 2)
                    and (not capture or (duration != 0 if lifetime == 1 else duration == 0))
                    and (capture != 2 or blob[condition_entries_offset
                        + index * condition_entry_size + 39] == OWBD_CONDITION_TARGET_ACTOR),
                    f"{path}: condition entry {index} has invalid binding/pickup options",
                )
                if version >= 95:
                    required, minimum, maximum, bound, padding = struct.unpack_from(
                        "<H4B", blob, options_base + index * options_stride + 12)
                    require(required <= override_profile_count and bound <= 1 and not padding
                        and (not required or profile_condition_slices[required-1][0]
                            == OWBD_PROFILE_KIND_CONDITIONAL)
                        and (0 <= minimum <= maximum <= 32 and maximum >= 1 and uses_binding == 1
                            and blob[condition_entries_offset + index * condition_entry_size + 38] == 0
                            and blob[condition_entries_offset + index * condition_entry_size + 39] != 0
                            if bound else minimum == maximum == 0),
                        f"{path}: condition entry {index} has invalid profile/distance options")
            if condition_entry_count == 0:
                require(not any(blob[options_base:options_base + options_size]),
                    f"{path}: unused condition options are nonzero")
        if version >= 93:
            arc_count = read_define(source, "OWBD_HOP_ARC_RECORD_COUNT")
            arc_storage = max(1, arc_count)
            arc_end = tail_base + arc_storage * 6
            require(arc_end <= blob_size, f"{path}: truncated Hop Arc records")
            prior_arc = -1
            for index in range(arc_count):
                global_id, rise, hang, drop, peak = struct.unpack_from(
                    "<H4B", blob, tail_base + index * 6)
                require(prior_arc < global_id < override_profile_count
                    and profile_condition_slices[global_id][0] == OWBD_PROFILE_KIND_CONDITIONAL
                    and rise > 0 and drop > 0 and peak > 0
                    and rise + hang + drop <= 255,
                    f"{path}: Hop Arc record {index} is invalid")
                prior_arc = global_id
            if arc_count == 0:
                require(not any(blob[tail_base:arc_end]),
                    f"{path}: unused Hop Arc record is nonzero")
            if version < 94:
                require(arc_end == blob_size,
                    f"{path}: bad Hop Arc tail size")
        if version >= 94:
            directory_count = read_define(source,
                "OWBD_APPLICATION_BANK_DIRECTORY_COUNT")
            index_count = read_define(source, "OWBD_APPLICATION_BANK_INDEX_COUNT")
            require(directory_count >= 1 and index_count <= 65535,
                f"{path}: invalid application bank dimensions")
            directory_base = arc_end
            indexes_base = directory_base + directory_count * 6
            owners_base = indexes_base + index_count * 2
            subject_owners_base = owners_base + max(1, condition_entry_count) * 2
            limit_base = subject_owners_base + max(1, condition_entry_count) * 2
            tint_base = limit_base + override_profile_count
            tired_class_base = tint_base + override_profile_count
            tired_override_base = tired_class_base + class_profile_count * 2
            tail_end = tired_override_base + override_profile_count * 2
            require((tail_end + 3) & ~3 == blob_size,
                f"{path}: bad application bank tail size")
            require(not any(blob[tail_end:blob_size]),
                f"{path}: application bank tail padding is not zero")
            bank_indexes = struct.unpack_from(
                f"<{index_count}H", blob, indexes_base) if index_count else ()
            prior_species = -1
            next_first = 0
            for index in range(directory_count):
                species, first, count, reserved = struct.unpack_from(
                    "<HHBB", blob, directory_base + index * 6)
                require((species == 0xFFFF) == (index == directory_count - 1)
                    and species > prior_species and reserved == 0
                    and first == next_first and count <= 32
                    and first + count <= index_count,
                    f"{path}: application bank row {index} is invalid")
                globals_for_subject = bank_indexes[first:first + count]
                require(all(global_id < override_profile_count
                    for global_id in globals_for_subject)
                    and all(a < b for a, b in zip(
                        globals_for_subject, globals_for_subject[1:])),
                    f"{path}: application bank row {index} has invalid global IDs")
                next_first += count
                prior_species = species
            require(next_first == index_count,
                f"{path}: application bank index table is incomplete")
            for index, (mirror, subject_mirror) in enumerate(condition_mirrors):
                owner = struct.unpack_from("<H", blob, owners_base + index * 2)[0]
                subject_owner = struct.unpack_from(
                    "<H", blob, subject_owners_base + index * 2)[0]
                require(owner < override_profile_count
                    and profile_condition_slices[owner][0] == OWBD_PROFILE_KIND_CONDITIONAL
                    and mirror == (owner if owner < 255 else 0xFF)
                    and index in range(profile_condition_slices[owner][1],
                        profile_condition_slices[owner][1]
                        + profile_condition_slices[owner][2]),
                    f"{path}: condition {index} has invalid global owner")
                if version >= 95:
                    required = struct.unpack_from("<H", blob, options_base + index * options_stride + 12)[0]
                    require(not required or required-1 < owner,
                        f"{path}: condition {index} has a forward or circular profile dependency")
                require(subject_owner == 0xFFFF or subject_owner < override_profile_count,
                    f"{path}: condition {index} has invalid global subject")
                require(subject_mirror == (subject_owner
                    if subject_owner < 255 else 0xFF),
                    f"{path}: condition {index} has invalid subject mirror")
            limits = blob[limit_base:tint_base]
            require(1 not in limits and len({key for key in limits if key})
                == sum(bool(key) for key in limits),
                f"{path}: application limit keys are invalid")
            for index, enabled in enumerate(blob[tint_base:tired_class_base]):
                require(enabled in (0, 1)
                    and (not enabled or profile_condition_slices[index][0]
                        == OWBD_PROFILE_KIND_CONDITIONAL),
                    f"{path}: application {index} has invalid rest tint")
            for base, count in ((tired_class_base, class_profile_count),
                                (tired_override_base, override_profile_count)):
                for index in range(count):
                    target = struct.unpack_from("<H", blob, base + index * 2)[0]
                    require(target == 0xFFFF or target < override_profile_count,
                        f"{path}: Tired reference {index} is invalid")
    else:
        require(padded_surface_end == blob_size, f"{path}: bad padding after surface catalog")
    require(not any(blob[surface_templates_end:padded_surface_end]), f"{path}: nonzero padding after surface catalog")

    templates = []
    for index in range(surface_template_count):
        width, height = struct.unpack_from(
            "<BB",
            blob,
            surface_templates_offset + index * surface_template_size,
        )
        require(width != 0 and height != 0, f"{path}: surface template {index} has an empty rectangle")
        require(width * height <= 255, f"{path}: surface template {index} has more than 255 dense nodes")
        templates.append((width, height))

    instances = []
    for index in range(surface_instance_count):
        min_x, min_y, template_id, local_surface_id, height_q4, packed_surface, packed_anchor = struct.unpack_from(
            "<BBBBHBB",
            blob,
            surface_instances_offset + index * surface_instance_size,
        )
        height_page = packed_surface & 0x1F
        surface_type = packed_surface >> 5
        anchor_dx = (packed_anchor & 0x0F) - (0x10 if packed_anchor & 0x08 else 0)
        anchor_dy = (packed_anchor >> 4) - (0x10 if packed_anchor & 0x80 else 0)
        require(template_id < surface_template_count, f"{path}: surface instance {index} has an invalid template")
        require(surface_type < OWBD_SURFACE_TYPE_COUNT, f"{path}: surface instance {index} has an invalid surface type")
        if height_page == OWBD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND:
            require(local_surface_id == 0, f"{path}: native-ground surface instance {index} has a local surface ID")
            require(surface_type in (OWBD_SURFACE_TYPE_FLOWERBED, OWBD_SURFACE_TYPE_CANOPY), f"{path}: native-ground surface instance {index} is not Flowerbed or Canopy")
            require(
                height_q4 == (
                    OWBD_SURFACE_CANOPY_HEIGHT_OFFSET_Q4
                    if surface_type == OWBD_SURFACE_TYPE_CANOPY
                    else 0
                ),
                f"{path}: native-ground surface instance {index} has an invalid height offset",
            )
            require(anchor_dx == 0 and anchor_dy == 0, f"{path}: native-ground surface instance {index} has an anchor delta")
        else:
            require(1 <= local_surface_id <= 15, f"{path}: elevated surface instance {index} local surface ID must be 1..15")
            require(height_q4 != 0 or height_page != 0, f"{path}: surface instance {index} has zero height")
        width, height = templates[template_id]
        require(min_x + width <= 32, f"{path}: surface instance {index} exceeds the block width")
        require(min_y + height <= 32, f"{path}: surface instance {index} exceeds the block height")
        instances.append((local_surface_id, min_x, min_y, width, height, anchor_dx, anchor_dy, height_page))

    previous_land_data_id = -1
    expected_first_instance = 0
    for index in range(surface_model_count):
        land_data_id, first_instance, instance_count, reserved = struct.unpack_from(
            "<HHBB",
            blob,
            surface_models_offset + index * surface_model_size,
        )
        require(land_data_id > previous_land_data_id, f"{path}: surface model directory is not strictly sorted")
        require(reserved == 0, f"{path}: surface model {index} has nonzero reserved data")
        require(instance_count != 0, f"{path}: surface model {index} has no instances")
        require(first_instance == expected_first_instance, f"{path}: surface model {index} leaves a gap or overlap")
        require(first_instance + instance_count <= surface_instance_count, f"{path}: surface model {index} instance range is invalid")
        model_instances = instances[first_instance:first_instance + instance_count]
        for left_index, left in enumerate(model_instances):
            _, left_x, left_y, left_width, left_height, _left_anchor_dx, _left_anchor_dy, _left_height_page = left
            for right in model_instances[left_index + 1:]:
                _, right_x, right_y, right_width, right_height, _right_anchor_dx, _right_anchor_dy, _right_height_page = right
                overlaps = (
                    left_x < right_x + right_width
                    and right_x < left_x + left_width
                    and left_y < right_y + right_height
                    and right_y < left_y + left_height
                )
                require(not overlaps, f"{path}: surface model {index} has overlapping dense rectangles")
        previous_land_data_id = land_data_id
        expected_first_instance += instance_count
    require(expected_first_instance == surface_instance_count, f"{path}: unreferenced surface instances")


def validate_owed(path: Path, source: Path, encounter_narc: Optional[Path]) -> None:
    blob = path.read_bytes()
    expected_count = read_define(source, "OWED_ENCOUNTER_AREA_COUNT")
    require(len(blob) >= OWED_HEADER_SIZE, f"{path}: truncated OWED header")
    fields = struct.unpack_from("<IHHHHIIIII", blob, 0)
    (
        magic,
        version,
        header_size,
        record_count,
        directory_entry_size,
        directory_offset,
        payload_offset,
        total_size,
        checksum,
        flags,
    ) = fields

    require(magic == OWED_MAGIC, f"{path}: bad OWED magic")
    require(version == OWED_VERSION, f"{path}: bad OWED version")
    require(header_size == OWED_HEADER_SIZE, f"{path}: bad OWED header size")
    require(record_count == expected_count, f"{path}: bad OWED record count")
    require(directory_entry_size == OWED_DIRECTORY_ENTRY_SIZE, f"{path}: bad OWED directory entry size")
    require(total_size == len(blob), f"{path}: OWED total size does not match file size")
    require(flags == 0, f"{path}: bad OWED flags value")
    require(checksum == owed_checksum(blob), f"{path}: bad OWED checksum")

    directory_size = record_count * directory_entry_size
    require(directory_offset >= header_size, f"{path}: OWED directory starts before header")
    require(directory_offset % 4 == 0, f"{path}: OWED directory has bad alignment")
    require(directory_offset <= total_size and directory_size <= total_size - directory_offset, f"{path}: OWED directory extends past blob")
    require(payload_offset == directory_offset + directory_size, f"{path}: OWED payload is not immediately after directory")
    require(payload_offset <= total_size, f"{path}: OWED payload starts past blob")

    encounter_members = read_narc_members(encounter_narc) if encounter_narc is not None else None
    seen_maps: set[int] = set()
    for index in range(record_count):
        entry_offset = directory_offset + index * directory_entry_size
        map_id, data_id, offset, size, entry_flags = struct.unpack_from("<HHIHH", blob, entry_offset)
        require(entry_flags == 0, f"{path}: OWED directory entry {index} has bad flags")
        require(map_id not in seen_maps, f"{path}: duplicate OWED map id {map_id}")
        seen_maps.add(map_id)
        require(size >= 4, f"{path}: OWED directory entry {index} has a tiny record")
        require(offset >= payload_offset, f"{path}: OWED directory entry {index} points before payload")
        require(offset <= total_size and size <= total_size - offset, f"{path}: OWED directory entry {index} extends past blob")

        record = blob[offset:offset + size]
        decoded = decode_sparse_record(path, record)
        if encounter_members is not None:
            require(data_id < len(encounter_members), f"{path}: OWED dataId {data_id} is outside encounter NARC member count {len(encounter_members)}")
            expected_record = encode_sparse_record(encounter_members[data_id])
            require(record == expected_record, f"{path}: OWED sparse record for dataId {data_id} does not match encounter NARC")
            require(decoded == decode_sparse_record(path, expected_record), f"{path}: OWED decoded record mismatch for dataId {data_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owbd", type=Path)
    parser.add_argument("--owbd-source", type=Path, default=Path("include/overworld_wild_behavior_data.h"))
    parser.add_argument("--owed", type=Path)
    parser.add_argument("--owed-source", type=Path, default=Path("include/overworld_wild_behavior_data.h"))
    parser.add_argument("--encounter-narc", type=Path)
    args = parser.parse_args()
    try:
        if args.owbd is not None:
            validate_owbd(args.owbd, args.owbd_source)
        if args.owed is not None:
            validate_owed(args.owed, args.owed_source, args.encounter_narc)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
