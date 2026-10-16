"""Generate vanilla-looking map chunks from an ASCII layout.

  python3 -B -m tools.maps.style examples --map 33 --count 3   # learn from vanilla
  python3 -B -m tools.maps.style precheck --layout L.txt --map 33 [--relax 1]   # ~1 s, before generate
  python3 -B -m tools.maps.style design --brief B.json --out S.txt [--plan P.json]   # intent -> semantic map
  python3 -B -m tools.maps.style paint --semantic S.txt --map 33 --land 676 [--seeds 2]  # semantic map -> lands
  python3 -B -m tools.maps.style generate --layout L.txt --map 33 --land 676 [--seeds 16] [--relax 1]  # old: walk classes only
  python3 -B -m tools.maps.style new-map --map 541 --template 33 --land 676 --start 16 16
  python3 -B -m tools.maps.style resolve --land 682 (--region X0 Z0 W H | --hotspots K) [--set X Z C] [--seeds 4] [--write]
  python3 -B -m tools.maps.style inspect --map 543 --x 16 --z 44 [--radius 2]

`generate` solves the layout with cells from the kit of map 33's tileset,
scores every seed, keeps the best one that passes all gates (score.GATES),
and writes data/maps/land/NNNN/{land.json, model.nsbmd}. A land id equal to
the archive length appends a new chunk. The report (scores, the realized
layout) goes to build/map-style/report-NNNN.json; nothing ROM-derived is
written outside the override tree.

`design` + `paint` are the current pipeline (style-system.md, "Semantic
pipeline"): a brief of gameplay intent becomes a semantic map (what each tile
is: kind, floor level, walk class), and `paint` realises it with vanilla cells
(paint.py), writing lands and build/map-style/report-NNNN.json like generate.
`generate` (walk classes only) is kept for the old lab benchmark.

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

import numpy as np

from .. import codecs, world
from ..cli import REPO
from . import bdhc_gen, coverage, kit as kits, layout, quilt, score, wfc

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
    passed = not score.blocking(result)
    report = {"map": map_id, "tileset": tileset, "land": land_id, "seed": seed, "score": result,
              "failedGates": score.passes(result), "seedsTried": seeds, "seedsSolved": len(candidates),
              "realizedLayout": layout.render(grid, kit), "hotspots": score.hotspots(kit, grid),
              "grid": grid, "layout": rows, "relax": relax_depth,
              "seconds": round(time.time() - started, 1)}
    if result.get("renderVoid"):
        found = coverage.render_void(kit, np.array(grid))
        report["renderVoidTiles"] = {k: sorted(map(list, v)) for k, v in found.items()}
    if not passed:
        report["written"] = False
        return report
    report.update(write_lands(base, kit, grid, map_id, land_id, overrides))
    return report


def rank(result: dict) -> tuple:
    """Seed ranking key, lower is better: failed gates, then fewest problems, then best joins."""
    return (len(score.passes(result)), result["criticalMismatches"], result["rigidViolations"],
            result["holes"], result.get("renderVoid", 0), -result["seamRate"])


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


def land_bytes(base, kit: dict, grid: list[list[int]], map_id: int, land_id: int) -> dict[int, bytes]:
    """{land id: encoded land} for a solved grid, as write_lands composes it (nothing written)."""
    area = base.member("area", base.headers[map_id]["areaDataBank"])
    anim_materials = kits.area_animation_materials(world.RomSource(REPO / "rom.nds"), area["dynamicTextureType"])
    out = {}
    chunk_w, chunk_h = len(grid[0]) // layout.GRID, len(grid) // layout.GRID
    for cz in range(chunk_h):
        for cx in range(chunk_w):
            part = [row[cx * layout.GRID:(cx + 1) * layout.GRID]
                    for row in grid[cz * layout.GRID:(cz + 1) * layout.GRID]]
            this_land = land_id + cz * chunk_w + cx
            model, tiles, corners = kits.compose(kit, part, f"gen_{this_land:04d}", anim_materials=anim_materials)
            land = {"backgroundSound": "", "tiles": tiles, "buildings": [], "bdhc": bdhc_gen.bdhc_from_corners(corners)}
            out[this_land] = codecs.encode_land(land, model)
    return out


def rendered_void(base, overrides: Path, kit: dict, grid, map_id: int, land_id: int) -> list[tuple[int, int]] | None:
    """Grid tiles where the renderer (render.voids) sees black void with these lands in place,
    or None when no map uses land_id yet (nothing to render it in)."""
    import dataclasses
    from .. import render
    edited = world.apply_overrides(base, overrides)
    for header in edited.headers:
        if header.get("alias"):
            continue
        try:
            matrix = edited.matrix_for(header["id"])
        except (KeyError, IndexError, ValueError):
            continue
        spots = [(x, z) for z, row in enumerate(matrix["landData"]) for x, land in enumerate(row) if land == land_id]
        if spots and (matrix["headers"] is None or matrix["headers"][spots[0][1]][spots[0][0]] in (0, header["id"])):
            target_map, (cx0, cz0) = header["id"], spots[0]
            break
    else:
        return None
    scene = render.MapScene(target_map, overrides)
    raw = dict(scene.world.raw)
    raw["land"] = list(raw["land"])
    for land, data in land_bytes(base, kit, np.asarray(grid).tolist(), map_id, land_id).items():
        if land < len(raw["land"]):
            raw["land"][land] = data
    scene.world = dataclasses.replace(scene.world, raw=raw, _cache={})
    # Every tile where the renderer sees through to nothing, from above or from the camera:
    # render.voids keeps only void beside reachable ground (its gate), but a notch in a
    # wall band between corridors is just as visible. The caller skips tiles meant dark.
    h, w = np.asarray(grid).shape
    ox, oz = cx0 * layout.GRID, cz0 * layout.GRID
    chunks = [(cx0 + cx, cz0 + cz) for cz in range(h // layout.GRID) for cx in range(w // layout.GRID)]
    tiles = set()
    ppt = 4
    _, _, where = scene.overview(ppt, top=True, pick=True, chunks=chunks)
    gaps = np.isnan(where[..., 0])
    for z, x in zip(*np.nonzero(gaps)):
        tiles.add((int(x) // ppt, int(z) // ppt))
    _, cam, where = scene.overview(ppt, top=False, pick=True, chunks=chunks)
    ys, xs = np.nonzero(np.isnan(where[..., 0]))
    wv, hv = cam.size
    k = cam.ortho_height / hv
    origin = (cam.pos + ((xs + 0.5 - wv / 2) * k)[:, None] * cam.right
              + ((hv / 2 - ys - 0.5) * k)[:, None] * cam.up)
    t = (cam.floor - origin[:, 1]) / cam.forward[1]
    hit = origin + t[:, None] * cam.forward
    for px, pz in hit[:, [0, 2]]:
        tiles.add((int(px // 16) - ox, int(pz // 16) - oz))
    # The camera sees past the map's own edge: that void is the border's, not a tile's fault.
    return sorted((x, z) for x, z in tiles if 1 <= x < w - 1 and 2 <= z < h - 1)


def paint_lands(semantic_text: str, map_id: int, land_id: int, overrides: Path, seeds: int = 1,
                render_rounds: int = 4) -> dict:
    """Paint a semantic map with map_id's tileset; write the best seed's lands.

    After painting, up to render_rounds times: render the map with the new lands
    (render.voids, the renderer's own void check), charge the cells at void tiles,
    and repair around them. The coverage rasters the painter uses are fast but
    approximate; this closes the gap where they disagree with the renderer."""
    from . import paint, semantic
    base = _base()
    tileset = _tileset_of_map(base, map_id)
    started = time.time()
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    target = semantic.SemanticMap.from_text(semantic_text)
    h, w = target.shape
    if h % layout.GRID or w % layout.GRID:
        raise SystemExit(f"semantic map is {w}x{h}; it must be whole {layout.GRID}x{layout.GRID} chunks")
    tried = []
    for seed in range(seeds):
        painter = paint.Painter(paint.source_for(kit), target, None, seed)
        painter.solve()
        tried.append((paint.rank(painter.report()), seed, painter))
    tried.sort(key=lambda t: (t[0], t[1]))
    _, seed, painter = tried[0]
    rounds = []
    for _ in range(render_rounds):
        void = rendered_void(base, overrides, kit, painter.grid, map_id, land_id)
        rounds.append(None if void is None else len(void))
        if not void:
            break
        void = [(x, z) for x, z in void if painter.want_open[z, x]]  # not tiles meant dark
        rounds[-1] = len(void)
        if not void:
            break
        painter.mark_bad(void)
        painter.repair_pass(only=void)
    grid = painter.grid.copy()
    found = painter.report()
    got = semantic.extract(kit, grid)
    report = {"map": map_id, "tileset": tileset, "land": land_id, "seed": seed, "builder": "paint",
              "paint": found, "seedsTried": seeds, "renderVoidRounds": rounds,
              "labelMatch": round(float(np.mean([[target.label(x, z) == got.label(x, z) for x in range(w)]
                                                 for z in range(h)])), 4),
              "renderVoidTiles": {k: sorted(map(list, v)) for k, v in
                                  coverage.render_void(kit, grid).items() if k != "floor"},
              "grid": grid.tolist(), "layout": [row.replace("?", "T") for row in target.walk],
              "semantic": semantic_text, "realizedLayout": layout.render(grid.tolist(), kit),
              "seconds": round(time.time() - started, 1)}
    report.update(write_lands(base, kit, grid.tolist(), map_id, land_id, overrides))
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


def _precheck(args) -> int:
    """`precheck`: exit 1 on errors (a gate will fail), 0 with warnings only."""
    from . import precheck
    tileset, lands = precheck.load_vanilla(args.map)
    if not lands:
        print(f"error: map {args.map}'s tileset {tileset} has no vanilla chunks to compare with; pass the "
              "vanilla template map generate used (a report's \"map\")", file=sys.stderr)
        return 2
    if args.calibrate:
        print(json.dumps({"map": args.map, "tileset": tileset, "chunks": precheck.calibrate(lands)}, indent=1))
        return 0
    if args.layout is None:
        print("error: --layout is required (or --calibrate)", file=sys.stderr)
        return 2
    events = json.loads(args.events.read_text()) if args.events else None
    vanilla = precheck.Vanilla(lands)
    ox, oz = args.origin
    points = [(x - ox, z - oz, what) for x, z, what in precheck.points_from(events, ())]
    points += [(x, z, "start") for x, z in args.start]
    _, findings = precheck.check_text(args.layout.read_text(), vanilla, args.relax, points)
    if args.json:
        print(json.dumps({"layout": str(args.layout), "map": args.map, "tileset": tileset, "relax": args.relax,
                          "vanillaChunks": len(lands), **precheck.summary(findings), "findings": findings},
                         indent=1))
    else:
        print(precheck.format_text(findings, f"precheck {args.layout} on map {args.map} (tileset {tileset}, "
                                             f"{len(lands)} vanilla chunks), relax {args.relax}"))
    return 1 if any(f["severity"] == "error" for f in findings) else 0


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
    des = sub.add_parser("design", help="brief (gameplay intent) -> semantic map; see style/design.py")
    des.add_argument("--brief", type=Path, required=True)
    des.add_argument("--out", type=Path, required=True)
    des.add_argument("--plan", type=Path)
    pnt = sub.add_parser("paint", help="semantic map -> lands with vanilla cells; see style/paint.py")
    pnt.add_argument("--semantic", type=Path, required=True)
    pnt.add_argument("--map", type=int, required=True, help="map whose area tileset to use")
    pnt.add_argument("--land", type=int, required=True, help="first land id to replace or append")
    pnt.add_argument("--seeds", type=int, default=1)
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
    pre = sub.add_parser("precheck", help="about 1 s: layout patterns vanilla never uses, before generate")
    pre.add_argument("--layout", type=Path, help="layout file (required unless --calibrate)")
    pre.add_argument("--map", type=int, required=True, help="map whose area tileset to use")
    pre.add_argument("--relax", type=int, default=0, help="the --relax generate will use")
    pre.add_argument("--events", type=Path, help="events JSON; its warps (matrix-wide x/z) must be on '.'")
    pre.add_argument("--origin", type=int, nargs=2, default=(0, 0), metavar=("X0", "Z0"),
                     help="map tile of the layout's top-left corner, for --events (default 0 0)")
    pre.add_argument("--start", type=int, nargs=2, action="append", default=[], metavar=("X", "Z"),
                     help="a start tile in layout x/z")
    pre.add_argument("--calibrate", action="store_true", help="check every vanilla chunk (leave-one-out)")
    pre.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "precheck":
        return _precheck(args)
    if args.command == "design":
        from . import design
        argv2 = ["--brief", str(args.brief), "--out", str(args.out)] + (["--plan", str(args.plan)] if args.plan else [])
        return design.main(argv2)
    if args.command == "paint":
        report = paint_lands(args.semantic.read_text(), args.map, args.land, args.overrides, args.seeds)
        default = args.overrides.resolve() == (REPO / "data/maps").resolve()
        report_dir = REPORT_DIR if default else args.overrides.parent / "map-style-reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"report-{args.land:04d}.json").write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps({k: v for k, v in report.items()
                          if k not in ("realizedLayout", "grid", "semantic", "layout")}, indent=1))
        return 0
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
        if report.get("written") and report.get("renderVoidTiles"):
            print(f"warning: written, but {report['score']['renderVoid']} tiles show black void (renderVoidTiles); "
                  "fix them with `resolve --hotspots K` and check with `tools.maps.render sheet`", file=sys.stderr)
        return 0 if report.get("written") else 1
    print(json.dumps(new_map(args.map, args.template, args.land, tuple(args.start), args.overrides,
                             tuple(args.chunks))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
