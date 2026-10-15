"""Wire the three generated showcase maps (541-543) into the game.

  python3 -B -m tools.maps.showcase write    # after tools.maps.style generate/new-map
  python3 -B -m tools.maps.showcase probe    # live melonDS walk-through, JSON out

Cherrygrove (map 67) gets three warp panels just south-west of the
Pokémon Center door, one per showcase map, and a plain arrival tile for
the way back. Each showcase map has a plain arrival tile and a return
panel one step south of it. Plain-tile warps never trigger, so arriving
can never bounce you straight back.

Content reuses the template maps' own local scripts (the headers point at
their script and text banks): Route 29's talkers, signs and apricorn tree in
Twinwood Crossing, Route 44's signs and apricorn tree in Mirrorlake Basin.
Every placement snaps to the nearest open, reachable tile of the generated
terrain, so regenerating a map keeps the content valid.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

from . import cli, world
from .proof_route29 import _ow, _where

CHERRYGROVE, CHERRYGROVE_LAND, CHERRYGROVE_ORIGIN = 67, 5, (544, 384)
WARP_PANEL = 0x67
# Level-script bank with no entries (vanilla bank 399, used by 89 maps). The
# templates' own banks carry story triggers: Union Cave 1F's on-frame table
# walks the player east and locks input when copied to a new map.
EMPTY_LEVEL_SCRIPTS = 399
CHERRYGROVE_ARRIVAL = (561, 393)   # plain tile: where you land coming back
SAVE_START = (564, 392)            # test.sav continues here, facing the PC door

SHOWCASE = [
    # map, name, arrival (plain), return panel, Cherrygrove panel
    {"map": 541, "name": "Twinwood Crossing", "arrival": (32, 57), "panel": (32, 58), "door": (559, 394)},
    {"map": 542, "name": "Mirrorlake Basin", "arrival": (5, 16), "panel": (5, 17), "door": (561, 394)},
    {"map": 543, "name": "Echo Cavern", "arrival": (16, 60), "panel": (16, 61), "door": (563, 394)},
]

# (template object/bg index, wanted position) per map
CONTENT = {
    541: {"template": 33, "objects": [(0, (31, 50)), (1, (30, 27)), (2, (17, 22)), (3, (46, 31)), (9, (27, 24))],
          "bgs": [(0, (34, 53)), (1, (16, 10))]},
    542: {"template": 46, "objects": [(7, (55, 21))], "bgs": [(0, (7, 15)), (1, (31, 4))]},
    543: {"template": 107, "objects": [], "bgs": []},
}


def _land_path(overrides: Path, land: int) -> Path:
    return overrides / "land" / f"{land:04d}" / "land.json"


def _set_behavior(overrides: Path, land: int, local: tuple[int, int], behavior: int) -> None:
    path = _land_path(overrides, land)
    spec = json.loads(path.read_text())
    x, z = local
    if spec["tiles"]["collision"][z][x] == "#":
        raise SystemExit(f"land {land} tile {local} is blocked; cannot place a warp panel there")
    row = spec["tiles"]["behavior"][z].split()
    row[x] = f"{behavior:02x}"
    spec["tiles"]["behavior"][z] = " ".join(row)
    path.write_text(json.dumps(spec, indent=1) + "\n")


def _land_of(edited, map_id: int, x: int, z: int) -> tuple[int, tuple[int, int]]:
    matrix = edited.matrix_for(map_id)
    return matrix["landData"][z // 32][x // 32], (x % 32, z % 32)


def _snap(edited, map_id: int, want: tuple[int, int], taken: set) -> tuple[int, int]:
    """Nearest open tile (with an open neighbour) to `want`, breadth-first."""
    queue, seen = deque([want]), {want}
    while queue:
        x, z = queue.popleft()
        tile = edited.tile(map_id, x, z)
        neighbours = [(x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)]
        if tile and not tile[0] and tile[1] == 0 and (x, z) not in taken and any(
                (t := edited.tile(map_id, *n)) and not t[0] for n in neighbours):
            return x, z
        for n in neighbours:
            if n not in seen and edited.tile(map_id, *n) is not None:
                seen.add(n)
                queue.append(n)
    raise SystemExit(f"no open tile near {want} on map {map_id}")


def write(overrides: Path) -> None:
    base = world.load_base(world.RomSource(cli.REPO / "rom.nds"))
    # Cherrygrove events + its chunk (owned only by Cherrygrove).
    events_bank = base.headers[CHERRYGROVE]["eventsBank"]
    cherry_events = base.member("events", events_bank)
    land_dir = overrides / "land" / f"{CHERRYGROVE_LAND:04d}"
    if not land_dir.exists():
        land_dir.mkdir(parents=True)
        (land_dir / "land.json").write_text(json.dumps(base.member("land", CHERRYGROVE_LAND), indent=1) + "\n")
    else:
        land = json.loads((land_dir / "land.json").read_text())
        land["tiles"] = base.member("land", CHERRYGROVE_LAND)["tiles"]  # rebuild panels from vanilla
        (land_dir / "land.json").write_text(json.dumps(land, indent=1) + "\n")
    arrival_index = len(cherry_events["warps"]) + len(SHOWCASE)
    warps = [dict(w) for w in cherry_events["warps"]]
    for entry in SHOWCASE:
        x, z = entry["door"]
        warps.append({"x": x, "z": z, "header": entry["map"], "anchor": 0, "y": 0})
        _set_behavior(overrides, CHERRYGROVE_LAND, (x - CHERRYGROVE_ORIGIN[0], z - CHERRYGROVE_ORIGIN[1]), WARP_PANEL)
    warps.append({"x": CHERRYGROVE_ARRIVAL[0], "z": CHERRYGROVE_ARRIVAL[1],
                  "header": SHOWCASE[0]["map"], "anchor": 0, "y": 0})
    (overrides / "events" / f"{events_bank:04d}.json").write_text(
        json.dumps({**cherry_events, "warps": warps}, indent=1) + "\n")

    edited = world.apply_overrides(base, overrides)
    for entry in SHOWCASE:
        map_id = entry["map"]
        header = edited.headers[map_id]
        bank = header["eventsBank"]
        (ax, az), (px, pz) = entry["arrival"], entry["panel"]
        land, local = _land_of(edited, map_id, px, pz)
        _set_behavior(overrides, land, local, WARP_PANEL)
        content = CONTENT[map_id]
        template = base.member("events", base.headers[content["template"]]["eventsBank"])
        taken = {entry["arrival"], entry["panel"]}
        objects = []
        for number, (index, want) in enumerate(content["objects"]):
            x, z = _snap(edited, map_id, want, taken)
            taken.add((x, z))
            objects.append({**template["objects"][index], "id": number, "x": x, "z": z})
        bgs = []
        for index, want in content["bgs"]:
            x, z = _snap(edited, map_id, want, taken)
            taken.add((x, z))
            bgs.append({**template["bgs"][index], "x": x, "z": z})
        events = {"bgs": bgs, "objects": objects, "coords": [], "warps": [
            {"x": ax, "z": az, "header": CHERRYGROVE, "anchor": arrival_index, "y": 0},
            {"x": px, "z": pz, "header": CHERRYGROVE, "anchor": arrival_index, "y": 0}]}
        (overrides / "events" / f"{bank:04d}.json").write_text(json.dumps(events, indent=1) + "\n")
        name = entry["name"].upper().replace(" ", "")[:16]
        header_path = overrides / "headers" / f"{map_id:04d}.json"
        header_spec = json.loads(header_path.read_text())
        header_spec["name"] = name
        header_spec["scriptHeaderBank"] = EMPTY_LEVEL_SCRIPTS
        header_path.write_text(json.dumps(header_spec, indent=1) + "\n")
        print(f"map {map_id} {entry['name']}: {len(objects)} objects, {len(bgs)} signs, "
              f"arrival {entry['arrival']}, return panel {entry['panel']}")
    print(f"Cherrygrove: panels {[e['door'] for e in SHOWCASE]}, arrival {CHERRYGROVE_ARRIVAL}")


def _move(map_id: int, start: tuple[int, int], facing: int, key: str, frames: int):
    _ow("teleport", str(map_id), str(start[0]), str(start[1]), "--facing", str(facing))
    before = _where()
    _ow("step", str(frames), "--keys", key)
    _ow("step", "60")
    return before, _where()


def goal_checks() -> dict:
    """One measured check per map's headline goal (runs inside a session)."""
    out = {}
    # Twinwood Crossing: walk east across the x = 32 chunk seam in the long corridor.
    before, after = _move(541, (29, 42), 3, "RIGHT", 24)
    out["541 crosses chunk seam"] = {"before": before, "after": after,
                                     "pass": before == (541, 29, 42) and after[0] == 541 and after[1] >= 33}
    # Mirrorlake Basin: jump down terrace 1, then fail to climb it.
    before, after = _move(542, (20, 5), 1, "DOWN", 8)
    _, back = _move(542, (20, 7), 0, "UP", 16)
    out["542 terrace is one-way"] = {"down": [before, after], "upAttempt": back,
                                     "pass": before == (542, 20, 5) and after[2] >= 7 and back == (542, 20, 7)}
    # Echo Cavern: drop over the ledge into the central chamber.
    before, after = _move(543, (15, 10), 1, "DOWN", 8)
    out["543 ledge drop"] = {"before": before, "after": after,
                             "pass": before == (543, 15, 10) and after[0] == 543 and after[2] >= 12}
    return out


