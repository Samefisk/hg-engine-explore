"""Generate vanilla-looking map chunks from an ASCII layout.

  python3 -B -m tools.maps.style examples --map 33 --count 3   # learn from vanilla
  python3 -B -m tools.maps.style generate --layout L.txt --map 33 --land 676 [--seeds 16] [--relax 1]
  python3 -B -m tools.maps.style new-map --map 541 --template 33 --land 676 --start 16 16

`generate` solves the layout with cells from the kit of map 33's tileset,
scores every seed, keeps the best one that passes all gates (score.GATES),
and writes data/maps/land/NNNN/{land.json, model.nsbmd}. A land id equal to
the archive length appends a new chunk. The report (scores, the realized
layout) goes to build/map-style/report-NNNN.json; nothing ROM-derived is
written outside the override tree.

`new-map` scaffolds a standalone map around a generated chunk: a 1x1
matrix, an events file with one warp tile at --start (so lint can check
reachability), and a header copied from --template with those ids.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .. import codecs, world
from ..cli import REPO
from . import bdhc_gen, kit as kits, layout, quilt, score, wfc

REPORT_DIR = REPO / "build/map-style"


def _base():
    return world.load_base(world.RomSource(REPO / "rom.nds"), repo=REPO)


def _tileset_of_map(base, map_id: int) -> int:
    return base.member("area", base.headers[map_id]["areaDataBank"])["mapTileset"]


def generate(layout_text: str, map_id: int, land_id: int, overrides: Path,
             seeds: int = 16, relax_depth: int = 0, edges: dict | None = None) -> dict:
    base = _base()
    tileset = _tileset_of_map(base, map_id)
    started = time.time()
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    rows = layout.parse(layout_text)
    if relax_depth:
        rows = layout.relax(rows, relax_depth)
    model = wfc.learn(kit)
    windows = score.vanilla_windows(kit)
    candidates, errors = [], []
    for seed in range(seeds):
        try:
            if edges:  # pinned seams need the tile-level solver
                grid = wfc.solve(kit, rows, seed=seed, edges=edges, model=model)
            else:
                grid = quilt.solve(kit, rows, seed)
        except wfc.SolveError as error:
            errors.append(str(error))
            continue
        result = score.score(kit, grid, rows, model=model, windows=windows)
        candidates.append((not score.passes(result), -result["criticalMismatches"], result["edgeRate"],
                           seed, grid, result))
    if not candidates:
        raise SystemExit("no seed solved the layout:\n  " + "\n  ".join(sorted(set(errors))[:5]))
    candidates.sort(key=lambda c: c[:3], reverse=True)
    passed, _, _, seed, grid, result = candidates[0]  # gates, then most vanilla-like
    report = {"map": map_id, "tileset": tileset, "land": land_id, "seed": seed, "score": result,
              "failedGates": score.passes(result), "seedsTried": seeds, "seedsSolved": len(candidates),
              "realizedLayout": layout.render(grid, kit), "seconds": round(time.time() - started, 1)}
    if not passed:
        report["written"] = False
        return report

    # Multi-chunk layouts are solved as one grid (so chunk seams are solved
    # too), then split into chunks with consecutive land ids in reading order.
    lands, sizes, outputs = [], [], []
    chunk_w = len(grid[0]) // layout.GRID
    for cx, cz, _rows in layout.chunks(rows):
        this_land = land_id + cz * chunk_w + cx
        part = [row[cx * layout.GRID:(cx + 1) * layout.GRID]
                for row in grid[cz * layout.GRID:(cz + 1) * layout.GRID]]
        model_bytes, tiles, corners = kits.compose(kit, part, f"gen_{this_land:04d}")
        bdhc = bdhc_gen.bdhc_from_corners(corners)
        land = {"backgroundSound": "", "tiles": tiles, "buildings": [], "bdhc": bdhc}
        codecs.encode_land(land, model_bytes)  # every game limit is checked here
        outputs.append((this_land, land, model_bytes))
        lands.append(this_land)
        sizes.append(len(model_bytes))
    for this_land, land, model_bytes in outputs:  # write only after every chunk passed
        target = overrides / "land" / f"{this_land:04d}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "land.json").write_text(json.dumps(land, indent=1) + "\n")
        (target / "model.nsbmd").write_bytes(model_bytes)
    report.update(written=[str(overrides / "land" / f"{n:04d}") for n in lands], lands=lands,
                  chunks=[chunk_w, len(grid) // layout.GRID], modelBytes=sizes)
    return report


def new_map(map_id: int, template: int, land_id: int, start: tuple[int, int], overrides: Path,
            size: tuple[int, int] = (1, 1)) -> dict:
    """W x H matrix (consecutive land ids from land_id) + events with one warp tile + header."""
    base = world.apply_overrides(_base(), overrides)
    matrix_id, events_id = len(base.raw["matrix"]), len(base.raw["events"])
    width, height = size
    matrix = {"width": width, "height": height, "name": f"gen{map_id}",
              "headers": [[map_id] * width for _ in range(height)], "altitudes": None,
              "landData": [[land_id + z * width + x for x in range(width)] for z in range(height)]}
    events = {"bgs": [], "objects": [], "coords": [],
              # A warp tile so lint seeds reachability; it leads to the template map's first warp.
              "warps": [{"x": start[0], "z": start[1], "header": template, "anchor": 0, "y": 0}]}
    header = {k: v for k, v in base.headers[template].items() if k != "alias"}
    header.update(id=map_id, name=f"GEN{map_id}", matrixId=matrix_id, eventsBank=events_id)
    for kind, index, spec in (("matrix", matrix_id, matrix), ("events", events_id, events),
                              ("headers", map_id, header)):
        path = overrides / kind / f"{index:04d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, indent=1) + "\n")
    return {"map": map_id, "matrix": matrix_id, "events": events_id, "land": land_id}


def examples(map_id: int, count: int) -> list[str]:
    """Vanilla chunks of the map's tileset as class layouts, the map's own first."""
    base = _base()
    tileset = _tileset_of_map(base, map_id)
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    matrix = base.matrix_for(map_id)
    own = [land for z, row in enumerate(matrix["landData"]) for x, land in enumerate(row)
           if land in kit["chunks"] and (matrix["headers"] is None or matrix["headers"][z][x] == map_id)]
    ordered = own + sorted(land for land in kit["chunks"] if land not in own)
    out = []
    for land in ordered[:count]:
        out.append(f"# land {land} (tileset {tileset})")
        out += layout.render(kit["chunks"][land], kit)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.style", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overrides", type=Path, default=REPO / "data/maps")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--layout", type=Path, required=True)
    gen.add_argument("--map", type=int, required=True, help="map whose area tileset to use")
    gen.add_argument("--land", type=int, required=True, help="land id to replace or append")
    gen.add_argument("--seeds", type=int, default=16)
    gen.add_argument("--relax", type=int, default=0)
    ex = sub.add_parser("examples")
    ex.add_argument("--map", type=int, required=True)
    ex.add_argument("--count", type=int, default=3)
    new = sub.add_parser("new-map")
    new.add_argument("--map", type=int, required=True)
    new.add_argument("--template", type=int, required=True)
    new.add_argument("--land", type=int, required=True)
    new.add_argument("--start", type=int, nargs=2, required=True, metavar=("X", "Z"))
    new.add_argument("--chunks", type=int, nargs=2, default=(1, 1), metavar=("W", "H"))
    args = parser.parse_args(argv)
    if args.command == "examples":
        print("\n".join(examples(args.map, args.count)))
        return 0
    if args.command == "generate":
        report = generate(args.layout.read_text(), args.map, args.land, args.overrides, args.seeds, args.relax)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / f"report-{args.land:04d}.json").write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k not in ("realizedLayout", "written")}, indent=1))
        return 0 if report.get("written") else 1
    print(json.dumps(new_map(args.map, args.template, args.land, tuple(args.start), args.overrides,
                             tuple(args.chunks))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
