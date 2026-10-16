"""Cell kit: vanilla map chunks sliced into recombinable 16x16 tiles.

  python3 -B -m tools.maps.style.kit build --tileset 2       # or --map 33
  python3 -B -m tools.maps.style.kit fidelity --map 33 [--sample 12] [--lands 1,2]

`build_kit(source, map_tileset)` and `compose(kit, grid, name)` implement the
interface in documentation/map-system/style-system.md. Kits are ROM-derived:
`load_or_build_kit` caches them under build/map-style/ (git-ignored), keyed by
the ROM's SHA-256. Never commit them.

Decisions the spec leaves open:

* Land ownership. A matrix cell belongs to the map in its header grid; a cell
  whose header-grid entry is 0, or a matrix without a header grid, belongs to
  every map header that uses the matrix. A land claimed by maps of more than one
  mapTileset is skipped and counted in kit["skipped"].
* Corner heights come from the chunk's own BDHC through a minimal port of the
  game's height query (Bdhc_GetHeight, fixed point): the one plate under the
  tile centre (HIGHEST where plates overlap, as the player's jump landing), its
  plane evaluated at the four corners. One plane per tile keeps every tile
  planar. A tile without a plate under its centre gets corners None.
* Texture coordinates are reduced per polygon by whole texture periods (size,
  doubled when flipped; repeating axes only). That is invisible on the DS and
  lets equal-looking cells deduplicate. Fidelity is compared modulo the period.
* Normals are stored as components n/512 of the raw 10-bit values, colours as
  0..31 integers; compose re-packs them without renormalising (lossless).
* compose re-merges flat axis-aligned ground rectangles that share material,
  height, normal, colour and texture mapping, then emits quad strips and the
  short vertex forms (VTX_XZ/XY/YZ/DIFF/10) so models stay within 0xF000 bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from .. import codecs, narc, nsbmd

KIT_VERSION = 5
GRID, TILE, HALF = 32, 16, 256
FX = 4096
REPO = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO / "build" / "map-style"

# Behaviors (pokeheartgold include/constants/metatile_behavior.h, src/metatile_behavior.c)
GRASS_BEHAVIORS = {0x02, 0x03}
SURFABLE_BEHAVIORS = {0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x19, 0x2A, 0x50, 0x51, 0x52, 0x53,
                      0x73, 0x78, 0x7C}
LEDGE_BEHAVIORS = {0x3B: "v", 0x3A: "^", 0x39: "<", 0x38: ">"}

MAX_UV = 2047.0  # texels: TEXCOORD is 12.4 signed


class ComposeError(ValueError):
    pass


def classify(behavior: int, collision: bool) -> str:
    """Layout class char of one tile (style-system.md table); '?' if none fits."""
    if behavior in LEDGE_BEHAVIORS:
        return LEDGE_BEHAVIORS[behavior]
    if behavior in SURFABLE_BEHAVIORS:
        return "?" if collision else "~"
    if collision:
        return "T"
    if behavior in GRASS_BEHAVIORS:
        return ","
    return "."


# --- Land ownership ---------------------------------------------------------

def tileset_lands(w) -> tuple[dict, dict]:
    """({tileset: {"lands": set, "areas": set}}, {conflicting land: set(tilesets)})."""
    by_matrix = defaultdict(list)
    for h in w.headers:
        if not h.get("alias"):
            by_matrix[h["matrixId"]].append(h["id"])
    claims, areas = defaultdict(set), defaultdict(set)

    def owner(hid):
        area = w.headers[hid]["areaDataBank"]
        return w.member("area", area)["mapTileset"], area

    nland = len(w.raw["land"])
    for mid, hids in sorted(by_matrix.items()):
        if mid >= len(w.raw["matrix"]):
            continue
        m = w.member("matrix", mid)
        for z, row in enumerate(m["landData"]):
            for x, land in enumerate(row):
                if land == 0xFFFF or land >= nland:
                    continue
                hg = m["headers"][z][x] if m["headers"] else 0
                for hid in ([hg] if hg and hg < len(w.headers) else hids):
                    ts, area = owner(hid)
                    claims[land].add(ts)
                    areas[ts].add(area)
    out = defaultdict(lambda: {"lands": set(), "areas": set()})
    conflicts = {}
    for land, tss in claims.items():
        if len(tss) == 1:
            out[next(iter(tss))]["lands"].add(land)
        else:
            conflicts[land] = tss
    for ts, a in areas.items():
        out[ts]["areas"] |= a
    return dict(out), conflicts


# --- Heights (minimal Bdhc_GetHeight port) ----------------------------------

def _fx_mul(a: int, b: int) -> int:
    return (a * b + 0x800) >> 12


def _fx_div(n: int, d: int) -> int:
    num = n << 32
    q = abs(num) // abs(d)
    if (num < 0) != (d < 0):
        q = -q
    return (q + (1 << 19)) >> 20


def _plates(bdhc: dict) -> list[tuple]:
    out = []
    for p1, p2, ni, ci in bdhc["plates"]:
        (x1, z1), (x2, z2) = bdhc["points"][p1], bdhc["points"][p2]
        nx, ny, nz = bdhc["normals"][ni]
        out.append((min(x1, x2), max(x1, x2), min(z1, z2), max(z1, z2), nx, ny, nz,
                    bdhc["constants"][ci]))
    return out


def _plate_y(p, x: int, z: int) -> int | None:
    if p[5] == 0:
        return None
    return _fx_div(-(p[7] + (_fx_mul(p[4], x) + _fx_mul(p[6], z))), p[5])


def tile_corners(bdhc: dict) -> list[list]:
    """32x32 grid of [nw, ne, se, sw] world-unit heights (or None)."""
    plates = _plates(bdhc)
    per_tile = defaultdict(list)
    for p in plates:
        tx0 = max(0, math.floor((p[0] / FX + HALF - TILE / 2) / TILE))
        tx1 = min(GRID - 1, math.floor((p[1] / FX + HALF - TILE / 2) / TILE))
        tz0 = max(0, math.floor((p[2] / FX + HALF - TILE / 2) / TILE))
        tz1 = min(GRID - 1, math.floor((p[3] / FX + HALF - TILE / 2) / TILE))
        for tz in range(max(0, tz0 - 1), tz1 + 2):
            for tx in range(max(0, tx0 - 1), tx1 + 2):
                if tx < GRID and tz < GRID:
                    per_tile[(tx, tz)].append(p)
    out = []
    for tz in range(GRID):
        row = []
        for tx in range(GRID):
            cx, cz = (-HALF + TILE * tx + TILE // 2) * FX, (-HALF + TILE * tz + TILE // 2) * FX
            best = None
            for p in per_tile.get((tx, tz), ()):
                if p[0] <= cx <= p[1] and p[2] <= cz <= p[3]:
                    y = _plate_y(p, cx, cz)
                    if y is not None and (best is None or y > best[0]):
                        best = (y, p)
            if best is None:
                row.append(None)
                continue
            x0, z0 = (-HALF + TILE * tx) * FX, (-HALF + TILE * tz) * FX
            x1, z1 = x0 + TILE * FX, z0 + TILE * FX
            row.append([_plate_y(best[1], x, z) / FX for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))])
        out.append(row)
    return out


# --- Polygons ---------------------------------------------------------------
# A vertex is [x, y, z, s, t, nx, ny, nz, r, g, b] (world units, texels, n/512, 0..31).

def _s10(v: int) -> int:
    v &= 0x3FF
    return v - 0x400 if v & 0x200 else v


def _model_polys(model: dict, keys: list[str]) -> list[tuple[str, list[list]]]:
    scale = model["info"]["posScale"]
    tr = [c / FX for c in model["nodes"][0].get("translation", (0, 0, 0))]
    out = []
    for mat, shp in nsbmd._shape_materials(model):
        for prim in nsbmd.dl_primitives(model["shapes"][shp]["dl"]):
            for poly in nsbmd._polygons(prim):
                vs = []
                for v in poly:
                    x, y, z = (c * scale / FX / FX + tr[k] for k, c in enumerate(v["pos"]))
                    uv = v["uv"]
                    n, c = v["normal"], v["color"]
                    vs.append([x, y, z,
                               None if uv is None else uv[0] / 16, None if uv is None else uv[1] / 16,
                               *((None,) * 3 if n is None else (_s10(n) / 512, _s10(n >> 10) / 512,
                                                               _s10(n >> 20) / 512)),
                               *((None,) * 3 if c is None else (c & 31, (c >> 5) & 31, (c >> 10) & 31))])
                out.append((keys[mat], vs))
    return out


def _lerp(a: list, b: list, t: float) -> list:
    return [None if p is None or q is None else p + (q - p) * t for p, q in zip(a, b)]


def _clip(poly: list[list], axis: int, bound: float, keep_above: bool) -> list[list]:
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina = a[axis] >= bound if keep_above else a[axis] <= bound
        inb = b[axis] >= bound if keep_above else b[axis] <= bound
        if ina:
            out.append(a)
        if ina != inb:
            t = (bound - a[axis]) / (b[axis] - a[axis])
            p = _lerp(a, b, t)
            p[axis] = bound
            out.append(p)
    dedup = []
    for v in out:
        if not dedup or v[0] != dedup[-1][0] or v[2] != dedup[-1][2]:
            dedup.append(v)
    if len(dedup) > 1 and dedup[0][0] == dedup[-1][0] and dedup[0][2] == dedup[-1][2]:
        dedup.pop()
    return dedup


def _area2(poly: list[list]) -> float:
    """Twice the signed xz area (positive = +y facing with vanilla winding)."""
    s = 0.0
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        s += a[2] * b[0] - a[0] * b[2]
    return s


def _split(poly: list[list]) -> list[list[list]]:
    """Convex polygon -> quads (and one triangle if odd), fan from vertex 0."""
    if len(poly) <= 4:
        return [poly]
    out, i = [], 1
    while i + 2 < len(poly):
        out.append([poly[0], poly[i], poly[i + 1], poly[i + 2]])
        i += 2
    if i + 1 < len(poly):
        out.append([poly[0], poly[i], poly[i + 1]])
    return out


def _tile_of(v: float) -> int:
    return min(GRID - 1, max(0, math.floor((v + HALF) / TILE)))


def _is_flat(vs: list[list]) -> bool:
    return all(v[1] == vs[0][1] for v in vs)


def _affine_attrs(vs: list[list]) -> bool:
    """True if every attribute is an affine function of (x, z) over the polygon."""
    if len(vs) == 3:
        return True
    a, b, c = vs[0], vs[1], vs[2]
    det = (b[0] - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (b[2] - a[2])
    if det == 0:
        return False
    for v in vs[3:]:
        u = ((v[0] - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (v[2] - a[2])) / det
        w = ((b[0] - a[0]) * (v[2] - a[2]) - (v[0] - a[0]) * (b[2] - a[2])) / det
        for k in range(3, 11):
            if a[k] is None:
                continue
            want = a[k] + u * (b[k] - a[k]) + w * (c[k] - a[k])
            if abs(want - v[k]) > (1 / 32 if k < 5 else 1 / 1024 if k < 8 else 0.01):
                return False
    return True


def slice_polys(polys) -> dict:
    """{(tx, tz): [(key, verts in world units)]}: centroid rule, flat ground clipped per tile."""
    cells = defaultdict(list)
    eps = 1e-6
    for key, vs in polys:
        xs, zs = [v[0] for v in vs], [v[2] for v in vs]
        tx0, tx1 = _tile_of(min(xs) + eps), _tile_of(max(xs) - eps)
        tz0, tz1 = _tile_of(min(zs) + eps), _tile_of(max(zs) - eps)
        if _is_flat(vs) and (tx0 != tx1 or tz0 != tz1) and _affine_attrs(vs):
            for tz in range(tz0, tz1 + 1):
                for tx in range(tx0, tx1 + 1):
                    piece = vs
                    if tx > 0:
                        piece = _clip(piece, 0, -HALF + TILE * tx, True)
                    if piece and tx < GRID - 1:
                        piece = _clip(piece, 0, -HALF + TILE * (tx + 1), False)
                    if piece and tz > 0:
                        piece = _clip(piece, 2, -HALF + TILE * tz, True)
                    if piece and tz < GRID - 1:
                        piece = _clip(piece, 2, -HALF + TILE * (tz + 1), False)
                    if len(piece) < 3 or abs(_area2(piece)) < 1e-9:
                        continue
                    for part in _split(piece):
                        cells[(tx, tz)].append((key, part))
        else:
            cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
            cells[(_tile_of(cx), _tile_of(cz))].append((key, vs))
    return cells


def _reduce_uv(vs: list[list], period) -> list[list]:
    if period is None or vs[0][3] is None:
        return vs
    ps, pt = period
    ds = math.floor(min(v[3] for v in vs) / ps) * ps if ps else 0
    dt = math.floor(min(v[4] for v in vs) / pt) * pt if pt else 0
    if not ds and not dt:
        return vs
    return [[*v[:3], v[3] - ds, v[4] - dt, *v[5:]] for v in vs]


def _canon(vs: list[list]) -> tuple:
    def r(c, q):
        return None if c is None else round(c * q)
    return tuple((r(v[0], 4096), r(v[1], 4096), r(v[2], 4096), r(v[3], 16), r(v[4], 16),
                  r(v[5], 512), r(v[6], 512), r(v[7], 512), r(v[8], 1), r(v[9], 1), r(v[10], 1))
                 for v in vs)


# --- Kit --------------------------------------------------------------------

def _material_content(m: dict, texture, palette) -> str:
    # The name is content: map texture animations bind to material names.
    return repr((sorted(m.items()), texture, palette))


def _period(mat: dict, textures: dict):
    tex = mat.get("texture")
    if not tex or tex not in textures:
        return None
    tip = mat["texImageParam"]
    w, h = textures[tex]["width"], textures[tex]["height"]
    ps = (w * (2 if tip >> 18 & 1 else 1)) if tip >> 16 & 1 else 0
    pt = (h * (2 if tip >> 19 & 1 else 1)) if tip >> 17 & 1 else 0
    return (ps, pt) if ps or pt else None


def _texset(source, tileset: int) -> dict:
    return nsbmd.texture_set(narc.members(source.read("a/0/4/4"))[tileset])


def build_kit(source, map_tileset: int) -> dict:
    from .. import world
    started = time.time()
    w = world.load_base(source)
    owned, conflicts = tileset_lands(w)
    mine = owned.get(map_tileset, {"lands": set(), "areas": set()})
    textures = _texset(source, map_tileset)["textures"]
    materials, content_key, name_count = {}, {}, Counter()
    order_acc = defaultdict(list)
    cells, sig_index, chunks = [], {}, {}
    periods = {}
    for land in sorted(mine["lands"]):
        spec, model_bytes = codecs.decode_land(w.raw["land"][land])
        model = nsbmd.parse(model_bytes)["models"][0]
        tex_of = {i: t["name"] for t in model["textures"] for i in t["materials"]}
        pal_of = {i: p["name"] for p in model["palettes"] for i in p["materials"]}
        keys = []
        for i, m in enumerate(model["materials"]):
            content = _material_content(m, tex_of.get(i), pal_of.get(i))
            if content not in content_key:
                name_count[m["name"]] += 1
                key = m["name"] if name_count[m["name"]] == 1 else f"{m['name']}~{name_count[m['name']]}"
                content_key[content] = key
                materials[key] = {**m, "texture": tex_of.get(i), "palette": pal_of.get(i)}
                periods[key] = _period(materials[key], textures)
            keys.append(content_key[content])
        drawn = [keys[mat] for mat, _ in nsbmd._shape_materials(model)]
        for rank, key in enumerate(dict.fromkeys(drawn)):
            order_acc[key].append(rank / max(1, len(set(drawn)) - 1))
        sliced = slice_polys(_model_polys(model, keys))
        tiles = spec["tiles"]
        corners = tile_corners(spec["bdhc"])
        grid = []
        for tz in range(GRID):
            beh = [int(v, 16) for v in tiles["behavior"][tz].split()]
            sec = [int(v, 16) for v in tiles["secondary"][tz].split()]
            row = []
            for tx in range(GRID):
                ox, oz = -HALF + TILE * tx, -HALF + TILE * tz
                polys = []
                for key, vs in sliced.get((tx, tz), ()):
                    rel = [[v[0] - ox, v[1], v[2] - oz, *v[3:]] for v in vs]
                    polys.append({"mat": key, "verts": _reduce_uv(rel, periods[key])})
                polys.sort(key=lambda p: (p["mat"], repr(_canon(p["verts"]))))
                collision = tiles["collision"][tz][tx] == "#"
                cell = {"cls": classify(beh[tx], collision), "behavior": beh[tx],
                        "collision": collision, "secondary": sec[tx], "corners": corners[tz][tx],
                        "polys": polys}
                sig = hashlib.sha1(repr((
                    [(p["mat"], _canon(p["verts"])) for p in polys], beh[tx], collision, sec[tx],
                    corners[tz][tx])).encode()).hexdigest()[:16]
                if sig not in sig_index:
                    sig_index[sig] = len(cells)
                    cells.append({"sig": sig, **cell, "count": 0})
                index = sig_index[sig]
                cells[index]["count"] += 1
                row.append(index)
            grid.append(row)
        chunks[land] = grid
    order = sorted(materials, key=lambda k: (sum(order_acc[k]) / max(1, len(order_acc[k])), k))
    return {"tileset": map_tileset, "areas": sorted(mine["areas"]), "materials": materials,
            "cells": cells, "chunks": chunks,
            # additions beyond the spec, used by compose and reports
            "materialOrder": order, "periods": periods,
            "skipped": {"conflictingLands": len(conflicts),
                        "conflictingLandsHere": sorted(l for l, t in conflicts.items() if map_tileset in t)},
            "version": KIT_VERSION, "seconds": round(time.time() - started, 2)}


def _rom_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_or_build_kit(source, map_tileset: int, cache: bool = True) -> dict:
    """build_kit with a pickle cache keyed by the ROM's SHA-256 (RomSource only)."""
    path = getattr(source, "path", None)
    if not cache or path is None:
        return build_kit(source, map_tileset)
    sha = _rom_sha(Path(path))
    file = CACHE_DIR / f"kit-{map_tileset}.pickle"
    if file.exists():
        try:
            data = pickle.loads(file.read_bytes())
            if data.get("sha") == sha and data.get("version") == KIT_VERSION:
                return data["kit"]
        except Exception:  # stale or partial cache: rebuild
            pass
    kit = build_kit(source, map_tileset)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps({"sha": sha, "version": KIT_VERSION, "kit": kit}, protocol=5))
    tmp.replace(file)
    return kit


