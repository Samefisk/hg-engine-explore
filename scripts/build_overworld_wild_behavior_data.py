#!/usr/bin/env python3
"""Build and validate the pointerless OWBD resource stub."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path


MAGIC = b"OWBD"
VERSION = 1
HEADER_FORMAT = "<4sHHIIHHHHIIIIHHHHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

SECTION_NAMES = (
    "profiles",
    "class_rules",
    "species_rules",
    "variable_overrides",
)


class OwbdError(ValueError):
    pass


def checksum_for(blob: bytes) -> int:
    if len(blob) < 4:
        raise OwbdError("OWBD blob is too small to contain a checksum")
    return zlib.crc32(blob[:-4] + b"\0\0\0\0") & 0xFFFFFFFF


def pack_header(checksum: int = 0) -> bytes:
    return struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        HEADER_SIZE,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        checksum,
    )


def build_dummy_blob() -> bytes:
    blob = pack_header()
    return pack_header(checksum_for(blob))


def read_header(blob: bytes) -> dict[str, object]:
    if len(blob) < HEADER_SIZE:
        raise OwbdError(f"OWBD blob is {len(blob)} bytes, expected at least {HEADER_SIZE}")

    (
        magic,
        version,
        header_size,
        total_size,
        payload_size,
        profile_count,
        class_rule_count,
        species_rule_count,
        variable_override_count,
        profiles_offset,
        class_rules_offset,
        species_rules_offset,
        variable_overrides_offset,
        profile_size,
        class_rule_size,
        species_rule_size,
        variable_override_size,
        checksum,
    ) = struct.unpack_from(HEADER_FORMAT, blob)

    return {
        "magic": magic,
        "version": version,
        "header_size": header_size,
        "total_size": total_size,
        "payload_size": payload_size,
        "counts": {
            "profiles": profile_count,
            "class_rules": class_rule_count,
            "species_rules": species_rule_count,
            "variable_overrides": variable_override_count,
        },
        "offsets": {
            "profiles": profiles_offset,
            "class_rules": class_rules_offset,
            "species_rules": species_rules_offset,
            "variable_overrides": variable_overrides_offset,
        },
        "element_sizes": {
            "profiles": profile_size,
            "class_rules": class_rule_size,
            "species_rules": species_rule_size,
            "variable_overrides": variable_override_size,
        },
        "checksum": checksum,
    }


def validate_blob(blob: bytes) -> dict[str, object]:
    header = read_header(blob)

    if header["magic"] != MAGIC:
        raise OwbdError(f"bad magic {header['magic']!r}; expected {MAGIC!r}")
    if header["version"] != VERSION:
        raise OwbdError(f"unsupported OWBD version {header['version']}; expected {VERSION}")
    if header["header_size"] != HEADER_SIZE:
        raise OwbdError(
            f"bad header size {header['header_size']}; expected {HEADER_SIZE}"
        )
    if header["total_size"] != len(blob):
        raise OwbdError(f"total size {header['total_size']} does not match {len(blob)}")
    if header["payload_size"] != len(blob) - HEADER_SIZE:
        raise OwbdError(
            f"payload size {header['payload_size']} does not match "
            f"{len(blob) - HEADER_SIZE}"
        )
    if header["checksum"] != checksum_for(blob):
        raise OwbdError("checksum mismatch")

    ranges: list[tuple[int, int, str]] = []
    counts = header["counts"]
    offsets = header["offsets"]
    element_sizes = header["element_sizes"]

    for name in SECTION_NAMES:
        count = int(counts[name])
        offset = int(offsets[name])
        element_size = int(element_sizes[name])

        if count == 0:
            if offset != 0:
                raise OwbdError(f"{name} offset must be 0 when count is 0")
            if element_size != 0:
                raise OwbdError(f"{name} element size must be 0 when count is 0")
            continue

        if element_size == 0:
            raise OwbdError(f"{name} element size must be non-zero when count is non-zero")
        if offset < HEADER_SIZE:
            raise OwbdError(f"{name} offset {offset} is before the end of the header")
        if offset % 4 != 0:
            raise OwbdError(f"{name} offset {offset} is not 4-byte aligned")

        byte_count = count * element_size
        end = offset + byte_count
        if end > len(blob):
            raise OwbdError(f"{name} range {offset}..{end} exceeds blob size {len(blob)}")
        ranges.append((offset, end, name))

    ranges.sort()
    for (_, previous_end, previous_name), (next_start, _, next_name) in zip(
        ranges, ranges[1:]
    ):
        if next_start < previous_end:
            raise OwbdError(f"{previous_name} overlaps {next_name}")

    return header


def write_blob(output: Path) -> None:
    blob = build_dummy_blob()
    validate_blob(blob)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    print(f"wrote {output} ({len(blob)} bytes)")


def validate_path(path: Path, dump_json: bool) -> None:
    header = validate_blob(path.read_bytes())
    if dump_json:
        printable = {
            **header,
            "magic": header["magic"].decode("ascii"),
        }
        print(json.dumps(printable, indent=2, sort_keys=True))
    else:
        print(f"validated {path} ({header['total_size']} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="write the dummy OWBD blob")
    build_parser.add_argument("--output", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate", help="validate an OWBD blob")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--json", action="store_true", help="dump parsed header")

    args = parser.parse_args()

    try:
        if args.command == "build":
            write_blob(args.output)
        elif args.command == "validate":
            validate_path(args.path, args.json)
        else:
            parser.error(f"unknown command {args.command}")
    except OwbdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
