"""BDHC (terrain height) query and generation.

Port source: ``src/field/bdhc.c`` and ``src/field_terrain.c`` in
``.codex-reference/pokeheartgold-full``.

Coordinates
-----------
BDHC space is chunk-local, in world units (fx32 in the file, 4096 = 1 unit).
``Terrain_CalcHeight`` subtracts the chunk centre from the object position::

    bdhc_x = objectX - (matrixX * 32 + 16) * 16      (same for z)

and an object standing on tile (tx, tz) has
``objectX = tx * 16 + 8`` (``map_object.c``).  So tile (x, z) of a chunk
spans BDHC ``[-256 + 16x, -256 + 16(x+1)]`` and its centre is
``-256 + 16x + 8``: the same frame as the map model.  Vanilla data agrees:
93% of plate corner coordinates are multiples of 16 units (tile edges), most
of the rest multiples of 8 (half tiles).  Heights are chunk-local; the matrix
altitude is added elsewhere.  North is -z, east is +x.

Height query (``height_at``)
----------------------------
``Bdhc_FindStrip`` binary-searches the strips by z.  Its result equals the
first strip whose scanline is strictly greater than z, clamped to the last
strip (so strip i serves ``scanline[i-1] <= z < scanline[i]``; z below the
first or beyond the last scanline uses the first or last strip).  Then every plate of the strip whose closed
bounding rectangle contains (x, z) yields
``FX_Div(-(c + FX_Mul(nx, x) + FX_Mul(nz, z)), ny)`` (s32 wraparound, FX_Mul
rounds, FX_Div uses the 64/32 hardware divider then rounds).  At most 10
candidates are collected.  Mode 0 (NEAREST, the default for every object)
picks the candidate closest to the object's current height; the player's
jump landing uses mode 1 (HIGHEST).

Vanilla strip layout (verified on all 676 land chunks)
------------------------------------------------------
* Scanlines are the distinct plate z edges, sorted, minus the smallest one.
* Strip i lists, in ascending plate order, every plate with
  ``zmin <= scanline[i]`` and ``zmax > scanline[i-1]`` (for i = 0 the lower
  bound is the smallest z edge).
* Each plate's first point is its (xmin, zmin) corner, the second (xmax, zmax).
"""

from __future__ import annotations

import argparse
import math
import sys
from fractions import Fraction

from tools.maps import codecs

FX_ONE = 4096
TILE = 16
GRID = 32
HALF = 256
MAX_CANDIDATES = 10

NEAREST, HIGHEST, LOWEST = 0, 1, 2


# ---------------------------------------------------------------- fx32 math

def _s32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def _s64(v: int) -> int:
    v &= 0xFFFFFFFFFFFFFFFF
    return v - 0x10000000000000000 if v & 0x8000000000000000 else v


def fx_mul(a: int, b: int) -> int:
    """FX_MulInline: ((s64)a * b + 0x800) >> 12, truncated to s32."""
    return _s32((a * b + 0x800) >> 12)


def fx_div(num: int, den: int) -> int:
    """FX_Div: 64/32 hardware divide of num << 32, then (q + 2^19) >> 20."""
    numer = _s64(num << 32)
    den = _s32(den)
    if den == 0:
        quotient = -1 if numer >= 0 else 1      # DS divider: sign opposite the numerator
    else:
        quotient = abs(numer) // abs(den)       # truncates toward zero
        if (numer < 0) != (den < 0):
            quotient = -quotient
        quotient = _s64(quotient)
    return _s32((quotient + (1 << 19)) >> 20)


def to_fx(value: float) -> int:
    return int(round(value * FX_ONE))


# ---------------------------------------------------------------- query

def find_strip(scanlines: list[int], z: int) -> int | None:
    """Bdhc_FindStrip, statement for statement (== bisect_right clamped to the last strip)."""
    count = len(scanlines) & 0xFFFF
    if count == 0:
        return None
    if count == 1:
        return 0
    count -= 1
    lo = 0
    mid = count // 2
    while True:
        if scanlines[mid] > z:
            count -= 1
            if count > lo:
                count = mid
                mid = (lo + count) // 2
            else:
                return mid
        else:
            lo += 1
            if lo < count:
                lo = mid
                mid = (lo + count) // 2
            else:
                return mid + 1


