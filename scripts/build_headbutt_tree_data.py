#!/usr/bin/env python3
"""Build and validate compact headbutt tree NARC members."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "armips/data/headbutt.s"
DEFAULT_OUTPUT_DIR = ROOT / "build/headbutttrees"
SPECIES_CONSTANTS = ROOT / "asm/include/species.inc"

NORMAL_SLOT_COUNT = 12
SPECIAL_SLOT_COUNT = 6
SLOTS_PER_MEMBER = NORMAL_SLOT_COUNT + SPECIAL_SLOT_COUNT
COORDS_PER_TREE = 6
EMPTY_COORD = -1
LEGACY_TREE_SIZE = COORDS_PER_TREE * 4
COMPACT_TREE_HEADER_SIZE = 2


class HeadbuttDataError(ValueError):
    pass


@dataclass
class HeadbuttSlot:
    species: int
    form: int
    min_level: int
    max_level: int

    @property
    def encoded_species(self) -> int:
        return self.species | (self.form << 11)


@dataclass
class HeadbuttTree:
    coords: list[tuple[int, int]]
    line_no: int


@dataclass
class HeadbuttMember:
    member_id: int
    normal_tree_count: int
    special_tree_count: int
    comment: str
    line_no: int
    slots: list[HeadbuttSlot] = field(default_factory=list)
    trees: list[HeadbuttTree] = field(default_factory=list)

    @property
    def tree_count(self) -> int:
        return self.normal_tree_count + self.special_tree_count


def strip_comment(line: str) -> tuple[str, str]:
    code, _, comment = line.partition("//")
    return code.strip(), comment.strip()


def load_species_constants(path: Path) -> dict[str, int]:
    constants: dict[str, int] = {}
    pattern = re.compile(r"^\.equ\s+(SPECIES_[A-Z0-9_]+)\s*,\s*([0-9]+)\s*$")
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        code, _ = strip_comment(line)
        match = pattern.match(code)
        if match is None:
            continue
        constants[match.group(1)] = int(match.group(2))
    if "SPECIES_NONE" not in constants:
        raise HeadbuttDataError(f"{path}: missing SPECIES_NONE")
    return constants


def parse_int_list(raw: str, line_no: int, expected: int) -> list[int]:
    values = [part.strip() for part in raw.split(",")]
    if len(values) != expected:
        raise HeadbuttDataError(
            f"line {line_no}: expected {expected} values, got {len(values)}"
        )
    try:
        return [int(value, 0) for value in values]
    except ValueError as exc:
        raise HeadbuttDataError(f"line {line_no}: invalid integer in {raw!r}") from exc


def resolve_species(token: str, constants: dict[str, int], line_no: int) -> int:
    if token not in constants:
        raise HeadbuttDataError(f"line {line_no}: unknown species constant {token}")
    return constants[token]


def parse_headbutt_source(path: Path, constants: dict[str, int]) -> list[HeadbuttMember]:
    members: list[HeadbuttMember] = []
    current: HeadbuttMember | None = None
    header_pattern = re.compile(r"^headbuttheader\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*$")
    slot_pattern = re.compile(
        r"^headbuttencounter\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*$"
    )
    slot_form_pattern = re.compile(
        r"^headbuttencounterwithform\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*$"
    )
    tree_pattern = re.compile(r"^treecoords\s+(.+)$")

    for line_no, line in enumerate(path.read_text(encoding="latin-1").splitlines(), start=1):
        code, comment = strip_comment(line)
        if not code or code.startswith(".") or code.startswith("#"):
            continue

        header_match = header_pattern.match(code)
        if header_match is not None:
            if current is not None:
                members.append(current)
            current = HeadbuttMember(
                member_id=int(header_match.group(1)),
                normal_tree_count=int(header_match.group(2)),
                special_tree_count=int(header_match.group(3)),
                comment=comment,
                line_no=line_no,
            )
            continue

        if current is None:
            continue

        form_match = slot_form_pattern.match(code)
        if form_match is not None:
            species = resolve_species(form_match.group(1), constants, line_no)
            current.slots.append(
                HeadbuttSlot(
                    species=species,
                    form=int(form_match.group(2)),
                    min_level=int(form_match.group(3)),
                    max_level=int(form_match.group(4)),
                )
            )
            continue

        slot_match = slot_pattern.match(code)
        if slot_match is not None:
            species = resolve_species(slot_match.group(1), constants, line_no)
            current.slots.append(
                HeadbuttSlot(
                    species=species,
                    form=0,
                    min_level=int(slot_match.group(2)),
                    max_level=int(slot_match.group(3)),
                )
            )
            continue

        tree_match = tree_pattern.match(code)
        if tree_match is not None:
            values = parse_int_list(tree_match.group(1), line_no, COORDS_PER_TREE * 2)
            pairs = list(zip(values[0::2], values[1::2]))
            live_pairs: list[tuple[int, int]] = []
            seen_empty = False
            for x, y in pairs:
                is_empty = x == EMPTY_COORD and y == EMPTY_COORD
                if is_empty:
                    seen_empty = True
                    continue
                if x == EMPTY_COORD or y == EMPTY_COORD:
                    raise HeadbuttDataError(
                        f"line {line_no}: partial empty coord pair ({x}, {y})"
                    )
                if seen_empty:
                    raise HeadbuttDataError(
                        f"line {line_no}: live coord appears after empty padding"
                    )
                live_pairs.append((x, y))
            if not live_pairs:
                raise HeadbuttDataError(f"line {line_no}: tree has no live coords")
            current.trees.append(HeadbuttTree(live_pairs, line_no))
            continue

    if current is not None:
        members.append(current)
    return members


def validate_members(members: list[HeadbuttMember]) -> None:
    seen: set[int] = set()
    for member in members:
        if member.member_id < 0:
            raise HeadbuttDataError(
                f"line {member.line_no}: member id {member.member_id} is negative"
            )
        if member.member_id in seen:
            raise HeadbuttDataError(
                f"line {member.line_no}: duplicate headbutt member {member.member_id}"
            )
        seen.add(member.member_id)
        if member.normal_tree_count > 0xFFFF or member.special_tree_count > 0xFFFF:
            raise HeadbuttDataError(
                f"line {member.line_no}: tree count exceeds u16 for member {member.member_id}"
            )
        if member.tree_count == 0:
            if member.slots or member.trees:
                raise HeadbuttDataError(
                    f"line {member.line_no}: empty member {member.member_id} has payload"
                )
            continue
        if len(member.slots) != SLOTS_PER_MEMBER:
            raise HeadbuttDataError(
                f"line {member.line_no}: member {member.member_id} has "
                f"{len(member.slots)} slots, expected {SLOTS_PER_MEMBER}"
            )
        if len(member.trees) != member.tree_count:
            raise HeadbuttDataError(
                f"line {member.line_no}: member {member.member_id} declares "
                f"{member.tree_count} trees but has {len(member.trees)} treecoords"
            )
        for slot_index, slot in enumerate(member.slots):
            if slot.form > 0x1F:
                raise HeadbuttDataError(
                    f"line {member.line_no}: member {member.member_id} slot "
                    f"{slot_index + 1} form {slot.form} exceeds 5 bits"
                )
            if slot.encoded_species > 0xFFFF:
                raise HeadbuttDataError(
                    f"line {member.line_no}: member {member.member_id} slot "
                    f"{slot_index + 1} encoded species exceeds u16"
                )
            if not (0 <= slot.min_level <= 100 and 0 <= slot.max_level <= 100):
                raise HeadbuttDataError(
                    f"line {member.line_no}: member {member.member_id} slot "
                    f"{slot_index + 1} level outside 0..100"
                )
        for tree in member.trees:
            if len(tree.coords) > COORDS_PER_TREE:
                raise HeadbuttDataError(
                    f"line {tree.line_no}: compact tree has {len(tree.coords)} coords, "
                    f"max {COORDS_PER_TREE}"
                )
            for x, y in tree.coords:
                if not (-0x8000 <= x <= 0x7FFF and -0x8000 <= y <= 0x7FFF):
                    raise HeadbuttDataError(
                        f"line {tree.line_no}: coord ({x}, {y}) is outside s16 range"
                    )

    if members:
        max_member_id = max(member.member_id for member in members)
        expected = set(range(max_member_id + 1))
        missing = sorted(expected - seen)
        if missing:
            preview = ", ".join(str(member_id) for member_id in missing[:8])
            if len(missing) > 8:
                preview += ", ..."
            raise HeadbuttDataError(
                f"missing headbutt member ids: {preview}; map id must match member id"
            )


def encode_member(member: HeadbuttMember) -> bytes:
    data = bytearray()
    data += struct.pack("<HH", member.normal_tree_count, member.special_tree_count)
    if member.tree_count == 0:
        return bytes(data)
    for slot in member.slots:
        data += struct.pack("<HBB", slot.encoded_species, slot.min_level, slot.max_level)
    for tree in member.trees:
        data += struct.pack("<BB", len(tree.coords), 0)
        for x, y in tree.coords:
            data += struct.pack("<hh", x, y)
    return bytes(data)


def write_members(members: list[HeadbuttMember], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.iterdir():
        if path.is_file():
            path.unlink()
    for member in members:
        (output_dir / f"{member.member_id:03d}").write_bytes(encode_member(member))


def size_report(members: list[HeadbuttMember]) -> str:
    legacy_size = 0
    compact_size = 0
    for member in members:
        legacy_size += 4
        compact_size += len(encode_member(member))
        if member.tree_count != 0:
            legacy_size += SLOTS_PER_MEMBER * 4
            legacy_size += member.tree_count * LEGACY_TREE_SIZE
    return (
        f"headbutt compact members: {len(members)} members, "
        f"{legacy_size} -> {compact_size} bytes "
        f"({legacy_size - compact_size} saved)"
    )


def command_build(args: argparse.Namespace) -> None:
    constants = load_species_constants(args.species_constants)
    members = parse_headbutt_source(args.input, constants)
    validate_members(members)
    write_members(members, args.output_dir)
    print(size_report(members))


def command_validate(args: argparse.Namespace) -> None:
    constants = load_species_constants(args.species_constants)
    members = parse_headbutt_source(args.input, constants)
    validate_members(members)
    print(size_report(members))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
        subparser.add_argument(
            "--species-constants",
            type=Path,
            default=SPECIES_CONSTANTS,
        )

    build_parser = subparsers.add_parser("build", help="write compact members")
    add_common(build_parser)
    build_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    build_parser.set_defaults(func=command_build)

    validate_parser = subparsers.add_parser("validate", help="validate without writing")
    add_common(validate_parser)
    validate_parser.set_defaults(func=command_validate)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except HeadbuttDataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
