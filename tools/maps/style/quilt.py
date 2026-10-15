"""Patch quilting: fill a layout with whole windows copied from vanilla chunks.

Vanilla HeartGold chunks are modelled scenes, not tile sets: most cells only
fit their original neighbours, so tile-by-tile collapse (wfc.py) is slow and
rarely solves new layouts. Quilting copies P x P windows instead, so nearly
everything inside a window is a real vanilla arrangement, and only window
seams are new. A seam pair is compatible when the facing edges share an edge
label (union-find over every vanilla neighbour pair; see wfc.learn).

1. Windows: every P x P window of every vanilla chunk in the kit.
2. Placement: windows tile the chunk on a P-step grid in reading order. Each
   is chosen by cost = layout mismatches * LAYOUT_WEIGHT + incompatible seam
   pairs * SEAM_WEIGHT, picking randomly (seeded) among the cheapest few.
3. Repair: tiles whose class differs from the layout, or whose seams are
   incompatible, are replaced by single cells that fit all four neighbours
   and the class, where one exists.

Every number is reported; score.py applies the gates.
"""

from __future__ import annotations

import random

import numpy as np

from .layout import CLASSES, GRID, cell_char

PATCH = 8
LAYOUT_WEIGHT = 4.0
SEAM_WEIGHT = 3.0
TOP_K = 4
CHAR_CODES = {ch: i for i, ch in enumerate(sorted(set(CLASSES) | {"?"}))}
WALKABLE = set(".,")
LEDGES = set("v^<>")


def mismatch_cost(want: str, got: str) -> float:
    """How bad it is to get class `got` where the layout asked for `want`."""
    if want == "*" or want == got:
        return 0.0
    if want in WALKABLE and got in WALKABLE:
        return 0.25            # grass vs ground: cosmetic
    if want in LEDGES or got in LEDGES:
        return 4.0             # one-way movement changes the route
    return 2.0                 # walkable vs blocked/water


def critical(want: str, got: str) -> bool:
    """Mismatches that change where the player can go."""
    return mismatch_cost(want, got) >= 2.0


