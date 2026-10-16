"""Edit one map's zone events with lint's checks run at edit time.

  python3 -B -m tools.maps events list --map 33
  python3 -B -m tools.maps events add-npc --map 33 --x 620 --z 400 --sprite 317 --script 7
  python3 -B -m tools.maps events add-sign --map 33 --x 580 --z 397 --script 5
  python3 -B -m tools.maps events add-warp --map 33 --x 626 --z 389 --to-map 134 --anchor 0
  python3 -B -m tools.maps events add-trigger --map 33 --x 666 --z 396 --h 7 --script 2 --var 0x408B --value 1
  python3 -B -m tools.maps events move --map 33 --kind object --index 0 --x 627 --z 410
  python3 -B -m tools.maps events remove --map 33 --kind bg --index 1

Coordinates are matrix-wide tiles. The map's events bank comes from its
header; a bank missing from the override tree is copied in the way
`checkout --parts events` does, with the same refusal for banks other maps
share (`--private` appends a copy at the next free index and points a header
override at it; `--shared` edits the shared bank for every user).

Every edit is checked before anything is written: the codec must encode it
(field ranges, the 0x800-byte file limit), and `lint.findings` is run on the
world before and after the edit. Findings the edit adds are reported; errors
refuse the edit unless `--force` (waivers in lint_waivers.json apply).
Removing a warp also refuses when other warps target it or a later anchor,
because their anchors would shift. `--dry-run` prints the member diff only.

`y` defaults to 0, as vanilla stores for 2642 of 2667 objects and every warp
and trigger: the game places objects on the terrain height itself.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
from pathlib import Path

from . import codecs, lint, world

KINDS = {"object": "objects", "warp": "warps", "bg": "bgs", "coord": "coords"}
FACING = {"up": 0, "down": 1, "left": 2, "right": 3}  # DIR_NORTH/SOUTH/WEST/EAST
BG_TYPES = {"normal": 0, "signpost": 1, "hidden-item": 2}  # BG_TYPE_*
BG_DIRS = {"south": 0, "east": 1, "west": 2, "north": 3, "all": 4, "eastwest": 5, "northsouth": 6}
NOT_PER_MAP = {"matrix-land", "land-anim-order"}


class EditError(Exception):
    pass


def _number(value: str) -> int:
    return int(value, 0)


def _choice(table: dict):
    def parse(value: str) -> int:
        if value in table:
            return table[value]
        try:
            return int(value, 0)
        except ValueError:
            raise argparse.ArgumentTypeError(f"use one of {sorted(table)} or a number") from None
    return parse


def _text(spec) -> list[str]:
    return (json.dumps(spec, indent=1) + "\n").splitlines(keepends=True)


def _world_with(edited: world.World, events: dict[int, dict], headers: dict[int, dict]) -> world.World:
    """A copy of `edited` with encoded event members and header entries replaced."""
    raw = {kind: list(members) for kind, members in edited.raw.items()}
    for bank, spec in events.items():
        data = codecs.encode_events(spec)
        if bank < len(raw["events"]):
            raw["events"][bank] = data
        elif bank == len(raw["events"]):
            raw["events"].append(data)
        else:
            raise codecs.FormatError(f"events {bank}: appends must be contiguous")
    table = [dict(entry) for entry in edited.headers]
    for map_id, entry in headers.items():
        codecs.encode_header(entry)
        table[map_id] = {**entry, "id": map_id}
    return world.World(raw=raw, headers=table, archive_counts=dict(edited.archive_counts),
                       script_entries=list(edited.script_entries), script_ranges=list(edited.script_ranges),
                       overridden={kind: set(ids) for kind, ids in edited.overridden.items()},
                       land_anims=edited.land_anims)


def _bank_users(edited: world.World, bank: int) -> list[int]:
    return [entry["id"] for entry in edited.headers if entry["eventsBank"] == bank]


def _short(ids: list[int], limit: int = 12) -> str:
    shown = ", ".join(str(i) for i in ids[:limit])
    return shown + (f", ... {len(ids) - limit} more" if len(ids) > limit else "")


def _load(args):
    from . import cli
    try:
        base, edited = cli._load(args)
    except codecs.FormatError as error:
        raise EditError(f"cannot load the override tree: {error}") from None
    if not 0 <= args.map < len(edited.headers):
        raise EditError(f"map {args.map} is outside 0..{len(edited.headers) - 1}")
    return base, edited


# --- list -------------------------------------------------------------------

def cmd_list(args) -> int:
    try:
        _, edited = _load(args)
    except EditError as error:
        print(f"events list failed: {error}", file=sys.stderr)
        return 1
    entry = edited.headers[args.map]
    bank = entry["eventsBank"]
    users = _bank_users(edited, bank)
    source = "override" if bank in edited.overridden.get("events", ()) else "rom"
    print(f"map {args.map} ({entry['name']}) matrix {entry['matrixId']} events bank {bank} ({source})"
          + (f", shared with maps {[u for u in users if u != args.map]}" if len(users) > 1 else ""))
    scripts = entry["scriptsBank"]
    if scripts < len(edited.script_entries) and edited.script_entries[scripts] is not None:
        print(f"scripts: scr_seq {scripts} has {edited.script_entries[scripts]} (local ids 1..{edited.script_entries[scripts]})")
    else:
        print(f"scripts: scr_seq {scripts} (entry count unknown: replaced by the build)")
    events = edited.member("events", bank)

    def tile_note(item) -> str:
        tile = edited.tile(args.map, item["x"], item["z"])
        return "  [outside land]" if tile is None else ("  [blocked]" if tile[0] else "")

    print(f"objects ({len(events['objects'])}):")
    for i, o in enumerate(events["objects"]):
        print(f"  [{i}] id {o['id']} at ({o['x']}, {o['z']}) y {o['y']} sprite {o['spriteId']} script {o['scriptId']} "
              f"movement {o['movement']} facing {o['facingDirection']} flag {o['eventFlag']} "
              f"range ({o['xRange']}, {o['yRange']}){tile_note(o)}")
    print(f"warps ({len(events['warps'])}):")
    for i, w in enumerate(events["warps"]):
        dest = edited.headers[w["header"]]["name"] if w["header"] < len(edited.headers) else "?"
        if w["header"] == lint.DYNAMIC_WARP_HEADER:
            dest = "previous map"
        print(f"  [{i}] at ({w['x']}, {w['z']}) -> map {w['header']} ({dest}) anchor {w['anchor']}")
    print(f"bgs ({len(events['bgs'])}):")
    for i, b in enumerate(events["bgs"]):
        print(f"  [{i}] at ({b['x']}, {b['z']}) script {b['scriptId']} type {b['type']} dir {b['dir']}{tile_note(b)}")
    print(f"coords ({len(events['coords'])}):")
    for i, c in enumerate(events["coords"]):
        print(f"  [{i}] at ({c['x']}, {c['z']}) size {c['w']}x{c['h']} script {c['scriptId']} "
              f"var {c['var']:#x} value {c['val']}")
    return 0


# --- edits ------------------------------------------------------------------

def _occupied(events: dict, x: int, z: int, skip=None) -> list[str]:
    out = []
    for kind in ("objects", "bgs", "warps"):
        for i, item in enumerate(events[kind]):
            if (kind, i) != skip and (item["x"], item["z"]) == (x, z):
                out.append(f"{kind}[{i}]")
    return out


def _add_npc(args, events, edited):
    ids = [o["id"] for o in events["objects"]]
    object_id = args.id if args.id is not None else (max(ids) + 1 if ids else 0)
    xr, zr = args.range or (0, 0)
    item = {"id": object_id, "spriteId": args.sprite, "movement": args.movement, "type": 0,
            "eventFlag": args.flag, "scriptId": args.script, "facingDirection": args.facing,
            "param0": 0, "param1": 0, "param2": 0, "xRange": xr, "yRange": zr,
            "x": args.x, "z": args.z, "y": args.y}
    events["objects"].append(item)
    return f"add object [{len(events['objects']) - 1}] id {object_id}", ("objects", len(events["objects"]) - 1)


def _add_sign(args, events, edited):
    events["bgs"].append({"scriptId": args.script, "type": args.type, "x": args.x, "z": args.z,
                          "y": args.y, "dir": args.dir, "dirPadding": 0})
    return f"add bg [{len(events['bgs']) - 1}]", ("bgs", len(events["bgs"]) - 1)


def _add_warp(args, events, edited):
    if args.to_map != lint.DYNAMIC_WARP_HEADER and not 0 <= args.to_map < len(edited.headers):
        raise EditError(f"target map {args.to_map} does not exist (0..{len(edited.headers) - 1}, "
                        f"or {lint.DYNAMIC_WARP_HEADER} for the previous map)")
    events["warps"].append({"x": args.x, "z": args.z, "header": args.to_map, "anchor": args.anchor, "y": args.y})
    return f"add warp [{len(events['warps']) - 1}]", ("warps", len(events["warps"]) - 1)


def _add_trigger(args, events, edited):
    if args.w < 1 or args.h < 1:
        raise EditError("--w and --h must be at least 1")
    events["coords"].append({"scriptId": args.script, "x": args.x, "z": args.z, "w": args.w, "h": args.h,
                             "y": args.y, "val": args.value, "var": args.var})
    return f"add coord [{len(events['coords']) - 1}]", ("coords", len(events["coords"]) - 1)


def _pick(args, events) -> tuple[str, list]:
    kind = KINDS[args.kind]
    items = events[kind]
    if not 0 <= args.index < len(items):
        raise EditError(f"{kind} index {args.index} is outside 0..{len(items) - 1}")
    return kind, items


def _move(args, events, edited):
    kind, items = _pick(args, events)
    item = items[args.index]
    old = (item["x"], item["z"])
    item["x"], item["z"] = args.x, args.z
    return f"move {kind}[{args.index}] {old} -> ({args.x}, {args.z})", (kind, args.index)


def _remove(args, events, edited):
    kind, items = _pick(args, events)
    removed = items.pop(args.index)
    return f"remove {kind}[{args.index}] at ({removed['x']}, {removed['z']})", None


def _incoming_shift(after: world.World, targets: set[int], index: int) -> list[str]:
    """Warps that target warp `index` or a later anchor of maps in `targets`."""
    problems, seen_banks = [], set()
    for entry in after.headers:
        bank = entry["eventsBank"]
        if bank in seen_banks or bank >= len(after.raw["events"]):
            continue
        seen_banks.add(bank)
        for i, warp in enumerate(after.member("events", bank)["warps"]):
            if warp["header"] in targets and warp["anchor"] >= index:
                what = "now dangles or points elsewhere" if warp["anchor"] == index else "would shift by one"
                problems.append(f"events bank {bank} warps[{i}] at ({warp['x']}, {warp['z']}) -> map "
                                f"{warp['header']} anchor {warp['anchor']} {what}")
    return problems


def _run(args, mutate) -> int:
    from . import cli
    try:
        base, edited = _load(args)
        entry = edited.headers[args.map]
        bank = entry["eventsBank"]
        users = _bank_users(edited, bank)
        events_path = args.overrides / "events" / f"{bank:04d}.json"
        header_changes: dict[int, dict] = {}
        writes: list[tuple[Path, object, object, str]] = []  # (path, old spec or None, new spec, diff label)
        if events_path.exists():
            old = json.loads(events_path.read_text())
        else:
            old = copy.deepcopy(edited.member("events", bank))
        target_bank, target_path = bank, events_path
        if len(users) > 1 and not args.shared:
            if not args.private:
                raise EditError(
                    f"events bank {bank} is used by {len(users)} maps ({_short(users)}); editing it changes all "
                    f"of them. Pass "
                    f"--private to append a copy at the next free index ({len(edited.raw['events'])}) and point a "
                    f"header override for map {args.map} at it (README edit loop step 1), or --shared to edit "
                    f"every listed map")
            target_bank = len(edited.raw["events"])
            target_path = args.overrides / "events" / f"{target_bank:04d}.json"
            header_path = args.overrides / "headers" / f"{args.map:04d}.json"
            old_header = json.loads(header_path.read_text()) if header_path.exists() else None
            new_header = dict(old_header if old_header is not None else entry)
            new_header.pop("alias", None)
            new_header["eventsBank"] = target_bank
            header_changes[args.map] = new_header
            writes.append((header_path, old_header if old_header is not None else entry, new_header,
                           "override" if old_header is not None else "rom header"))
            print(f"private copy: events bank {bank} -> {target_bank} for map {args.map}")
        label = f"{'override' if events_path.exists() else 'rom'} events/{bank:04d}"
        new = copy.deepcopy(old)
        for kind in KINDS.values():
            new.setdefault(kind, [])
        description, focus = mutate(args, new, edited)
        writes.insert(0, (target_path, old, new, label))
        try:
            after = _world_with(edited, {target_bank: new}, header_changes)
        except (codecs.FormatError, KeyError) as error:
            raise EditError(f"the edited events do not encode: {error}") from None
    except EditError as error:
        print(f"events {args.events_command} refused: {error}", file=sys.stderr)
        return 1

    maps = {args.map} | (set(users) if target_bank == bank else set())
    errors, warnings = [], []
    if focus is not None:
        kind, index = focus
        item = new[kind][index]
        busy = _occupied(new, item["x"], item["z"], skip=focus) if kind != "coords" else []
        if busy:
            warnings.append(f"tile ({item['x']}, {item['z']}) already has {', '.join(busy)}")
    if args.events_command == "remove" and KINDS[args.kind] == "warps":
        errors += [f"{line} [warp-anchor-shift]" for line in _incoming_shift(after, maps, args.index)]

    try:
        waivers = lint.load_waivers(args.overrides)
    except (ValueError, KeyError) as error:
        print(f"events {args.events_command} refused: invalid waiver file: {error}", file=sys.stderr)
        return 1
    before_findings = lint.findings(edited)
    for key, (severity, message) in sorted(lint.findings(after).items(), key=lambda kv: str(kv[0])):
        if key in before_findings:
            continue
        text = lint.key_text(key)
        line = f"{message} [{text}]"
        if text in waivers:
            print(f"  waived: {line}: {waivers[text]}")
        else:
            (errors if severity == lint.ERROR else warnings).append(line)

    print(f"map {args.map} ({entry['name']}): {description}")
    for line in warnings:
        print(f"  warning: {line}")
    for line in errors:
        print(f"  error: {line}")
    if args.dry_run:
        for path, old_spec, new_spec, from_label in writes:
            print("".join(difflib.unified_diff(_text(old_spec), _text(new_spec), fromfile=from_label,
                                               tofile=f"{args.overrides / path.relative_to(args.overrides)}")),
                  end="")
        print("dry run: nothing written" + (f" ({len(errors)} error(s) would refuse without --force)" if errors else ""))
        return 1 if errors and not args.force else 0
    if errors and not args.force:
        print(f"events {args.events_command} refused: {len(errors)} error(s); fix them or pass --force",
              file=sys.stderr)
        return 1

    for path, _, spec, _ in writes:
        cli._dump(path, spec)
        print(f"wrote {path}")

    # Re-read the tree from disk and report lint (vs vanilla) for the edited maps.
    try:
        reread = world.apply_overrides(base, args.overrides)
    except codecs.FormatError as error:
        print(f"events {args.events_command}: written tree does not load: {error}", file=sys.stderr)
        return 1
    result = lint.lint(reread, base, waivers)
    counts = {lint.ERROR: 0, lint.WARNING: 0}
    for severity in (lint.ERROR, lint.WARNING):
        for message in result[severity]:
            key = message.rsplit("[", 1)[-1].rstrip("]").split(":")
            if len(key) > 1 and key[0] not in NOT_PER_MAP and key[1].isdigit() and int(key[1]) in maps:
                counts[severity] += 1
                print(f"  lint {severity}: {message}")
    print(f"lint for map(s) {sorted(maps)}: {counts[lint.ERROR]} error(s), {counts[lint.WARNING]} warning(s); "
          f"whole tree: {len(result[lint.ERROR])} error(s), {len(result[lint.WARNING])} warning(s)")
    return 0


# --- argparse ---------------------------------------------------------------

def register(sub) -> None:
    events = sub.add_parser("events", help="list or edit one map's zone events (checked at edit time)",
                            description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = events.add_subparsers(dest="events_command", required=True)

    def command(name: str, func, edit: bool = True):
        parser = commands.add_parser(name)
        parser.add_argument("--map", type=int, required=True)
        # Also accepted after the subcommand; SUPPRESS keeps the global default.
        parser.add_argument("--overrides", type=Path, default=argparse.SUPPRESS, help="sparse override tree")
        if edit:
            parser.add_argument("--dry-run", action="store_true", help="print the member diff; write nothing")
            parser.add_argument("--force", action="store_true", help="write despite errors")
            share = parser.add_mutually_exclusive_group()
            share.add_argument("--private", action="store_true",
                               help="if the bank is shared, append a private copy and override this map's header")
            share.add_argument("--shared", action="store_true", help="edit a bank other maps also use")
            parser.set_defaults(func=lambda args: _run(args, func))
        else:
            parser.set_defaults(func=func)
        return parser

    def position(parser, y: bool = True):
        parser.add_argument("--x", type=int, required=True, help="matrix-wide tile x")
        parser.add_argument("--z", type=int, required=True, help="matrix-wide tile z")
        if y:
            parser.add_argument("--y", type=_number, default=0, help="stored height (vanilla: 0)")

    command("list", cmd_list, edit=False)
    npc = command("add-npc", _add_npc)
    position(npc)
    npc.add_argument("--sprite", type=_number, required=True)
    npc.add_argument("--script", type=_number, required=True)
    npc.add_argument("--movement", type=_number, default=0)
    npc.add_argument("--facing", type=_choice(FACING), default=FACING["down"], help="up|down|left|right")
    npc.add_argument("--flag", type=_number, default=0, help="event flag that hides the object (0 = none)")
    npc.add_argument("--range", type=int, nargs=2, metavar=("RX", "RZ"), help="wander range")
    npc.add_argument("--id", type=int, help="object id (default: next free)")
    sign = command("add-sign", _add_sign)
    position(sign)
    sign.add_argument("--script", type=_number, required=True)
    sign.add_argument("--type", type=_choice(BG_TYPES), default=BG_TYPES["signpost"],
                      help="normal|signpost|hidden-item")
    sign.add_argument("--dir", type=_choice(BG_DIRS), default=BG_DIRS["all"],
                      help="facing that triggers it: south|east|west|north|all|eastwest|northsouth")
    warp = command("add-warp", _add_warp)
    position(warp)
    warp.add_argument("--to-map", type=_number, required=True, help="destination map id (4095 = previous map)")
    warp.add_argument("--anchor", type=int, required=True, help="destination warp index")
    trigger = command("add-trigger", _add_trigger)
    position(trigger)
    trigger.add_argument("--w", type=int, default=1)
    trigger.add_argument("--h", type=int, default=1)
    trigger.add_argument("--script", type=_number, required=True)
    trigger.add_argument("--var", type=_number, required=True)
    trigger.add_argument("--value", type=_number, required=True)
    for name, func in (("move", _move), ("remove", _remove)):
        parser = command(name, func)
        parser.add_argument("--kind", choices=sorted(KINDS), required=True)
        parser.add_argument("--index", type=int, required=True)
        if name == "move":
            position(parser, y=False)
