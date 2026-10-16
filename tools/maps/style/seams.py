"""Geometry-aware joins: what makes two kit cells look right side by side.

A kit cell is the slice of a vanilla chunk model over one 16x16 tile. Two
things decide whether cells placed next to each other look like vanilla:

1. Edge profiles. Where a seam is new (not copied from vanilla), every
   polygon edge lying on the shared tile edge must continue on the other
   side: same material, height and texture coordinates (modulo the texture's
   repeat period). A side's profile samples its boundary at 8 points plus
   the vertical edges standing on it (cliff faces, walls). Two sides are
   compatible when their profiles are equal and not empty, or when vanilla
   shows that exact profile pair next to each other (a cliff top meeting
   lower ground, a path border meeting grass). There is no transitive
   closure: an A|B and a B|C join in vanilla do not allow A|C.

2. Overhangs and bonds. Trees, cliffs, ledges and sloped ground are not
   clipped per tile; a polygon belongs to the tile under its centroid and
   reaches into, or stands on the edge of, its neighbours. A cell with such a
   polygon at offset o only fits where the cell at o is one vanilla had there
   ("rigid" offsets). The receiving side is bonded too: if vanilla always put
   a neighbour polygon on a cell's side (a rock top whose side faces belong to
   the next tile), that side keeps a neighbour vanilla had there. Otherwise
   pieces are cut off, float, or leave black gaps between heights.

Coverage: ground polygons (mostly-horizontal) cover the tile centres
under them. A cell whose own polygons do not cover its centre, but which was
covered in every vanilla occurrence, needs that cover from a neighbour; a
placement without it is a hole (black in game).

Bare edges: standable floor must not border a tile that no polygon touches
(black void beside the path). Vanilla never does this inside a chunk; a
chunk that does (its walls are separate props, not land geometry) is not
learned from at all.

Height breaks: two standable tiles side by side must meet at the same floor
height along their shared edge (BDHC corners), unless one is a ledge. A
break shows as a black gap between levels and makes the player pop up or
down. Vanilla's few exact cell pairs that do this (bridges, stairs) are
allowed.

All of these are computed from the kit only, so the same checks run on vanilla
chunks (where they hold by construction) and on generated grids.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from .layout import GRID

TILE = 16.0
EPS = 1e-3
SAMPLES = [TILE * (i + 0.5) / 8 for i in range(8)]
SIDES = ("east", "west", "south", "north")
# side -> (axis fixed, value, axis along)
SIDE_LINE = {"east": (0, TILE, 2), "west": (0, 0.0, 2), "south": (2, TILE, 0), "north": (2, 0.0, 0)}


def _mod(value, period):
    return value % period if period else value


def _q(value, scale=16):
    return None if value is None else round(value * scale)


def _normal_y(vs) -> float:
    nx = ny = nz = 0.0
    for i in range(len(vs)):
        a, b = vs[i], vs[(i + 1) % len(vs)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return abs(ny) / length if length else 0.0


def _inside_xz(vs, x, z) -> bool:
    sign = 0
    for i in range(len(vs)):
        a, b = vs[i], vs[(i + 1) % len(vs)]
        cross = (b[0] - a[0]) * (z - a[2]) - (b[2] - a[2]) * (x - a[0])
        if abs(cross) < EPS:
            continue
        s = 1 if cross > 0 else -1
        if sign and s != sign:
            return False
        sign = s
    return True


def profile(cell: dict, side: str, periods: dict) -> tuple:
    """Hashable description of everything drawn on one side of a cell."""
    fixed, value, along = SIDE_LINE[side]
    samples, uprights = [], []
    for poly in cell["polys"]:
        vs, period = poly["verts"], periods.get(poly["mat"])
        ps, pt = period or (0, 0)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            if abs(a[fixed] - value) > EPS or abs(b[fixed] - value) > EPS:
                continue
            if abs(a[along] - b[along]) < EPS:  # vertical edge standing on the line
                lo, hi = sorted((a[1], b[1]))
                uprights.append((poly["mat"], _q(a[along]), _q(lo), _q(hi)))
                continue
            lo, hi = (a, b) if a[along] < b[along] else (b, a)
            for s in SAMPLES:
                if lo[along] - EPS <= s <= hi[along] + EPS:
                    t = (s - lo[along]) / (hi[along] - lo[along])
                    y = lo[1] + (hi[1] - lo[1]) * t
                    if lo[3] is None:
                        u = v = None
                    else:
                        u = _mod(lo[3] + (hi[3] - lo[3]) * t, ps)
                        v = _mod(lo[4] + (hi[4] - lo[4]) * t, pt)
                    samples.append((_q(s), poly["mat"], _q(y), _q(u, 2), _q(v, 2)))
    return tuple(sorted(samples, key=repr)), tuple(sorted(uprights, key=repr))


def footprint(cell: dict) -> set[tuple[int, int]]:
    """Tile offsets (dx, dz) != (0, 0) that the cell's polygons reach into."""
    out = set()
    for poly in cell["polys"]:
        xs = [v[0] for v in poly["verts"]]
        zs = [v[2] for v in poly["verts"]]
        for dx in range(math.floor((min(xs) + EPS) / TILE), math.floor((max(xs) - EPS) / TILE) + 1):
            for dz in range(math.floor((min(zs) + EPS) / TILE), math.floor((max(zs) - EPS) / TILE) + 1):
                if (dx, dz) != (0, 0):
                    out.add((dx, dz))
    return out


