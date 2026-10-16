"""Local edits of generated maps: re-solve a region in place, inspect one tile.

  python3 -B -m tools.maps.style resolve --land 682 --hotspots 2 --seeds 4 [--write]
  python3 -B -m tools.maps.style resolve --land 676 --region 24 16 8 8 --set 27 19 . [--write]
  python3 -B -m tools.maps.style inspect --map 543 --x 16 --z 44 --radius 2

Coordinates. A generate report (build/map-style/report-NNNN.json) holds one
cell grid for all its chunks: grid x/z run over the whole multi-chunk layout
(chunk (cx, cz) covers x 32cx..32cx+31, z 32cz..32cz+31, lands numbered from
the report's first land in reading order). `--land` takes grid coordinates;
`--map` takes matrix-wide tile coordinates of that map (as in events) and
converts them through the map's matrix.

resolve: every tile outside the regions keeps its cell. Inside, the region is
re-solved with the quilt Solver (fresh window placement, and refinement of
the current cells), windows never leave the region, and joins/overhangs with
the pinned surroundings count. Each seed's candidates are ranked like
generate (failed gates, route changes, overhangs, holes, seam rate), then by
the problems near the region. A region changes only when that rank strictly
improves and no gate fails that passed before; otherwise it keeps its cells.
`--write` composes and writes the lands like generate and updates the report.

inspect_tile(map_id, x, z, radius) returns the JSON dict the inspect command
prints; kits, seam tables and reports are cached in-process.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np

from . import layout, quilt, score
from . import seams as seams_mod
from .layout import CLASSES, GRID, cell_char

SIDES = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
SUMMARY_KEYS = ("seamRate", "badSeams", "criticalMismatches", "rigidViolations", "holes", "voidExposed",
                "bareEdges", "walkableComponents", "layoutMatch")
SHOWCASE_NOTE = ("lands rewritten: run `python3 -B -m tools.maps.showcase write` (showcase maps 541-543) "
                 "and `python3 -B -m tools.maps lint`, as after generate")


class EditError(ValueError):
    pass


# --- regions and local problems (pure: kit + grid + rows) ---------------------

def clip_region(region, width: int, height: int) -> tuple[int, int, int, int]:
    x0, z0, w, h = (int(v) for v in region)
    x1, z1 = min(width, x0 + w), min(height, z0 + h)
    x0, z0 = max(0, x0), max(0, z0)
    if x1 <= x0 or z1 <= z0:
        raise EditError(f"region {list(region)} lies outside the {width}x{height} grid")
    return x0, z0, x1 - x0, z1 - z0


def _box(region, pad: int, width: int, height: int) -> tuple[int, int, int, int]:
    """(x0, z0, x1, z1) of the region grown by pad, clipped to the grid."""
    x0, z0, w, h = region
    return max(0, x0 - pad), max(0, z0 - pad), min(width, x0 + w + pad), min(height, z0 + h + pad)


def local_problems(solver: quilt.Solver, grid: np.ndarray, codes: np.ndarray, region) -> dict:
    """Problems a region change can affect: those within reach+1 of the region.

    Measured on a crop twice that wide, so problems at the counted tiles see
    all their real neighbours. Problems among pinned tiles inside the band are
    included too; they are equal before and after, so differences are exact.
    """
    s = solver.seams
    height, width = grid.shape
    pad = s.reach + 1
    ox0, oz0, ox1, oz1 = _box(region, 2 * pad, width, height)
    ix0, iz0, ix1, iz1 = _box(region, pad, width, height)
    sub, sc = grid[oz0:oz1, ox0:ox1], codes[oz0:oz1, ox0:ox1]
    inner = np.zeros(sub.shape, dtype=bool)
    inner[iz0 - oz0:iz1 - oz0, ix0 - ox0:ix1 - ox0] = True

    def count(tiles):
        return sum(bool(inner[z, x]) for x, z in tiles)

    crit = solver.critical_table[sc, solver.char[sub]] & inner
    h = ~s.h_ok(s.prof["east"][sub[:, :-1]], s.prof["west"][sub[:, 1:]]) & (inner[:, :-1] | inner[:, 1:])
    v = ~s.v_ok(s.prof["south"][sub[:-1, :]], s.prof["north"][sub[1:, :]]) & (inner[:-1, :] | inner[1:, :])
    rigid = sum(bool(inner[z, x] or inner[z + dz, x + dx]) for x, z, dx, dz in s.rigid_violations(sub))
    return {"critical": int(crit.sum()), "voidExposed": count(solver.void_exposed(sub)),
            "bareEdges": count(s.bare_edges(sub)), "rigidViolations": rigid,
            "holes": count(s.holes(sub)), "badSeams": int(h.sum() + v.sum())}


def local_key(problems: dict) -> tuple:
    """quilt.Solver.evaluate's order: route changes and void, overhangs, holes, joins."""
    p = problems
    return (p["critical"] + p["voidExposed"] + p["bareEdges"], p["rigidViolations"], p["holes"], p["badSeams"])


