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
OWBD_PROFILE_SIZE = 72
OWBD_CLASS_RULE_SIZE = 16
OWBD_SPECIES_RULE_SIZE = 4
OWBD_OVERRIDE_PROFILE_SIZE = 212
OWBD_OVERRIDE_MEMBER_SIZE = 2
OWBD_CONDITIONAL_STATE_SIZE = 8
OWBD_CONDITIONAL_TERRAIN_MASK_ALLOWED = 0x03FF
OWBD_CONDITIONAL_MOVEMENT_SPEED_MAX = 32
OWBD_CONDITIONAL_PROFILE_NONE = 0xFF
OWBD_CHILL_ACTION_OFFSET = 12
OWBD_CHILL_ACTION_FIELD_BIT = 1 << 12
OWBD_LOCOMOTION_MAX = 11
OWBD_SURFACE_MODEL_SIZE = 6
OWBD_SURFACE_INSTANCE_SIZE = 10
OWBD_SURFACE_TEMPLATE_SIZE = 2
OWBD_MASK_ALLOWED = 0x07FFFFFF
OWBD_MASK2_ALLOWED = 0x7FFF
OWBD_MASK3_ALLOWED = 0x01FFFFFF
OWBD_RELATIVE_MASK_ALLOWED = 0x05F101F8
OWBD_RELATIVE_MASK2_ALLOWED = 0x1F8F
OWBD_RELATIVE_MASK3_ALLOWED = 0x0140F8F3
OWBD_BOUNDED_MASK_ALLOWED = 0x01C00180
OWBD_BOUNDED_MASK2_ALLOWED = 0x1F84
OWBD_BOUNDED_MASK3_ALLOWED = 0x0140F8F3
# Compact data fields are stored in the same order as the mask bits.
OWBD_OPERATOR_FIELD_PROFILE_OFFSETS = tuple(
    index if index < 34 else index + 2 if index < 52 else index + 4
    for index in range(67)
)
OWBD_OPERATOR_FIELD_MAXIMUMS = (
    0, 0, 0, 255, 64, 64, 64, 32, 64, 0, 0, 0, 0, 0, 0, 0, 100, 0, 0,
    0, 12, 12, 255, 64, 255, 0, 10, 8, 8, 32, 255, 0, 0, 0, 64, 32, 32,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 32, 32, 0, 0, 0, 8, 8, 8, 32,
    5, 0, 0, 0, 0, 0, 0, 255, 32, 32,
)
OWBD_BOUNDED_FIELD_MAXIMUMS = (
    0, 0, 0, 0, 0, 0, 0, 32, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 255, 64, 255, 0, 0, 0, 0, 32, 0, 0, 0, 0, 64, 32, 32,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 32, 32, 0, 0, 0, 8, 8, 8, 32,
    5, 0, 0, 0, 0, 0, 0, 255, 32, 32,
)
OWBD_OVERRIDE_PROFILE_VALUE_OFFSET = 32
OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET = 140
OWBD_ALLOWED_TERRAIN_ALL = 0x3FF
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
OWBD_WALK_STOMP_TIME_OFFSET = 70
OWBD_WALK_STOMP_TIME_FIELD_BIT = 1 << 24
OWBD_WALK_OPTIONS_RESERVED_MASK = 0x0E
OWBD_WALK_CRASH_SOUND_MASK = 0x10
OWBD_WALK_CRASH_SOUND_SHIFT = 4
OWBD_WALK_FACING_MASK = 0xC0
OWBD_SPAWN_DESTINATION_OFFSET = 17
OWBD_SPAWN_DESTINATION_MAX = 20
OWBD_SURFACE_TYPE_FLOWERBED = 3
OWBD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND = 0xFF

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
    expected_conditional_state_count = read_define(source, "OWBD_CONDITIONAL_STATE_COUNT")
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
        conditional_states_offset,
        conditional_state_count,
        conditional_state_size,
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
    require(conditional_state_count == expected_conditional_state_count, f"{path}: bad conditional state count")
    require(surface_model_count == expected_surface_model_count, f"{path}: bad surface model count")
    require(surface_instance_count == expected_surface_instance_count, f"{path}: bad surface instance count")
    require(surface_template_count == expected_surface_template_count, f"{path}: bad surface template count")
    require(surface_template_count <= 256, f"{path}: surface templates exceed byte-addressable range")
    require(class_profile_size == OWBD_PROFILE_SIZE, f"{path}: bad class profile element size")
    require(class_rule_size == OWBD_CLASS_RULE_SIZE, f"{path}: bad class rule element size")
    require(species_rule_size == OWBD_SPECIES_RULE_SIZE, f"{path}: bad species class rule element size")
    require(override_profile_size == OWBD_OVERRIDE_PROFILE_SIZE, f"{path}: bad override profile element size")
    require(override_member_size == OWBD_OVERRIDE_MEMBER_SIZE, f"{path}: bad override member element size")
    require(conditional_state_size == OWBD_CONDITIONAL_STATE_SIZE, f"{path}: bad conditional state element size")
    require(surface_model_size == OWBD_SURFACE_MODEL_SIZE, f"{path}: bad surface model element size")
    require(surface_instance_size == OWBD_SURFACE_INSTANCE_SIZE, f"{path}: bad surface instance element size")
    require(surface_template_size == OWBD_SURFACE_TEMPLATE_SIZE, f"{path}: bad surface template element size")

    class_profiles_end = range_end(path, "classProfiles", class_profiles_offset, class_profile_count, class_profile_size, blob_size, 2, header_size)
    class_rules_end = range_end(path, "classRules", class_rules_offset, class_rule_count, class_rule_size, blob_size, 4, class_profiles_end)
    species_rules_end = range_end(path, "speciesClassRules", species_rules_offset, species_rule_count, species_rule_size, blob_size, 2, class_rules_end)
    override_profiles_end = range_end(path, "overrideProfiles", override_profiles_offset, override_profile_count, override_profile_size, blob_size, 4, species_rules_end)
    for index in range(class_profile_count):
        profile_offset = class_profiles_offset + index * class_profile_size
        require(
            blob[profile_offset + OWBD_CHILL_ACTION_OFFSET] <= OWBD_LOCOMOTION_MAX,
            f"{path}: class profile {index} has an invalid locomotion",
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
            1 <= blob[profile_offset + OWBD_TILES_TO_ACCELERATE_OFFSET] <= 32,
            f"{path}: class profile {index} tiles-to-accelerate value must be between 1 and 32",
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
            blob[profile_offset + OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_OFFSET] <= 1,
            f"{path}: class profile {index} has an invalid vertical-obstacle hop policy",
        )
        require(
            1 <= blob[profile_offset + OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET] <= 8,
            f"{path}: class profile {index} reposition-jump count must be between 1 and 8",
        )
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
            require(
                blob[profile_offset + option_offset] <= 1,
                f"{path}: class profile {index} has an invalid reposition {option_name} option",
            )
        walk_options = blob[profile_offset + OWBD_WALK_OPTIONS_OFFSET]
        require(
            (walk_options & OWBD_WALK_OPTIONS_RESERVED_MASK) == 0
            and ((walk_options & OWBD_WALK_CRASH_SOUND_MASK)
                 >> OWBD_WALK_CRASH_SOUND_SHIFT) <= 1
            and (walk_options & OWBD_WALK_FACING_MASK) != OWBD_WALK_FACING_MASK,
            f"{path}: class profile {index} has invalid Walk options",
        )
        require(
            blob[profile_offset + OWBD_TILES_BEFORE_TURN_SKID_OFFSET] <= 32,
            f"{path}: class profile {index} turn-skid buildup must be between 0 and 32",
        )
        require(
            blob[profile_offset + OWBD_WALK_STOMP_TIME_OFFSET] <= 32,
            f"{path}: class profile {index} stomp time must be 0 (off) or 1..32 frames",
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
    for index in range(override_profile_count):
        profile_offset = override_profiles_offset + index * override_profile_size
        mask, mask2, mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 20)
        relative_mask, relative_mask2, relative_mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 104)
        at_least_mask, at_least_mask2, at_least_mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 116)
        at_most_mask, at_most_mask2, at_most_mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 128)
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
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_TILES_TO_ACCELERATE_OFFSET] <= 32,
                f"{path}: override profile {index} exact tiles-to-accelerate value must be between 1 and 32",
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
        require((mask2 & ~OWBD_MASK2_ALLOWED) == 0, f"{path}: override profile {index} mask2 has undefined bits")
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
                blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_HOP_ALLOW_VERTICAL_OBSTACLES_OFFSET] <= 1,
                f"{path}: override profile {index} has an invalid vertical-obstacle hop policy",
            )
        if mask3 & OWBD_CHAIN_REPOSITION_JUMP_COUNT_FIELD_BIT \
                and not operator_mask3 & OWBD_CHAIN_REPOSITION_JUMP_COUNT_FIELD_BIT:
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_CHAIN_REPOSITION_JUMP_COUNT_OFFSET] <= 8,
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
                and ((walk_options & OWBD_WALK_CRASH_SOUND_MASK)
                     >> OWBD_WALK_CRASH_SOUND_SHIFT) <= 1
                and (walk_options & OWBD_WALK_FACING_MASK) != OWBD_WALK_FACING_MASK,
                f"{path}: override profile {index} has invalid Walk options",
            )
        if mask3 & OWBD_TILES_BEFORE_TURN_SKID_FIELD_BIT \
                and not operator_mask3 & OWBD_TILES_BEFORE_TURN_SKID_FIELD_BIT:
            require(
                blob[
                    profile_offset
                    + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                    + OWBD_TILES_BEFORE_TURN_SKID_OFFSET
                ] <= 32,
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
                require(
                    blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + option_offset] <= 1,
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
        for operator_mask, width in zip((relative_mask, relative_mask2, relative_mask3), (27, 15, 25)):
            for bit in range(width):
                if operator_mask & (1 << bit):
                    value_offset = profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_OPERATOR_FIELD_PROFILE_OFFSETS[field_index]
                    require(blob[value_offset] != 0x80, f"{path}: override profile {index} relative delta cannot be -128")
                field_index += 1
        for operator_name, operator_masks in (
            ("at-least", (at_least_mask, at_least_mask2, at_least_mask3)),
            ("at-most", (at_most_mask, at_most_mask2, at_most_mask3)),
        ):
            for word, (operator_mask, active_mask, numeric_mask) in enumerate(zip(
                operator_masks,
                (mask, mask2, mask3),
                (OWBD_BOUNDED_MASK_ALLOWED, OWBD_BOUNDED_MASK2_ALLOWED, OWBD_BOUNDED_MASK3_ALLOWED),
            ), 1):
                require((operator_mask & ~active_mask) == 0, f"{path}: override profile {index} {operator_name} mask{word} is not active")
                require((operator_mask & ~numeric_mask) == 0, f"{path}: override profile {index} has a non-numeric {operator_name} field in mask{word}")
            field_index = 0
            for operator_mask, compound_word, width in zip(
                operator_masks,
                (relative_mask, relative_mask2, relative_mask3),
                (27, 15, 25),
            ):
                for bit in range(width):
                    if operator_mask & (1 << bit):
                        maximum = OWBD_BOUNDED_FIELD_MAXIMUMS[field_index]
                        value_base = (
                            OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET
                            if compound_word & (1 << bit)
                            else OWBD_OVERRIDE_PROFILE_VALUE_OFFSET
                        )
                        value_offset = profile_offset + value_base + OWBD_OPERATOR_FIELD_PROFILE_OFFSETS[field_index]
                        require(blob[value_offset] <= maximum, f"{path}: override profile {index} {operator_name} threshold exceeds field maximum")
                        if field_index in (7, 48, 49, 53, 56, 57):
                            require(blob[value_offset] != 0, f"{path}: override profile {index} positive field bound must be at least 1")
                    field_index += 1
        for word, (relative_word, at_least_word, at_most_word) in enumerate(zip(
            (relative_mask, relative_mask2, relative_mask3),
            (at_least_mask, at_least_mask2, at_least_mask3),
            (at_most_mask, at_most_mask2, at_most_mask3),
        ), 1):
            require((at_least_word & at_most_word) == 0, f"{path}: override profile {index} has overlapping at-least/at-most mask{word}")
    override_members_end = range_end(path, "overrideMembers", override_members_offset, override_member_count, override_member_size, blob_size, 2, override_profiles_end)
    conditional_states_end = range_end(path, "conditionalStates", conditional_states_offset, conditional_state_count, conditional_state_size, blob_size, 2, override_members_end)
    for index in range(conditional_state_count):
        parent_profile, override_profile, terrain_mask, terrain_override_mask, min_speed, max_speed = struct.unpack_from(
            "<BBHHBB",
            blob,
            conditional_states_offset + index * conditional_state_size,
        )
        require(parent_profile < override_profile_count, f"{path}: conditional state {index} has an invalid parent profile")
        require(override_profile == OWBD_CONDITIONAL_PROFILE_NONE or override_profile < override_profile_count, f"{path}: conditional state {index} has an invalid override profile")
        require((terrain_mask & ~OWBD_CONDITIONAL_TERRAIN_MASK_ALLOWED) == 0, f"{path}: conditional state {index} enables an unknown terrain")
        require((terrain_override_mask & ~OWBD_CONDITIONAL_TERRAIN_MASK_ALLOWED) == 0, f"{path}: conditional state {index} explicitly sets an unknown terrain")
        require((terrain_mask & ~terrain_override_mask) == 0, f"{path}: conditional state {index} enables a terrain that is not explicit")
        require(min_speed <= OWBD_CONDITIONAL_MOVEMENT_SPEED_MAX, f"{path}: conditional state {index} has an invalid no-faster-than Walk time")
        require(max_speed <= OWBD_CONDITIONAL_MOVEMENT_SPEED_MAX, f"{path}: conditional state {index} has an invalid no-slower-than Walk time")
        require((min_speed == 0) == (max_speed == 0), f"{path}: conditional state {index} has an incomplete Walk-time range")
        require(min_speed <= max_speed, f"{path}: conditional state {index} Walk-time range is reversed")
        require(terrain_override_mask != 0 or min_speed != 0 or max_speed != 0, f"{path}: conditional state {index} has no condition")
    surface_models_end = range_end(path, "surfaceModels", surface_models_offset, surface_model_count, surface_model_size, blob_size, 2, conditional_states_end)
    surface_instances_end = range_end(path, "surfaceInstances", surface_instances_offset, surface_instance_count, surface_instance_size, blob_size, 2, surface_models_end)
    surface_templates_end = range_end(path, "surfaceTemplates", surface_templates_offset, surface_template_count, surface_template_size, blob_size, 1, surface_instances_end)
    padded_surface_end = (surface_templates_end + 3) & ~3
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
        min_x, min_y, template_id, local_surface_id, height_q4, height_page, surface_type, anchor_dx, anchor_dy = struct.unpack_from(
            "<BBBBHBBbb",
            blob,
            surface_instances_offset + index * surface_instance_size,
        )
        require(template_id < surface_template_count, f"{path}: surface instance {index} has an invalid template")
        require(surface_type < 4, f"{path}: surface instance {index} has an invalid surface type")
        if height_page == OWBD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND:
            require(local_surface_id == 0, f"{path}: native-ground surface instance {index} has a local surface ID")
            require(height_q4 == 0, f"{path}: native-ground surface instance {index} has a stored height")
            require(surface_type == OWBD_SURFACE_TYPE_FLOWERBED, f"{path}: native-ground surface instance {index} is not Flowerbed")
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