def _axis_tiles(lo: float, hi: float) -> list[int]:
    if hi - lo > EPS:
        return list(range(math.floor((lo + EPS) / TILE), math.floor((hi - EPS) / TILE) + 1))
    k = lo / TILE  # a vertical face standing on this coordinate
    return [round(k) - 1, round(k)] if abs(k - round(k)) < EPS / TILE else [math.floor(k)]


def occupies(cell: dict) -> set[tuple[int, int]]:
    """Tile offsets (including (0, 0)) that any of the cell's polygons touches."""
    out = set()
    for poly in cell["polys"]:
        xs = [v[0] for v in poly["verts"]]
        zs = [v[2] for v in poly["verts"]]
        for dx in _axis_tiles(min(xs), max(xs)):
            for dz in _axis_tiles(min(zs), max(zs)):
                out.add((dx, dz))
    return out


STANDABLE = set(".,v^<>")


def covers(cell: dict) -> set[tuple[int, int]]:
    """Tile offsets whose centres lie under one of the cell's ground polygons."""
    out = set()
    for poly in cell["polys"]:
        vs = poly["verts"]
        if _normal_y(vs) < 0.5:
            continue
        xs = [v[0] for v in vs]
        zs = [v[2] for v in vs]
        for dx in range(math.floor(min(xs) / TILE), math.floor(max(xs) / TILE) + 1):
            for dz in range(math.floor(min(zs) / TILE), math.floor(max(zs) / TILE) + 1):
                if _inside_xz(vs, TILE * dx + TILE / 2, TILE * dz + TILE / 2):
                    out.add((dx, dz))
    return out