# --- Compose ----------------------------------------------------------------

def _pack_normal(v) -> int | None:
    if v[5] is None:
        return None
    return sum((max(-512, min(511, round(v[5 + k] * 512))) & 0x3FF) << (10 * k) for k in range(3))


def _pack_color(v) -> int | None:
    if v[8] is None:
        return None
    r, g, b = (max(0, min(31, round(v[8 + k]))) for k in range(3))
    return r | g << 5 | b << 10


def _rect_of(vs):
    """(x0, x1, z0, z1, orientation) if vs is an axis-aligned flat rectangle."""
    if len(vs) != 4:
        return None
    xs, zs = sorted({v[0] for v in vs}), sorted({v[2] for v in vs})
    if len(xs) != 2 or len(zs) != 2 or {(v[0], v[2]) for v in vs} != {(x, z) for x in xs for z in zs}:
        return None
    a = _area2(vs)
    if a == 0:
        return None
    return xs[0], xs[1], zs[0], zs[1], 1 if a > 0 else -1


def _merge_rects(rects, ok):
    """Merge touching rectangles (x0, x1, z0, z1) row-wise then column-wise."""
    changed = True
    while changed:
        changed = False
        for along in (0, 1):
            if along == 0:
                rects.sort(key=lambda r: (r[2], r[3], r[0]))
            else:
                rects.sort(key=lambda r: (r[0], r[1], r[2]))
            out = []
            for r in rects:
                if out:
                    p = out[-1]
                    if along == 0 and p[2] == r[2] and p[3] == r[3] and p[1] == r[0]:
                        m = (p[0], r[1], p[2], p[3])
                    elif along == 1 and p[0] == r[0] and p[1] == r[1] and p[3] == r[2]:
                        m = (p[0], p[1], p[2], r[3])
                    else:
                        m = None
                    if m is not None and ok(m):
                        out[-1] = m
                        changed = True
                        continue
                out.append(r)
            rects = out
    return rects


