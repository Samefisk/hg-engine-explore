#!/usr/bin/env python3
"""Build and validate compact overworld-wild encounter data.

The stock encounter archive stays in its legacy 196-byte member format because
normal wild encounters still read it. This script builds an overworld-only
sidecar with the fields the visible-spawn roller actually uses.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "build/a037"
DEFAULT_OUTPUT = ROOT / "build/OverworldWildEncounterData.bin"

MAGIC = b"OWED"
VERSION = 1
HEADER_FORMAT = "<4sHHHHII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
CHECKSUM_OFFSET = 16
CHECKSUM_SIZE = 4

LEGACY_RECORD_SIZE = 196
COMPACT_RECORD_SIZE = 168

LEGACY_LEVELS_OFFSET = 8
LEGACY_LAND_SPECIES_OFFSET = 20
LEGACY_SURF_OFFSET = 100
LEGACY_OLD_ROD_OFFSET = 128
LEGACY_GOOD_ROD_OFFSET = 148
LEGACY_SUPER_ROD_OFFSET = 168

COMPACT_LEVELS_OFFSET = 4
COMPACT_LAND_SPECIES_OFFSET = 16
COMPACT_SURF_OFFSET = 88
COMPACT_OLD_ROD_OFFSET = 108
COMPACT_GOOD_ROD_OFFSET = 128
COMPACT_SUPER_ROD_OFFSET = 148


class OwedError(Exception):
    pass


def checksum_for(blob: bytes | bytearray) -> int:
    checksum = 0
    for index, value in enumerate(blob):
        if CHECKSUM_OFFSET <= index < CHECKSUM_OFFSET + CHECKSUM_SIZE:
            value = 0
        checksum = (checksum + value) & 0xFFFFFFFF
    return checksum


def sorted_legacy_members(input_dir: Path) -> list[Path]:
    members = sorted(input_dir.glob("7_*"))
    if not members:
        raise OwedError(f"no legacy encounter members found in {input_dir}")
    return members


def read_legacy_records(input_dir: Path) -> list[bytes]:
    records: list[bytes] = []
    for expected, path in enumerate(sorted_legacy_members(input_dir)):
        try:
            member_id = int(path.name.split("_", 1)[1])
        except (IndexError, ValueError) as exc:
            raise OwedError(f"bad encounter member name {path.name}") from exc
        if member_id != expected:
            raise OwedError(f"expected member {expected}, got {path.name}")
        data = path.read_bytes()
        if len(data) != LEGACY_RECORD_SIZE:
            raise OwedError(
                f"{path} is {len(data)} bytes; expected {LEGACY_RECORD_SIZE}"
            )
        records.append(data)
    return records


def validate_species(value: int, context: str) -> None:
    species = value & 0x07FF
    form = value >> 11
    if species > 0x07FF:
        raise OwedError(f"{context} species {species} exceeds packed species mask")
    if form > 0x1F:
        raise OwedError(f"{context} form {form} exceeds packed form mask")


def validate_slot(data: bytes, offset: int, context: str) -> None:
    min_level = data[offset]
    max_level = data[offset + 1]
    species = struct.unpack_from("<H", data, offset + 2)[0]
    validate_species(species, context)
    if min_level > max_level:
        raise OwedError(f"{context} min level {min_level} exceeds max {max_level}")
    if species == 0 and (min_level != 0 or max_level != 0):
        raise OwedError(f"{context} has levels for SPECIES_NONE")


def validate_legacy_record(data: bytes, record_index: int) -> None:
    for slot in range(36):
        offset = LEGACY_LAND_SPECIES_OFFSET + slot * 2
        species = struct.unpack_from("<H", data, offset)[0]
        validate_species(species, f"encounter {record_index} land species {slot}")

    for table_name, offset, count in (
        ("surf", LEGACY_SURF_OFFSET, 5),
        ("old rod", LEGACY_OLD_ROD_OFFSET, 5),
        ("good rod", LEGACY_GOOD_ROD_OFFSET, 5),
        ("super rod", LEGACY_SUPER_ROD_OFFSET, 5),
    ):
        for slot in range(count):
            validate_slot(
                data,
                offset + slot * 4,
                f"encounter {record_index} {table_name} slot {slot}",
            )


def compact_record_from_legacy(data: bytes, record_index: int) -> bytes:
    validate_legacy_record(data, record_index)

    compact = bytearray(COMPACT_RECORD_SIZE)
    compact[0] = data[3]  # old rod rate
    compact[1] = data[4]  # good rod rate
    compact[2] = data[5]  # super rod rate
    compact[
        COMPACT_LEVELS_OFFSET : COMPACT_LEVELS_OFFSET + 12
    ] = data[LEGACY_LEVELS_OFFSET : LEGACY_LEVELS_OFFSET + 12]
    compact[
        COMPACT_LAND_SPECIES_OFFSET : COMPACT_LAND_SPECIES_OFFSET + 72
    ] = data[LEGACY_LAND_SPECIES_OFFSET : LEGACY_LAND_SPECIES_OFFSET + 72]
    compact[COMPACT_SURF_OFFSET : COMPACT_SURF_OFFSET + 20] = data[
        LEGACY_SURF_OFFSET : LEGACY_SURF_OFFSET + 20
    ]
    compact[COMPACT_OLD_ROD_OFFSET : COMPACT_OLD_ROD_OFFSET + 20] = data[
        LEGACY_OLD_ROD_OFFSET : LEGACY_OLD_ROD_OFFSET + 20
    ]
    compact[COMPACT_GOOD_ROD_OFFSET : COMPACT_GOOD_ROD_OFFSET + 20] = data[
        LEGACY_GOOD_ROD_OFFSET : LEGACY_GOOD_ROD_OFFSET + 20
    ]
    compact[COMPACT_SUPER_ROD_OFFSET : COMPACT_SUPER_ROD_OFFSET + 20] = data[
        LEGACY_SUPER_ROD_OFFSET : LEGACY_SUPER_ROD_OFFSET + 20
    ]
    return bytes(compact)


def ow_fields_from_legacy(data: bytes) -> dict[str, bytes | int]:
    return {
        "oldRodRate": data[3],
        "goodRodRate": data[4],
        "superRodRate": data[5],
        "levels": data[LEGACY_LEVELS_OFFSET : LEGACY_LEVELS_OFFSET + 12],
        "landSpecies": data[LEGACY_LAND_SPECIES_OFFSET : LEGACY_LAND_SPECIES_OFFSET + 72],
        "surf": data[LEGACY_SURF_OFFSET : LEGACY_SURF_OFFSET + 20],
        "oldRod": data[LEGACY_OLD_ROD_OFFSET : LEGACY_OLD_ROD_OFFSET + 20],
        "goodRod": data[LEGACY_GOOD_ROD_OFFSET : LEGACY_GOOD_ROD_OFFSET + 20],
        "superRod": data[LEGACY_SUPER_ROD_OFFSET : LEGACY_SUPER_ROD_OFFSET + 20],
    }


def ow_fields_from_compact(data: bytes) -> dict[str, bytes | int]:
    if len(data) != COMPACT_RECORD_SIZE:
        raise OwedError(f"compact record is {len(data)} bytes")
    return {
        "oldRodRate": data[0],
        "goodRodRate": data[1],
        "superRodRate": data[2],
        "levels": data[COMPACT_LEVELS_OFFSET : COMPACT_LEVELS_OFFSET + 12],
        "landSpecies": data[COMPACT_LAND_SPECIES_OFFSET : COMPACT_LAND_SPECIES_OFFSET + 72],
        "surf": data[COMPACT_SURF_OFFSET : COMPACT_SURF_OFFSET + 20],
        "oldRod": data[COMPACT_OLD_ROD_OFFSET : COMPACT_OLD_ROD_OFFSET + 20],
        "goodRod": data[COMPACT_GOOD_ROD_OFFSET : COMPACT_GOOD_ROD_OFFSET + 20],
        "superRod": data[COMPACT_SUPER_ROD_OFFSET : COMPACT_SUPER_ROD_OFFSET + 20],
    }


def build_blob(records: list[bytes]) -> bytes:
    if len(records) > 0xFFFF:
        raise OwedError(f"too many encounter records: {len(records)}")

    compact_records = [
        compact_record_from_legacy(record, index) for index, record in enumerate(records)
    ]
    total_size = HEADER_SIZE + len(compact_records) * COMPACT_RECORD_SIZE
    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        COMPACT_RECORD_SIZE,
        len(compact_records),
        total_size,
        0,
    )
    blob = bytearray(header)
    for compact in compact_records:
        blob.extend(compact)
    struct.pack_into("<I", blob, CHECKSUM_OFFSET, checksum_for(blob))
    return bytes(blob)


def read_header(blob: bytes) -> dict[str, int | bytes]:
    if len(blob) < HEADER_SIZE:
        raise OwedError(f"blob is {len(blob)} bytes; expected at least {HEADER_SIZE}")
    magic, version, header_size, record_size, record_count, total_size, checksum = (
        struct.unpack_from(HEADER_FORMAT, blob, 0)
    )
    return {
        "magic": magic,
        "version": version,
        "headerSize": header_size,
        "recordSize": record_size,
        "recordCount": record_count,
        "totalSize": total_size,
        "checksum": checksum,
    }


def validate_blob(blob: bytes) -> dict[str, int | bytes]:
    header = read_header(blob)
    if header["magic"] != MAGIC:
        raise OwedError(f"bad magic {header['magic']!r}; expected {MAGIC!r}")
    if header["version"] != VERSION:
        raise OwedError(f"unsupported version {header['version']}; expected {VERSION}")
    if header["headerSize"] != HEADER_SIZE:
        raise OwedError(
            f"header size {header['headerSize']} does not match {HEADER_SIZE}"
        )
    if header["recordSize"] != COMPACT_RECORD_SIZE:
        raise OwedError(
            f"record size {header['recordSize']} does not match {COMPACT_RECORD_SIZE}"
        )
    if header["totalSize"] != len(blob):
        raise OwedError(f"total size {header['totalSize']} does not match {len(blob)}")
    expected_size = HEADER_SIZE + int(header["recordCount"]) * COMPACT_RECORD_SIZE
    if header["totalSize"] != expected_size:
        raise OwedError(
            f"total size {header['totalSize']} does not match records {expected_size}"
        )
    if header["checksum"] != checksum_for(blob):
        raise OwedError("checksum mismatch")
    return header


def validate_roundtrip(blob: bytes, input_dir: Path) -> None:
    header = validate_blob(blob)
    legacy_records = read_legacy_records(input_dir)
    record_count = int(header["recordCount"])
    if len(legacy_records) != record_count:
        raise OwedError(
            f"legacy record count {len(legacy_records)} does not match compact {record_count}"
        )
    for index, legacy in enumerate(legacy_records):
        offset = HEADER_SIZE + index * COMPACT_RECORD_SIZE
        compact = blob[offset : offset + COMPACT_RECORD_SIZE]
        if ow_fields_from_compact(compact) != ow_fields_from_legacy(legacy):
            raise OwedError(f"compact record {index} does not match legacy OW fields")


def write_blob(output: Path, input_dir: Path) -> None:
    records = read_legacy_records(input_dir)
    blob = build_blob(records)
    validate_roundtrip(blob, input_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    legacy_size = len(records) * LEGACY_RECORD_SIZE
    compact_payload_size = len(records) * COMPACT_RECORD_SIZE
    print(
        "OW encounter compact records: "
        f"{len(records)} records, {legacy_size} -> {compact_payload_size} bytes "
        f"({legacy_size - compact_payload_size} bytes sidecar payload saving; "
        f"{len(blob)} bytes with header)"
    )


def validate_path(path: Path, input_dir: Path | None, dump_json: bool) -> None:
    blob = path.read_bytes()
    header = validate_blob(blob)
    if input_dir is not None:
        validate_roundtrip(blob, input_dir)
    if dump_json:
        printable = dict(header)
        printable["magic"] = header["magic"].decode("ascii")
        print(json.dumps(printable, indent=2, sort_keys=True))
    else:
        print(f"validated {path} ({header['totalSize']} bytes)")


def run_probe() -> None:
    legacy = bytearray(LEGACY_RECORD_SIZE)
    legacy[3] = 25
    legacy[4] = 50
    legacy[5] = 75
    legacy[LEGACY_LEVELS_OFFSET : LEGACY_LEVELS_OFFSET + 12] = bytes(range(1, 13))
    for slot in range(36):
        struct.pack_into("<H", legacy, LEGACY_LAND_SPECIES_OFFSET + slot * 2, slot + 1)
    for offset, base_level, base_species in (
        (LEGACY_SURF_OFFSET, 10, 100),
        (LEGACY_OLD_ROD_OFFSET, 20, 200),
        (LEGACY_GOOD_ROD_OFFSET, 30, 300),
        (LEGACY_SUPER_ROD_OFFSET, 40, 400),
    ):
        for slot in range(5):
            legacy[offset + slot * 4] = base_level + slot
            legacy[offset + slot * 4 + 1] = base_level + slot + 1
            struct.pack_into("<H", legacy, offset + slot * 4 + 2, base_species + slot)

    blob = build_blob([bytes(legacy)])
    validate_blob(blob)
    compact = blob[HEADER_SIZE:]
    if ow_fields_from_compact(compact) != ow_fields_from_legacy(bytes(legacy)):
        raise OwedError("probe compact fields did not match legacy fields")

    mutated = bytearray(blob)
    mutated[-1] ^= 0xFF
    try:
        validate_blob(mutated)
    except OwedError as exc:
        if "checksum mismatch" not in str(exc):
            raise
    else:
        raise OwedError("probe accepted payload mutation")

    print(
        "validated OW encounter compact probe "
        f"({LEGACY_RECORD_SIZE} -> {COMPACT_RECORD_SIZE} bytes per record)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="write the compact OWED blob")
    build_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    build_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)

    validate_parser = subparsers.add_parser("validate", help="validate an OWED blob")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--input-dir", type=Path)
    validate_parser.add_argument("--dump-json", action="store_true")

    subparsers.add_parser("probe", help="run an in-memory codec sanity check")

    args = parser.parse_args()
    try:
        if args.command == "build":
            write_blob(args.output, args.input_dir)
        elif args.command == "validate":
            validate_path(args.path, args.input_dir, args.dump_json)
        elif args.command == "probe":
            run_probe()
    except OwedError as exc:
        raise SystemExit(f"OWED error: {exc}") from exc


if __name__ == "__main__":
    main()