class Query:
    """A BDHC spec prepared for repeated queries (same results as height_at)."""

    def __init__(self, spec: dict):
        points, normals, constants = spec["points"], spec["normals"], spec["constants"]
        self.plates = []
        for p1, p2, n, c in spec["plates"]:
            a, b = points[p1], points[p2]
            self.plates.append((min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]),
                                normals[n][0], normals[n][1], normals[n][2], constants[c]))
        self.scanlines = [s[0] for s in spec["strips"]]
        self.strips = [[self.plates[i] for i in spec["access"][start:start + count]]
                       for _, count, start in spec["strips"]]

    def candidates_fx(self, x: int, z: int) -> list[int]:
        strip = find_strip(self.scanlines, z)
        if strip is None:
            return []
        out = []
        # An out-of-range strip index reads past the array in the game; treat as empty.
        for x0, x1, z0, z1, nx, ny, nz, c in (self.strips[strip] if strip < len(self.strips) else ()):
            if x0 <= x <= x1 and z0 <= z <= z1:
                out.append(fx_div(_s32(-_s32(c + _s32(fx_mul(nx, x) + fx_mul(nz, z)))), ny))
                if len(out) >= MAX_CANDIDATES:
                    break
        return out

    def height_fx(self, x: int, z: int, current_y: int = 0, mode: int = NEAREST) -> int | None:
        cands = self.candidates_fx(x, z)
        if not cands:
            return None
        best = 0
        if len(cands) > 1:
            if mode == HIGHEST:
                top = _s32(0xFF000000)
                for j, y in enumerate(cands):
                    if top < y:
                        top, best = y, j
            elif mode == LOWEST:
                low = 0x01000000
                for j, y in enumerate(cands):
                    if low > y:
                        low, best = y, j
            else:
                low = _s32(max(current_y, cands[0]) - min(current_y, cands[0]))
                for j in range(1, len(cands)):
                    d = _s32(max(current_y, cands[j]) - min(current_y, cands[j]))
                    if low > d:
                        low, best = d, j
        return cands[best]

    def height(self, x: float, z: float, current_y: float | None = None, mode: int = NEAREST) -> float | None:
        y = self.height_fx(to_fx(x), to_fx(z), to_fx(current_y or 0.0), mode)
        return None if y is None else y / FX_ONE


def height_at(bdhc_spec: dict, x: float, z: float, current_y: float | None = None,
              mode: int = NEAREST) -> float | None:
    """Terrain height at BDHC-local (x, z) in world units, or None (no plate).

    ``current_y`` (default 0) is the object's present height, used by the
    NEAREST mode to choose between overlapping plates (bridges).
    """
    return Query(bdhc_spec).height(x, z, current_y, mode)


def tile_center(tx: int, tz: int) -> tuple[float, float]:
    return -HALF + TILE * tx + TILE / 2, -HALF + TILE * tz + TILE / 2


# ---------------------------------------------------------------- generation

class NonPlanarTile(ValueError):
    pass


PLANAR_TOLERANCE = 2 / FX_ONE   # world units; nw + se must equal ne + sw


def _plane_of(tx: int, tz: int, corners: list) -> tuple[Fraction, Fraction, Fraction]:
    """(sx, sz, h0): height = h0 + sx * x + sz * z in BDHC space, exact in fx units."""
    nw, ne, se, sw = (Fraction(to_fx(v)) for v in corners)
    if abs((nw + se) - (ne + sw)) > PLANAR_TOLERANCE * FX_ONE:
        raise NonPlanarTile(
            f"tile ({tx}, {tz}) is not planar: corners nw={corners[0]} ne={corners[1]} "
            f"se={corners[2]} sw={corners[3]} (nw+se != ne+sw); split it or level it")
    sx = ((ne - nw) + (se - sw)) / 2 / TILE
    sz = ((sw - nw) + (se - ne)) / 2 / TILE
    x0, z0 = -HALF + TILE * tx, -HALF + TILE * tz
    h0 = (nw + ne + se + sw) / 4 - sx * (x0 + TILE / 2) - sz * (z0 + TILE / 2)
    return sx, sz, h0


