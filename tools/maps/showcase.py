"""Wire the three generated showcase maps (541-543) into the game.

  python3 -B -m tools.maps.showcase design   # briefs -> semantic maps + plans, then paint the lands
  python3 -B -m tools.maps.showcase write    # after design (or a paint/resolve): events, panels
  python3 -B -m tools.maps.showcase probe    # live melonDS walk-through, JSON out
  python3 -B -m tools.maps.showcase shots    # screenshot sheets, ONLY when the user asks

Cherrygrove (map 67) gets three warp panels just south-west of the
Pokémon Center door, one per showcase map, and a plain arrival tile for
the way back. Each showcase map has a plain arrival tile and a return
panel one step south of it. Plain-tile warps never trigger, so arriving
can never bounce you straight back.

Each map is designed from a brief in data/maps/designs/ (style/design.py):
NNN-name.brief.json (gameplay intent) -> NNN-name.semantic.txt (what every
tile is) + NNN-name.plan.json (route, exits, ledges, trainer and item spots),
then painted with vanilla cells (style/paint.py).

Content reuses the template maps' own local scripts (the headers point at
their script and text banks): Route 29's talkers, signs and apricorn tree in
Twinwood Crossing, Route 44's signs and apricorn tree in Mirrorlake Basin.
They go to the plan's trainer and item spots, each snapped to the nearest
open, reachable tile of the painted terrain. The probe's goal checks come
from the plan too: jump each designed ledge (and fail to climb it), and walk
the route across a chunk seam.
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
    # map, name, arrival (plain), return panel, Cherrygrove panel, design (data/maps/designs/<design>.*)
    {"map": 541, "name": "Twinwood Crossing", "arrival": (32, 57), "panel": (32, 58), "door": (559, 394),
     "design": "541-twinwood-crossing", "land": 676},
    {"map": 542, "name": "Mirrorlake Basin", "arrival": (5, 16), "panel": (5, 17), "door": (561, 394),
     "design": "542-mirrorlake-basin", "land": 680},
    {"map": 543, "name": "Echo Cavern", "arrival": (16, 60), "panel": (16, 61), "door": (563, 394),
     "design": "543-echo-cavern", "land": 682},
]
DESIGNS = cli.REPO / "data/maps/designs"

# Template script content per map: object and bg (sign) indices into the template's events.
CONTENT = {
    541: {"template": 33, "objects": [0, 1, 2, 3, 9], "bgs": [0, 1]},
    542: {"template": 46, "objects": [7], "bgs": [0, 1]},
    543: {"template": 107, "objects": [], "bgs": []},
}


def design_files(entry: dict) -> dict[str, Path]:
    stem = DESIGNS / entry["design"]
    return {k: stem.with_name(f"{stem.name}.{k}{ext}") for k, ext in
            (("brief", ".json"), ("semantic", ".txt"), ("plan", ".json"))}


def load_plan(entry: dict) -> dict:
    return json.loads(design_files(entry)["plan"].read_text())


def wanted_spots(entry: dict, plan: dict) -> tuple[list, list]:
    """(object spots, sign spots) in priority order: trainers, items, then along the route."""
    route = [tuple(p) for p in plan.get("route", [])]
    trainers = [(t["x"], t["z"]) for t in plan.get("trainers", [])]
    items = [(i["x"], i["z"]) for i in plan.get("items", [])]
    along = [route[int(len(route) * f)] for f in (0.2, 0.4, 0.6, 0.8)] if route else []
    ax, az = entry["arrival"]
    signs = [(ax + 2, az - 1)] + ([route[len(route) // 2]] if route else [])
    return trainers + items + along, signs


def design(overrides: Path, maps: list[int] | None = None, seeds: int = 1) -> None:
    """Design every showcase map from its brief and paint its lands."""
    from .style import cli as style_cli, design as style_design
    for entry in SHOWCASE:
        if maps and entry["map"] not in maps:
            continue
        files = design_files(entry)
        brief = json.loads(files["brief"].read_text())
        sem, plan_, facts = style_design.design(brief)
        if facts["problems"]:
            raise SystemExit(f"map {entry['map']}: design problems {facts['problems']}")
        files["semantic"].write_text(f"# {entry['name']}: designed from {files['brief'].name}\n" + sem.to_text())
        files["plan"].write_text(json.dumps({"brief": brief, "intent": plan_.text().splitlines(), **facts,
                                             "notes": plan_.notes, "route": [list(p) for p in plan_.route]},
                                            indent=1) + "\n")
        report = style_cli.paint_lands(files["semantic"].read_text(), brief["template"], entry["land"],
                                       overrides, seeds)
        report_dir = style_cli.REPORT_DIR if overrides.resolve() == (cli.REPO / "data/maps").resolve() \
            else overrides.parent / "map-style-reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"report-{entry['land']:04d}.json").write_text(json.dumps(report, indent=1) + "\n")
        print(f"map {entry['map']} {entry['name']}: lands {report['lands']}, paint {report['paint']}, "
              f"labelMatch {report['labelMatch']}")


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
        object_spots, sign_spots = wanted_spots(entry, load_plan(entry))
        objects = []
        for number, (index, want) in enumerate(zip(content["objects"], object_spots)):
            x, z = _snap(edited, map_id, tuple(want), taken)
            taken.add((x, z))
            objects.append({**template["objects"][index], "id": number, "x": x, "z": z})
        bgs = []
        for index, want in zip(content["bgs"], sign_spots):
            x, z = _snap(edited, map_id, tuple(want), taken)
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


def goal_specs() -> list[dict]:
    """Measurable goals from the design plans: each ledge jumps one way, the route crosses a
    chunk seam where the map has more than one chunk."""
    from .style import semantic
    out = []
    for entry in SHOWCASE:
        plan = load_plan(entry)
        sem = semantic.SemanticMap.from_text(design_files(entry)["semantic"].read_text())
        walk = lambda x, z: 0 <= z < len(sem.walk) and 0 <= x < len(sem.walk[0]) and sem.walk[z][x] in ".,"
        for span in plan.get("notes", {}).get("ledgeTiles", [])[:1]:
            spots = [(x, z) for x, z in span if walk(x, z - 1) and walk(x, z + 1) and sem.walk[z][x] == "v"]
            if spots:
                x, z = spots[len(spots) // 2]
                out.append({"name": f"{entry['map']} ledge is one-way", "map": entry["map"], "kind": "ledge",
                            "top": (x, z - 1), "bottom": (x, z + 1)})
        route = [tuple(p) for p in plan.get("route", [])]
        for a, b in zip(route, route[1:]):
            if (a[0] // 32, a[1] // 32) != (b[0] // 32, b[1] // 32) and walk(*a) and walk(*b):
                dx, dz = b[0] - a[0], b[1] - a[1]
                key, facing = {(1, 0): ("RIGHT", 3), (-1, 0): ("LEFT", 2), (0, 1): ("DOWN", 1),
                               (0, -1): ("UP", 0)}[(dx, dz)]
                out.append({"name": f"{entry['map']} crosses chunk seam", "map": entry["map"], "kind": "seam",
                            "start": a, "key": key, "facing": facing, "to": b})
                break
    return out


def goal_checks() -> dict:
    """One measured check per design goal (runs inside a session)."""
    out = {}
    for goal in goal_specs():
        m = goal["map"]
        if goal["kind"] == "ledge":
            before, after = _move(m, goal["top"], 1, "DOWN", 8)
            _, back = _move(m, goal["bottom"], 0, "UP", 16)
            out[goal["name"]] = {"down": [before, after], "upAttempt": back,
                                 "pass": before == (m, *goal["top"]) and after == (m, *goal["bottom"])
                                 and back == (m, *goal["bottom"])}
        else:
            before, after = _move(m, goal["start"], goal["facing"], goal["key"], 8)
            # Walked off the start and ended in the chunk across the seam (a held key may
            # carry the player more than one tile).
            to_chunk = (goal["to"][0] // 32, goal["to"][1] // 32)
            out[goal["name"]] = {"before": before, "after": after,
                                 "pass": before == (m, *goal["start"]) and after[0] == m
                                 and (after[1] // 32, after[2] // 32) == to_chunk}
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


SHOTS_DIR = cli.REPO / "build/map-showcase-screens"


def _viewpoints(edited, entry: dict) -> list[tuple[str, tuple[int, int]]]:
    """A 3 x 3 spread of standable tiles over the map (nearest land to each target)."""
    from .style import semantic
    rows = [r.replace(",", ".") for r in
            semantic.SemanticMap.from_text(design_files(entry)["semantic"].read_text()).walk]
    height, width = len(rows), len(rows[0])
    land = [(x, z) for z in range(height) for x in range(width)
            if rows[z][x] in ".," and (t := edited.tile(entry["map"], x, z)) and not t[0]]
    out = []
    for j, fz in enumerate((0.2, 0.5, 0.8)):
        for i, fx in enumerate((0.2, 0.5, 0.8)):
            tx, tz = int(fx * width), int(fz * height)
            x, z = min(land, key=lambda p: (abs(p[0] - tx) + abs(p[1] - tz), p))
            out.append((f"{entry['map']}-{'nms'[j]}{'wce'[i]}-x{x:02d}-z{z:02d}", (x, z)))
    return out


def _teleport_when_idle(map_id: int, x: int, z: int, tries: int = 6) -> None:
    """Teleport, waiting out a follower still moving from the last spot (owctl reports busy)."""
    for attempt in range(tries):
        try:
            _ow("teleport", str(map_id), str(x), str(z), "--facing", "1")
            return
        except SystemExit as error:
            if '"busy"' not in str(error) or attempt == tries - 1:
                raise
            _ow("step", "60")


def shots(rom: str, save: str) -> int:
    """Capture each showcase map at nine spots and write one contact sheet per map.

    Screenshots are for the user's visual review. Run only when the user asks
    for them (AGENTS.md); agents never inspect images as a test step.
    """
    import shutil
    from PIL import Image, ImageDraw
    base = world.load_base(world.RomSource(cli.REPO / "rom.nds"))
    edited = world.apply_overrides(base, cli.REPO / "data/maps")
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    plan = [(entry, _viewpoints(edited, entry)) for entry in SHOWCASE]
    _ow("start", "--rom", rom, "--save", save)
    try:
        for entry, views in plan:
            files = []
            for name, (x, z) in views:
                _teleport_when_idle(entry["map"], x, z)
                _ow("step", "90")
                target = SHOTS_DIR / f"{name}.png"
                shutil.copy(_ow("capture")["screenshot"]["path"], target)
                files.append(target)
            scale, label = 2, 14
            cell_w, cell_h = 256 * scale, (192 + label) * scale
            sheet = Image.new("RGB", (cell_w * 3, cell_h * 3), "white")
            draw = ImageDraw.Draw(sheet)
            for i, path in enumerate(files):
                top = Image.open(path).convert("RGB").crop((0, 0, 256, 192))
                x0, y0 = (i % 3) * cell_w, (i // 3) * cell_h
                sheet.paste(top.resize((256 * scale, 192 * scale), Image.NEAREST), (x0, y0 + label * scale))
                draw.text((x0 + 6, y0 + 6), path.stem, fill="black")
            out = SHOTS_DIR / f"sheet-{entry['map']}.png"
            sheet.save(out)
            print(out)
    finally:
        _ow("stop")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.showcase", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("design", "write", "probe", "shots"))
    parser.add_argument("--overrides", type=Path, default=cli.REPO / "data/maps")
    parser.add_argument("--map", type=int, action="append", help="design: only these maps")
    parser.add_argument("--seeds", type=int, default=1, help="design: paint seeds per map")
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--save", default="test.sav")
    args = parser.parse_args(argv)
    if args.action == "design":
        design(args.overrides, args.map, args.seeds)
        return 0
    if args.action == "write":
        write(args.overrides)
        return 0
    if args.action == "shots":
        return shots(args.rom, args.save)
    return probe(args.rom, args.save)


if __name__ == "__main__":
    sys.exit(main())
