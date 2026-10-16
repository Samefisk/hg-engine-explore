"""Generate vanilla-looking map chunks from an ASCII layout.

  python3 -B -m tools.maps.style examples --map 33 --count 3   # learn from vanilla
  python3 -B -m tools.maps.style generate --layout L.txt --map 33 --land 676 [--seeds 16] [--relax 1]
  python3 -B -m tools.maps.style new-map --map 541 --template 33 --land 676 --start 16 16
  python3 -B -m tools.maps.style resolve --land 682 (--region X0 Z0 W H | --hotspots K) [--set X Z C] [--seeds 4] [--write]
  python3 -B -m tools.maps.style inspect --map 543 --x 16 --z 44 [--radius 2]

`generate` solves the layout with cells from the kit of map 33's tileset,
scores every seed, keeps the best one that passes all gates (score.GATES),
and writes data/maps/land/NNNN/{land.json, model.nsbmd}. A land id equal to
the archive length appends a new chunk. The report (scores, the realized
layout) goes to build/map-style/report-NNNN.json; nothing ROM-derived is
written outside the override tree.

`resolve` re-solves only the given regions of a generated map (report grid
coordinates with --land, matrix-wide with --map) and keeps every other tile;
`inspect` prints the judge's and the game's view of one tile as JSON. Both
are in edit.py. After `generate` or `resolve --write`, the showcase maps need
`python3 -B -m tools.maps.showcase write` again.

`new-map` scaffolds a standalone map around a generated chunk: a 1x1
matrix, an events file with one warp tile at --start (so lint can check
reachability), and a header copied from --template with those ids.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
             seeds: int = 16, relax_depth: int = 0, edges: dict | None = None, seed_start: int = 0) -> dict:
    base = _base()
    tileset = _tileset_of_map(base, map_id)
    started = time.time()
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    rows = layout.parse(layout_text)
    if relax_depth:
        rows = layout.relax(rows, relax_depth)
    windows, pairs = score.vanilla_windows(kit), score.vanilla_pairs(kit)
    model = wfc.learn(kit) if edges else None
    candidates, errors = [], []
    for seed in range(seed_start, seed_start + seeds):
        try:
            if edges:  # pinned seams need the tile-level solver
                grid = wfc.solve(kit, rows, seed=seed, edges=edges, model=model)
            else:
                grid = quilt.solve(kit, rows, seed)
        except wfc.SolveError as error:
            errors.append(str(error))
            continue
        result = score.score(kit, grid, rows, windows=windows, pairs=pairs)
        candidates.append((rank(result), seed, grid, result))
    if not candidates:
        raise SystemExit("no seed solved the layout:\n  " + "\n  ".join(sorted(set(errors))[:5]))
    candidates.sort(key=lambda c: (c[0], c[1]))
    _, seed, grid, result = candidates[0]  # gates, then fewest problems, then best joins
    passed = not score.passes(result)
    report = {"map": map_id, "tileset": tileset, "land": land_id, "seed": seed, "score": result,
              "failedGates": score.passes(result), "seedsTried": seeds, "seedsSolved": len(candidates),
              "realizedLayout": layout.render(grid, kit), "hotspots": score.hotspots(kit, grid),
              "grid": grid, "layout": rows, "relax": relax_depth,
              "seconds": round(time.time() - started, 1)}
    if not passed:
        report["written"] = False
        return report
    report.update(write_lands(base, kit, grid, map_id, land_id, overrides))
    return report


def rank(result: dict) -> tuple:
    """Seed ranking key, lower is better: failed gates, then fewest problems, then best joins."""
    return (len(score.passes(result)), result["criticalMismatches"], result["rigidViolations"],
            result["holes"], -result["seamRate"])


def _replace(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def model_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_lands(base, kit: dict, grid: list[list[int]], map_id: int, land_id: int, overrides: Path,
                write: bool = True) -> dict:
    """Compose a solved grid into land overrides; report fields (written, lands, chunks, ...).

    Multi-chunk layouts are solved as one grid (so chunk seams are solved
    too), then split into chunks with consecutive land ids in reading order.
    Every chunk is composed and checked against the game limits first; files
    are written only after all of them passed, each through a temporary file.
    `modelHashes` (SHA-256 per land model) lets a later resolve check that the
    lands on disk are still the ones this grid made. write=False only composes.
    """
    area = base.member("area", base.headers[map_id]["areaDataBank"])
    anim_materials = kits.area_animation_materials(world.RomSource(REPO / "rom.nds"), area["dynamicTextureType"])
    lands, sizes, outputs = [], [], []
    chunk_w, chunk_h = len(grid[0]) // layout.GRID, len(grid) // layout.GRID
    for cz in range(chunk_h):
        for cx in range(chunk_w):
            this_land = land_id + cz * chunk_w + cx
            part = [row[cx * layout.GRID:(cx + 1) * layout.GRID]
                    for row in grid[cz * layout.GRID:(cz + 1) * layout.GRID]]
            model_bytes, tiles, corners = kits.compose(kit, part, f"gen_{this_land:04d}",
                                                         anim_materials=anim_materials)
            bdhc = bdhc_gen.bdhc_from_corners(corners)
            land = {"backgroundSound": "", "tiles": tiles, "buildings": [], "bdhc": bdhc}
            codecs.encode_land(land, model_bytes)  # every game limit is checked here
            outputs.append((this_land, land, model_bytes))
            lands.append(this_land)
            sizes.append(len(model_bytes))
    for this_land, land, model_bytes in outputs if write else ():  # only after every chunk passed
        target = overrides / "land" / f"{this_land:04d}"
        target.mkdir(parents=True, exist_ok=True)
        _replace(target / "land.json", (json.dumps(land, indent=1) + "\n").encode())
        _replace(target / "model.nsbmd", model_bytes)
    return {"animMaterials": anim_materials, "written": [str(overrides / "land" / f"{n:04d}") for n in lands],
            "lands": lands, "chunks": [chunk_w, chunk_h], "modelBytes": sizes,
            "modelHashes": {str(n): model_sha(m) for n, _, m in outputs}}


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
    gen.add_argument("--seed-start", type=int, default=0, help="first seed (to continue a search)")
    ex = sub.add_parser("examples")
    ex.add_argument("--map", type=int, required=True)
    ex.add_argument("--count", type=int, default=3)
    new = sub.add_parser("new-map")
    new.add_argument("--map", type=int, required=True)
    new.add_argument("--template", type=int, required=True)
    new.add_argument("--land", type=int, required=True)
    new.add_argument("--start", type=int, nargs=2, required=True, metavar=("X", "Z"))
    new.add_argument("--chunks", type=int, nargs=2, default=(1, 1), metavar=("W", "H"))
    res = sub.add_parser("resolve", help="re-solve regions of a generated map, keep the rest")
    where = res.add_mutually_exclusive_group(required=True)
    where.add_argument("--land", type=int, help="a land of the report; coordinates are report-grid x/z")
    where.add_argument("--map", type=int, help="a map using the lands; coordinates are matrix-wide x/z")
    res.add_argument("--region", type=int, nargs=4, action="append", default=[], metavar=("X0", "Z0", "W", "H"))
    res.add_argument("--hotspots", type=int, default=0, metavar="K", help="also the report's top K 8x8 hotspots")
    res.add_argument("--set", type=str, nargs=3, action="append", default=[], metavar=("X", "Z", "CHAR"),
                     help="change the intent layout char at X Z (inside a region) before solving")
    res.add_argument("--layout", type=Path, help="intent layout, for reports without a stored one")
    res.add_argument("--relax", type=int, default=0, help="with --layout: the --relax generate used")
    res.add_argument("--seeds", type=int, default=4)
    res.add_argument("--write", action="store_true", help="write lands and report (default: dry run)")
    ins = sub.add_parser("inspect", help="one tile as JSON: cell, joins, overhangs, events")
    where = ins.add_mutually_exclusive_group(required=True)
    where.add_argument("--map", type=int, help="x/z are matrix-wide map coordinates")
    where.add_argument("--land", type=int, help="x/z are report-grid coordinates (land-local without a report)")
    ins.add_argument("--x", type=int, required=True)
    ins.add_argument("--z", type=int, required=True)
    ins.add_argument("--radius", type=int, default=0, help="also an ASCII neighbourhood of this radius")
    ins.add_argument("--layout", type=Path, help="intent layout, for reports without a stored one")
    ins.add_argument("--relax", type=int, default=0)
    args = parser.parse_args(argv)
    if args.command in ("resolve", "inspect"):
        from . import edit
        layout_text = args.layout.read_text() if args.layout else None
        try:
            if args.command == "inspect":
                print(json.dumps(edit.inspect_tile(args.map, args.x, args.z, args.radius, land=args.land,
                                                   layout_text=layout_text, relax_depth=args.relax), indent=1))
                return 0
            sets = [(int(x), int(z), ch) for x, z, ch in args.set]
            result = edit.resolve(args.land, args.map, args.region, args.hotspots, sets, layout_text,
                                  args.relax, args.seeds, args.write, args.overrides)
        except (edit.EditError, layout.LayoutError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=1))
        return 0 if result["improved"] and (result["written"] or not args.write) else 1
    if args.command == "examples":
        print("\n".join(examples(args.map, args.count)))
        return 0
    if args.command == "generate":
        report = generate(args.layout.read_text(), args.map, args.land, args.overrides, args.seeds, args.relax,
                          seed_start=args.seed_start)
        # Reports describe the grid written to *these* overrides; a scratch tree keeps its own.
        default = args.overrides.resolve() == (REPO / "data/maps").resolve()
        report_dir = REPORT_DIR if default else args.overrides.parent / "map-style-reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"report-{args.land:04d}.json").write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k not in ("realizedLayout", "written", "grid")}, indent=1))
        return 0 if report.get("written") else 1
    print(json.dumps(new_map(args.map, args.template, args.land, tuple(args.start), args.overrides,
                             tuple(args.chunks))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
