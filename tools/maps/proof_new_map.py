"""In-game proof that a map ID past the vanilla 540 works (test-only edit).

  python3 -B -m tools.maps.proof_new_map write    # header for map 540
  (build test.nds with hg-engine-delta-build)
  python3 -B -m tools.maps.proof_new_map probe    # live melonDS check, JSON out
  python3 -B -m tools.maps.proof_new_map remove   # take the edit out, rebuild

Map 540 gets a copy of map 62's header (the back room of Elm's lab), so it
reuses that room's matrix, land and events under a new ID. The probe
teleports to 540 and checks that the game reports map 540 and loaded map
62's event file (a header-table read that vanilla would redirect to
MAP_NOTHING, whose event file is empty).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import cli, world
from .proof_route29 import _ow, _where

NEW_MAP, TEMPLATE_MAP, START = 540, 62, (10, 10)


def write(overrides: Path) -> None:
    path = overrides / "headers" / f"{NEW_MAP:04d}.json"
    if path.exists():
        raise SystemExit(f"{path} already exists; refusing to mix with other edits")
    base = world.load_base(world.RomSource(cli.REPO / "rom.nds"))
    header = {key: value for key, value in base.headers[TEMPLATE_MAP].items() if key != "alias"}
    header.update(id=NEW_MAP, name="PROOF540")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(header, indent=1) + "\n")
    print(f"wrote {path}")


def remove(overrides: Path) -> None:
    (overrides / "headers" / f"{NEW_MAP:04d}.json").unlink(missing_ok=True)
    for folder in (overrides / "headers", overrides):
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    print("removed new-map proof edit")


def probe(rom: str, save: str) -> int:
    base = world.load_base(world.RomSource(cli.REPO / "rom.nds"))
    template_events = hashlib.sha256(base.raw["events"][base.headers[TEMPLATE_MAP]["eventsBank"]]).hexdigest()
    nothing_events = hashlib.sha256(base.raw["events"][base.headers[1]["eventsBank"]]).hexdigest()
    _ow("start", "--rom", rom, "--save", save)
    try:
        _ow("teleport", str(NEW_MAP), str(START[0]), str(START[1]), "--facing", "2")
        start = _where()
        terrain = _ow("terrain", "--x", str(START[0]), "--z", str(START[1]), "--radius", "0")
        terrain = terrain.get("terrain", terrain)
        events = terrain.get("events") or {}
        _ow("step", "8", "--keys", "LEFT")
        _ow("step", "60")
        after = _where()
    finally:
        _ow("stop")
    checks = {
        "gameReportsNewMapId": start == (NEW_MAP, *START),
        "loadedTemplateEventFile": events.get("sha256") == template_events,
        "walkableOnNewMap": after[0] == NEW_MAP and after[1] < START[0],
    }
    print(json.dumps({"start": start, "after": after, "events": events,
                      "eventsAreMapNothing": events.get("sha256") == nothing_events,
                      "checks": checks, "passed": all(checks.values())}))
    return 0 if all(checks.values()) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.proof_new_map", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("write", "probe", "remove"))
    parser.add_argument("--overrides", type=Path, default=cli.REPO / "data/maps")
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--save", default="test.sav")
    args = parser.parse_args(argv)
    if args.action == "write":
        write(args.overrides)
    elif args.action == "remove":
        remove(args.overrides)
    else:
        return probe(args.rom, args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
