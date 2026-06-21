#!/usr/bin/env python3
"""Build the sparse overworld-wild encounter data sidecar."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path
from typing import Optional


OWED_MAGIC = 0x4F574544
OWED_VERSION = 2
OWED_HEADER_SIZE = 32
OWED_DIRECTORY_ENTRY_SIZE = 12
OWED_FLAGS = 0
OWED_CHECKSUM_OFFSET = 24

ENCOUNTER_DATA_SIZE = 196
SPECIES_MASK = 0x7FF

RATE_OLD_ROD = 3
RATE_GOOD_ROD = 4
RATE_SUPER_ROD = 5

SECTION_LAND_LEVELS = 1 << 0
SECTION_LAND_MORNING = 1 << 1
SECTION_LAND_DAY = 1 << 2
SECTION_LAND_NIGHT = 1 << 3
SECTION_SURF = 1 << 4
SECTION_OLD_ROD = 1 << 5
SECTION_GOOD_ROD = 1 << 6
SECTION_SUPER_ROD = 1 << 7

SECTIONS: tuple[tuple[int, int, int], ...] = (
    (SECTION_LAND_LEVELS, 8, 12),
    (SECTION_LAND_MORNING, 20, 24),
    (SECTION_LAND_DAY, 44, 24),
    (SECTION_LAND_NIGHT, 68, 24),
    (SECTION_SURF, 100, 20),
    (SECTION_OLD_ROD, 128, 20),
    (SECTION_GOOD_ROD, 148, 20),
    (SECTION_SUPER_ROD, 168, 20),
)


class EncounterMapping:
    def __init__(self, map_id: int, data_id: int) -> None:
        self.map_id = map_id
        self.data_id = data_id


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_defines(path: Path) -> dict[str, int]:
    define_re = re.compile(r"^\s*#\s*define\s+([A-Za-z0-9_]+)\s+((?:0x)?[0-9A-Fa-f]+)\b", re.MULTILINE)
    return {name: int(value, 0) for name, value in define_re.findall(path.read_text())}


def top_level_initializer_blocks(text: str, symbol: str) -> list[str]:
    symbol_index = text.find(symbol)
    require(symbol_index >= 0, f"could not find {symbol}")
    start = text.find("{", symbol_index)
    require(start >= 0, f"could not find initializer for {symbol}")

    blocks: list[str] = []
    depth = 0
    block_start: Optional[int] = None
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
            if depth == 2:
                block_start = index + 1
        elif char == "}":
            if depth == 2 and block_start is not None:
                blocks.append(text[block_start:index])
                block_start = None
            depth -= 1
            if depth == 0:
                break
    require(len(blocks) >= 3, f"could not parse {symbol} initializer")
    return blocks


def parse_mapping(source: Path, maps_header: Path) -> list[EncounterMapping]:
    defines = parse_defines(maps_header)
    blocks = top_level_initializer_blocks(source.read_text(), "gOverworldWildEncounterLookupDataBlob")
    map_tokens = re.findall(r"\bMAP_[A-Za-z0-9_]+\b", blocks[1])
    data_ids = [int(value, 10) for value in re.findall(r"\b[0-9]+\b", blocks[2])]
    require(len(map_tokens) == len(data_ids), "map/data-id list lengths differ")

    mappings: list[EncounterMapping] = []
    seen_maps: set[int] = set()
    for token, data_id in zip(map_tokens, data_ids):
        require(token in defines, f"unknown map symbol {token}")
        map_id = defines[token]
        require(map_id not in seen_maps, f"duplicate map id {map_id} ({token})")
        seen_maps.add(map_id)
        mappings.append(EncounterMapping(map_id=map_id, data_id=data_id))
    return mappings


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
    members: list[bytes] = []
    for member_index in range(member_count):
        start, end = struct.unpack_from("<II", blob, entries_offset + member_index * 8)
        require(start <= end and data_start + end <= len(blob), f"{path}: bad FAT range for member {member_index}")
        members.append(blob[data_start + start:data_start + end])
    return members


def any_species(slots: bytes) -> bool:
    require(len(slots) % 2 == 0, "species table has odd byte length")
    for offset in range(0, len(slots), 2):
        species = struct.unpack_from("<H", slots, offset)[0] & SPECIES_MASK
        if species != 0:
            return True
    return False


def any_slot_species(slots: bytes) -> bool:
    require(len(slots) % 4 == 0, "encounter slot table has odd byte length")
    for offset in range(0, len(slots), 4):
        species = struct.unpack_from("<H", slots, offset + 2)[0] & SPECIES_MASK
        if species != 0:
            return True
    return False


def section_is_present(data: bytes, mask: int, offset: int, size: int, land_has_species: bool) -> bool:
    section = data[offset:offset + size]
    if not any(section):
        return False
    if mask == SECTION_LAND_LEVELS:
        return land_has_species
    if mask in (SECTION_LAND_MORNING, SECTION_LAND_DAY, SECTION_LAND_NIGHT):
        return any_species(section)
    return any_slot_species(section)


def encode_sparse_record(data: bytes) -> bytes:
    require(len(data) >= ENCOUNTER_DATA_SIZE, "encounter record is smaller than expected")
    data = data[:ENCOUNTER_DATA_SIZE]
    land_has_species = (
        any_species(data[20:44])
        or any_species(data[44:68])
        or any_species(data[68:92])
    )

    present_sections: list[bytes] = []
    section_mask = 0
    for mask, offset, size in SECTIONS:
        if section_is_present(data, mask, offset, size, land_has_species):
            section_mask |= mask
            present_sections.append(data[offset:offset + size])

    return bytes((
        data[RATE_OLD_ROD],
        data[RATE_GOOD_ROD],
        data[RATE_SUPER_ROD],
        section_mask,
    )) + b"".join(present_sections)


def owed_checksum(blob: bytes) -> int:
    scratch = bytearray(blob)
    struct.pack_into("<I", scratch, OWED_CHECKSUM_OFFSET, 0)
    return sum(scratch) & 0xFFFFFFFF


def build_blob(mappings: list[EncounterMapping], encounter_members: list[bytes]) -> bytes:
    payload = bytearray()
    record_offsets: dict[bytes, int] = {}
    directory_entries: list[tuple[int, int, int, int, int]] = []
    payload_offset = OWED_HEADER_SIZE + len(mappings) * OWED_DIRECTORY_ENTRY_SIZE

    for mapping in mappings:
        require(mapping.data_id < len(encounter_members), f"data id {mapping.data_id} is outside encounter NARC")
        record = encode_sparse_record(encounter_members[mapping.data_id])
        if record not in record_offsets:
            record_offsets[record] = payload_offset + len(payload)
            payload.extend(record)
        directory_entries.append((
            mapping.map_id,
            mapping.data_id,
            record_offsets[record],
            len(record),
            0,
        ))

    directory = bytearray()
    for entry in directory_entries:
        directory.extend(struct.pack("<HHIHH", *entry))

    total_size = OWED_HEADER_SIZE + len(directory) + len(payload)
    header = struct.pack(
        "<IHHHHIIIII",
        OWED_MAGIC,
        OWED_VERSION,
        OWED_HEADER_SIZE,
        len(directory_entries),
        OWED_DIRECTORY_ENTRY_SIZE,
        OWED_HEADER_SIZE,
        payload_offset,
        total_size,
        0,
        OWED_FLAGS,
    )
    blob = bytearray(header + directory + payload)
    checksum = owed_checksum(blob)
    struct.pack_into("<I", blob, 24, checksum)
    return bytes(blob)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/OverworldWildEncounterLookupData.c"))
    parser.add_argument("--maps-header", type=Path, default=Path("include/constants/maps.h"))
    parser.add_argument("--encounter-narc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        mappings = parse_mapping(args.source, args.maps_header)
        encounter_members = read_narc_members(args.encounter_narc)
        blob = build_blob(mappings, encounter_members)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(blob)
    print(
        f"wrote OWED v2: {len(mappings)} map entries, "
        f"{len({entry[2] for entry in struct.iter_unpack('<HHIHH', blob[OWED_HEADER_SIZE:OWED_HEADER_SIZE + len(mappings) * OWED_DIRECTORY_ENTRY_SIZE])})} "
        f"unique sparse records, {len(blob)} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
