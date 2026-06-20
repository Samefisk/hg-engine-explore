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
CHECKSUM_OFFSET = struct.calcsize("<4sHHIIHHHHIIIIHHHH")
CHECKSUM_SIZE = 4

SECTION_NAMES = (
    "profiles",
    "class_rules",
    "species_rules",
    "variable_overrides",
)


class OwbdError(ValueError):
    pass


def checksum_for(blob: bytes) -> int:
    checksum_end = CHECKSUM_OFFSET + CHECKSUM_SIZE
    if len(blob) < checksum_end:
        raise OwbdError("OWBD blob is too small to contain a checksum field")
    work = bytearray(blob)
    work[CHECKSUM_OFFSET:checksum_end] = b"\0" * CHECKSUM_SIZE
    return zlib.crc32(work) & 0xFFFFFFFF


def pack_header(
    *,
    total_size: int = HEADER_SIZE,
    payload_size: int = 0,
    counts: tuple[int, int, int, int] = (0, 0, 0, 0),
    offsets: tuple[int, int, int, int] = (0, 0, 0, 0),
    element_sizes: tuple[int, int, int, int] = (0, 0, 0, 0),
    checksum: int = 0,
) -> bytes:
    return struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        total_size,
        payload_size,
        *counts,
        *offsets,
        *element_sizes,
        checksum,
    )


def build_dummy_blob() -> bytes:
    blob = pack_header()
    return pack_header(checksum=checksum_for(blob))


def build_probe_blob(payload: bytes = b"\x01\x02\x03\x04") -> bytes:
    blob = (
        pack_header(
            total_size=HEADER_SIZE + len(payload),
            payload_size=len(payload),
            counts=(1, 0, 0, 0),
            offsets=(HEADER_SIZE, 0, 0, 0),
            element_sizes=(len(payload), 0, 0, 0),
        )
        + payload
    )
    return (
        pack_header(
            total_size=len(blob),
            payload_size=len(payload),
            counts=(1, 0, 0, 0),
            offsets=(HEADER_SIZE, 0, 0, 0),
            element_sizes=(len(payload), 0, 0, 0),
            checksum=checksum_for(blob),
        )
        + payload
    )


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


def run_probe() -> None:
    blob = build_probe_blob()
    header = validate_blob(blob)
    checksum_end = CHECKSUM_OFFSET + CHECKSUM_SIZE
    if checksum_end == len(blob):
        raise OwbdError("probe checksum field unexpectedly sits at EOF")

    mutated = bytearray(blob)
    mutated[-1] ^= 0xFF
    try:
        validate_blob(mutated)
    except OwbdError as exc:
        if "checksum mismatch" not in str(exc):
            raise
    else:
        raise OwbdError("probe accepted a payload mutation")

    trailing_zero_blob = build_probe_blob(b"\x01\x02\x03\x04\0\0\0\0")
    trailing_zero_header = validate_blob(trailing_zero_blob)
    old_style_checksum = zlib.crc32(trailing_zero_blob[:-4] + b"\0\0\0\0") & 0xFFFFFFFF
    if old_style_checksum == trailing_zero_header["checksum"]:
        raise OwbdError("probe checksum is still compatible with zeroing the last 4 bytes")

    print(
        "validated non-empty OWBD probe "
        f"({header['total_size']} bytes, checksum offset {CHECKSUM_OFFSET})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="write the dummy OWBD blob")
    build_parser.add_argument("--output", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate", help="validate an OWBD blob")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--json", action="store_true", help="dump parsed header")

    subparsers.add_parser(
        "probe",
        help="validate an in-memory non-empty OWBD blob with payload after the header",
    )

    args = parser.parse_args()

    try:
        if args.command == "build":
            write_blob(args.output)
        elif args.command == "validate":
            validate_path(args.path, args.json)
        elif args.command == "probe":
            run_probe()
        else:
            parser.error(f"unknown command {args.command}")
    except OwbdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
