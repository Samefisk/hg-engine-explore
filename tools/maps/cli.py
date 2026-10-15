"""Command line for HeartGold map specs.

  python3 -B -m tools.maps roundtrip            # prove decode/encode is lossless
  python3 -B -m tools.maps extract --out DIR    # binary -> editable spec tree
  python3 -B -m tools.maps pack --spec DIR --out DIR2
  python3 -B -m tools.maps check-reference      # compare with .codex-reference

Spec tree layout (one file per archive member):
  headers.json              map header table + internal names
  matrix/NNNN.json          a/0/4/1
  area/NNNN.json            a/0/4/2
  events/NNNN.json          a/0/3/2
  land/NNNN/land.json       a/0/6/5 (tiles, buildings, BDHC)
  land/NNNN/model.nsbmd     embedded map model, kept binary
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

from . import codecs, narc

REPO = Path(__file__).resolve().parents[2]

# kind -> (archive path under the filesystem root, decode, encode)
ARCHIVES = {
    "matrix": ("a/0/4/1", codecs.decode_matrix, codecs.encode_matrix),
    "area": ("a/0/4/2", codecs.decode_area, codecs.encode_area),
    "events": ("a/0/3/2", codecs.decode_events, codecs.encode_events),
    "land": ("a/0/6/5", None, None),
}
NAMES_PATH = "fielddata/maptable/mapname.bin"


def _json_cycle(spec):
    """Serialize through JSON text so the check covers what lands on disk."""
    return json.loads(json.dumps(spec))


def _dump(path: Path, spec) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=1) + "\n")


def cmd_roundtrip(args) -> int:
    failures = 0
    for kind, (rel, decode, encode) in ARCHIVES.items():
        members = narc.read_members(args.root / rel)
        bad = []
        for index, data in enumerate(members):
            try:
                if kind == "land":
                    spec, model = codecs.decode_land(data)
                    rebuilt = codecs.encode_land(_json_cycle(spec), model)
                else:
                    rebuilt = encode(_json_cycle(decode(data)))
            except (codecs.FormatError, KeyError, ValueError, struct.error) as error:
                bad.append(f"{index}: {error}")
                continue
            if rebuilt != data:
                bad.append(f"{index}: bytes differ")
        archive_ok = narc.build(members) == (args.root / rel).read_bytes()
        print(f"{kind:7} {rel}  members={len(members)}  lossless={len(members) - len(bad)}  archive_identical={archive_ok}")
        for line in bad[:10]:
            print(f"  FAIL {line}")
        failures += len(bad) + (not archive_ok)

    arm9 = args.arm9.read_bytes()
    names = (args.root / NAMES_PATH).read_bytes()
    table = _json_cycle(codecs.decode_header_table(arm9, names, args.header_offset))
    raw_table = arm9[args.header_offset:args.header_offset + len(table) * codecs.HEADER_SIZE]
    headers_ok = codecs.encode_header_table(table) == raw_table and codecs.encode_names(table) == names
    print(f"headers arm9+{args.header_offset:#x}  entries={len(table)}  lossless={headers_ok}")
    failures += not headers_ok

    print("PASS" if failures == 0 else f"FAIL ({failures})")
    return 0 if failures == 0 else 1


def cmd_extract(args) -> int:
    out = args.out
    for kind, (rel, decode, _) in ARCHIVES.items():
        for index, data in enumerate(narc.read_members(args.root / rel)):
            if kind == "land":
                spec, model = codecs.decode_land(data)
                _dump(out / "land" / f"{index:04d}" / "land.json", spec)
                (out / "land" / f"{index:04d}" / "model.nsbmd").write_bytes(model)
            else:
                _dump(out / kind / f"{index:04d}.json", decode(data))
    names = (args.root / NAMES_PATH).read_bytes()
    _dump(out / "headers.json", codecs.decode_header_table(args.arm9.read_bytes(), names, args.header_offset))
    print(f"extracted to {out}")
    return 0


def _members_from_spec(spec_dir: Path, kind: str) -> list[bytes]:
    _, _, encode = ARCHIVES[kind]
    if kind == "land":
        dirs = sorted(p for p in (spec_dir / "land").iterdir() if p.is_dir())
    else:
        dirs = sorted((spec_dir / kind).glob("*.json"))
    members = []
    for path in dirs:
        try:
            if kind == "land":
                members.append(codecs.encode_land(json.loads((path / "land.json").read_text()),
                                                  (path / "model.nsbmd").read_bytes()))
            else:
                members.append(encode(json.loads(path.read_text())))
        except (codecs.FormatError, KeyError) as error:
            raise codecs.FormatError(f"{path.relative_to(spec_dir)}: {error}") from None
    expected = [f"{i:04d}" for i in range(len(dirs))]
    if [d.stem if d.suffix else d.name for d in dirs] != expected:
        raise SystemExit(f"{kind}: member files must be numbered 0000..{len(dirs) - 1:04d} without gaps")
    return members


def validate_tree(members: dict[str, list[bytes]], table: list[dict]) -> list[str]:
    """Cross-archive checks that per-member codecs cannot see."""
    errors = []
    if [entry["id"] for entry in table] != list(range(len(table))):
        errors.append("headers.json ids must be 0..N-1 in order")
    if len(table) != codecs.HEADER_COUNT:
        errors.append(f"headers.json has {len(table)} entries; the ARM9 table holds exactly "
                      f"{codecs.HEADER_COUNT} (reuse an unused ID instead of appending)")
    counts = {kind: len(items) for kind, items in members.items()}
    for entry in table:
        for field, kind in (("matrixId", "matrix"), ("areaDataBank", "area"), ("eventsBank", "events")):
            if entry[field] >= counts[kind]:
                errors.append(f"map {entry['id']} {field}={entry[field]} but {kind} has {counts[kind]} members")
    for index, data in enumerate(members["matrix"]):
        for row in codecs.decode_matrix(data)["landData"]:
            for land_id in row:
                if land_id != 0xFFFF and land_id >= counts["land"]:
                    errors.append(f"matrix {index} uses land {land_id} but land has {counts['land']} members")
    return errors


def cmd_pack(args) -> int:
    try:
        members = {kind: _members_from_spec(args.spec, kind) for kind in ARCHIVES}
        table = json.loads((args.spec / "headers.json").read_text())
        header_bytes, name_bytes = codecs.encode_header_table(table), codecs.encode_names(table)
    except (codecs.FormatError, KeyError) as error:
        print(f"pack failed: {error!r}", file=sys.stderr)
        return 1
    errors = validate_tree(members, table)
    if errors:
        for line in errors[:20]:
            print(f"pack failed: {line}", file=sys.stderr)
        return 1
    # Everything validated; only now touch the output directory.
    for kind, (rel, _, _) in ARCHIVES.items():
        target = args.out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(narc.build(members[kind]))
    (args.out / "map_headers.bin").write_bytes(header_bytes)
    (args.out / NAMES_PATH).parent.mkdir(parents=True, exist_ok=True)
    (args.out / NAMES_PATH).write_bytes(name_bytes)
    print(f"packed to {args.out} (map_headers.bin is the raw ARM9 table, not yet patched into a ROM)")
    return 0


def cmd_check_reference(args) -> int:
    """Compare decoded data with pokeheartgold's vanilla sources.

    Events: decoded numeric fields must match the JSON (symbols are skipped).
    Matrices: the reference .bin files must equal the archive members (raw bytes).
    Headers: decoded literal-valued fields must match sMapHeaders.
    Land and area data have no decomp source to compare against.
    """
    ref = args.reference / "files/fielddata"
    if not ref.exists():
        print(f"reference not found at {args.reference}; nothing was compared", file=sys.stderr)
        return 2
    failures = 0
    events = narc.read_members(args.root / ARCHIVES["events"][0])
    ref_events = sorted((ref / "eventdata/zone_event").glob("*.json"))
    compared = skipped = 0
    for path in ref_events:
        index = int(path.name.split("_")[0])
        ours = codecs.decode_events(events[index])
        theirs = json.loads(path.read_text())
        for key in ("bgs", "objects", "warps", "coords"):
            ref_items = theirs.get(key, [])
            if len(ref_items) != len(ours[key]):
                print(f"  events {index} {key}: count {len(ours[key])} != reference {len(ref_items)}")
                failures += 1
                continue
            for mine, other in zip(ours[key], ref_items):
                for field, value in other.items():
                    if isinstance(value, int):
                        compared += 1
                        if mine[field] != value:
                            failures += 1
                            print(f"  events {index} {key}.{field}: {mine[field]} != reference {value}")
                    else:
                        skipped += 1
    print(f"events  files={len(ref_events)}  numeric_fields={compared}  symbolic_skipped={skipped}")

    matrices = narc.read_members(args.root / ARCHIVES["matrix"][0])
    ref_matrices = sorted((ref / "mapmatrix/map_matrix").glob("*.bin"))
    differing = [p.name for p in ref_matrices if matrices[int(p.name.split("_")[2].split(".")[0])] != p.read_bytes()]
    print(f"matrix  files={len(ref_matrices)}  identical={len(ref_matrices) - len(differing)}")
    for name in differing[:10]:
        print(f"  differs: {name}")
    failures += len(differing)
    failures += _check_reference_headers(args)
    print("PASS" if failures == 0 else f"DIFFERENCES ({failures}); base/ may contain intentional edits")
    return 0 if failures == 0 else 1


def _check_reference_headers(args) -> int:
    """Compare literal-valued fields of pokeheartgold's sMapHeaders initializers."""
    ref = args.reference
    ids = {name: int(value) for name, value in
           re.findall(r"#define\s+(MAP_\w+)\s+(\d+)", (ref / "include/constants/maps.h").read_text())}
    source = (ref / "src/data/map_headers.h").read_text()
    table = codecs.decode_header_table(args.arm9.read_bytes(), (args.root / NAMES_PATH).read_bytes(),
                                       args.header_offset)
    literals = {"TRUE": 1, "FALSE": 0}
    compared = failures = entries = 0
    for name, body in re.findall(r"\[(MAP_\w+)\]\s*=\s*\{(.*?)\}", source, re.S):
        entries += 1
        entry = table[ids[name]]
        for field, value in re.findall(r"\.(\w+)\s*=\s*([\w]+)", body):
            number = literals.get(value, int(value) if value.isdigit() else None)
            if number is None:
                continue
            compared += 1
            if entry[field] != number:
                failures += 1
                print(f"  header {name}.{field}: {entry[field]} != reference {number}")
    print(f"headers entries={entries}  literal_fields={compared}")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=REPO / "base/root", help="unpacked ROM filesystem")
    parser.add_argument("--arm9", type=Path, default=REPO / "base/arm9.bin")
    parser.add_argument("--header-offset", type=lambda v: int(v, 0), default=codecs.HEADER_TABLE_OFFSET_USA)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("roundtrip").set_defaults(func=cmd_roundtrip)
    extract = sub.add_parser("extract")
    extract.add_argument("--out", type=Path, required=True)
    extract.set_defaults(func=cmd_extract)
    pack = sub.add_parser("pack")
    pack.add_argument("--spec", type=Path, required=True)
    pack.add_argument("--out", type=Path, required=True)
    pack.set_defaults(func=cmd_pack)
    check = sub.add_parser("check-reference")
    check.add_argument("--reference", type=Path, default=REPO / ".codex-reference/pokeheartgold")
    check.set_defaults(func=cmd_check_reference)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