def _targets(solver, grid, codes, region, hard: bool) -> list[tuple[int, int]]:
    """Problem tiles at or next to the region, moved into it (the tile a window can change)."""
    height, width = grid.shape
    x0, z0, w, h = region
    ox0, oz0, ox1, oz1 = _box(region, 2 * (solver.seams.reach + 1), width, height)
    sub, sc = grid[oz0:oz1, ox0:ox1], codes[oz0:oz1, ox0:ox1]
    found = solver.hard_tiles(sub, sc) if hard else solver.bad_tiles(sub, sc)
    out = set()
    for x, z in found:
        x, z = x + ox0, z + oz0
        if x0 - 1 <= x <= x0 + w and z0 - 1 <= z <= z0 + h:
            out.add((min(max(x, x0), x0 + w - 1), min(max(z, z0), z0 + h - 1)))
    return sorted(out)


def _window(rng, x, z, size_w, size_h, region) -> tuple[int, int]:
    x0, z0, w, h = region
    return (min(max(x0, x - rng.randrange(size_w)), x0 + w - size_w),
            min(max(z0, z - rng.randrange(size_h)), z0 + h - size_h))


def _place(solver, grid, codes, region, patch, rng) -> None:
    """Fresh windows over the region in reading order, against the pinned surroundings."""
    x0, z0, w, h = region
    grid[z0:z0 + h, x0:x0 + w] = -1
    for wz in range(z0, z0 + h, patch):
        for wx in range(x0, x0 + w, patch):
            solver.solve_region(grid, codes, wx, wz, min(patch, z0 + h - wz), min(patch, x0 + w - wx), patch, rng)


def _improve(solver, grid, codes, region, rng) -> None:
    """quilt refine + polish, restricted to windows inside the region (never worse locally)."""
    cfg = solver.cfg
    x0, z0, w, h = region

    def key():
        return local_key(local_problems(solver, grid, codes, region))

    best = (key(), grid[z0:z0 + h, x0:x0 + w].copy())
    for _ in range(cfg["refineRounds"]):
        bad = _targets(solver, grid, codes, region, hard=False)
        if not bad:
            break
        rng.shuffle(bad)
        changed = False
        for x, z in bad[:cfg["refinePerRound"]]:
            for patch in cfg["refineSizes"]:
                pw, ph = min(patch, w), min(patch, h)
                wx, wz = _window(rng, x, z, pw, ph, region)
                if solver.solve_region(grid, codes, wx, wz, ph, pw, patch, rng, current=True):
                    changed = True
                    break
        now = key()
        if now < best[0]:
            best = (now, grid[z0:z0 + h, x0:x0 + w].copy())
        if not changed:
            break
    grid[z0:z0 + h, x0:x0 + w] = best[1]
    current = best[0]
    for _ in range(cfg.get("polishRounds", 0)):
        hard = _targets(solver, grid, codes, region, hard=True)
        if not hard:
            break
        rng.shuffle(hard)
        for x, z in hard[:60]:
            for patch in cfg.get("polishSizes", [4, 2, 1]):
                pw, ph = min(patch, w), min(patch, h)
                for _try in range(2):
                    wx, wz = _window(rng, x, z, pw, ph, region)
                    saved = grid[wz:wz + ph, wx:wx + pw].copy()
                    if not solver.solve_region(grid, codes, wx, wz, ph, pw, patch, rng, current=True,
                                               candidates=cfg.get("polishCandidates", 1000)):
                        continue
                    now = key()
                    if now < current:
                        current = now
                    else:
                        grid[wz:wz + ph, wx:wx + pw] = saved


