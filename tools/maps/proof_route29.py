"""End-to-end proof of the map pipeline on Route 29 (test-only edit).

  python3 -B -m tools.maps.proof_route29 write    # add the edit to data/maps
  (build test.nds with hg-engine-delta-build)
  python3 -B -m tools.maps.proof_route29 probe    # live melonDS check, JSON out
  python3 -B -m tools.maps.proof_route29 remove   # take the edit out again, rebuild

The edit blocks tile (628, 394) and turns (624, 396) into a warp panel that
leads to the Route 46 gate (map 134, warp 0, which lands at 5, 12). Probe
uses only shared owctl reads: player map/tile and the loaded terrain/warps.
Before the edit both steps simply walk on; after it the first is refused
and the second warps. Do not ship a ROM built with this edit.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import cli

MAP_ROUTE_29, EVENTS_BANK, LAND_ID, CELL_ORIGIN = 33, 30, 2, (608, 384)
BLOCK_TILE, PANEL_TILE = (628, 394), (624, 396)
OPEN_CONTROL = (627, 395)  # stepping UP from here must move: proves input and teleport work
WARP_PANEL = 0x67  # TILE_BEHAVIOR_WARP_PANEL
NEW_WARP = {"x": PANEL_TILE[0], "z": PANEL_TILE[1], "header": 134, "anchor": 0, "y": 0}
GATE_LANDING = (134, 5, 12)


def _paths(overrides: Path) -> tuple[Path, Path]:
    return overrides / "land" / f"{LAND_ID:04d}", overrides / "events" / f"{EVENTS_BANK:04d}.json"


def write(overrides: Path) -> None:
    land_dir, events_path = _paths(overrides)
    if land_dir.exists() or events_path.exists():
        raise SystemExit(f"{land_dir} or {events_path} already exists; refusing to mix with other edits")
    land_root = overrides / "land"
    existing = set(land_root.iterdir()) if land_root.exists() else set()
    if cli.main(["--overrides", str(overrides), "checkout", "--map", str(MAP_ROUTE_29), "--parts", "events,land"]):
        raise SystemExit("checkout failed")
    for created in set(land_root.iterdir()) - existing - {land_dir}:
        shutil.rmtree(created)  # only the other Route 29 chunks this checkout just wrote
    land = json.loads((land_dir / "land.json").read_text())
    tiles = land["tiles"]
    bx, bz = BLOCK_TILE[0] - CELL_ORIGIN[0], BLOCK_TILE[1] - CELL_ORIGIN[1]
    tiles["collision"][bz] = tiles["collision"][bz][:bx] + "#" + tiles["collision"][bz][bx + 1:]
    px, pz = PANEL_TILE[0] - CELL_ORIGIN[0], PANEL_TILE[1] - CELL_ORIGIN[1]
    row = tiles["behavior"][pz].split()
    row[px] = f"{WARP_PANEL:02x}"
    tiles["behavior"][pz] = " ".join(row)
    (land_dir / "land.json").write_text(json.dumps(land, indent=1) + "\n")
    events = json.loads(events_path.read_text())
    events["warps"].append(NEW_WARP)
    events_path.write_text(json.dumps(events, indent=1) + "\n")
    print(f"wrote proof edit to {land_dir} and {events_path}")


def remove(overrides: Path) -> None:
    land_dir, events_path = _paths(overrides)
    shutil.rmtree(land_dir, ignore_errors=True)
    events_path.unlink(missing_ok=True)
    for folder in (overrides / "land", overrides / "events", overrides):
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    print("removed proof edit")


def _ow(*args: str) -> dict:
    out = subprocess.run([str(cli.REPO / "scripts/owctl"), "dev", *args, "--json", "--summary"],
                         capture_output=True, text=True, cwd=cli.REPO)
    data = json.loads(out.stdout)
    if not data.get("ok"):
        raise SystemExit(f"owctl dev {' '.join(args)} failed: {json.dumps(data)[:600]}")
    return data["result"]


def _where() -> tuple[int, int, int]:
    result = _ow("status")
    return result["context"]["mapId"], result["player"]["x"], result["player"]["y"]


def expected_event_hashes() -> dict[str, str]:
    """SHA-256 of Route 29's events member, vanilla and with the proof edit."""
    import hashlib
    import tempfile
    from . import world
    base = world.load_base(world.RomSource(cli.REPO / "rom.nds"))
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            write(Path(tmp))
        edited = world.apply_overrides(base, Path(tmp))
    return {"vanilla": hashlib.sha256(base.raw["events"][EVENTS_BANK]).hexdigest(),
            "edited": hashlib.sha256(edited.raw["events"][EVENTS_BANK]).hexdigest()}


def probe(rom: str, save: str) -> int:
    expected = expected_event_hashes()
    _ow("start", "--rom", rom, "--save", save)
    try:
        _ow("teleport", str(MAP_ROUTE_29), str(BLOCK_TILE[0]), str(BLOCK_TILE[1] + 1), "--facing", "0")
        terrain = _ow("terrain", "--x", str(BLOCK_TILE[0]), "--z", str(BLOCK_TILE[1]), "--radius", "0")
        terrain = terrain.get("terrain", terrain)
        blocked_cells = terrain["cellSummary"]["blocked"]
        loaded_events = terrain.get("events") or {}
        loaded_warp = any((w["x"], w["y"], w["header"], w["anchor"]) ==
                          (NEW_WARP["x"], NEW_WARP["z"], NEW_WARP["header"], NEW_WARP["anchor"])
                          for w in terrain["warps"])
        start = _where()
        _ow("step", "24", "--keys", "UP")
        _ow("step", "60")
        after_block = _where()

        _ow("teleport", str(MAP_ROUTE_29), str(OPEN_CONTROL[0]), str(OPEN_CONTROL[1]), "--facing", "0")
        control_start = _where()
        _ow("step", "8", "--keys", "UP")  # short hold: the gate warp is 6 tiles north
        _ow("step", "60")
        control_after = _where()

        _ow("teleport", str(MAP_ROUTE_29), str(PANEL_TILE[0]), str(PANEL_TILE[1] - 1), "--facing", "1")
        _ow("step", "24", "--keys", "DOWN")
        _ow("step", "90")
        after_panel = _where()
    finally:
        _ow("stop")
    checks = {
        "teleportedToBlockStart": start == (MAP_ROUTE_29, BLOCK_TILE[0], BLOCK_TILE[1] + 1),
        "controlStepMoves": (control_start == (MAP_ROUTE_29, *OPEN_CONTROL) and control_after[0] == MAP_ROUTE_29
                             and control_after[2] < OPEN_CONTROL[1]),
        "blockTileCollisionBit": blocked_cells == 1,
        "newWarpInLoadedTable": loaded_warp,
        "loadedEventsEqualEditedFile": loaded_events.get("sha256") == expected["edited"],
        "stepIntoBlockRefused": after_block == start,
        "panelWarpsToGate": after_panel == GATE_LANDING,
    }
    print(json.dumps({"start": start, "afterBlock": after_block, "control": [control_start, control_after],
                      "afterPanel": after_panel, "loadedEvents": loaded_events,
                      "loadedEventsIsVanilla": loaded_events.get("sha256") == expected["vanilla"],
                      "checks": checks, "passed": all(checks.values())}))
    return 0 if all(checks.values()) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.proof_route29", description=__doc__,
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