def _normal_and_constant(sx: Fraction, sz: Fraction, h0: Fraction, x0: int, x1: int,
                         z0: int, z1: int) -> tuple[list[int], int]:
    """fx32 normal/constant for y = h0 + sx*x + sz*z (heights in fx units, x/z in units)."""
    if sx == 0 and sz == 0:
        return [0, FX_ONE, 0], -int(h0)      # exact: FX_Div(-c, 4096) == -c
    # sx/sz are fx height units per world unit; the slope itself is sx / 4096.
    gx, gz = float(sx) / FX_ONE, float(sz) / FX_ONE
    length = math.sqrt(1 + gx * gx + gz * gz)
    normal = [int(round(-gx / length * FX_ONE)), int(round(1 / length * FX_ONE)), int(round(-gz / length * FX_ONE))]
    # Best integer constant: minimise the game's error at the plate's sample points.
    xs = [x0, (x0 + x1) / 2, x1]
    zs = [z0, (z0 + z1) / 2, z1]
    samples = [(to_fx(x), to_fx(z), h0 + sx * x + sz * z) for x in xs for z in zs]
    # Start from the constant that is exact at the plate centre (the quantized
    # normal tilts the plane slightly, so the intercept at x = z = 0 is no guide).
    cx, cz = to_fx((x0 + x1) / 2), to_fx((z0 + z1) / 2)
    want = float(h0 + sx * ((x0 + x1) / 2) + sz * ((z0 + z1) / 2))
    guess = -(fx_mul(normal[0], cx) + fx_mul(normal[2], cz) + normal[1] * want / FX_ONE)
    best = None
    for c in range(int(guess) - 4, int(guess) + 5):
        err = 0.0
        for fx_x, fx_z, want in samples:
            y = fx_div(_s32(-_s32(c + fx_mul(normal[0], fx_x) + fx_mul(normal[2], fx_z))), normal[1])
            err = max(err, abs(y - float(want)))
        if best is None or err < best[0]:
            best = (err, c)
    return normal, best[1]


def bdhc_from_corners(corners: list) -> dict:
    """Codecs-format BDHC from a 32x32 grid (rows = z) of [nw, ne, se, sw] heights or None."""
    if len(corners) != GRID or any(len(row) != GRID for row in corners):
        raise ValueError("corners must be a 32x32 grid")
    keys = [[None] * GRID for _ in range(GRID)]
    for tz in range(GRID):
        for tx in range(GRID):
            cell = corners[tz][tx]
            if cell is not None:
                if len(cell) != 4 or any(v is None for v in cell):
                    raise ValueError(f"tile ({tx}, {tz}) needs four corner heights or None")
                keys[tz][tx] = _plane_of(tx, tz, cell)

    # Greedy rectangles of identical planes, row-major.
    used = [[False] * GRID for _ in range(GRID)]
    rects = []
    for tz in range(GRID):
        for tx in range(GRID):
            key = keys[tz][tx]
            if key is None or used[tz][tx]:
                continue
            w = 1
            while tx + w < GRID and not used[tz][tx + w] and keys[tz][tx + w] == key:
                w += 1
            h = 1
            while tz + h < GRID and all(not used[tz + h][tx + i] and keys[tz + h][tx + i] == key
                                        for i in range(w)):
                h += 1
            for dz in range(h):
                for dx in range(w):
                    used[tz + dz][tx + dx] = True
            rects.append((tx, tz, w, h, key))

    points, normals, constants, plates = [], [], [], []
    index = {"points": {}, "normals": {}, "constants": {}}

    def intern(kind, table, value):
        k = tuple(value) if isinstance(value, list) else value
        if k not in index[kind]:
            index[kind][k] = len(table)
            table.append(value)
        return index[kind][k]

    edges = []
    for tx, tz, w, h, (sx, sz, h0) in sorted(rects, key=lambda r: (r[1], r[0])):
        x0, x1 = -HALF + TILE * tx, -HALF + TILE * (tx + w)
        z0, z1 = -HALF + TILE * tz, -HALF + TILE * (tz + h)
        normal, constant = _normal_and_constant(sx, sz, h0, x0, x1, z0, z1)
        plates.append([intern("points", points, [to_fx(x0), to_fx(z0)]),
                       intern("points", points, [to_fx(x1), to_fx(z1)]),
                       intern("normals", normals, normal),
                       intern("constants", constants, constant)])
        edges.append((to_fx(x0), to_fx(x1), to_fx(z0), to_fx(z1)))

    strips, access = [], []
    zs = sorted({e[2] for e in edges} | {e[3] for e in edges})
    for i, scan in enumerate(zs[1:]):
        lower = zs[i]
        members = [k for k, e in enumerate(edges) if e[2] <= scan and e[3] > lower]
        strips.append([scan, len(members), len(access)])
        access.extend(members)
    spec = {"points": points, "normals": normals, "constants": constants,
            "plates": plates, "strips": strips, "access": access}
    codecs.encode_bdhc(spec)   # validates references, ordering and the buffer limit
    return spec


