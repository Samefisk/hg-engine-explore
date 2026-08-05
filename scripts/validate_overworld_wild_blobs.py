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
OWBD_HEADER_SIZE = 52
OWBD_PROFILE_SIZE = 46
OWBD_CLASS_RULE_SIZE = 16
OWBD_SPECIES_RULE_SIZE = 4
OWBD_OVERRIDE_PROFILE_SIZE = 164
OWBD_OVERRIDE_MEMBER_SIZE = 2
OWBD_MASK_ALLOWED = 0x07FFFFFF
OWBD_MASK2_ALLOWED = 0x7FFF
OWBD_MASK3_ALLOWED = 0x0000000F
OWBD_RELATIVE_MASK_ALLOWED = 0x05F101F8
OWBD_RELATIVE_MASK2_ALLOWED = 0x1F8F
OWBD_RELATIVE_MASK3_ALLOWED = 0x00000003
OWBD_BOUNDED_MASK_ALLOWED = 0x01C00180
OWBD_BOUNDED_MASK2_ALLOWED = 0x1F84
OWBD_BOUNDED_MASK3_ALLOWED = 0x00000003
# Compact data fields are stored in the same order as the mask bits.
OWBD_OPERATOR_FIELD_PROFILE_OFFSETS = tuple(range(46))
OWBD_OPERATOR_FIELD_MAXIMUMS = (
    0, 0, 0, 255, 64, 64, 64, 4, 64, 0, 0, 0, 0, 0, 0, 0, 100, 0, 0,
    0, 12, 12, 255, 64, 255, 0, 10, 8, 8, 32, 255, 0, 0, 0, 64, 32, 4,
    15, 64, 15, 0, 0, 32, 255, 0, 0,
)
OWBD_BOUNDED_FIELD_MAXIMUMS = (
    0, 0, 0, 0, 0, 0, 0, 4, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 255, 64, 255, 0, 0, 0, 0, 32, 0, 0, 0, 0, 64, 32, 4,
    15, 64, 15, 0, 0, 32, 255, 0, 0,
)
OWBD_OVERRIDE_PROFILE_VALUE_OFFSET = 32
OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET = 116
OWBD_ALLOWED_TERRAIN_ALL = 0x3F
OWBD_ALLOWED_TERRAIN_VALUE_OFFSET = 32
OWBD_ALLOWED_TERRAIN_OVERRIDE_OFFSET = 33
OWBD_ALLOWED_TERRAIN_FIELD_BITS = (1 << 5) | (1 << 6)

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

DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z0-9_]+)\s+([0-9]+)\b", re.MULTILINE)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_define(source: Path, symbol: str) -> int:
    text = source.read_text()
    for name, value in DEFINE_RE.findall(text):
        if name == symbol:
            return int(value, 10)
    raise ValueError(f"{source}: could not find #define {symbol}")


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
    require(len(blob) >= OWBD_HEADER_SIZE, f"{path}: truncated OWBD header")
    fields = struct.unpack_from("<IHHI IHH IHH IHH IHH IHH", blob, 0)
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
    require(class_profile_size == OWBD_PROFILE_SIZE, f"{path}: bad class profile element size")
    require(class_rule_size == OWBD_CLASS_RULE_SIZE, f"{path}: bad class rule element size")
    require(species_rule_size == OWBD_SPECIES_RULE_SIZE, f"{path}: bad species class rule element size")
    require(override_profile_size == OWBD_OVERRIDE_PROFILE_SIZE, f"{path}: bad override profile element size")
    require(override_member_size == OWBD_OVERRIDE_MEMBER_SIZE, f"{path}: bad override member element size")

    class_profiles_end = range_end(path, "classProfiles", class_profiles_offset, class_profile_count, class_profile_size, blob_size, 2, header_size)
    class_rules_end = range_end(path, "classRules", class_rules_offset, class_rule_count, class_rule_size, blob_size, 4, class_profiles_end)
    species_rules_end = range_end(path, "speciesClassRules", species_rules_offset, species_rule_count, species_rule_size, blob_size, 2, class_rules_end)
    override_profiles_end = range_end(path, "overrideProfiles", override_profiles_offset, override_profile_count, override_profile_size, blob_size, 4, species_rules_end)
    for index in range(class_profile_count):
        profile_offset = class_profiles_offset + index * class_profile_size
        require(
            1 <= blob[profile_offset + 15] <= 0xF,
            f"{path}: class profile {index} Next-to-player side mask must be between 1 and 15",
        )
        require(
            1 <= blob[profile_offset + 7] <= 4,
            f"{path}: class profile {index} Chill movement speed must be between 1 and 4",
        )
        require(
            (blob[profile_offset + OWBD_ALLOWED_TERRAIN_VALUE_OFFSET]
             | blob[profile_offset + OWBD_ALLOWED_TERRAIN_OVERRIDE_OFFSET])
            & ~OWBD_ALLOWED_TERRAIN_ALL == 0,
            f"{path}: class profile {index} has undefined terrain-policy bits",
        )
    for index in range(override_profile_count):
        profile_offset = override_profiles_offset + index * override_profile_size
        mask, mask2, mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 20)
        relative_mask, relative_mask2, relative_mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 80)
        at_least_mask, at_least_mask2, at_least_mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 92)
        at_most_mask, at_most_mask2, at_most_mask3 = struct.unpack_from("<I H 2x I", blob, profile_offset + 104)
        operator_mask = relative_mask | at_least_mask | at_most_mask
        if (mask & (1 << 7)) and not (operator_mask & (1 << 7)):
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + 7] <= 4,
                f"{path}: override profile {index} exact Chill speed must be between 1 and 4",
            )
        if mask & (1 << 15):
            require(
                1 <= blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + 15] <= 0xF,
                f"{path}: override profile {index} Next-to-player side mask must be between 1 and 15",
            )
        require((mask & ~OWBD_MASK_ALLOWED) == 0, f"{path}: override profile {index} mask has undefined bits")
        require((mask2 & ~OWBD_MASK2_ALLOWED) == 0, f"{path}: override profile {index} mask2 has undefined bits")
        require(
            (mask2 & OWBD_ALLOWED_TERRAIN_FIELD_BITS) in (0, OWBD_ALLOWED_TERRAIN_FIELD_BITS),
            f"{path}: override profile {index} must update both terrain-policy fields together",
        )
        require(
            (blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_ALLOWED_TERRAIN_VALUE_OFFSET]
             | blob[profile_offset + OWBD_OVERRIDE_PROFILE_VALUE_OFFSET + OWBD_ALLOWED_TERRAIN_OVERRIDE_OFFSET])
            & ~OWBD_ALLOWED_TERRAIN_ALL == 0,
            f"{path}: override profile {index} has undefined terrain-policy bits",
        )
        require((mask3 & ~OWBD_MASK3_ALLOWED) == 0, f"{path}: override profile {index} mask3 has undefined bits")
        require((relative_mask & ~mask) == 0, f"{path}: override profile {index} relative mask is not active")
        require((relative_mask2 & ~mask2) == 0, f"{path}: override profile {index} relative mask2 is not active")
        require((relative_mask3 & ~mask3) == 0, f"{path}: override profile {index} relative mask3 is not active")
        require((relative_mask & ~OWBD_RELATIVE_MASK_ALLOWED) == 0, f"{path}: override profile {index} has a non-numeric relative field")
        require((relative_mask2 & ~OWBD_RELATIVE_MASK2_ALLOWED) == 0, f"{path}: override profile {index} has a non-numeric relative field in mask2")
        require((relative_mask3 & ~OWBD_RELATIVE_MASK3_ALLOWED) == 0, f"{path}: override profile {index} has a non-numeric relative field in mask3")
        field_index = 0
        for operator_mask, width in zip((relative_mask, relative_mask2, relative_mask3), (27, 15, 4)):
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
                (27, 15, 4),
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
                        if field_index == 7:
                            require(blob[value_offset] != 0, f"{path}: override profile {index} movement speed bound must be at least 1")
                    field_index += 1
        for word, (relative_word, at_least_word, at_most_word) in enumerate(zip(
            (relative_mask, relative_mask2, relative_mask3),
            (at_least_mask, at_least_mask2, at_least_mask3),
            (at_most_mask, at_most_mask2, at_most_mask3),
        ), 1):
            require((at_least_word & at_most_word) == 0, f"{path}: override profile {index} has overlapping at-least/at-most mask{word}")
    range_end(path, "overrideMembers", override_members_offset, override_member_count, override_member_size, blob_size, 2, override_profiles_end)


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