def apply_sets(rows: list[str], sets, regions) -> list[str]:
    """Intent chars changed at (x, z); each must lie inside a region."""
    out = [list(row) for row in rows]
    for x, z, ch in sets:
        x, z = int(x), int(z)
        if ch not in CLASSES:
            raise EditError(f"--set {x} {z} {ch!r}: allowed characters are {''.join(CLASSES)}")
        if not any(r[0] <= x < r[0] + r[2] and r[1] <= z < r[1] + r[3] for r in regions):
            raise EditError(f"--set {x} {z}: outside every region (only re-solved tiles can change)")
        out[z][x] = ch
    return ["".join(row) for row in out]


def _summary(result: dict) -> dict:
    out = {k: result[k] for k in SUMMARY_KEYS if k in result}
    out["failedGates"] = score.passes(result)
    return out


def resolve_grid(kit: dict, grid: list[list[int]], rows: list[str], regions, seeds: int = 4,
                 sets=(), old_rows: list[str] | None = None, config: dict | None = None) -> dict:
    """Re-solve `regions` (x0, z0, w, h in grid coordinates) of a solved grid; pure, nothing written.

    rows: the intent layout (already relaxed); `sets` edit it first. Returns
    {"grid", "rows", "before", "after", "regions", "improved"}. A region keeps
    its cells unless a candidate ranks strictly better (cli.rank, then local
    problems) without failing a gate that passed before (judged with the old
    and the edited intent).
    """
    from .cli import rank
    solver = quilt.solver_for(kit, config)
    g0 = np.array(grid, dtype=np.int64)
    height, width = g0.shape
    if len(rows) != height or any(len(r) != width for r in rows):
        raise EditError(f"layout is {len(rows)}x{len(rows[0]) if rows else 0} rows/cols, grid is {height}x{width}")
    regions = [clip_region(r, width, height) for r in regions]
    old_rows = list(old_rows or rows)
    rows = apply_sets(rows, sets, regions)
    codes = solver.codes(rows)
    extras = {"windows": score.vanilla_windows(kit), "pairs": score.vanilla_pairs(kit)}
    before = score.score(kit, g0.tolist(), rows, **extras)
    allowed_fail = set(score.passes(before)) & set(score.passes(score.score(kit, g0.tolist(), old_rows, **extras)))
    g = g0.copy()
    current = before
    report = []
    for region in regions:
        started = time.time()
        x0, z0, w, h = region
        problems_before = local_problems(solver, g, codes, region)
        own_key = (rank(current), local_key(problems_before))
        best = None
        for seed in range(seeds):
            starts = [("current", None)] + [(f"place{p}", p) for p in solver.cfg["placeSizes"]]
            for label, patch in starts:
                rng = random.Random(seed * 1009 + (patch or 0))
                trial = g.copy()
                if patch:
                    _place(solver, trial, codes, region, patch, rng)
                _improve(solver, trial, codes, region, rng)
                if np.array_equal(trial[z0:z0 + h, x0:x0 + w], g[z0:z0 + h, x0:x0 + w]):
                    continue
                result = score.score(kit, trial.tolist(), rows, **extras)
                key = (rank(result), local_key(local_problems(solver, trial, codes, region)))
                if best is None or key < best[0]:
                    best = (key, seed, label, trial, result)
        entry = {"region": list(region), "before": problems_before, "changedTiles": 0, "accepted": False,
                 "realizedBefore": layout.render(g[z0:z0 + h, x0:x0 + w].tolist(), kit)}
        if best is None:
            entry["reason"] = "no seed found a different region"
        elif not best[0] < own_key:
            entry["reason"] = "no candidate ranks better than the current cells"
            entry["bestCandidate"] = {"seed": best[1], "start": best[2],
                                      "problems": local_problems(solver, best[3], codes, region)}
        elif set(score.passes(best[4])) - allowed_fail:
            entry["reason"] = f"best candidate fails gates {sorted(set(score.passes(best[4])) - allowed_fail)}"
        else:
            _, seed, label, trial, result = best
            entry.update(accepted=True, seed=seed, start=label,
                         changedTiles=int((trial[z0:z0 + h, x0:x0 + w] != g[z0:z0 + h, x0:x0 + w]).sum()))
            g, current = trial, result
        entry["after"] = local_problems(solver, g, codes, region)
        entry["realizedAfter"] = layout.render(g[z0:z0 + h, x0:x0 + w].tolist(), kit)
        entry["seconds"] = round(time.time() - started, 1)
        report.append(entry)
    return {"grid": g.tolist(), "rows": rows, "before": before, "after": current, "regions": report,
            "improved": any(e["accepted"] for e in report)}


