#!/usr/bin/env python3
"""Build and validate the headbutt-tree NARC.

The runtime and vanilla field code address ARC_HEADBUTT_TREES by map id.  To
keep that contract intact while avoiding hundreds of duplicate empty payloads,
this packer preserves every member id and aliases empty members to one shared
four-byte empty header in the GMIF data section.
"""

from __future__ import annotations

import argparse
import re
import struct
import tempfile
from pathlib import Path

import ndspy.narc


EMPTY_HEADBUTT_HEADER = b"\0\0\0\0"
HEADBUTT_HEADER_SIZE = 4
HEADBUTT_SLOT_SIZE = 4
HEADBUTT_SLOT_COUNT = 18
HEADBUTT_TREE_SIZE = 24
HEADER_RE = re.compile(r"^headbuttheader\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
TREECOORDS_RE = re.compile(r"^\s*treecoords\b")
ENCOUNTER_RE = re.compile(r"^\s*headbuttencounter(?:withform)?\b")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def member_sort_key(path: Path) -> int:
    require(path.name.isdigit(), f"{path}: headbutt member filename is not numeric")
    return int(path.name, 10)


def read_stage_members(input_dir: Path) -> list[bytes]:
    require(input_dir.is_dir(), f"{input_dir}: input directory does not exist")
    paths = sorted((p for p in input_dir.iterdir() if p.is_file()), key=member_sort_key)
    require(paths, f"{input_dir}: no headbutt members found")
    ids = [member_sort_key(path) for path in paths]
    require(ids == list(range(ids[-1] + 1)), f"{input_dir}: headbutt member ids are not contiguous")
    return [path.read_bytes() for path in paths]


def expected_member_size(record: dict[str, int]) -> int:
    tree_count = record["normal"] + record["special"]
    if tree_count == 0:
        return HEADBUTT_HEADER_SIZE
    return HEADBUTT_HEADER_SIZE + HEADBUTT_SLOT_COUNT * HEADBUTT_SLOT_SIZE + tree_count * HEADBUTT_TREE_SIZE


def create_standard_narc(members: list[bytes]) -> bytearray:
    narc = ndspy.narc.NARC.fromFilesAndNames(files=members)
    narc.endiannessOfBeginning = ">"
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        narc.saveToFile(str(tmp_path))
        data = bytearray(tmp_path.read_bytes())
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass

    fntb_offset = data.find(b"BTNF")
    require(fntb_offset >= 0, "generated NARC is missing BTNF")

    # Match tools/narcpy.py's HGSS empty-FNTB shape.
    file_size = struct.unpack_from("<I", data, 8)[0] - 4
    struct.pack_into("<I", data, 8, file_size)
    data[fntb_offset + 4] = 0x10
    data[fntb_offset + 8] = 0x04
    del data[fntb_offset + 0x10:fntb_offset + 0x14]
    return data


def compact_empty_members(narc: bytearray, members: list[bytes]) -> bytearray:
    fat_offset = narc.find(b"BTAF")
    fimg_offset = narc.find(b"GMIF")
    require(fat_offset >= 0, "generated NARC is missing BTAF")
    require(fimg_offset >= 0, "generated NARC is missing GMIF")
    require(struct.unpack_from("<I", narc, fat_offset + 8)[0] == len(members), "generated NARC member count mismatch")

    compact_data = bytearray()
    empty_range: tuple[int, int] | None = None
    ranges: list[tuple[int, int]] = []

    for member in members:
        if member == EMPTY_HEADBUTT_HEADER:
            if empty_range is None:
                start = len(compact_data)
                compact_data.extend(EMPTY_HEADBUTT_HEADER)
                empty_range = (start, start + len(EMPTY_HEADBUTT_HEADER))
            ranges.append(empty_range)
            continue

        start = len(compact_data)
        compact_data.extend(member)
        end = len(compact_data)
        compact_data.extend(b"\xFF" * ((4 - (len(member) % 4)) % 4))
        ranges.append((start, end))

    for index, (start, end) in enumerate(ranges):
        struct.pack_into("<II", narc, fat_offset + 12 + index * 8, start, end)

    compact_fimg = bytearray(b"GMIF")
    compact_fimg.extend(struct.pack("<I", 8 + len(compact_data)))
    compact_fimg.extend(compact_data)
    del narc[fimg_offset:]
    narc.extend(compact_fimg)
    struct.pack_into("<I", narc, 8, len(narc))
    return narc


def write_compact_narc(input_dir: Path, output: Path) -> dict[str, int]:
    members = read_stage_members(input_dir)
    standard = create_standard_narc(members)
    baseline_size = len(standard)
    compact = compact_empty_members(standard, members)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(compact)

    empty_count = sum(1 for member in members if member == EMPTY_HEADBUTT_HEADER)
    non_empty_count = len(members) - empty_count
    return {
        "members": len(members),
        "empty_members": empty_count,
        "non_empty_members": non_empty_count,
        "baseline_size": baseline_size,
        "compact_size": len(compact),
        "saved_bytes": baseline_size - len(compact),
    }


def read_narc_members(path: Path) -> list[bytes]:
    blob = path.read_bytes()
    fat_offset = blob.find(b"BTAF")
    fimg_offset = blob.find(b"GMIF")
    require(fat_offset >= 0, f"{path}: missing BTAF")
    require(fimg_offset >= 0, f"{path}: missing GMIF")
    count = struct.unpack_from("<I", blob, fat_offset + 8)[0]
    data_start = fimg_offset + 8
    members = []
    for index in range(count):
        start, end = struct.unpack_from("<II", blob, fat_offset + 12 + index * 8)
        require(start <= end, f"{path}: member {index} has inverted range")
        require(data_start + end <= len(blob), f"{path}: member {index} extends past GMIF data")
        members.append(blob[data_start + start:data_start + end])
    return members


def validate_source(source: Path) -> list[dict[str, int]]:
    require(source.is_file(), f"{source}: source file does not exist")
    records = []
    current: dict[str, int] | None = None
    for raw_line in source.read_text(encoding="latin-1").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        match = HEADER_RE.match(line)
        if match:
            if current is not None:
                records.append(current)
            current = {
                "map_id": int(match.group(1)),
                "normal": int(match.group(2)),
                "special": int(match.group(3)),
                "slots": 0,
                "trees": 0,
            }
            continue
        if current is None:
            continue
        if ENCOUNTER_RE.match(line):
            current["slots"] += 1
        elif TREECOORDS_RE.match(line):
            current["trees"] += 1
    if current is not None:
        records.append(current)

    require(records, f"{source}: no headbuttheader records found")
    map_ids = [record["map_id"] for record in records]
    require(map_ids == list(range(map_ids[-1] + 1)), f"{source}: map ids are not contiguous")
    for record in records:
        tree_count = record["normal"] + record["special"]
        if tree_count == 0:
            require(record["slots"] == 0 and record["trees"] == 0, f"{source}: empty map {record['map_id']} has payload lines")
        else:
            require(record["slots"] == HEADBUTT_SLOT_COUNT, f"{source}: map {record['map_id']} has {record['slots']} slots, expected {HEADBUTT_SLOT_COUNT}")
            require(
                record["trees"] == tree_count,
                f"{source}: map {record['map_id']} declares {tree_count} trees but has {record['trees']} treecoords",
            )
    return records


def validate_members(members: list[bytes], records: list[dict[str, int]], label: str) -> None:
    require(len(members) == len(records), f"{label}: has {len(members)} members, expected {len(records)}")
    for index, (member, record) in enumerate(zip(members, records)):
        require(record["map_id"] == index, f"{label}: source map id {record['map_id']} does not match member {index}")
        require(len(member) >= HEADBUTT_HEADER_SIZE, f"{label}: member {index} is smaller than a headbutt header")
        normal, special = struct.unpack_from("<HH", member, 0)
        require(
            normal == record["normal"] and special == record["special"],
            f"{label}: member {index} header is {normal}, {special}; expected {record['normal']}, {record['special']}",
        )
        expected_size = expected_member_size(record)
        require(len(member) == expected_size, f"{label}: member {index} is {len(member)} bytes, expected {expected_size}")


def validate_narc(path: Path, records: list[dict[str, int]]) -> None:
    members = read_narc_members(path)
    validate_members(members, records, str(path))
    require(members, f"{path}: no members")
    empty_members = [index for index, member in enumerate(members) if member == EMPTY_HEADBUTT_HEADER]
    require(empty_members, f"{path}: no empty headbutt members found")
    for index, member in enumerate(members):
        require(len(member) >= 4, f"{path}: member {index} is smaller than a headbutt header")
        normal, special = struct.unpack_from("<HH", member, 0)
        if member == EMPTY_HEADBUTT_HEADER:
            continue
        if normal == 0 and special == 0:
            raise ValueError(f"{path}: member {index} stores an unaliased empty header")

    blob = path.read_bytes()
    fat_offset = blob.find(b"BTAF")
    empty_ranges = set()
    for index in empty_members:
        empty_ranges.add(struct.unpack_from("<II", blob, fat_offset + 12 + index * 8))
    require(len(empty_ranges) == 1, f"{path}: empty members do not share one payload range")


def command_pack(args: argparse.Namespace) -> None:
    records = validate_source(args.source)
    members = read_stage_members(args.input_dir)
    validate_members(members, records, str(args.input_dir))
    stats = write_compact_narc(args.input_dir, args.output)
    print(
        "headbutt.narc: "
        f"{stats['members']} members, {stats['non_empty_members']} non-empty, "
        f"{stats['empty_members']} empty; {stats['baseline_size']} -> "
        f"{stats['compact_size']} bytes ({stats['saved_bytes']} saved)"
    )


def command_validate(args: argparse.Namespace) -> None:
    records = validate_source(args.source)
    if args.narc is not None:
        validate_narc(args.narc, records)
    print("headbutt data validation passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack = subparsers.add_parser("pack", help="pack build/headbutttrees into a compact NARC")
    pack.add_argument("--source", type=Path, default=Path("armips/data/headbutt.s"))
    pack.add_argument("--input-dir", type=Path, default=Path("build/headbutttrees"))
    pack.add_argument("--output", type=Path, default=Path("build/narc/headbutt.narc"))
    pack.set_defaults(func=command_pack)

    validate = subparsers.add_parser("validate", help="validate source and optionally packed NARC")
    validate.add_argument("--source", type=Path, default=Path("armips/data/headbutt.s"))
    validate.add_argument("--narc", type=Path)
    validate.set_defaults(func=command_validate)

    args = parser.parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