def probe(rom: str, save: str) -> int:
    """Walk from the save start onto each panel, check the map, walk back."""
    results = []
    _ow("start", "--rom", rom, "--save", save)
    try:
        start = _where()
        for entry in SHOWCASE:
            dx, dz = entry["door"]
            # Stand north of the panel, then step south onto it.
            _ow("teleport", str(CHERRYGROVE), str(dx), str(dz - 1), "--facing", "1")
            _ow("step", "8", "--keys", "DOWN")
            _ow("step", "120")
            arrived = _where()
            terrain = _ow("terrain", "--x", str(arrived[1]), "--z", str(arrived[2]), "--radius", "0")
            terrain = terrain.get("terrain", terrain)
            models = sorted({bytes.fromhex(m["headHex"])[0x34:0x44].split(b"\0")[0].decode("latin-1")
                             for c in (terrain.get("landModels") or {}).get("chunks", []) if c.get("known")
                             for m in c.get("models", [])})
            _ow("step", "60")
            stayed = _where()
            # Step onto the return panel (one south of the arrival tile).
            _ow("step", "8", "--keys", "DOWN")
            _ow("step", "120")
            back = _where()
            results.append({
                "map": entry["map"], "arrived": arrived, "stayedAfterArrival": stayed, "back": back,
                "loadedModels": models, "eventsKnown": (terrain.get("events") or {}).get("known"),
                "checks": {
                    "panelWarpsToMap": arrived == (entry["map"], *entry["arrival"]),
                    "arrivalDoesNotBounce": stayed == arrived,
                    "generatedModelsLoaded": bool(models) and all(m.startswith("gen_") for m in models),
                    "returnPanelWarpsBack": back == (CHERRYGROVE, *CHERRYGROVE_ARRIVAL),
                }})
        goals = goal_checks()
    finally:
        _ow("stop")
    passed = all(all(r["checks"].values()) for r in results) and all(g["pass"] for g in goals.values())
    print(json.dumps({"saveStart": start, "maps": results, "goals": goals, "passed": passed}, indent=1))
    return 0 if passed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.showcase", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("write", "probe"))
    parser.add_argument("--overrides", type=Path, default=cli.REPO / "data/maps")
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--save", default="test.sav")
    args = parser.parse_args(argv)
    if args.action == "write":
        write(args.overrides)
        return 0
    return probe(args.rom, args.save)


if __name__ == "__main__":
    sys.exit(main())
