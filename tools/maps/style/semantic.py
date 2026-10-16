"""Semantic map: what each tile of a chunk *is*, in a designer's words.

The old layout (layout.py) only knew the game's walk classes, so `.` covered
grass, paths and flowers alike and `T` covered tree belts, cave walls and the
black outside of a cave. A solver given only that fills the gaps with anything
of the right walk class, which is why rebuilt vanilla chunks came out as
random paths, flat rock slabs and tree shadows without trees.

A semantic map has three layers per tile:

* `kind`: what the tile looks like from above, from the top-most ground
  polygon's material name (vanilla names are descriptive: road01, egrass,
  tree01, dwall_ne). Edge and corner variants (road01_r, egrass_u, dwall_sw)
  belong to the same kind; the builder picks the variant from the neighbours,
  the way a 2D game picks autotiles.
* `level`: floor height in steps of HEIGHT_STEP world units (half a tile).
* `walk`: the game's walk class (layout.py classes: . , ~ T v ^ < >).
* `shore`: `b` where a land tile carries a water bank (pond, river or sea
  polygons of its own under a grass or tree top), else `.`. Designers never
  write it; design.refine copies it from vanilla with the rest.

`extract(kit, grid)` reads all three from a solved or vanilla grid, so the
same description drives the rebuild benchmark (rebuild.py) and new maps.
"""

from __future__ import annotations

import math
import re

import numpy as np

from .layout import GRID, cell_char

TILE = 16.0
HEIGHT_STEP = 8.0  # half a tile: water surfaces sit 8 units apart, and must not be confused

# (kind, char, texture-name pattern). First match wins; checked against the
# texture name, then the material name. Order matters: specific before generic.
KINDS = [
    ("roundtree", "Y", r"^treekn"),  # a second tree model; belts do not mix the two
    ("tree", "T", r"^(tree|hu_tree|ki_obj|tree_w)"),
    ("tallgrass", ",", r"^egrass"),
    ("flowers", "*", r"^flower"),
    ("path", "=", r"^(road|droad|beach|cr_suna|sand)"),
    # Water comes in looks that do not mix: a pond has banks and an underside, a river is
    # one flowing sheet, the sea has its own shore line.
    ("pond", "~", r"^(pond|dpond)"),
    ("river", "%", r"^(river|driver)"),
    ("sea", "s", r"^(sea_|dsea|swave)"),
    ("cavewall", "W", r"^dwall"),
    ("cliff", "#", r"^(cliff|dcliff|wall0|wallkn|slope|dslope|cliffkn|allpeak|dallpeak)"),
    ("rock", "o", r"^(rock|d_rock|sea_rock)"),
    ("bridge", "b", r"^(bridge|cr_bridge)"),
    ("fence", "f", r"^fence"),
    ("hole", "O", r"^(cavehole|chole|d_stairhole|icehole|r_climb|dr_climb|d_level)"),
    ("roof", "R", r"^d_ro$"),
    ("lightgrass", "g", r"^(grass01_a|grass02)"),
    ("grass", ".", r"^grass"),
]
VOID, OTHER = ("void", " "), ("other", "?")
VOID_LEVEL = -99  # nothing drawn: no floor height to match
CHAR = {kind: ch for kind, ch, _ in KINDS} | {VOID[0]: VOID[1], OTHER[0]: OTHER[1]}
KIND_OF_CHAR = {ch: kind for kind, ch in CHAR.items()}
_PATTERNS = [(kind, re.compile(p)) for kind, _, p in KINDS]
# Ground kinds a tile shows *through*: a tree's shadow disc lies on grass, but the
# tile is a tree tile. When a tile carries one of these anywhere in its own cell,
# that kind wins over the ground under it.
OVERRIDING = ("tree", "roundtree", "tallgrass", "flowers")
# A tile with no ground polygon (a cave wall face, a cliff's side) is named after
# its own geometry, most structural kind first.
STANDING = ("cavewall", "cliff", "rock", "tree", "roundtree", "fence", "bridge", "hole", "roof", "pond", "river", "sea")
WATER_KINDS = ("~", "%", "s")
WATER_NAMES = ("pond", "river", "sea")


def kind_of(name: str | None) -> str:
    if not name:
        return OTHER[0]
    for kind, pattern in _PATTERNS:
        if pattern.search(name):
            return kind
    return OTHER[0]