class Seams:
    """Join rules learned from one kit (see module docstring)."""

    def __init__(self, kit: dict, exclude: set | None = None):
        cells = kit["cells"]
        n = len(cells)
        periods = kit.get("periods", {})
        ids: dict[tuple, int] = {}

        def intern(p):
            return ids.setdefault(p, len(ids))

        self.prof = {side: np.zeros(n, dtype=np.int64) for side in SIDES}
        for index, cell in enumerate(cells):
            for side in SIDES:
                self.prof[side][index] = intern(profile(cell, side, periods) if "polys" in cell
                                                else ("cell", index, side))
        empty = intern(((), ()))
        self.profiles = len(ids)
        self.empty = empty
        foot = [footprint(c) if "polys" in c else set() for c in cells]
        self.occupies = [occupies(c) if "polys" in c else {(0, 0)} for c in cells]
        from .layout import cell_char
        self.standable = np.array([cell_char(c) in STANDABLE for c in cells])
        # Chunks whose own geometry leaves floor beside empty tiles draw their walls as
        # props; learning joins or windows from them teaches "floor beside nothing".
        corners = [c.get("corners") for c in cells]
        ledge = np.array([cell_char(c) in "v^<>" for c in cells])
        floor = self.standable & ~ledge & np.array([cc is not None for cc in corners])
        edge = {side: np.zeros((n, 2)) for side in ("east", "west", "south", "north")}
        for i, cc in enumerate(corners):
            if cc is not None:  # corners: nw, ne, se, sw
                edge["east"][i], edge["west"][i] = (cc[1], cc[2]), (cc[0], cc[3])
                edge["south"][i], edge["north"][i] = (cc[3], cc[2]), (cc[0], cc[1])
        self.floor, self.edge_heights = floor, edge
        self.break_exempt: set = set()
        for land, grid in kit["chunks"].items():
            for a, b, axis in self._break_pairs(np.array(grid)):
                self.break_exempt.add((a, b, axis))
        self.self_excluded = sorted(land for land, grid in kit["chunks"].items()
                                    if not (exclude and land in exclude)
                                    and self.bare_edges(np.array(grid), margin=2))
        exclude = set(exclude or ()) | set(self.self_excluded)
        self.covers = [covers(c) if "polys" in c else {(0, 0)} for c in cells]
        allowed: dict[int, dict] = defaultdict(lambda: defaultdict(set))
        covered_always = [True] * n
        feeders: dict[int, dict] = defaultdict(lambda: defaultdict(set))  # cell -> offset -> cells
        occupied_always = [True] * n
        # Side bonds: a neighbour's polygon touching this tile (a cliff face standing on the
        # shared edge, a rock skirt). bonded_always[c][d] stays True only if every vanilla
        # occurrence of c had such a polygon from its neighbour at d.
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
        bonded_always: dict[int, dict] = defaultdict(lambda: {d: True for d in dirs})
        side_seen: dict[int, dict] = defaultdict(lambda: defaultdict(set))
        occupiers: dict[int, dict] = defaultdict(lambda: defaultdict(set))
        h_pairs, v_pairs = set(), set()
        for land, grid in kit["chunks"].items():
            if exclude and land in exclude:
                continue
            cov = self.coverage(np.array(grid))
            occ = self.occupancy(np.array(grid))
            for z in range(GRID):
                for x in range(GRID):
                    c = grid[z][x]
                    if x + 1 < GRID:
                        h_pairs.add((int(self.prof["east"][c]), int(self.prof["west"][grid[z][x + 1]])))
                    if z + 1 < GRID:
                        v_pairs.add((int(self.prof["south"][c]), int(self.prof["north"][grid[z + 1][x]])))
                    for dx, dz in foot[c] | (self.occupies[c] - {(0, 0)}):
                        if 0 <= x + dx < GRID and 0 <= z + dz < GRID:
                            allowed[c][(dx, dz)].add(grid[z + dz][x + dx])
                    for d in dirs:
                        nx, nz = x + d[0], z + d[1]
                        if 0 <= nx < GRID and 0 <= nz < GRID:
                            other = grid[nz][nx]
                            side_seen[c][d].add(other)
                            if (-d[0], -d[1]) not in self.occupies[other]:
                                bonded_always[c][d] = False
                    if not occ[z, x]:
                        occupied_always[c] = False
                    elif (0, 0) not in self.occupies[c]:
                        for dz in range(-4, 5):
                            for dx in range(-4, 5):
                                if 0 <= x + dx < GRID and 0 <= z + dz < GRID:
                                    other = grid[z + dz][x + dx]
                                    if (-dx, -dz) in self.occupies[other]:
                                        occupiers[c][(dx, dz)].add(other)
                    if not cov[z, x]:
                        covered_always[c] = False
                    elif (0, 0) not in self.covers[c]:
                        for dz in range(-4, 5):
                            for dx in range(-4, 5):
                                if 0 <= x + dx < GRID and 0 <= z + dz < GRID:
                                    other = grid[z + dz][x + dx]
                                    if (-dx, -dz) in self.covers[other]:
                                        feeders[c][(dx, dz)].add(other)
        self.needs_cover = np.array([(0, 0) not in self.covers[c] and covered_always[c] for c in range(n)])
        # A cell that always borrowed its ground from a neighbour keeps the neighbour that fed
        # it most often (as a rigid offset), so the solver never strips the ground away.
        # Likewise a cell with no geometry of its own that a neighbour's wall always filled
        # keeps that neighbour, or the floor beside it would face black void.
        chosen = {}
        self.needs_occupant = np.array([(0, 0) not in self.occupies[c] and occupied_always[c] for c in range(n)])
        for wanted, sources in ((self.needs_cover, feeders), (self.needs_occupant, occupiers)):
            for c in np.nonzero(wanted)[0]:
                if sources[c] and int(c) not in chosen:
                    offset = max(sources[c], key=lambda o: (len(allowed[c].get(o, ())), len(sources[c][o]), o))
                    if offset not in allowed[c]:
                        chosen[int(c)] = offset
        for c, sides in bonded_always.items():
            for d, always in sides.items():
                if always and side_seen[c][d] and d not in allowed[c]:
                    allowed[c][d] = set(side_seen[c][d])
        # Allow every cell vanilla had at that offset, so vanilla itself never breaks the rule.
        for land, grid in kit["chunks"].items():
            if exclude and land in exclude:
                continue
            for z in range(GRID):
                for x in range(GRID):
                    offset = chosen.get(grid[z][x])
                    if offset and 0 <= x + offset[0] < GRID and 0 <= z + offset[1] < GRID:
                        allowed[grid[z][x]][offset].add(grid[z + offset[1]][x + offset[0]])
        self.rigid = [[(dx, dz, frozenset(cs)) for (dx, dz), cs in sorted(allowed[c].items())] for c in range(n)]
        self.reach = max((max(abs(dx), abs(dz)) for r in self.rigid for dx, dz, _ in r), default=0)
        self.np = len(ids)
        self.pairs = (len(h_pairs), len(v_pairs))
        # Dense lookup tables for the solver: H[east, west], V[south, north].
        self.H = np.zeros((self.np, self.np), dtype=bool)
        self.V = np.zeros((self.np, self.np), dtype=bool)
        for a, b in h_pairs:
            self.H[a, b] = True
        for a, b in v_pairs:
            self.V[a, b] = True
        diagonal = np.arange(self.np)
        self.H[diagonal, diagonal] = True
        self.V[diagonal, diagonal] = True
        self.H[empty, empty] = (empty, empty) in h_pairs
        self.V[empty, empty] = (empty, empty) in v_pairs

    # --- pair compatibility --------------------------------------------------

    def h_ok(self, east, west) -> np.ndarray:
        """Vectorized: profile ids of a left cell's east side and a right cell's west side."""
        return self.H[np.asarray(east), np.asarray(west)]

    def v_ok(self, south, north) -> np.ndarray:
        return self.V[np.asarray(south), np.asarray(north)]

    def pair_h(self, a: int, b: int) -> bool:
        return bool(self.H[self.prof["east"][a], self.prof["west"][b]])

    def pair_v(self, a: int, b: int) -> bool:
        return bool(self.V[self.prof["south"][a], self.prof["north"][b]])

    # --- grid checks -------------------------------------------------------

    def coverage(self, grid: np.ndarray) -> np.ndarray:
        height, width = grid.shape
        out = np.zeros((height, width), dtype=bool)
        for z in range(height):
            for x in range(width):
                c = grid[z, x]
                if c < 0:
                    continue
                for dx, dz in self.covers[c]:
                    if 0 <= x + dx < width and 0 <= z + dz < height:
                        out[z + dz, x + dx] = True
        return out

    def occupancy(self, grid: np.ndarray) -> np.ndarray:
        height, width = grid.shape
        out = np.zeros((height, width), dtype=bool)
        for z in range(height):
            for x in range(width):
                c = grid[z, x]
                if c < 0:
                    continue
                for dx, dz in self.occupies[c]:
                    if 0 <= x + dx < width and 0 <= z + dz < height:
                        out[z + dz, x + dx] = True
        return out

    def bare_edges(self, grid: np.ndarray, margin: int = 0) -> list[tuple[int, int]]:
        """Standable tiles beside a tile no polygon touches (visible void).

        margin skips tiles near the grid edge, whose cover may come from a
        neighbouring chunk (used when judging vanilla chunks on their own).
        """
        occ = self.occupancy(grid)
        stand = self.standable[np.maximum(grid, 0)] & (grid >= 0)
        height, width = grid.shape
        out = []
        for z in range(margin, height - margin):
            for x in range(margin, width - margin):
                if not stand[z, x]:
                    continue
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, nz = x + dx, z + dz
                    if margin <= nx < width - margin and margin <= nz < height - margin and not occ[nz, nx]:
                        out.append((x, z))
                        break
        return out

    def _break_pairs(self, grid: np.ndarray, tolerance: float = 1.0) -> list[tuple[int, int, str]]:
        out = []
        for axis, a, b, far, near in (("h", grid[:, :-1], grid[:, 1:], "east", "west"),
                                      ("v", grid[:-1, :], grid[1:, :], "south", "north")):
            ok = (a >= 0) & (b >= 0)
            aa, bb = np.maximum(a, 0), np.maximum(b, 0)
            diff = np.abs(self.edge_heights[far][aa] - self.edge_heights[near][bb]).max(axis=-1)
            bad = ok & self.floor[aa] & self.floor[bb] & (diff > tolerance)
            out += [(int(aa[i]), int(bb[i]), axis) for i in zip(*np.nonzero(bad))]
        return out

    def height_breaks(self, grid: np.ndarray) -> list[tuple[int, int]]:
        """Tiles whose east/south standable neighbour meets them at another floor height."""
        out = []
        for axis, a, b, far, near in (("h", grid[:, :-1], grid[:, 1:], "east", "west"),
                                      ("v", grid[:-1, :], grid[1:, :], "south", "north")):
            ok = (a >= 0) & (b >= 0)
            aa, bb = np.maximum(a, 0), np.maximum(b, 0)
            diff = np.abs(self.edge_heights[far][aa] - self.edge_heights[near][bb]).max(axis=-1)
            for z, x in zip(*np.nonzero(ok & self.floor[aa] & self.floor[bb] & (diff > 1.0))):
                if (int(aa[z, x]), int(bb[z, x]), axis) not in self.break_exempt:
                    out.append((int(x), int(z)))
        return out

    def holes(self, grid: np.ndarray) -> list[tuple[int, int]]:
        cov = self.coverage(grid)
        need = self.needs_cover[np.maximum(grid, 0)] & (grid >= 0)
        zs, xs = np.nonzero(need & ~cov)
        return list(zip(xs.tolist(), zs.tolist()))

    def rigid_violations(self, grid: np.ndarray) -> list[tuple[int, int, int, int]]:
        """(x, z, dx, dz): the cell at (x, z) overhangs into a neighbour vanilla never had there."""
        height, width = grid.shape
        out = []
        for z in range(height):
            for x in range(width):
                c = grid[z, x]
                if c < 0:
                    continue
                for dx, dz, ok in self.rigid[c]:
                    nx, nz = x + dx, z + dz
                    if 0 <= nx < width and 0 <= nz < height and grid[nz, nx] >= 0 and grid[nz, nx] not in ok:
                        out.append((x, z, dx, dz))
        return out

    def profile_seams(self, grid: np.ndarray) -> tuple[int, int]:
        """(incompatible joins, total joins) over every horizontal and vertical neighbour pair."""
        g = np.asarray(grid)
        h = self.h_ok(self.prof["east"][g[:, :-1]], self.prof["west"][g[:, 1:]])
        v = self.v_ok(self.prof["south"][g[:-1, :]], self.prof["north"][g[1:, :]])
        return int((~h).sum() + (~v).sum()), int(h.size + v.size)

    def seam_map(self, grid: np.ndarray) -> np.ndarray:
        """Per tile: number of incompatible joins on its east/south sides (for reports)."""
        g = np.asarray(grid)
        out = np.zeros(g.shape, dtype=np.int64)
        out[:, :-1] += ~self.h_ok(self.prof["east"][g[:, :-1]], self.prof["west"][g[:, 1:]])
        out[:-1, :] += ~self.v_ok(self.prof["south"][g[:-1, :]], self.prof["north"][g[1:, :]])
        return out


_CACHE: dict = {}


def for_kit(kit: dict, exclude: frozenset = frozenset()) -> Seams:
    key = (id(kit), exclude)
    if key not in _CACHE:
        _CACHE[key] = Seams(kit, set(exclude))
    return _CACHE[key]
