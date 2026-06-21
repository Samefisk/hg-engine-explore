#!/usr/bin/env python3
"""Validate generated overworld-wild code-addon blob metadata."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


OWBD_MAGIC = 0x4F574244
OWBD_VERSION = 18
OWBD_HEADER_SIZE = 44
OWBD_PROFILE_COUNT = 8
OWBD_CLASS_RULE_COUNT = 2
OWBD_SPECIES_RULE_COUNT = 110
OWBD_OVERRIDE_COUNT = 2
OWBD_PROFILE_SIZE = 66
OWBD_CLASS_RULE_SIZE = 16
OWBD_SPECIES_RULE_SIZE = 4
OWBD_OVERRIDE_SIZE = 92

OWED_MAGIC = 0x4F574544
OWED_VERSION = 1
OWED_HEADER_SIZE = 24
OWED_COUNT = 150


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_owbd(path: Path) -> None:
    blob = path.read_bytes()
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
    require(class_profile_count == OWBD_PROFILE_COUNT, f"{path}: bad class profile count")
    require(class_rule_count == OWBD_CLASS_RULE_COUNT, f"{path}: bad class rule count")
    require(species_rule_count == OWBD_SPECIES_RULE_COUNT, f"{path}: bad species class rule count")
    require(override_count == OWBD_OVERRIDE_COUNT, f"{path}: bad override count")
    require(class_profile_size == OWBD_PROFILE_SIZE, f"{path}: bad class profile element size")
    require(class_rule_size == OWBD_CLASS_RULE_SIZE, f"{path}: bad class rule element size")
    require(species_rule_size == OWBD_SPECIES_RULE_SIZE, f"{path}: bad species class rule element size")
    require(override_size == OWBD_OVERRIDE_SIZE, f"{path}: bad override element size")

    expected_class_rules_offset = class_profiles_offset + class_profile_count * class_profile_size
    expected_species_rules_offset = class_rules_offset + class_rule_count * class_rule_size
    expected_overrides_offset = species_rules_offset + species_rule_count * species_rule_size
    expected_end = overrides_offset + override_count * override_size
    require(class_profiles_offset == OWBD_HEADER_SIZE, f"{path}: bad class profile offset")
    require(class_rules_offset == expected_class_rules_offset, f"{path}: bad class rule offset")
    require(species_rules_offset == expected_species_rules_offset, f"{path}: bad species class rule offset")
    require(overrides_offset == expected_overrides_offset, f"{path}: bad override offset")
    require(expected_end <= len(blob), f"{path}: OWBD arrays extend past blob size")


def validate_owed(path: Path) -> None:
    blob = path.read_bytes()
    require(len(blob) >= OWED_HEADER_SIZE, f"{path}: truncated OWED header")
    fields = struct.unpack_from("<IHHI IIHH", blob, 0)
    magic, version, header_size, blob_size, map_ids_offset, data_ids_offset, count, reserved = fields

    require(magic == OWED_MAGIC, f"{path}: bad OWED magic")
    require(version == OWED_VERSION, f"{path}: bad OWED version")
    require(header_size == OWED_HEADER_SIZE, f"{path}: bad OWED header size")
    require(blob_size == len(blob), f"{path}: OWED blob size does not match file size")
    require(count == OWED_COUNT, f"{path}: bad OWED entry count")
    require(reserved == 0, f"{path}: bad OWED reserved value")
    require(map_ids_offset == OWED_HEADER_SIZE, f"{path}: bad OWED map-id offset")
    require(data_ids_offset == map_ids_offset + count * 2, f"{path}: bad OWED data-id offset")
    require(data_ids_offset + count <= len(blob), f"{path}: OWED arrays extend past blob size")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owbd", type=Path)
    parser.add_argument("--owed", type=Path)
    args = parser.parse_args()
    try:
        if args.owbd is not None:
            validate_owbd(args.owbd)
        if args.owed is not None:
            validate_owed(args.owed)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