def material_kind(material: dict) -> str:
    kind = kind_of(material.get("texture"))
    return kind if kind != OTHER[0] else kind_of(material.get("name"))


def _normal_y(vs) -> float:
    nx = ny = nz = 0.0
    for i in range(len(vs)):
        a, b = vs[i], vs[(i + 1) % len(vs)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return abs(ny) / length if length else 0.0


def _y_at(vs, x: float, z: float) -> float | None:
    """Height of polygon vs at (x, z) if (x, z) lies inside its xz projection."""
    inside = False
    n = len(vs)
    for i in range(n):
        a, b = vs[i], vs[(i + 1) % n]
        if (a[2] > z) != (b[2] > z):
            t = (z - a[2]) / (b[2] - a[2])
            if x < a[0] + t * (b[0] - a[0]):
                inside = not inside
    if not inside:
        return None
    # Plane through the first three non-collinear vertices.
    p0 = vs[0]
    for i in range(1, n - 1):
        p1, p2 = vs[i], vs[i + 1]
        ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        wx, wy, wz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
        cx, cy, cz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        if abs(cy) > 1e-6:
            return p0[1] - (cx * (x - p0[0]) + cz * (z - p0[2])) / cy
    return max(v[1] for v in vs)


class CellFacts:
    """Per kit cell: own kinds and ground polygons (cached per kit)."""

    def __init__(self, kit: dict):
        mats = kit["materials"]
        self.kinds, self.ground = [], []
        for cell in kit["cells"]:
            kinds, ground = set(), []
            for poly in cell.get("polys", ()):
                kind = material_kind(mats[poly["mat"]])
                kinds.add(kind)
                # Tree billboards lean back (normal y ~0.6-0.8): they are what stands on a tile,
                # not its ground. A walkable tile behind a tree is still ground.
                if _normal_y(poly["verts"]) >= (0.95 if kind in ("tree", "roundtree") else 0.7):
                    vs = poly["verts"]
                    xs, zs = [v[0] for v in vs], [v[2] for v in vs]
                    ground.append((kind, vs, min(xs), max(xs), min(zs), max(zs)))
            self.kinds.append(kinds)
            self.ground.append(ground)
        self.walk = [cell_char(c) for c in kit["cells"]]
        self.reach = max((max(abs(math.floor(g[2] / TILE)), abs(math.floor(g[3] / TILE)),
                              abs(math.floor(g[4] / TILE)), abs(math.floor(g[5] / TILE)))
                          for gs in self.ground for g in gs), default=0)


_FACTS: dict[int, CellFacts] = {}


def facts(kit: dict) -> CellFacts:
    if id(kit) not in _FACTS:
        _FACTS[id(kit)] = CellFacts(kit)
    return _FACTS[id(kit)]


class SemanticMap:
    """Three equally sized layers (lists of strings / int arrays)."""

    def __init__(self, kind: list[str], level: np.ndarray, walk: list[str], shore: list[str] | None = None):
        self.kind, self.level, self.walk = kind, np.asarray(level, dtype=np.int64), walk
        self.shore = shore or ["." * len(row) for row in kind]
        assert len(kind) == len(walk) == len(self.shore) == self.level.shape[0]

    @property
    def shape(self) -> tuple[int, int]:
        return self.level.shape

    def label(self, x: int, z: int) -> tuple[str, int, str, str]:
        return self.kind[z][x], int(self.level[z, x]), self.walk[z][x], self.shore[z][x]

    def to_text(self) -> str:
        real = self.level[self.level != VOID_LEVEL]
        base = int(real.min()) if real.size else 0
        return "\n".join(["# semantic map v1: [kind] see semantic.KINDS, [level] floor height steps "
                          f"above {base * HEIGHT_STEP:g}, [walk] layout.py classes",
                          f"base {base}", "[kind]", *self.kind, "[level]",
                          *("".join("-" if v == VOID_LEVEL else _level_char(int(v) - base) for v in row)
                            for row in self.level),
                          "[walk]", *self.walk, "[shore]", *self.shore]) + "\n"

    @classmethod
    def from_text(cls, text: str) -> "SemanticMap":
        sections, current, base = {}, None, 0
        for raw in text.splitlines():
            line = raw.rstrip("\n")
            if line.startswith("#") or not line.strip():
                continue
            if line.startswith("base "):
                base = int(line.split()[1])
            elif line.startswith("[") and line.endswith("]"):
                current = sections.setdefault(line[1:-1], [])
            elif current is not None:
                current.append(line)
        kind, walk = sections["kind"], sections["walk"]
        level = np.array([[VOID_LEVEL if c == "-" else _level_value(c) + base for c in row]
                          for row in sections["level"]])
        if not (len(kind) == len(walk) == len(level)) or len({len(r) for r in kind + walk}) != 1:
            raise ValueError("semantic map layers must have equal sizes")
        return cls(kind, level, walk, sections.get("shore"))


def _level_char(v: int) -> str:
    return "0123456789abcdefghijklmnopqrstuvwxyz"[v] if 0 <= v < 36 else "?"


def _level_value(c: str) -> int:
    return "0123456789abcdefghijklmnopqrstuvwxyz".index(c)


def _fill_blocked_void(kinds: list[str], walks: list[str], rounds: int = 3) -> None:
    """A blocked tile with nothing drawn over its centre (inside a cave wall mass, under a
    tree canopy) is part of the structure around it: which wall tile a face polygon's
    centroid lands on is not something a designer can or should say. Such tiles take the
    most common kind among their blocked, drawn neighbours."""
    height, width = len(kinds), len(kinds[0])
    rows = [list(r) for r in kinds]
    for _ in range(rounds):
        changed = False
        new = [r[:] for r in rows]
        for z in range(height):
            for x in range(width):
                if rows[z][x] != VOID[1] or walks[z][x] != "T":
                    continue
                votes = {}
                for dz in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, nz = x + dx, z + dz
                        if (dx or dz) and 0 <= nx < width and 0 <= nz < height \
                                and rows[nz][nx] != VOID[1] and walks[nz][nx] == "T":
                            votes[rows[nz][nx]] = votes.get(rows[nz][nx], 0) + 1
                if votes:
                    new[z][x] = max(sorted(votes), key=votes.get)
                    changed = True
        rows = new
        if not changed:
            break
    kinds[:] = ["".join(r) for r in rows]


def extract(kit: dict, grid, level_of_void: int | None = None) -> SemanticMap:
    """Semantic map of a grid of kit cell ids (any size; -1 = no cell)."""
    f = facts(kit)
    g = np.asarray(grid)
    height, width = g.shape
    top_kind = [[VOID[0]] * width for _ in range(height)]
    top_y = np.full((height, width), -1e9)
    for z in range(height):
        for x in range(width):
            c = g[z, x]
            if c < 0:
                continue
            for kind, vs, x0, x1, z0, z1 in f.ground[c]:
                for dz in range(math.floor(z0 / TILE), math.floor(z1 / TILE) + 1):
                    for dx in range(math.floor(x0 / TILE), math.floor(x1 / TILE) + 1):
                        tx, tz = x + dx, z + dz
                        if not (0 <= tx < width and 0 <= tz < height):
                            continue
                        y = _y_at(vs, TILE * dx + TILE / 2, TILE * dz + TILE / 2)
                        if y is not None and y > top_y[tz, tx] + 0.01:
                            top_y[tz, tx], top_kind[tz][tx] = y, kind
    kinds, walks, shores = [], [], []
    for z in range(height):
        krow, wrow, srow = [], [], []
        for x in range(width):
            c = g[z, x]
            own = f.kinds[c] if c >= 0 else set()
            kind = top_kind[z][x]
            if kind == VOID[0]:
                kind = next((k for k in STANDING if k in own), kind)
            for over in OVERRIDING:
                if over in own and kind != over and (over not in ("tree", "roundtree") or f.walk[c] == "T"):
                    kind = over
                    break
            krow.append(CHAR.get(kind, OTHER[1]))
            wrow.append(f.walk[c] if c >= 0 else "T")
            srow.append("b" if kind not in WATER_NAMES and own & set(WATER_NAMES) else ".")
        kinds.append("".join(krow))
        walks.append("".join(wrow))
        shores.append("".join(srow))
    _fill_blocked_void(kinds, walks)
    known = top_y > -1e8
    fill = level_of_void if level_of_void is not None else (
        int(round(np.median(top_y[known]) / HEIGHT_STEP)) if known.any() else 0)
    level = np.where(known, np.round(top_y / HEIGHT_STEP), fill).astype(np.int64)
    for z in range(height):
        for x in range(width):
            if kinds[z][x] == VOID[1]:
                level[z, x] = VOID_LEVEL
    return SemanticMap(kinds, level, walks, shores)