def _vertex(v) -> dict:
    return {"pos": (v[0], v[1], v[2]), "uv": None if v[3] is None else (v[3], v[4]),
            "normalRaw": _pack_normal(v), "colorRaw": _pack_color(v)}


def _affine_maps(vs):
    """Per attribute (s, t, nx, ny, nz, r, g, b): (a, b, c) with attr = a*x + b*z + c, or
    None when absent; returns None if the polygon's attributes are not affine."""
    n = len(vs)
    tri = None
    for j in range(1, n - 1):
        for k in range(j + 1, n):
            det = (vs[j][0] - vs[0][0]) * (vs[k][2] - vs[0][2]) - (vs[k][0] - vs[0][0]) * (vs[j][2] - vs[0][2])
            if abs(det) > 1e-9:
                tri = (vs[0], vs[j], vs[k], det)
                break
        if tri:
            break
    if tri is None:
        return None
    p, q, r, det = tri
    maps = []
    for k in range(3, 11):
        if p[k] is None:
            maps.append(None)
            continue
        da, db = q[k] - p[k], r[k] - p[k]
        a = (da * (r[2] - p[2]) - db * (q[2] - p[2])) / det
        b = (db * (q[0] - p[0]) - da * (r[0] - p[0])) / det
        c = p[k] - a * p[0] - b * p[2]
        tol = 1 / 32 if k < 5 else 1 / 1024 if k < 8 else 0.01
        if any(abs(a * v[0] + b * v[2] + c - v[k]) > tol for v in vs):
            return None
        maps.append((a, b, c))
    return maps