def bdhc_size(spec: dict) -> int:
    """Bytes of the six arrays (the part limited by codecs.BDHC_MAX_BYTES)."""
    return (8 * len(spec["points"]) + 12 * len(spec["normals"]) + 4 * len(spec["constants"])
            + 8 * len(spec["plates"]) + 8 * len(spec["strips"]) + 2 * len(spec["access"]))


# ---------------------------------------------------------------- vanilla check

INSET = 1.0   # world units from each tile corner
# Sample offsets from the tile's NW corner: four inset corners, centre, four interior points.
SAMPLES = [(INSET, INSET), (TILE - INSET, INSET), (TILE - INSET, TILE - INSET), (INSET, TILE - INSET),
           (8, 8), (4, 4), (12, 4), (12, 12), (4, 12)]
COMPARE = SAMPLES[4:]   # centre and interior points compared against the regenerated BDHC
FIT_TOLERANCE = 1 / 64  # world units; larger residuals mean the tile is not one plane


def _fit_plane(pts: list) -> tuple[float, float, float] | None:
    """Least-squares y = a + b*u + c*v over (u, v, y); flat mean if degenerate."""
    if not pts:
        return None
    n = len(pts)
    su = sum(p[0] for p in pts); sv = sum(p[1] for p in pts); sy = sum(p[2] for p in pts)
    suu = sum(p[0] * p[0] for p in pts); svv = sum(p[1] * p[1] for p in pts)
    suv = sum(p[0] * p[1] for p in pts)
    suy = sum(p[0] * p[2] for p in pts); svy = sum(p[1] * p[2] for p in pts)
    m = [[n, su, sv, sy], [su, suu, suv, suy], [sv, suv, svv, svy]]
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    if abs(det) < 1e-6:
        return sy / n, 0.0, 0.0
    def solve(col):   # Cramer's rule
        mm = [[(m[i][3] if j == col else m[i][j]) for j in range(3)] for i in range(3)]
        return (mm[0][0] * (mm[1][1] * mm[2][2] - mm[1][2] * mm[2][1])
                - mm[0][1] * (mm[1][0] * mm[2][2] - mm[1][2] * mm[2][0])
                + mm[0][2] * (mm[1][0] * mm[2][1] - mm[1][1] * mm[2][0])) / det
    return solve(0), solve(1), solve(2)


def sample_tile(query: Query, tx: int, tz: int, current_y: int = 0) -> list:
    """Heights (fx or None) at SAMPLES for one tile."""
    x0, z0 = -HALF + TILE * tx, -HALF + TILE * tz
    return [query.height_fx(to_fx(x0 + u), to_fx(z0 + v), current_y) for u, v in SAMPLES]


def corners_from_samples(samples: list) -> tuple[list | None, float]:
    """[nw, ne, se, sw] of the plane fitted to the present samples, and the fit residual."""
    pts = [(u, v, y / FX_ONE) for (u, v), y in zip(SAMPLES, samples) if y is not None]
    plane = _fit_plane(pts)
    if plane is None:
        return None, 0.0
    a, b, c = plane
    residual = max(abs(a + b * u + c * v - y) for u, v, y in pts)
    corners = [round((a + b * u + c * v) * FX_ONE) / FX_ONE
               for u, v in ((0, 0), (TILE, 0), (TILE, TILE), (0, TILE))]
    return corners, residual


def sample_corners(query: Query) -> list:
    """32x32 grid of corner heights recovered from a BDHC (None where no sample has a floor)."""
    return [[corners_from_samples(sample_tile(query, tx, tz))[0] for tx in range(GRID)]
            for tz in range(GRID)]


CATEGORIES = ("rounding", "multi_level", "partial_cover", "sub_tile", "other")