def edge_labels(kit: dict) -> dict[str, np.ndarray]:
    """Union-find edge labels: compatible(a right-of b) iff east[b] == west[a]."""
    n = len(kit["cells"])
    out = {}
    for axis, (far, near) in (("h", ("east", "west")), ("v", ("south", "north"))):
        parent = list(range(2 * n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for grid in kit["chunks"].values():
            for z in range(GRID):
                for x in range(GRID):
                    a = grid[z][x]
                    if axis == "h" and x + 1 < GRID:
                        b = grid[z][x + 1]
                    elif axis == "v" and z + 1 < GRID:
                        b = grid[z + 1][x]
                    else:
                        continue
                    ra, rb = find(a), find(n + b)
                    if ra != rb:
                        parent[ra] = rb
        out[far] = np.array([find(c) for c in range(n)], dtype=np.int64)
        out[near] = np.array([find(n + c) for c in range(n)], dtype=np.int64)
    return out


class Quilter:
    def __init__(self, kit: dict, patch: int = PATCH):
        self.kit, self.patch = kit, patch
        self.labels = edge_labels(kit)
        self.char = np.array([CHAR_CODES.get(cell_char(c), CHAR_CODES["?"]) for c in kit["cells"]])
        windows = []
        for grid in kit["chunks"].values():
            array = np.array(grid, dtype=np.int64)
            for z in range(GRID - patch + 1):
                for x in range(GRID - patch + 1):
                    windows.append(array[z:z + patch, x:x + patch])
        self.windows = np.stack(windows)                    # W x P x P cell ids
        self.window_chars = self.char[self.windows]         # W x P x P class codes
        self.west = self.labels["west"][self.windows[:, :, 0]]
        self.north = self.labels["north"][self.windows[:, 0, :]]
        n = len(kit["cells"])
        self.by_char = {ch: [i for i in range(n) if cell_char(kit["cells"][i]) == ch] for ch in CLASSES}
        self.weights = np.array([max(1, c.get("count", 1)) for c in kit["cells"]], dtype=float)
        chars = sorted(CHAR_CODES, key=CHAR_CODES.get)
        self.cost_table = np.array([[mismatch_cost(w, g) for g in chars] for w in chars])

    def _layout_codes(self, rows: list[str]) -> np.ndarray:
        return np.array([[CHAR_CODES[ch] for ch in row] for row in rows])

    def place(self, rows: list[str], seed: int) -> np.ndarray:
        rng = random.Random(seed)
        codes = self._layout_codes(rows)
        grid = np.full((GRID, GRID), -1, dtype=np.int64)
        p = self.patch
        for z0 in range(0, GRID, p):
            for x0 in range(0, GRID, p):
                want = codes[z0:z0 + p, x0:x0 + p]
                h, w = want.shape
                got = self.window_chars[:, :h, :w]
                mismatch = self.cost_table[want[None, :, :], got].sum(axis=(1, 2))
                seams = np.zeros(len(self.windows))
                if x0:
                    left = self.labels["east"][grid[z0:z0 + h, x0 - 1]]
                    seams += (self.west[:, :h] != left).sum(axis=1)
                if z0:
                    above = self.labels["south"][grid[z0 - 1, x0:x0 + w]]
                    seams += (self.north[:, :w] != above).sum(axis=1)
                cost = mismatch * LAYOUT_WEIGHT + seams * SEAM_WEIGHT
                best = np.argpartition(cost, TOP_K)[:TOP_K]
                best = sorted(best, key=lambda i: cost[i])
                cutoff = cost[best[0]] + 1.0
                choice = rng.choice([i for i in best if cost[i] <= cutoff])
                grid[z0:z0 + h, x0:x0 + w] = self.windows[choice][:h, :w]
        return grid

    def compatible(self, grid: np.ndarray, x: int, z: int, cell: int) -> bool:
        lab = self.labels
        if x and lab["east"][grid[z, x - 1]] != lab["west"][cell]:
            return False
        if x + 1 < GRID and lab["east"][cell] != lab["west"][grid[z, x + 1]]:
            return False
        if z and lab["south"][grid[z - 1, x]] != lab["north"][cell]:
            return False
        if z + 1 < GRID and lab["south"][cell] != lab["north"][grid[z + 1, x]]:
            return False
        return True

    def bad_tiles(self, grid: np.ndarray, codes: np.ndarray) -> list[tuple[int, int]]:
        any_code = CHAR_CODES["*"]
        out = []
        for z in range(GRID):
            for x in range(GRID):
                wrong_class = codes[z, x] != any_code and self.char[grid[z, x]] != codes[z, x]
                if wrong_class or not self.compatible(grid, x, z, grid[z, x]):
                    out.append((x, z))
        return out

    def repair(self, grid: np.ndarray, rows: list[str], seed: int, rounds: int = 3) -> np.ndarray:
        rng = random.Random(seed + 7)
        codes = self._layout_codes(rows)
        for _ in range(rounds):
            changed = False
            for x, z in self.bad_tiles(grid, codes):
                ch = rows[z][x]
                pool = range(len(self.kit["cells"])) if ch == "*" else self.by_char.get(ch, [])
                fits = [c for c in pool if self.compatible(grid, x, z, c)]
                if fits:
                    weights = self.weights[fits]
                    grid[z, x] = rng.choices(fits, weights=weights)[0]
                    changed = True
            if not changed:
                break
        return grid

    def solve(self, rows: list[str], seed: int = 0) -> list[list[int]]:
        grid = self.repair(self.place(rows, seed), rows, seed)
        return grid.tolist()


def critical_mismatches(kit: dict, grid: list[list[int]], rows: list[str]) -> list[tuple[int, int, str, str]]:
    out = []
    for z in range(GRID):
        for x in range(GRID):
            got = cell_char(kit["cells"][grid[z][x]])
            if critical(rows[z][x], got):
                out.append((x, z, rows[z][x], got))
    return out


_QUILTERS: dict[tuple[int, int], Quilter] = {}


def solve(kit: dict, rows: list[str], seed: int = 0, sizes=(8, 6, 4)) -> list[list[int]]:
    """Best of several patch sizes for this seed: fewest critical mismatches, then seams."""
    best = None
    for size in sizes:
        key = (id(kit), size)
        if key not in _QUILTERS:
            _QUILTERS[key] = Quilter(kit, size)
        quilter = _QUILTERS[key]
        grid = quilter.solve(rows, seed)
        array = np.array(grid)
        seams = sum(not quilter.compatible(array, x, z, array[z, x]) for z in range(GRID) for x in range(GRID))
        rank = (len(critical_mismatches(kit, grid, rows)), seams)
        if best is None or rank < best[0]:
            best = (rank, grid)
    return best[1]