def _group_key(y, orient, maps, period):
    key = [round(y * 4096), orient]
    for k, m in enumerate(maps):
        if m is None:
            key.append(None)
            continue
        a, b, c = m
        per = period[k] if period and k < 2 else 0
        cq = round(c * 256)
        if per:
            cq %= round(per * 256)
        key.append((round(a * 65536), round(b * 65536), cq if k < 2 else round(c * 4096)))
    return tuple(key)


def _q(v):
    return round(v[0] * 1024), round(v[2] * 1024)


def _cross(a, b, c):
    return (b[2] - a[2]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[2] - b[2])


def _dot(a, b, c):
    return (b[0] - a[0]) * (c[0] - b[0]) + (b[2] - a[2]) * (c[2] - b[2])


def _drop_collinear(loop):
    """Remove vertices lying on a straight continuation (not reversals/spikes)."""
    changed = True
    while changed and len(loop) > 3:
        changed = False
        for i in range(len(loop)):
            a, b, c = loop[i - 1], loop[i], loop[(i + 1) % len(loop)]
            if abs(_cross(a, b, c)) < 1e-6 and _dot(a, b, c) > 0:
                loop = loop[:i] + loop[i + 1:]
                changed = True
                break
    return loop


def _ear_clip(loop, orient):
    """Triangulate a simple polygon (orientation sign orient); None if it fails."""
    loop, out = list(loop), []

    def inside(p, a, b, c):  # strictly inside, or on the new diagonal c-a
        d1, d2, d3 = _cross(a, b, p), _cross(b, c, p), _cross(c, a, p)
        return d1 * orient > 1e-9 and d2 * orient > 1e-9 and d3 * orient > -1e-9
    guard = 0
    while len(loop) > 3:
        guard += 1
        if guard > 10000:
            return None
        for i in range(len(loop)):
            a, b, c = loop[i - 1], loop[i], loop[(i + 1) % len(loop)]
            if _cross(a, b, c) * orient <= 1e-9:
                continue
            if any(inside(p, a, b, c) for p in loop if p is not a and p is not b and p is not c):
                continue
            out.append([a, b, c])
            loop.pop(i)
            break
        else:
            return None
    out.append(loop)
    return out


def _reduce_ok(vs, period):
    vs = _reduce_uv(vs, period)
    if vs[0][3] is not None and max(abs(c) for v in vs for c in v[3:5]) > MAX_UV:
        return None
    return vs


def _boundary_loop(pieces):
    """Single boundary loop (collinear points kept) of edge-sharing pieces, or None."""
    directed, at = Counter(), {}
    for vs in pieces:
        for i in range(len(vs)):
            qa, qb = _q(vs[i]), _q(vs[(i + 1) % len(vs)])
            directed[(qa, qb)] += 1
            at.setdefault(qa, vs[i])
    if any(n > 1 for n in directed.values()):
        return None
    edges = [(a, b) for (a, b) in directed if (b, a) not in directed]
    boundary = dict(edges)
    if len(boundary) != len(edges):
        return None  # a vertex starts two boundary edges: pinched or holed region
    start = edges[0][0]
    loop, cur = [], start
    while True:
        loop.append(at[cur])
        cur = boundary[cur]
        if cur == start:
            break
        if len(loop) > len(boundary):
            return None
    if len(loop) != len(boundary):
        return None  # several loops (holes or islands)
    if abs(_area2(loop) - sum(_area2(vs) for vs in pieces)) > 1e-3:
        return None  # overlapping pieces: their union would change coverage
    return loop


def _is_convex(loop, orient):
    """Convex with the given facing; straight-through vertices allowed, reversals not."""
    n = len(loop)
    for i in range(n):
        a, b, c = loop[i - 1], loop[i], loop[(i + 1) % n]
        cr = _cross(a, b, c) * orient
        if cr > 1e-6:
            continue
        if cr < -1e-6 or _dot(a, b, c) <= 0:
            return False
    return True


def _greedy_convex(pieces, orient, period):
    """Pairwise-merge edge-sharing pieces while the union stays convex and in UV range."""
    polys = {i: vs for i, vs in enumerate(pieces)}
    edge_owner = {}

    def index(i):
        vs = polys[i]
        for j in range(len(vs)):
            edge_owner[(_q(vs[j]), _q(vs[(j + 1) % len(vs)]))] = i
    for i in polys:
        index(i)
    queue = list(polys)
    while queue:
        i = queue.pop()
        if i not in polys:
            continue
        vs = polys[i]
        for j in range(len(vs)):
            other = edge_owner.get((_q(vs[(j + 1) % len(vs)]), _q(vs[j])))
            if other is None or other == i or other not in polys:
                continue
            loop = _boundary_loop([vs, polys[other]])
            if loop is None or not _is_convex(loop, orient):
                continue
            if _reduce_ok(_drop_collinear(loop), period) is None:
                continue
            del polys[other]
            polys[i] = loop
            index(i)
            queue.append(i)
            break
    out = []
    for vs in polys.values():
        for part in _split(_drop_collinear(vs)):
            red = _reduce_ok(part, period)
            out.append(red if red is not None else _reduce_uv(part, period))
    return out


def _union_component(pieces, orient, period):
    """Boundary of a set of edge-sharing pieces -> polygons, or None to keep the pieces."""
    loop = _boundary_loop(pieces)
    if loop is None:
        return None
    loop = _drop_collinear(loop)
    if len(loop) < 3:
        return None
    if _is_convex(loop, orient):
        parts = _split(loop)
    else:
        if all(_rect_of(vs) for vs in pieces):
            return None  # rectangles: the rectangle merge does better than thin triangles
        parts = _ear_clip(loop, orient)
        if parts is None:
            return None
    out = []
    for vs in parts:
        vs = _reduce_ok(vs, period)
        if vs is None:
            return None
        out.append(vs)
    return out