def check_chunk(spec: dict) -> dict:
    """Regenerate a vanilla BDHC from sampled corners and compare heights.

    Mismatching sample points are put in the first matching category:
    multi_level (vanilla has several distinct heights there: bridges),
    partial_cover (some of the tile's samples have no vanilla plate),
    sub_tile (vanilla heights in the tile are not one plane: half-tile steps,
    ledges, warped tiles), rounding (both within 1/16 unit), other.
    """
    q = Query(spec)
    grid, info = [], []
    for tz in range(GRID):
        row = []
        for tx in range(GRID):
            samples = sample_tile(q, tx, tz)
            corners, residual = corners_from_samples(samples)
            row.append(corners)
            present = sum(y is not None for y in samples)
            info.append((0 < present < len(samples), residual > FIT_TOLERANCE))
        grid.append(row)
    gen = bdhc_from_corners(grid)
    g = Query(gen)
    stats = {"points": 0, "exact": 0, "tiles": 0, "tiles_exact": 0, "max_rounding": 0.0,
             "sub_tile_tiles": sum(i[1] for i in info), "partial_tiles": sum(i[0] for i in info),
             "size_vanilla": bdhc_size(spec), "size_generated": bdhc_size(gen),
             "plates_vanilla": len(spec["plates"]), "plates_generated": len(gen["plates"])}
    stats.update({k: 0 for k in CATEGORIES})
    for tz in range(GRID):
        for tx in range(GRID):
            partial, sub_tile = info[tz * GRID + tx]
            x0, z0 = -HALF + TILE * tx, -HALF + TILE * tz
            tile_ok = True
            for u, v in COMPARE:
                x, z = to_fx(x0 + u), to_fx(z0 + v)
                want, got = q.height_fx(x, z), g.height_fx(x, z)
                stats["points"] += 1
                if want == got:
                    stats["exact"] += 1
                    continue
                tile_ok = False
                close = want is not None and got is not None and abs(want - got) <= FX_ONE // 16
                if len(set(q.candidates_fx(x, z))) > 1:
                    stats["multi_level"] += 1
                elif partial:
                    stats["partial_cover"] += 1
                elif sub_tile:
                    stats["sub_tile"] += 1
                elif close:
                    stats["rounding"] += 1
                    stats["max_rounding"] = max(stats["max_rounding"], abs(want - got) / FX_ONE)
                else:
                    stats["other"] += 1
            stats["tiles"] += 1
            stats["tiles_exact"] += tile_ok
    return stats


def _check_one(args):
    index, data = args
    spec, _ = codecs.decode_land(data)
    return index, check_chunk(spec["bdhc"])


def run_check(rom: str = "rom.nds", jobs: int | None = None, limit: int | None = None,
              verbose: bool = False) -> dict:
    from multiprocessing import Pool
    from pathlib import Path

    from tools.maps import narc
    from tools.maps.world import RomSource

    members = narc.members(RomSource(Path(rom)).read("a/0/6/5"))
    work = list(enumerate(members))[:limit]
    with Pool(jobs) as pool:
        results = dict(pool.map(_check_one, work, chunksize=4))
    keys = ("points", "exact", "tiles", "tiles_exact", "sub_tile_tiles", "partial_tiles",
            "size_vanilla", "size_generated", "plates_vanilla", "plates_generated") + CATEGORIES
    total = {k: sum(r[k] for r in results.values()) for k in keys}
    total["max_rounding"] = max(r["max_rounding"] for r in results.values())
    total["chunks"] = len(results)
    total["chunks_all_exact"] = sum(r["exact"] == r["points"] for r in results.values())
    total["max_size_generated"] = max(r["size_generated"] for r in results.values())
    total["max_size_vanilla"] = max(r["size_vanilla"] for r in results.values())
    total["per_chunk"] = results
    pts = total["points"]
    print(f"chunks {total['chunks']}: every compared point exact in {total['chunks_all_exact']}")
    print(f"points {pts} (centre + 4 interior per tile): exact {total['exact']} ({total['exact'] / pts:.4%})")
    print("mismatches: " + ", ".join(f"{k} {total[k]} ({total[k] / pts:.4%})" for k in CATEGORIES)
          + f"; max rounding error {total['max_rounding']:.6f} units")
    print(f"tiles {total['tiles']}: all points exact {total['tiles_exact']} "
          f"({total['tiles_exact'] / total['tiles']:.4%}); vanilla sub-tile tiles {total['sub_tile_tiles']}, "
          f"partially covered tiles {total['partial_tiles']}")
    print(f"plates vanilla {total['plates_vanilla']} -> generated {total['plates_generated']}; "
          f"array bytes vanilla {total['size_vanilla']} -> generated {total['size_generated']} "
          f"(max per chunk {total['max_size_vanilla']} -> {total['max_size_generated']}, "
          f"limit {codecs.BDHC_MAX_BYTES})")
    if verbose:
        for i, r in sorted(results.items()):
            if r["exact"] != r["points"]:
                print(f"  land {i}: exact {r['exact']}/{r['points']} "
                      + " ".join(f"{k} {r[k]}" for k in CATEGORIES)
                      + f" bytes {r['size_vanilla']}->{r['size_generated']}")
    return total


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -B -m tools.maps.style.bdhc_gen")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="regenerate every vanilla BDHC and compare heights")
    check.add_argument("--rom", default="rom.nds")
    check.add_argument("--jobs", type=int)
    check.add_argument("--limit", type=int)
    check.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        run_check(args.rom, args.jobs, args.limit, args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
