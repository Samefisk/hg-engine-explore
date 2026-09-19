#!/usr/bin/env python3
"""Reject linker placement that violates actual Walk input ELF alignment."""
import argparse
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]

# A subset of the fixed resident Walk package must never count as proof.
REQUIRED_SECTIONS = frozenset(".overworld_walk_" + name for name in (
    "direction_key", "direction_key_body", "strict_diagonal_allowed", "candidate_rejection",
    "strict_diagonal_allowed_body", "module", "decelerate_time",
    "decelerate_time_body", "stop_skid_plan", "propose_step",
    "clamp_time", "accelerate_time", "decelerate_time_body",
    "skid_tiles", "skid_time", "stop_skid_plan", "stomp_applies", "direction_from_keys", "delta_x",
    "delta_y", "is_forty_five_degree_turn", "direction_from_delta",
    "diagonal_facing", "resolve_mounted_diagonal", "filter_mounted_input",
    "start_mounted_flat", "mount_abort",
))


def elf(path):
    data = Path(path).read_bytes()
    if data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("expected little-endian ELF32")
    offset = struct.unpack_from("<I", data, 32)[0]
    stride, count, strings = struct.unpack_from("<3H", data, 46)
    rows = [struct.unpack_from("<10I", data, offset + i * stride) for i in range(count)]
    def text(table, start):
        return table[start:table.index(b"\0", start)].decode()
    names = data[rows[strings][4]:rows[strings][4] + rows[strings][5]]
    sections = [{"name": text(names, row[0]), "alignment": row[8], "size": row[5],
                 "flags": row[2]} for row in rows]
    symbols = []
    for row in rows:
        if row[1] != 2: continue
        strings_row = rows[row[6]]
        table = data[strings_row[4]:strings_row[4] + strings_row[5]]
        for pos in range(row[4], row[4] + row[5], row[9]):
            name, value, size, info, other, index = struct.unpack_from("<IIIBBH", data, pos)
            if name:
                symbols.append({"name": text(table, name), "value": value, "section": index,
                                "type": info & 15})
    return sections, symbols


def inspect(input_path, linked_path):
    sections, symbols = elf(input_path)
    _, linked = elf(linked_path)
    inventory = [section["name"] for section in sections
                 if section["name"].startswith(".overworld_walk")
                 and section["size"] and section["flags"] & 4]
    if len(inventory) != len(REQUIRED_SECTIONS) or set(inventory) != REQUIRED_SECTIONS:
        raise ValueError("Walk executable section inventory mismatch: missing="
                         + repr(sorted(REQUIRED_SECTIONS - set(inventory)))
                         + "; unexpected=" + repr(sorted(set(inventory) - REQUIRED_SECTIONS)))
    rows = []
    for index, section in enumerate(sections):
        if not section["name"].startswith(".overworld_walk") or not section["size"] or not section["flags"] & 4:
            continue
        bases = set()
        for symbol in symbols:
            if symbol["section"] != index or symbol["type"] != 2: continue
            matches = [s for s in linked if s["name"] == symbol["name"] and s["section"] != 0]
            if len(matches) != 1:
                raise ValueError("missing or ambiguous linked function: " + symbol["name"])
            bases.add((matches[0]["value"] & ~1) - (symbol["value"] & ~1))
        if len(bases) != 1:
            raise ValueError("Walk section lacks one proved mapping: " + section["name"])
        address = bases.pop()
        alignment = section["alignment"]
        rows.append({"section": section["name"], "address": address, "alignment": alignment,
                     "size": section["size"], "passed": alignment > 0 and address % alignment == 0})
    if not rows: raise ValueError("no Walk helper sections checked")
    return {"passed": all(row["passed"] for row in rows), "sections": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "build/pokemon_move_history_overlay/overworld_walk_module.o")
    parser.add_argument("--linked", type=Path, default=ROOT / "build/pokemon_move_history_overlay_linked.o")
    args = parser.parse_args()
    result = inspect(args.input, args.linked)
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