def _rect_merge(pieces, period):
    """Merge same-map rectangles row-wise then column-wise; pieces share one affine map."""
    maps = _affine_maps(pieces[0])
    orient = 1 if _area2(pieces[0]) > 0 else -1
    y = pieces[0][0][1]

    def verts(r):
        x0, x1, z0, z1 = r
        order = [(x0, z1), (x1, z1), (x1, z0), (x0, z0)]
        if orient < 0:
            order.reverse()
        vs = []
        for x, z in order:
            v = [x, y, z] + [None if m is None else m[0] * x + m[1] * z + m[2] for m in maps]
            vs.append(v)
        return _reduce_ok(vs, period)

    rects, rest = [], []
    for vs in pieces:
        r = _rect_of(vs)
        if r is None:
            rest.append(vs)
        else:
            rects.append(r[:4])
    out = [verts(r) or None for r in _merge_rects(rects, lambda r: verts(r) is not None)]
    if any(v is None for v in out):
        return [_reduce_uv(vs, period) for vs in pieces]
    return out + [_reduce_uv(vs, period) for vs in rest]


def _material_polys(polys, period):
    """Kit polygons of one material (world units) -> list of nsbmd vertex-dict polygons.

    Flat polygons with affine attributes are grouped by (height, facing, attribute
    maps); edge-sharing pieces of a group are re-joined (convex union, else ear
    clipping, else rectangle merging) so clipped ground recombines.
    """
    groups, reps, out = defaultdict(list), {}, []
    for vs in polys:
        maps = _affine_maps(vs) if _is_flat(vs) else None
        if maps is None:
            out.append(vs)
            continue
        orient = 1 if _area2(vs) > 0 else -1
        key = _group_key(vs[0][1], orient, maps, period)
        if key not in reps:
            reps[key] = maps
        else:  # move UVs by whole periods onto the group's representative map
            shift = []
            for k in range(2):
                m, r = maps[k], reps[key][k]
                per = period[k] if period else 0
                shift.append(0 if m is None or not per else round((r[2] - m[2]) / per) * per)
            if any(shift):
                vs = [[*v[:3], v[3] + shift[0], v[4] + shift[1], *v[5:]] for v in vs]
        groups[key].append(vs)
    for key, pieces in groups.items():
        orient = key[1]
        # connected components over shared (opposite) edges
        parent = list(range(len(pieces)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        owner = {}
        for i, vs in enumerate(pieces):
            for j in range(len(vs)):
                owner.setdefault((_q(vs[j]), _q(vs[(j + 1) % len(vs)])), i)
        for i, vs in enumerate(pieces):
            for j in range(len(vs)):
                other = owner.get((_q(vs[(j + 1) % len(vs)]), _q(vs[j])))
                if other is not None:
                    parent[find(i)] = find(other)
        comps = defaultdict(list)
        for i in range(len(pieces)):
            comps[find(i)].append(pieces[i])
        for comp in comps.values():
            if len(comp) == 1:
                merged = [_reduce_uv(comp[0], period)]
            else:
                merged = _union_component(comp, orient, period)
                if merged is None:
                    rects = all(_rect_of(vs) for vs in comp)
                    merged = _rect_merge(comp, period) if rects else _greedy_convex(comp, orient, period)
            out += merged
    return [[_vertex(v) for v in vs] for vs in out]


def _vkey(v, scale, period=None):
    uv = None
    if v["uv"] is not None:
        uv = [round(c * 16) for c in v["uv"]]
        for k in range(2):
            if period and period[k]:
                uv[k] %= period[k] * 16
        uv = tuple(uv)
    return (tuple(nsbmd._raw_pos(c, scale) for c in v["pos"]), uv, v["normalRaw"], v["colorRaw"])


def _shift_to(q, pairs):
    """q with UVs moved by whole periods so each (src, dst) pair's UVs coincide, or None."""
    src, dst = pairs[0]
    if src["uv"] is None:
        return q
    ds, dt = dst["uv"][0] - src["uv"][0], dst["uv"][1] - src["uv"][1]
    for p, d in pairs[1:]:
        if abs(d["uv"][0] - p["uv"][0] - ds) > 1e-9 or abs(d["uv"][1] - p["uv"][1] - dt) > 1e-9:
            return None
    if not ds and not dt:
        return q
    out = [{**v, "uv": (v["uv"][0] + ds, v["uv"][1] + dt)} for v in q]
    if any(abs(c) > MAX_UV for v in out for c in v["uv"]):
        return None
    return out


def _strips(quads, scale, period=None):
    """Chain quads that share an edge into quad strips; return (strips, single quads).

    A strip is a list of rungs (vertex pairs); quad k spans rungs k and k+1 as
    [a_k, b_k, b_k+1, a_k+1]. Quads are seeded fewest-neighbours first and grown
    in both directions.
    """
    keyed = [[_vkey(v, scale, period) for v in q] for q in quads]
    entries, exits = defaultdict(list), defaultdict(list)
    for i, ks in enumerate(keyed):
        for r in range(4):
            entries[(ks[r], ks[(r + 1) % 4])].append((i, r))
            exits[(ks[(r + 3) % 4], ks[(r + 2) % 4])].append((i, r))
    used = [False] * len(quads)

    def free(edge_map, edge, me):
        return [(j, r) for j, r in edge_map.get(edge, ()) if not used[j] and j != me]

    def degree(i):
        ks = keyed[i]
        return sum(bool(free(entries, (ks[(r + 3) % 4], ks[(r + 2) % 4]), i)) for r in range(4))

    strips, singles = [], []
    for i in sorted(range(len(quads)), key=degree):
        if used[i]:
            continue
        ks = keyed[i]
        best, best_n = 0, -1
        for r in (0, 1):
            n = (bool(free(entries, (ks[(r + 3) % 4], ks[(r + 2) % 4]), i))
                 + bool(free(exits, (ks[r], ks[(r + 1) % 4]), i)))
            if n > best_n:
                best, best_n = r, n
        used[i] = True
        if best_n == 0:
            singles.append(quads[i])
            continue
        q = [quads[i][(best + k) % 4] for k in range(4)]
        kq = [ks[(best + k) % 4] for k in range(4)]
        rungs = [(q[0], q[1]), (q[3], q[2])]
        head, tail = (kq[0], kq[1]), (kq[3], kq[2])
        while True:
            found = None
            for j, r in free(entries, tail, -1):
                qj = [quads[j][(r + k) % 4] for k in range(4)]
                qj = _shift_to(qj, [(qj[0], rungs[-1][0]), (qj[1], rungs[-1][1])])
                if qj is not None:
                    found = (j, r, qj)
                    break
            if found is None:
                break
            j, r, qj = found
            used[j] = True
            kj = [keyed[j][(r + k) % 4] for k in range(4)]
            rungs.append((qj[3], qj[2]))
            tail = (kj[3], kj[2])
        while True:
            found = None
            for j, r in free(exits, head, -1):
                qj = [quads[j][(r + k) % 4] for k in range(4)]
                qj = _shift_to(qj, [(qj[3], rungs[0][0]), (qj[2], rungs[0][1])])
                if qj is not None:
                    found = (j, r, qj)
                    break
            if found is None:
                break
            j, r, qj = found
            used[j] = True
            kj = [keyed[j][(r + k) % 4] for k in range(4)]
            rungs.insert(0, (qj[0], qj[1]))
            head = (kj[0], kj[1])
        strips.append([v for rung in rungs for v in rung])
    return strips, singles


def _tri_strips(tris, scale, period=None):
    """Chain triangles into triangle strips (forward only); return (strips, single triangles)."""
    keyed = [[_vkey(v, scale, period) for v in t] for t in tris]
    starts = defaultdict(list)
    for i, ks in enumerate(keyed):
        for r in range(3):
            starts[(ks[r], ks[(r + 1) % 3])].append((i, r))
    used = [False] * len(tris)

    def degree(i):
        ks = keyed[i]
        return sum(any(not used[j] and j != i for j, _ in starts.get((ks[(r + 1) % 3], ks[r]), ()))
                   for r in range(3))

    strips, singles = [], []
    for i in sorted(range(len(tris)), key=degree):
        if used[i]:
            continue
        used[i] = True
        ks = keyed[i]
        best = None
        for r in range(3):  # even step 1 needs edge (v1, v2) reversed: (v2, v1)
            if any(not used[j] for j, _ in starts.get((ks[(r + 2) % 3], ks[(r + 1) % 3]), ())):
                best = r
                break
        if best is None:
            singles.append(tris[i])
            continue
        verts = [tris[i][(best + k) % 3] for k in range(3)]
        vkeys = [ks[(best + k) % 3] for k in range(3)]
        while True:
            odd = (len(verts) - 2) % 2 == 1
            edge = (vkeys[-1], vkeys[-2]) if odd else (vkeys[-2], vkeys[-1])
            found = None
            for j, r in starts.get(edge, ()):
                if used[j]:
                    continue
                t = [tris[j][(r + k) % 3] for k in range(3)]
                t = _shift_to(t, [(t[0], verts[-1]), (t[1], verts[-2])] if odd
                              else [(t[0], verts[-2]), (t[1], verts[-1])])
                if t is not None:
                    found = (j, r, t)
                    break
            if found is None:
                break
            j, r, t = found
            used[j] = True
            verts.append(t[2])
            vkeys.append(keyed[j][(r + 2) % 3])
        strips.append(verts)
    return strips, singles


def _pos_cmd(raw, prev):
    x, y, z = raw
    if prev is not None:
        if y == prev[1]:
            return [0x26, (x & 0xFFFF) | ((z & 0xFFFF) << 16)]
        if z == prev[2]:
            return [0x25, (x & 0xFFFF) | ((y & 0xFFFF) << 16)]
        if x == prev[0]:
            return [0x27, (y & 0xFFFF) | ((z & 0xFFFF) << 16)]
        d = [raw[k] - prev[k] for k in range(3)]
        if all(-512 <= c <= 511 for c in d):
            return [0x28, (d[0] & 0x3FF) | ((d[1] & 0x3FF) << 10) | ((d[2] & 0x3FF) << 20)]
    if all(c % 64 == 0 and -32768 <= c <= 32704 for c in raw):
        return [0x24, ((x >> 6) & 0x3FF) | (((y >> 6) & 0x3FF) << 10) | (((z >> 6) & 0x3FF) << 20)]
    return [0x23, (x & 0xFFFF) | ((y & 0xFFFF) << 16), z & 0xFFFF]


def _emit(cmds, verts, scale, state, flag):
    prev = None
    for v in verts:
        if v["uv"] is not None:
            raw = nsbmd._pack_uv(v["uv"])
            if state.get("uv") != raw:
                cmds.append([0x22, raw]); state["uv"] = raw
            flag |= 4
        if v["normalRaw"] is not None:
            if state.get("normal") != v["normalRaw"]:
                cmds.append([0x21, v["normalRaw"]]); state["normal"] = v["normalRaw"]
            flag |= 1
        if v["colorRaw"] is not None:
            if state.get("color") != v["colorRaw"]:
                cmds.append([0x20, v["colorRaw"]]); state["color"] = v["colorRaw"]
            flag |= 2
        raw = tuple(nsbmd._raw_pos(c, scale) for c in v["pos"])
        if any(not -32768 <= c <= 32767 for c in raw):
            raise ComposeError(f"vertex {v['pos']} does not fit the position scale")
        cmds.append(_pos_cmd(raw, prev))
        prev = raw
    return flag


def _shape_dl(polys, scale, period=None):
    quads = [p for p in polys if len(p) == 4]
    tris = [p for p in polys if len(p) == 3]
    strips, singles = _strips(quads, scale, period)
    tstrips, tris = _tri_strips(tris, scale, period)
    cmds, state, flag = [], {}, 0
    for kind, group in ((3, strips), (2, tstrips)):
        for strip in group:
            cmds.append([0x40, kind])
            flag = _emit(cmds, strip, scale, state, flag)
            cmds.append([0x41])
    for kind, group in ((1, singles), (0, tris)):
        if group:
            cmds.append([0x40, kind])
            flag = _emit(cmds, [v for p in group for v in p], scale, state, flag)
            cmds.append([0x41])
    while len(cmds) % 4:
        cmds.append([0])
    cmds += [[0]] * 4
    return cmds, flag


# An untextured animation-slot material exactly as vanilla land models store it
# (e.g. land 87 material 1, "swave_p").
UNTEXTURED_SLOT = {"diffAmb": 0x7FFFE739, "specEmi": 0, "polyAttr": 0x1F0081, "polyAttrMask": 0x3F1FF8FF,
                   "texImageParam": 0x40030000, "texImageParamMask": 0xFFFFFFFF, "texPlttBase": 0,
                   "flag": 0x1FCF, "origWidth": 0, "origHeight": 0, "magW": 0x1000, "magH": 0x1000,
                   "texture": None, "palette": None}


def area_animation_materials(source, file_id: int) -> list[str]:
    """Material names of an area's land texture animation (a/1/4/0 member, AreaData field 3).

    The game binds this NSBTA to every land model by material INDEX, not by name
    (map_prop_render.c AreaMapAnimation_InitAnimObj: mapData[i] = i | 0x100), so
    vanilla land models start their material table with exactly these names.
    0xFFFF means the area has no land animation.
    """
    import struct
    if file_id == 0xFFFF:
        return []
    data = bytes(narc.members(source.read("a/1/4/0"))[file_id])

    def dictionary(offset):
        count = data[offset + 1]
        size, entries = struct.unpack_from("<H", data, offset + 2)[0], struct.unpack_from("<H", data, offset + 6)[0]
        unit = struct.unpack_from("<H", data, offset + entries)[0]
        values = [struct.unpack_from("<I", data, offset + entries + 4 + unit * i)[0] for i in range(count)]
        base = offset + size - 16 * count
        names = [data[base + 16 * i:base + 16 * (i + 1)].split(b"\0")[0].decode("latin-1") for i in range(count)]
        return names, values

    if data[:4] != b"BTA0":
        raise ComposeError(f"a/1/4/0 member {file_id} is not an NSBTA")
    block = struct.unpack_from("<I", data, 16)[0]
    _, offsets = dictionary(block + 8)
    anim = block + offsets[0]  # the game uses the first animation only
    names, _ = dictionary(anim + 8)
    return names


def compose(kit: dict, grid: list[list[int]], name: str = "chunk",
            check: bool = True, anim_materials: list[str] | None = None) -> tuple[bytes, dict, list]:
    """Stitch a 32x32 grid of kit cell indices into (NSBMD bytes, tiles spec, corners).

    anim_materials: the area's land animation materials (area_animation_materials).
    They take material slots 0..n-1 in that order, as in vanilla; the animation
    binds by index, so any other material there would scroll like water. The
    slots are untextured (see below); drawn materials follow them.
    """
    if len(grid) != GRID or any(len(row) != GRID for row in grid):
        raise ComposeError("grid must be 32 rows of 32 cell indices")
    cells = kit["cells"]
    per_mat = defaultdict(list)
    collision, behavior, secondary, corners = [], [], [], []
    for tz, row in enumerate(grid):
        crow, brow, srow, hrow = [], [], [], []
        for tx, index in enumerate(row):
            cell = cells[index]
            ox, oz = -HALF + TILE * tx, -HALF + TILE * tz
            for p in cell["polys"]:
                per_mat[p["mat"]].append([[v[0] + ox, v[1], v[2] + oz, *v[3:]] for v in p["verts"]])
            crow.append("#" if cell["collision"] else ".")
            brow.append(f"{cell['behavior']:02x}")
            srow.append(f"{cell['secondary']:02x}")
            hrow.append(None if cell["corners"] is None else list(cell["corners"]))
        collision.append("".join(crow))
        behavior.append(" ".join(brow))
        secondary.append(" ".join(srow))
        corners.append(hrow)
    tiles = {"collision": collision, "behavior": behavior, "secondary": secondary}
    used = [k for k in kit["materialOrder"] if per_mat.get(k)]
    if not used:
        raise ComposeError("the grid has no geometry")
    mesh_polys = [_material_polys(per_mat[k], kit["periods"].get(k)) for k in used]
    coords = [c for polys in mesh_polys for p in polys for v in p for c in v["pos"]]
    lo, hi = min(coords), max(coords)
    scale = FX
    while not (-32768 <= nsbmd._raw_pos(lo, scale) and nsbmd._raw_pos(hi, scale) <= 32767):
        scale <<= 1  # smallest 2^k scale; -32768 is a valid fx16 (vanilla uses -512 at scale 64)
    # Material table: the animation's slots first, then everything the grid draws.
    # Slots hold untextured records, as most vanilla chunks do: drawing composed
    # geometry through an animated textured slot crashed the game on a field reload
    # (Mirrorlake 2026-10-16: teleports 542 (51,5) -> (12,16) -> (32,10), ARM9 abort,
    # 3/3; untextured slots 0/3). Water drawn here therefore does not animate.
    table: list = [("slot", anim_name) for anim_name in anim_materials or []]
    table += used
    names, materials = set(), []
    for k in table:
        if isinstance(k, tuple):
            m = {**UNTEXTURED_SLOT, "name": k[1]}
            names.add(m["name"])
            materials.append(m)
            continue
        m = dict(kit["materials"][k])
        base, n = m["name"], 1
        while m["name"] in names:
            n += 1
            m["name"] = f"{base[:13]}~{n}"  # same name, different attributes
        names.add(m["name"])
        materials.append(m)
    # build_model gives materials/SBC/info in vanilla form; shapes are then re-encoded
    # as quad strips with short vertex commands.
    first = [{"material": table.index(used[i]), "triangles": [p[:3]]}
             for i, polys in enumerate(mesh_polys) for p in polys[:1]]
    spec = nsbmd.build_model(name, materials, first, pos_scale=scale)
    model = spec["models"][0]
    for i, polys in enumerate(mesh_polys):
        dl, flag = _shape_dl(polys, scale, kit["periods"].get(used[i]))
        model["shapes"][i]["dl"], model["shapes"][i]["flag"] = dl, flag
    prims = [p for s in model["shapes"] for p in nsbmd.dl_primitives(s["dl"])]
    model["info"].update(nsbmd.primitive_counts(prims))
    world = [[c * scale / FX / FX for c in v["pos"]] for p in prims for v in p["vertices"]]
    lo = [min(w[k] for w in world) for k in range(3)]
    hi = [max(w[k] for w in world) for k in range(3)]
    k = 0
    while True:
        bps = FX << k
        box_min = [math.floor(v * FX * FX / bps) for v in lo]
        box_size = [math.ceil(hi[j] * FX * FX / bps) - box_min[j] for j in range(3)]
        if all(-32768 <= v <= 32767 for v in box_min + box_size):
            break
        k += 1
    model["info"].update(box=box_min + box_size, boxPosScale=bps, boxInvPosScale=FX * FX // bps)
    data = nsbmd.write(spec)
    errors, _ = nsbmd.validate(data)
    if errors and check:
        raise ComposeError("; ".join(errors))
    return data, tiles, corners


# --- Fidelity ---------------------------------------------------------------

def _mod(v, p):
    return v - math.floor(v / p) * p if p else v


def _canon_poly(key, vs, period):
    vs = _reduce_uv(vs, period)
    c = _canon([[round(v[0] * 64) / 64, round(v[1] * 64) / 64, round(v[2] * 64) / 64, *v[3:]] for v in vs])
    r = min(range(len(c)), key=lambda i: c[i:] + c[:i])
    return key, c[r:] + c[:r]


def _attrs_options(vs, x, z):
    """Attribute vectors at (x, z) under each fan origin (quads: both diagonals)."""
    out = []
    for r in range(min(2, len(vs) - 2)):
        t = _attrs_at(vs[r:] + vs[:r], x, z)
        if t is not None:
            out.append(t)
    return out


def _attrs_at(vs, x, z):
    """Attributes at (x, z) inside a convex flat polygon (fan barycentric), else None."""
    for i in range(1, len(vs) - 1):
        a, b, c = vs[0], vs[i], vs[i + 1]
        det = (b[0] - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (b[2] - a[2])
        if det == 0:
            continue
        u = ((x - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (z - a[2])) / det
        w = ((b[0] - a[0]) * (z - a[2]) - (x - a[0]) * (b[2] - a[2])) / det
        if u >= -1e-9 and w >= -1e-9 and u + w <= 1 + 1e-9:
            return [None if a[k] is None else a[k] + u * (b[k] - a[k]) + w * (c[k] - a[k])
                    for k in range(3, 11)]
    return None


def _uv_close(p, q, period):
    for k, per in ((0, period[0] if period else 0), (1, period[1] if period else 0)):
        if (p[k] is None) != (q[k] is None):
            return False
        if p[k] is None:
            continue
        d = p[k] - q[k]
        if per:
            d = _mod(d + per / 2, per) - per / 2
        if abs(d) > 1 / 8:
            return False
    for k in range(2, 8):
        if (p[k] is None) != (q[k] is None) or (p[k] is not None and abs(p[k] - q[k]) > 1.01 / (512 if k < 5 else 1)):
            return False
    return True


# Clip points on slanted edges fall between the model's vertex grid (1/64 or
# 1/128 unit); where the pieces cannot be re-joined, rounding them moves sliver
# edges by at most half a grid step. Allowed per (material, height) group:
AREA_TOLERANCE = 1.0


def compare_geometry(a_polys, b_polys, periods) -> dict:
    """Clip-normalised comparison of two polygon lists [(material key, world verts)]."""
    def split(polys):
        flat, rest = defaultdict(list), Counter()
        for key, vs in polys:
            if _is_flat(vs):
                flat[(key, round(vs[0][1] * 64))].append(vs)
            else:
                rest[_canon_poly(key, vs, periods.get(key))] += 1
        return flat, rest

    fa, ra = split(a_polys)
    fb, rb = split(b_polys)
    out = {"nonFlatA": sum(ra.values()), "nonFlatB": sum(rb.values()),
           "nonFlatMissing": sum((ra - rb).values()), "nonFlatExtra": sum((rb - ra).values()),
           "flatGroups": len(fa), "areaMismatch": 0, "maxAreaDelta": 0.0, "attrMismatch": 0,
           "attrChecked": 0}
    for g in set(fa) | set(fb):
        area_a = sum(_area2(vs) for vs in fa.get(g, ())) / 2
        area_b = sum(_area2(vs) for vs in fb.get(g, ())) / 2
        abs_a = sum(abs(_area2(vs)) for vs in fa.get(g, ())) / 2
        abs_b = sum(abs(_area2(vs)) for vs in fb.get(g, ())) / 2
        delta = max(abs(area_a - area_b), abs(abs_a - abs_b))
        out["maxAreaDelta"] = max(out["maxAreaDelta"], delta)
        if delta > AREA_TOLERANCE:
            out["areaMismatch"] += 1
        period = periods.get(g[0])
        for src, dst in ((fb.get(g, ()), fa.get(g, ())), (fa.get(g, ()), fb.get(g, ()))):
            exact = {_canon_poly(g[0], vs, period) for vs in dst}
            for vs in src:
                if abs(_area2(vs)) < 1e-6:
                    continue
                out["attrChecked"] += 1
                if _canon_poly(g[0], vs, period) in exact:
                    continue
                x = sum(v[0] for v in vs) / len(vs)
                z = sum(v[2] for v in vs) / len(vs)
                mine = _attrs_options(vs, x, z)
                hits = [t for o in dst for t in _attrs_options(o, x, z)]
                if not any(_uv_close(m, t, period) for m in mine for t in hits):
                    out["attrMismatch"] += 1
    out["match"] = not (out["nonFlatMissing"] or out["nonFlatExtra"] or out["areaMismatch"]
                        or out["attrMismatch"])
    return out


def _model_key_polys(model_bytes: bytes, kit: dict) -> list:
    """Polygons of a model keyed by kit material (composed models may rename duplicates)."""
    model = nsbmd.parse(model_bytes)["models"][0]
    tex_of = {i: t["name"] for t in model["textures"] for i in t["materials"]}
    pal_of = {i: p["name"] for p in model["palettes"] for i in p["materials"]}

    def content(m, tex, pal, named):
        return _material_content({k: v for k, v in m.items() if named or k != "name"}, tex, pal)
    exact, loose = {}, defaultdict(list)
    for key, m in kit["materials"].items():
        bare = {k: v for k, v in m.items() if k not in ("texture", "palette")}
        exact[content(bare, m.get("texture"), m.get("palette"), True)] = key
        loose[(m["name"][:13], content(bare, m.get("texture"), m.get("palette"), False))].append(key)
    keys = []
    for i, m in enumerate(model["materials"]):
        key = exact.get(content(m, tex_of.get(i), pal_of.get(i), True))
        if key is None:
            found = loose.get((m["name"].split("~")[0][:13], content(m, tex_of.get(i), pal_of.get(i), False)), [])
            key = found[0] if len(found) == 1 else f"?{m['name']}"
        keys.append(key)
    return _model_polys(model, keys)


def fidelity(kit: dict, source, lands) -> list[dict]:
    from .. import world
    w = world.load_base(source)
    rows = []
    for land in lands:
        spec, original = codecs.decode_land(w.raw["land"][land])
        started = time.time()
        try:
            data, tiles, _ = compose(kit, kit["chunks"][land], f"land{land}")
        except ComposeError as error:
            rows.append({"land": land, "match": False, "error": str(error),
                         "originalBytes": len(original)})
            continue
        seconds = time.time() - started
        geo = compare_geometry(_model_key_polys(original, kit), _model_key_polys(data, kit), kit["periods"])
        info = nsbmd.parse(data)["models"][0]["info"]
        oinfo = nsbmd.parse(original)["models"][0]["info"]
        rows.append({"land": land, "tilesEqual": tiles == spec["tiles"], **geo,
                     "bytes": len(data), "originalBytes": len(original),
                     "polygons": info["numPolygon"], "originalPolygons": oinfo["numPolygon"],
                     "vertices": info["numVertex"], "composeSeconds": round(seconds, 3)})
        rows[-1]["match"] = rows[-1]["match"] and rows[-1]["tilesEqual"]
    return rows


# --- Command line -----------------------------------------------------------

def _source(rom: str):
    from .. import world
    return world.RomSource(Path(rom))


def _tileset_arg(args, source) -> int:
    if args.tileset is not None:
        return args.tileset
    from .. import world
    w = world.load_base(source)
    return w.member("area", w.headers[args.map]["areaDataBank"])["mapTileset"]


def stats(kit: dict) -> dict:
    classes = Counter()
    for c in kit["cells"]:
        classes[c["cls"]] += c["count"]
    return {"tileset": kit["tileset"], "areas": kit["areas"], "chunks": len(kit["chunks"]),
            "tiles": sum(c["count"] for c in kit["cells"]), "distinctCells": len(kit["cells"]),
            "classes": dict(classes.most_common()),
            "distinctCellsByClass": dict(Counter(c["cls"] for c in kit["cells"]).most_common()),
            "materials": len(kit["materials"]), "skipped": kit["skipped"],
            "buildSeconds": kit.get("seconds")}


def main(argv=None) -> int:
    import json
    parser = argparse.ArgumentParser(prog="python3 -B -m tools.maps.style.kit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", default=str(REPO / "rom.nds"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("build", "fidelity"):
        p = sub.add_parser(cmd)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--tileset", type=int)
        g.add_argument("--map", type=int)
        p.add_argument("--no-cache", action="store_true")
        if cmd == "fidelity":
            p.add_argument("--sample", type=int, default=12, help="evenly spaced chunks (0 = all)")
            p.add_argument("--lands", help="comma-separated land ids")
    args = parser.parse_args(argv)
    source = _source(args.rom)
    tileset = _tileset_arg(args, source)
    started = time.time()
    kit = load_or_build_kit(source, tileset, cache=not args.no_cache)
    loaded = time.time() - started
    if args.cmd == "build":
        print(json.dumps({**stats(kit), "loadSeconds": round(loaded, 2)}, indent=1))
        return 0
    lands = sorted(kit["chunks"])
    if args.lands:
        lands = [int(v) for v in args.lands.split(",")]
    elif args.sample and len(lands) > args.sample:
        step = len(lands) / args.sample
        lands = [lands[int(i * step)] for i in range(args.sample)]
    rows = fidelity(kit, source, lands)
    for r in rows:
        print(json.dumps(r))
    ok = sum(r["match"] for r in rows)
    print(f"tileset {tileset}: {ok}/{len(rows)} chunks reproduce (max {max(r.get('bytes', 0) for r in rows)} bytes, "
          f"limit {codecs.MODEL_MAX_BYTES})")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