# --- reports, worlds, coordinates (ROM-backed, cached) -----------------------------

_REPORTS: dict = {}
_WORLD: dict = {}
_LANDS: dict = {}
_KITS: dict = {}
_ANALYSIS: dict = {}


def _repo():
    from ..cli import REPO
    return REPO


def report_lands(report: dict) -> list[int]:
    if report.get("lands"):
        return list(report["lands"])
    grid = report["grid"]
    count = (len(grid) // GRID) * (len(grid[0]) // GRID)
    return [report["land"] + i for i in range(count)]


def load_reports() -> list[tuple[Path, dict]]:
    from .cli import REPORT_DIR
    out = []
    for path in sorted(REPORT_DIR.glob("report-*.json")):
        stamp = path.stat().st_mtime_ns
        if _REPORTS.get(path, (None,))[0] != stamp:
            _REPORTS[path] = (stamp, json.loads(path.read_text()))
        out.append((path, _REPORTS[path][1]))
    return out


def find_report(land: int) -> tuple[Path, dict] | None:
    """The report whose grid holds this land (a written one first, then the newest)."""
    found = [(path, r) for path, r in load_reports() if "grid" in r and land in report_lands(r)]
    found.sort(key=lambda pr: (not pr[1].get("written"), -pr[0].stat().st_mtime))
    return found[0] if found else None


def grid_position(report: dict, land: int, lx: int, lz: int) -> tuple[int, int]:
    index = report_lands(report).index(land)
    width = len(report["grid"][0]) // GRID
    return (index % width) * GRID + lx, (index // width) * GRID + lz


def grid_land(report: dict, gx: int, gz: int) -> tuple[int, int, int]:
    """(land, local x, local z) of a report grid tile."""
    width = len(report["grid"][0]) // GRID
    return report_lands(report)[(gz // GRID) * width + gx // GRID], gx % GRID, gz % GRID


def kit_for(tileset: int) -> dict:
    if tileset not in _KITS:
        from .. import world
        from . import kit as kits
        _KITS[tileset] = kits.load_or_build_kit(world.RomSource(_repo() / "rom.nds"), tileset)
    return _KITS[tileset]


def _fingerprint(overrides: Path) -> tuple:
    return tuple(sorted((str(p), p.stat().st_mtime_ns) for kind in ("events", "headers", "matrix", "land", "area")
                        for p in (overrides / kind).rglob("*") if p.is_file())) if overrides.exists() else ()


def edited_world(overrides: Path | None = None):
    """The ROM with the override tree applied; rebuilt when an override file changes."""
    from .. import world
    from .cli import _base
    overrides = overrides or _repo() / "data/maps"
    if "base" not in _WORLD:
        _WORLD["base"] = _base()
    stamp = (str(overrides), _fingerprint(overrides))
    if _WORLD.get("stamp") != stamp:
        _WORLD.update(stamp=stamp, edited=world.apply_overrides(_WORLD["base"], overrides), where=None)
        _LANDS.clear()
    return _WORLD["edited"]


def land_places(land: int) -> list[tuple[int, int, int]]:
    """(map, chunk x, chunk z) of every map whose matrix shows this land."""
    edited = edited_world()
    if _WORLD.get("where") is None:
        where: dict = {}
        for map_id, header in enumerate(edited.headers):
            if header.get("alias"):
                continue
            try:
                matrix = edited.matrix_for(map_id)
            except (IndexError, KeyError):
                continue
            for cz, row in enumerate(matrix["landData"]):
                for cx, value in enumerate(row):
                    if matrix["headers"] is None or matrix["headers"][cz][cx] == map_id:
                        where.setdefault(value, []).append((map_id, cx, cz))
        _WORLD["where"] = where
    return _WORLD["where"].get(land, [])


def map_tile_land(map_id: int, x: int, z: int) -> tuple[int, int, int]:
    """(land, local x, local z) at matrix-wide tile x/z of a map."""
    matrix = edited_world().matrix_for(map_id)
    cx, cz = x // GRID, z // GRID
    if not (0 <= cx < matrix["width"] and 0 <= cz < matrix["height"]) or x < 0 or z < 0:
        raise EditError(f"tile ({x}, {z}) is outside map {map_id}'s {matrix['width']}x{matrix['height']} matrix")
    land = matrix["landData"][cz][cx]
    if land == 0xFFFF:
        raise EditError(f"tile ({x}, {z}) of map {map_id} has no land chunk")
    return land, x % GRID, z % GRID


def map_to_grid(map_id: int, x: int, z: int) -> tuple[Path, dict, int, int]:
    land, lx, lz = map_tile_land(map_id, x, z)
    found = find_report(land)
    if found is None:
        raise EditError(f"land {land} (map {map_id} tile {x},{z}) has no generate report in build/map-style")
    path, report = found
    return (path, report, *grid_position(report, land, lx, lz))


# --- resolve command -----------------------------------------------------------------

def resolve(land: int | None = None, map_id: int | None = None, regions=(), hotspots: int = 0, sets=(),
            layout_text: str | None = None, relax_depth: int = 0, seeds: int = 4, write: bool = False,
            overrides: Path | None = None) -> dict:
    """The resolve command: load the report, re-solve, optionally write lands and the report."""
    overrides = overrides or _repo() / "data/maps"
    regions, sets = [list(r) for r in regions], [list(s) for s in sets]
    if map_id is not None:  # matrix-wide map coordinates -> report grid coordinates
        path = report = None
        for r in regions:
            p, rep, gx, gz = map_to_grid(map_id, r[0], r[1])
            # every chunk the region touches must be the same report, at the same offset
            xs = sorted({*range(r[0], r[0] + r[2], GRID), r[0] + r[2] - 1})
            zs = sorted({*range(r[1], r[1] + r[3], GRID), r[1] + r[3] - 1})
            for x in xs:
                for z in zs:
                    q, _, qx, qz = map_to_grid(map_id, x, z)
                    if q != p or (qx - x, qz - z) != (gx - r[0], gz - r[1]):
                        raise EditError(f"region {r} on map {map_id} does not map to one rectangle of one report")
            if path and p != path:
                raise EditError(f"regions on map {map_id} come from different reports")
            path, report, r[0], r[1] = p, rep, gx, gz
        for s in sets:
            q, _, s[0], s[1] = map_to_grid(map_id, int(s[0]), int(s[1]))
            if path is not None and q != path:
                raise EditError(f"--set ({s}) is on another report's land than the regions")
        if path is None:
            land_here, _, _ = map_tile_land(map_id, 0, 0)
            found = find_report(land_here)
            if found is None:
                raise EditError(f"map {map_id} has no generate report")
            path, report = found
    else:
        found = find_report(land)
        if found is None:
            raise EditError(f"no generate report with a grid holds land {land} (build/map-style/report-*.json)")
        path, report = found
    for k in report.get("hotspots", [])[:hotspots]:
        regions.append([k["x"][0], k["z"][0], k["x"][1] - k["x"][0] + 1, k["z"][1] - k["z"][0] + 1])
    if not regions:
        raise EditError("give --region X0 Z0 W H and/or --hotspots K")
    if layout_text is not None:
        rows = layout.parse(layout_text)
        if relax_depth:
            rows = layout.relax(rows, relax_depth)
    elif "layout" in report:
        rows = report["layout"]
    else:
        raise EditError(f"{path.name} predates stored layouts: pass --layout FILE (and the --relax generate used)")
    kit = kit_for(report["tileset"])
    out = resolve_grid(kit, report["grid"], rows, regions, seeds, sets)
    summary = {"report": str(path), "lands": report_lands(report), "seeds": seeds,
               "before": _summary(out["before"]), "after": _summary(out["after"]),
               "improved": out["improved"], "regions": out["regions"], "written": False}
    if not report.get("written"):
        summary["warning"] = ("this report's grid was never written (its generate failed a gate); "
                              "the game's lands differ from it, so --write is refused")
    if write and out["improved"] and report.get("written"):
        from .cli import model_sha, write_lands
        # The lands on disk must still be the ones this report's grid made: a later generate or a
        # hand edit of one of them would otherwise be silently reverted.
        expected = report.get("modelHashes") or write_lands(
            _base_world(), kit, report["grid"], report["map"], report["land"], overrides, write=False)["modelHashes"]
        changed = [n for n in report_lands(report)
                   if not (overrides / "land" / f"{n:04d}" / "model.nsbmd").exists()
                   or model_sha((overrides / "land" / f"{n:04d}" / "model.nsbmd").read_bytes()) != expected.get(str(n))]
        if changed:
            raise EditError(f"lands {changed} on disk differ from {path.name}'s grid (regenerated or edited "
                            "since): --write refused; regenerate, or resolve the report that made them")
        report = dict(report)
        report.update(write_lands(_base_world(), kit, out["grid"], report["map"], report["land"], overrides))
        report.update(grid=out["grid"], layout=out["rows"], score=out["after"],
                      failedGates=score.passes(out["after"]), realizedLayout=layout.render(out["grid"], kit),
                      hotspots=score.hotspots(kit, out["grid"]))
        report.setdefault("resolves", []).append({
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seeds": seeds, "sets": sets,
            "regions": [{k: e[k] for k in ("region", "accepted", "changedTiles")} for e in out["regions"]],
            "seamRateBefore": out["before"]["seamRate"], "seamRateAfter": out["after"]["seamRate"]})
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(report, indent=1) + "\n")
        tmp.replace(path)
        summary["written"] = report["written"]
        summary["note"] = SHOWCASE_NOTE
    elif out["improved"]:
        summary["note"] = "dry run: add --write to compose the lands and update the report; then " + SHOWCASE_NOTE
    return summary


def _base_world():
    from .cli import _base
    _WORLD.setdefault("base", _base())
    return _WORLD["base"]


# --- inspect -------------------------------------------------------------------------

def _placements(kit: dict) -> dict:
    key = ("placements", id(kit))
    if key not in _ANALYSIS:
        where: dict = {}
        for land, grid in sorted(kit["chunks"].items()):
            for z, row in enumerate(grid):
                for x, c in enumerate(row):
                    where.setdefault(c, []).append((land, x, z))
        _ANALYSIS[key] = where
    return _ANALYSIS[key]


def _pairs(kit: dict) -> tuple:
    key = ("pairs", id(kit))
    if key not in _ANALYSIS:
        _ANALYSIS[key] = score.vanilla_pairs(kit)
    return _ANALYSIS[key]


def analyze(kit: dict, grid, rows: list[str] | None) -> dict:
    """Every problem of a grid, by tile (what score/hotspots count)."""
    s = seams_mod.for_kit(kit)
    solver = quilt.solver_for(kit)
    g = np.array(grid, dtype=np.int64)
    h_bad = ~s.h_ok(s.prof["east"][g[:, :-1]], s.prof["west"][g[:, 1:]])
    v_bad = ~s.v_ok(s.prof["south"][g[:-1, :]], s.prof["north"][g[1:, :]])
    critical = set()
    if rows is not None:
        critical = {(x, z) for x, z, _, _ in quilt.critical_mismatches(kit, g.tolist(), rows)}
    return {"grid": g, "h_bad": h_bad, "v_bad": v_bad, "rigid": s.rigid_violations(g),
            "holes": set(s.holes(g)), "void": set(solver.void_exposed(g)), "bare": set(s.bare_edges(g)),
            "critical": critical}


def _seam_bad(a: dict, x: int, z: int, dx: int, dz: int) -> bool | None:
    height, width = a["grid"].shape
    nx, nz = x + dx, z + dz
    if not (0 <= nx < width and 0 <= nz < height):
        return None
    if dz == 0:
        return bool(a["h_bad"][z, min(x, nx)])
    return bool(a["v_bad"][min(z, nz), x])


def _marker(a: dict, x: int, z: int) -> str:
    if (x, z) in a["critical"]:
        return "C"
    if any((x, z) in ((rx, rz), (rx + dx, rz + dz)) for rx, rz, dx, dz in a["rigid"]):
        return "R"
    if (x, z) in a["holes"]:
        return "H"
    if (x, z) in a["void"]:
        return "V"
    if (x, z) in a["bare"]:
        return "B"
    if any(_seam_bad(a, x, z, dx, dz) for dx, dz in SIDES.values()):
        return "S"
    return "."


MARKER_LEGEND = ("C route-changing mismatch, R overhang cut off, H hole, V void beside land, "
                 "B floor beside black void, S bad join on a side, . clean, blank outside the grid")


def describe_cell(kit: dict, grid, rows: list[str] | None, gx: int, gz: int, radius: int = 0,
                  hotspots=(), analysis: dict | None = None) -> dict:
    """Everything the judge knows about one grid tile (pure: kit + grid + rows)."""
    a = analysis or analyze(kit, grid, rows)
    g = a["grid"]
    height, width = g.shape
    if not (0 <= gx < width and 0 <= gz < height):
        raise EditError(f"grid tile ({gx}, {gz}) is outside the {width}x{height} grid")
    s = seams_mod.for_kit(kit)
    index = int(g[gz, gx])
    cell = kit["cells"][index]
    h_pairs, v_pairs = _pairs(kit)
    sides = {}
    for name, (dx, dz) in SIDES.items():
        bad = _seam_bad(a, gx, gz, dx, dz)
        if bad is None:
            sides[name] = None
            continue
        other = int(g[gz + dz, gx + dx])
        pair = ((index, other) if name == "east" else (other, index) if name == "west"
                else (index, other) if name == "south" else (other, index))
        seen = pair in (h_pairs if dz == 0 else v_pairs)
        sides[name] = {"neighbour": other, "neighbourChar": cell_char(kit["cells"][other]),
                       "profilesJoin": not bad, "vanillaPair": seen}
    rigid = [{"from": [x, z], "to": [x + dx, z + dz], "cellAtTarget": int(g[z + dz, x + dx]),
              "role": "overhangs" if (x, z) == (gx, gz) else "overhungBy"}
             for x, z, dx, dz in a["rigid"] if (gx, gz) in ((x, z), (x + dx, z + dz))]
    sources = _placements(kit).get(index, [])
    out = {
        "grid": {"x": gx, "z": gz},
        "wanted": rows[gz][gx] if rows is not None else None,
        "realized": cell_char(cell),
        "cell": {"index": index, "sig": cell.get("sig"), "cls": cell.get("cls"),
                 "behavior": cell.get("behavior"), "collision": cell.get("collision"),
                 "secondary": cell.get("secondary"), "corners": cell.get("corners"),
                 "vanillaCount": cell.get("count", len(sources)),
                 "vanillaSources": [{"land": land, "x": x, "z": z} for land, x, z in sources[:5]]},
        "criticalMismatch": (gx, gz) in a["critical"] if rows is not None else None,
        "seams": sides,
        "badSides": sorted(k for k, v in sides.items() if v and not v["profilesJoin"]),
        "rigidViolations": rigid,
        "hole": (gx, gz) in a["holes"],
        "voidExposed": (gx, gz) in a["void"],
        "bareEdge": (gx, gz) in a["bare"],
        "hotspot": next((dict(h, rank=i + 1) for i, h in enumerate(hotspots)
                         if h["x"][0] <= gx <= h["x"][1] and h["z"][0] <= gz <= h["z"][1]), None),
    }
    if radius:
        wanted, realized, marks = [], [], []
        for z in range(gz - radius, gz + radius + 1):
            w_row, r_row, m_row = [], [], []
            for x in range(gx - radius, gx + radius + 1):
                inside = 0 <= x < width and 0 <= z < height
                w_row.append(rows[z][x] if inside and rows is not None else " ")
                r_row.append(cell_char(kit["cells"][int(g[z, x])]) if inside else " ")
                m_row.append(_marker(a, x, z) if inside else " ")
            wanted.append("".join(w_row))
            realized.append("".join(r_row))
            marks.append("".join(m_row))
        out["neighbourhood"] = {"origin": {"x": gx - radius, "z": gz - radius}, "center": [radius, radius],
                                "wanted": wanted if rows is not None else None, "realized": realized,
                                "problems": marks,
                                "legend": MARKER_LEGEND}
    return out


def _land_tiles(land: int) -> dict:
    """Game tile attributes and BDHC corner heights of a land, from the override tree."""
    if land not in _LANDS:
        from .kit import tile_corners
        spec = edited_world().member("land", land)
        _LANDS[land] = {"tiles": spec["tiles"], "corners": tile_corners(spec["bdhc"])}
    return _LANDS[land]


def _events_at(map_id: int, x: int, z: int) -> dict:
    edited = edited_world()
    events = edited.member("events", edited.headers[map_id]["eventsBank"])
    out = {}
    for kind in ("objects", "warps", "bgs"):
        out[kind] = [dict(e, index=i) for i, e in enumerate(events.get(kind, [])) if (e["x"], e["z"]) == (x, z)]
    out["coords"] = [dict(e, index=i) for i, e in enumerate(events.get("coords", []))
                     if e["x"] <= x < e["x"] + max(1, e.get("w", 1)) and e["z"] <= z < e["z"] + max(1, e.get("h", 1))]
    return out


def _game_tile(land: int, lx: int, lz: int) -> dict:
    t = _land_tiles(land)
    tiles = t["tiles"]
    behavior = int(tiles["behavior"][lz].split()[lx], 16)
    blocked = tiles["collision"][lz][lx] == "#"
    from .kit import classify
    return {"behavior": behavior, "collision": blocked, "secondary": int(tiles["secondary"][lz].split()[lx], 16),
            "class": classify(behavior, blocked), "corners": t["corners"][lz][lx]}


def _report_analysis(path: Path, report: dict, rows) -> tuple[dict, dict]:
    kit = kit_for(report["tileset"])
    key = ("report", str(path), _REPORTS[path][0], json.dumps(rows) if rows is not None else None)
    if key not in _ANALYSIS:
        for old in [k for k in _ANALYSIS if k[1] == str(path) and k[2] != key[2]]:  # outdated report
            del _ANALYSIS[old]
        _ANALYSIS[key] = analyze(kit, report["grid"], rows)
    return kit, _ANALYSIS[key]


def inspect_tile(map_id: int | None, x: int, z: int, radius: int = 0, land: int | None = None,
                 layout_text: str | None = None, relax_depth: int = 0) -> dict:
    """One tile of a map (matrix-wide x/z) or of a land (report grid x/z; land-local without a report).

    Generated tiles get the judge's view from the report (cell, joins,
    overhangs, holes, void, hotspot); every tile gets the game's tile
    attributes, BDHC corner heights and the events on it.
    """
    out: dict = {}
    if map_id is not None:
        land_id, lx, lz = map_tile_land(map_id, x, z)
        found = find_report(land_id)
        mx, mz = x, z
    else:
        found = find_report(land)
        land_id = land
        if found is not None:
            gx, gz = x, z
            report = found[1]
            if not (0 <= gz < len(report["grid"]) and 0 <= gx < len(report["grid"][0])):
                raise EditError(f"grid tile ({x}, {z}) is outside {found[0].name}'s grid")
            land_id, lx, lz = grid_land(report, gx, gz)
        else:
            lx, lz = x, z
        places = land_places(land_id)
        map_id = places[0][0] if places else None
        mx = mz = None
        if places:
            mx, mz = places[0][1] * GRID + lx, places[0][2] * GRID + lz
    out.update(map=map_id, mapTile={"x": mx, "z": mz} if mx is not None else None, land=land_id,
               landTile={"x": lx, "z": lz})
    if not (0 <= lx < GRID and 0 <= lz < GRID):
        raise EditError(f"land-local tile ({lx}, {lz}) is outside 0..31")
    out["game"] = _game_tile(land_id, lx, lz)
    if map_id is not None and mx is not None:
        out["events"] = _events_at(map_id, mx, mz)
    if found is None:
        out["report"] = None
        out["note"] = f"no generate report holds land {land_id}: vanilla or hand-made chunk, game data only"
        if radius:  # game tile classes, in map space when the map is known (crosses chunks)
            in_map = map_id is not None and mx is not None
            cx, cz = (mx, mz) if in_map else (lx, lz)
            rows = []
            for tz in range(cz - radius, cz + radius + 1):
                row = ""
                for tx in range(cx - radius, cx + radius + 1):
                    try:
                        where = map_tile_land(map_id, tx, tz) if in_map else (land_id, tx, tz)
                    except EditError:
                        where = None
                    ok = where is not None and 0 <= where[1] < GRID and 0 <= where[2] < GRID
                    row += _game_tile(*where)["class"] if ok else " "
                rows.append(row)
            out["neighbourhood"] = {"origin": {"x": cx - radius, "z": cz - radius},
                                    "space": "map" if in_map else "land", "realized": rows}
        return out
    path, report = found
    gx, gz = grid_position(report, land_id, lx, lz)
    rows = report.get("layout")
    if layout_text is not None:
        rows = layout.parse(layout_text)
        rows = layout.relax(rows, relax_depth) if relax_depth else rows
    kit, a = _report_analysis(path, report, rows)
    cell = describe_cell(kit, report["grid"], rows, gx, gz, radius, report.get("hotspots", []), a)
    game = out["game"]
    cell["matchesGame"] = (cell["cell"]["behavior"] == game["behavior"]
                           and cell["cell"]["collision"] == game["collision"])
    out["report"] = {"path": str(path), "tileset": report["tileset"], "written": bool(report.get("written")),
                     "layoutKnown": rows is not None}
    if rows is None:
        out["report"]["note"] = "report predates stored layouts: wanted chars unknown (pass --layout/--relax)"
    if not report.get("written"):
        out["report"]["note"] = "this report's grid was never written; the game's land differs from it"
    out.update(cell)
    return out
