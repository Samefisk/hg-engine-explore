#!/usr/bin/env python3
"""Validate generated overworld-wild code-addon blob metadata."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path


OWBD_MAGIC = 0x4F574244
OWBD_VERSION = 18
OWBD_HEADER_SIZE = 44
OWBD_PROFILE_SIZE = 66
OWBD_CLASS_RULE_SIZE = 16
OWBD_SPECIES_RULE_SIZE = 4
OWBD_OVERRIDE_SIZE = 92

OWED_MAGIC = 0x4F574544
OWED_VERSION = 1
OWED_HEADER_SIZE = 24

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


def validate_owbd(path: Path, source: Path) -> None:
    blob = path.read_bytes()
    expected_class_profile_count = read_define(source, "OWBD_CLASS_PROFILE_COUNT")
    expected_class_rule_count = read_define(source, "OWBD_CLASS_RULE_COUNT")
    expected_species_rule_count = read_define(source, "OWBD_SPECIES_CLASS_RULE_COUNT")
    expected_override_count = read_define(source, "OWBD_OVERRIDE_COUNT")
    require(len(blob) >= OWBD_HEADER_SIZE, f"{path}: truncated OWBD header")
    fields = struct.unpack_from("<IHHI IHH IHH IHH IHH", blob, 0)
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
        overrides_offset,
        override_count,
        override_size,
    ) = fields

    require(magic == OWBD_MAGIC, f"{path}: bad OWBD magic")
    require(version == OWBD_VERSION, f"{path}: bad OWBD version")
    require(header_size == OWBD_HEADER_SIZE, f"{path}: bad OWBD header size")
    require(blob_size == len(blob), f"{path}: OWBD blob size does not match file size")
    require(class_profile_count == expected_class_profile_count, f"{path}: bad class profile count")
    require(class_rule_count == expected_class_rule_count, f"{path}: bad class rule count")
    require(species_rule_count == expected_species_rule_count, f"{path}: bad species class rule count")
    require(override_count == expected_override_count, f"{path}: bad override count")
    require(class_profile_size == OWBD_PROFILE_SIZE, f"{path}: bad class profile element size")
    require(class_rule_size == OWBD_CLASS_RULE_SIZE, f"{path}: bad class rule element size")
    require(species_rule_size == OWBD_SPECIES_RULE_SIZE, f"{path}: bad species class rule element size")
    require(override_size == OWBD_OVERRIDE_SIZE, f"{path}: bad override element size")

    class_profiles_end = range_end(path, "classProfiles", class_profiles_offset, class_profile_count, class_profile_size, blob_size, 2, header_size)
    class_rules_end = range_end(path, "classRules", class_rules_offset, class_rule_count, class_rule_size, blob_size, 4, class_profiles_end)
    species_rules_end = range_end(path, "speciesClassRules", species_rules_offset, species_rule_count, species_rule_size, blob_size, 2, class_rules_end)
    range_end(path, "overrides", overrides_offset, override_count, override_size, blob_size, 4, species_rules_end)


def validate_owed(path: Path, source: Path, encounter_narc: Path | None) -> None:
    blob = path.read_bytes()
    expected_count = read_define(source, "OWED_ENCOUNTER_AREA_COUNT")
    require(len(blob) >= OWED_HEADER_SIZE, f"{path}: truncated OWED header")
    fields = struct.unpack_from("<IHHI IIHH", blob, 0)
    magic, version, header_size, blob_size, map_ids_offset, data_ids_offset, count, reserved = fields

    require(magic == OWED_MAGIC, f"{path}: bad OWED magic")
    require(version == OWED_VERSION, f"{path}: bad OWED version")
    require(header_size == OWED_HEADER_SIZE, f"{path}: bad OWED header size")
    require(blob_size == len(blob), f"{path}: OWED blob size does not match file size")
    require(count == expected_count, f"{path}: bad OWED entry count")
    require(reserved == 0, f"{path}: bad OWED reserved value")
    map_ids_end = range_end(path, "mapIds", map_ids_offset, count, 2, blob_size, 2, header_size)
    range_end(path, "dataIds", data_ids_offset, count, 1, blob_size, 1, map_ids_end)

    if encounter_narc is not None:
        encounter_count = narc_member_count(encounter_narc)
        data_ids = blob[data_ids_offset:data_ids_offset + count]
        bad_ids = [data_id for data_id in data_ids if data_id >= encounter_count]
        if bad_ids:
            raise ValueError(f"{path}: OWED dataId {bad_ids[0]} is outside encounter NARC member count {encounter_count}")


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
