"""Patch quilting: fill a layout with whole windows copied from vanilla chunks.

Vanilla HeartGold chunks are modelled scenes, not tile sets: most cells only
fit their original neighbours, so tile-by-tile collapse (wfc.py) is slow and
rarely solves new layouts. Quilting copies P x P windows instead, so nearly
everything inside a window is a real vanilla arrangement, and only window
seams are new. Seams are judged by geometry (seams.py): edge profiles must
continue, overhanging pieces need the neighbours vanilla gave them, and
ground must not leave holes.

1. Placement: windows tile the grid on a P-step grid in reading order. Each
   region's cost = layout mismatches * layout + incompatible profile joins *
   seam + broken overhangs * rigid. The cheapest few are drawn at random
   (seeded).
2. Refinement: every bad tile (route-changing mismatch, broken join or
   overhang, hole) gets a region re-solved around it against all four sides,
   largest window size first, down to single cells. A region is replaced only
   when its cost strictly drops, so refinement never makes the grid worse.

Weights, window sizes and search widths live in solver_config.json, tuned by
the improvement loop (lab.py). Every number is reported; score.py gates.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from . import seams as seams_mod
from .layout import CLASSES, GRID, cell_char

CONFIG_PATH = Path(__file__).with_name("solver_config.json")
# Internal codes for tiles beside land, where floorless void would be exposed:
# "t" a blocked tile, "a" an any tile.
CHAR_CODES = {ch: i for i, ch in enumerate(sorted(set(CLASSES) | {"?", "t", "a"}))}
BESIDE_LAND = {"T": "t", "*": "a"}
WALKABLE = set(".,")
LEDGES = set("v^<>")


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text())["solver"]


def mismatch_cost(want: str, got: str) -> float:
    """How bad it is to get class `got` where the layout asked for `want`."""
    if want in ("t", "a"):
        return 2.0 if got == "?" else mismatch_cost("T" if want == "t" else "*", got)
    if want == "*" or want == got:
        return 0.0
    if want in WALKABLE and got in WALKABLE:
        return 0.25            # grass vs ground: cosmetic
    if {want, got} == {"T", "?"}:
        return 0.25            # wall vs floorless void: neither can be entered (score gates exposure)
    if want in LEDGES or got in LEDGES:
        return 4.0             # one-way movement changes the route
    return 2.0                 # walkable vs blocked/water


def critical(want: str, got: str) -> bool:
    """Mismatches that change where the player can go."""
    return mismatch_cost(want, got) >= 2.0


class Windows:
    """Every distinct P x P window of the kit's vanilla chunks (P = 1: every cell)."""

    def __init__(self, kit: dict, patch: int, exclude: frozenset = frozenset()):
        if patch == 1:
            cells = sorted({c for land, g in kit["chunks"].items() if land not in exclude for row in g for c in row})
            self.array = np.array(cells, dtype=np.int64).reshape(-1, 1, 1)
        else:
            windows = []
            for land, grid in kit["chunks"].items():
                if land in exclude:
                    continue
                a = np.array(grid, dtype=np.int64)
                view = np.lib.stride_tricks.sliding_window_view(a, (patch, patch))
                windows.append(view.reshape(-1, patch, patch))
            self.array = np.unique(np.concatenate(windows), axis=0)
        self.patch = patch


class Solver:
    def __init__(self, kit: dict, config: dict | None = None, exclude: frozenset = frozenset()):
        self.kit, self.cfg = kit, config or load_config()
        self.exclude = frozenset(exclude)
        self.seams = seams_mod.for_kit(kit, self.exclude)
        self.exclude = self.exclude | frozenset(self.seams.self_excluded)  # no windows from them either
        cells = kit["cells"]
        # Cells whose polygons touch nothing count as void ('?') for the solver: beside
        # land they would show black.
        self.char = np.array([CHAR_CODES["?"] if not self.seams.occupies[i]
                              else CHAR_CODES.get(cell_char(c), CHAR_CODES["?"]) for i, c in enumerate(cells)])
        chars = sorted(CHAR_CODES, key=CHAR_CODES.get)
        self.cost_table = np.array([[mismatch_cost(w, g) for g in chars] for w in chars])
        self.critical_table = self.cost_table >= 2.0
        self.stand = np.isin(self.char, [CHAR_CODES[c] for c in ".,v^<>"])
        self.empty = np.array([not o for o in self.seams.occupies])
        self._windows: dict[int, Windows] = {}
        self._onehot: dict[int, np.ndarray] = {}
        self._edge_cache: dict[int, tuple] = {}
        s = self.seams
        self.pe, self.pw, self.ps, self.pn = s.prof["east"], s.prof["west"], s.prof["south"], s.prof["north"]

    def windows(self, patch: int) -> np.ndarray:
        if patch not in self._windows:
            self._windows[patch] = Windows(self.kit, patch, self.exclude)
        return self._windows[patch].array

    def onehot(self, patch: int) -> np.ndarray:
        """W x (P*P*C) float32: window class codes one-hot, for mismatch cost as one matvec."""
        if patch not in self._onehot:
            got = self.char[self.windows(patch)].reshape(len(self.windows(patch)), -1)
            eye = np.eye(len(CHAR_CODES), dtype=np.float32)
            self._onehot[patch] = eye[got].reshape(len(got), -1)
        return self._onehot[patch]

    def codes(self, rows: list[str]) -> np.ndarray:
        height, width = len(rows), len(rows[0])

        def code(x, z):
            ch = rows[z][x]
            if ch in BESIDE_LAND and any(0 <= x + dx < width and 0 <= z + dz < height and rows[z + dz][x + dx] in ".,v^<>"
                                 for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                ch = BESIDE_LAND[ch]
            return CHAR_CODES[ch]
        return np.array([[code(x, z) for x in range(width)] for z in range(height)])

    # --- region cost --------------------------------------------------------

    def _edges(self, wins: np.ndarray, patch=None) -> tuple:
        """Each candidate's west, east, north, south edge profiles as (unique ids, W x n index)."""
        _, h, w = wins.shape
        if patch is not None and h == w == patch and patch in self._edge_cache:
            return self._edge_cache[patch]
        out = tuple(np.unique(e, return_inverse=True) for e in (
            self.pw[wins[:, :, 0]], self.pe[wins[:, :, w - 1]], self.pn[wins[:, 0, :]], self.ps[wins[:, h - 1, :]]))
        out = tuple((u, inv.reshape(len(wins), -1)) for u, inv in out)
        if patch is not None and h == w == patch:
            self._edge_cache[patch] = out
        return out

    def _seam_cost(self, grid, x0, z0, wins, patch=None) -> np.ndarray:
        """Incompatible joins between each candidate (W x h x w) and placed neighbours."""
        height, width = grid.shape
        _, h, w = wins.shape
        H, V = self.seams.H, self.seams.V
        west, east, north, south = self._edges(wins, patch)
        ok = np.zeros(len(wins), dtype=np.int64)
        joins = 0
        sides = []
        if x0 > 0:
            sides.append((grid[z0:z0 + h, x0 - 1], west, lambda n, u: H[self.pe[n], u]))
        if x0 + w < width:
            sides.append((grid[z0:z0 + h, x0 + w], east, lambda n, u: H[u, self.pw[n]]))
        if z0 > 0:
            sides.append((grid[z0 - 1, x0:x0 + w], north, lambda n, u: V[self.ps[n], u]))
        if z0 + h < height:
            sides.append((grid[z0 + h, x0:x0 + w], south, lambda n, u: V[u, self.pn[n]]))
        for side, (uniq, inv), table in sides:
            for j, neighbour in enumerate(side):
                if neighbour >= 0:
                    ok += table(neighbour, uniq)[inv[:, j]]
                    joins += 1
        return joins - ok

    def _void_cost(self, grid, x0, z0, wins) -> np.ndarray:
        """Standable cells joined to geometry-less cells across the region border (black void)."""
        height, width = grid.shape
        _, h, w = wins.shape
        out = np.zeros(len(wins), dtype=np.int64)
        for side, edge in ((grid[z0:z0 + h, x0 - 1] if x0 > 0 else None, wins[:, :, 0]),
                           (grid[z0:z0 + h, x0 + w] if x0 + w < width else None, wins[:, :, w - 1]),
                           (grid[z0 - 1, x0:x0 + w] if z0 > 0 else None, wins[:, 0, :]),
                           (grid[z0 + h, x0:x0 + w] if z0 + h < height else None, wins[:, h - 1, :])):
            if side is None:
                continue
            m = side >= 0
            if not m.any():
                continue
            n, e = side[m][None, :], edge[:, m]
            out += ((self.stand[e] & self.empty[n]) | (self.empty[e] & self.stand[n])).sum(1)
        return out

    def _height_cost(self, grid, x0, z0, wins) -> np.ndarray:
        """Floor tiles meeting a neighbour floor at another height across the region border."""
        height, width = grid.shape
        _, h, w = wins.shape
        floor, eh = self.seams.floor, self.seams.edge_heights
        out = np.zeros(len(wins), dtype=np.int64)
        for side, edge, mine, theirs in (
                (grid[z0:z0 + h, x0 - 1] if x0 > 0 else None, wins[:, :, 0], "west", "east"),
                (grid[z0:z0 + h, x0 + w] if x0 + w < width else None, wins[:, :, w - 1], "east", "west"),
                (grid[z0 - 1, x0:x0 + w] if z0 > 0 else None, wins[:, 0, :], "north", "south"),
                (grid[z0 + h, x0:x0 + w] if z0 + h < height else None, wins[:, h - 1, :], "south", "north")):
            if side is None:
                continue
            m = side >= 0
            if not m.any():
                continue
            n, e = side[m][None, :], edge[:, m]
            diff = np.abs(eh[mine][e] - eh[theirs][n]).max(axis=-1)
            out += (floor[e] & floor[n] & (diff > 1.0)).sum(1)
        return out

    def _incoming(self, grid, x0, z0, h, w) -> list:
        """Overhang constraints from placed cells outside the region into it."""
        height, width = grid.shape
        r = self.seams.reach
        out = []
        for z in range(max(0, z0 - r), min(height, z0 + h + r)):
            for x in range(max(0, x0 - r), min(width, x0 + w + r)):
                if x0 <= x < x0 + w and z0 <= z < z0 + h:
                    continue
                c = grid[z, x]
                if c < 0:
                    continue
                for dx, dz, ok in self.seams.rigid[c]:
                    tx, tz = x + dx, z + dz
                    if x0 <= tx < x0 + w and z0 <= tz < z0 + h:
                        out.append((tz - z0, tx - x0, ok))
        return out

    def _rigid_cost(self, grid, x0, z0, win, incoming) -> int:
        height, width = grid.shape
        h, w = win.shape
        bad = sum(win[lz, lx] not in ok for lz, lx, ok in incoming)
        rigid = self.seams.rigid
        for lz in range(h):
            for lx in range(w):
                for dx, dz, ok in rigid[win[lz, lx]]:
                    tx, tz = x0 + lx + dx, z0 + lz + dz
                    if x0 <= tx < x0 + w and z0 <= tz < z0 + h:
                        continue  # inside the candidate itself
                    if 0 <= tx < width and 0 <= tz < height and grid[tz, tx] >= 0 and grid[tz, tx] not in ok:
                        bad += 1
        return bad

    def _costs(self, grid, codes, x0, z0, wins, patch=None, hard_weight=None) -> np.ndarray:
        """Layout and join cost per candidate (rigid overhangs are added for the cheapest)."""
        _, h, w = wins.shape
        want = codes[z0:z0 + h, x0:x0 + w]
        if patch is not None and h == w == patch:
            mismatch = self.onehot(patch) @ self.cost_table[want.reshape(-1)].astype(np.float32).reshape(-1)
        else:
            mismatch = self.cost_table[want[None], self.char[wins]].sum(axis=(1, 2))
        cost = mismatch * self.cfg["layoutWeight"] + self._seam_cost(grid, x0, z0, wins, patch) * self.cfg["seamWeight"]
        if self.cfg.get("voidWeight"):
            cost = cost + self._void_cost(grid, x0, z0, wins) * self.cfg["voidWeight"]
        if self.cfg.get("heightWeight"):
            cost = cost + self._height_cost(grid, x0, z0, wins) * self.cfg["heightWeight"]
        if hard_weight:
            # Problems evaluate() ranks first: route changes, height breaks, floor beside void.
            hard = (self.critical_table[want[None], self.char[wins]].sum(axis=(1, 2))
                    + self._height_cost(grid, x0, z0, wins) + self._void_cost(grid, x0, z0, wins))
            cost = cost + hard * hard_weight
        return cost

    def solve_region(self, grid, codes, x0, z0, h, w, patch, rng, current=None, candidates=None,
                     rigid_weight=None, hard_weight=None) -> bool:
        """Choose a window for grid[z0:z0+h, x0:x0+w]; with `current`, only if strictly cheaper."""
        wins = self.windows(patch)[:, :h, :w]
        saved = grid[z0:z0 + h, x0:x0 + w].copy()
        grid[z0:z0 + h, x0:x0 + w] = -1
        cost = self._costs(grid, codes, x0, z0, wins, patch, hard_weight)
        incoming = self._incoming(grid, x0, z0, h, w)
        k = min(candidates or self.cfg["candidates"], len(wins))
        top = np.argpartition(cost, k - 1)[:k]
        rigid_w = self.cfg["rigidWeight"] if rigid_weight is None else rigid_weight
        total = {int(i): float(cost[i]) + rigid_w * self._rigid_cost(grid, x0, z0, wins[i], incoming) for i in top}
        best = min(total.values())
        if current is not None:
            cur_cost = self._costs(grid, codes, x0, z0, saved[None], hard_weight=hard_weight)
            now = float(cur_cost[0]) + rigid_w * self._rigid_cost(grid, x0, z0, saved, incoming)
            if best < now - 1e-9:
                pick = min(total, key=total.get)
            else:
                # Sideways: an equally good, different region lets refinement leave a local minimum.
                same = [i for i, c in total.items() if abs(c - now) < 1e-9 and not np.array_equal(wins[i], saved)]
                if not (self.cfg.get("sideways") and best >= now - 1e-9 and same):
                    grid[z0:z0 + h, x0:x0 + w] = saved
                    return False
                pick = rng.choice(sorted(same))
        else:
            pool = sorted(i for i, c in total.items() if c <= best + self.cfg["cutoff"])
            pick = rng.choice(pool)
        grid[z0:z0 + h, x0:x0 + w] = wins[pick]
        return True

    # --- whole grid ---------------------------------------------------------

    def place(self, rows: list[str], seed: int, patch: int) -> np.ndarray:
        rng = random.Random(seed)
        codes = self.codes(rows)
        height, width = codes.shape
        grid = np.full((height, width), -1, dtype=np.int64)
        for z0 in range(0, height, patch):
            for x0 in range(0, width, patch):
                self.solve_region(grid, codes, x0, z0, min(patch, height - z0), min(patch, width - x0), patch, rng)
        return grid

    def bad_tiles(self, grid: np.ndarray, codes: np.ndarray) -> list[tuple[int, int]]:
        bad = set()
        crit = self.critical_table[codes, self.char[grid]]
        bad |= {(int(x), int(z)) for z, x in zip(*np.nonzero(crit))}
        seam = self.seams.seam_map(grid)
        for z, x in zip(*np.nonzero(seam)):
            bad.add((int(x), int(z)))
        for x, z, dx, dz in self.seams.rigid_violations(grid):
            bad.add((x, z))
            bad.add((x + dx, z + dz))
        bad |= set(self.seams.holes(grid))
        bad |= set(self.void_exposed(grid))
        for x, z in self.seams.height_breaks(grid):
            bad |= {(nx, nz) for nx, nz in ((x, z), (x + 1, z), (x, z + 1))
                    if nx < grid.shape[1] and nz < grid.shape[0]}
        for x, z in self.seams.bare_edges(grid):
            bad.add((x, z))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= x + dx < grid.shape[1] and 0 <= z + dz < grid.shape[0]:
                    bad.add((x + dx, z + dz))
        return sorted(bad)

    def void_exposed(self, grid: np.ndarray) -> list[tuple[int, int]]:
        void = self.char[grid] == CHAR_CODES["?"]
        land = np.isin(self.char[grid], [CHAR_CODES[c] for c in ".,v^<>"])
        near = np.zeros_like(land)
        near[1:, :] |= land[:-1, :]
        near[:-1, :] |= land[1:, :]
        near[:, 1:] |= land[:, :-1]
        near[:, :-1] |= land[:, 1:]
        zs, xs = np.nonzero(void & near)
        return list(zip(xs.tolist(), zs.tolist()))

    def refine(self, grid: np.ndarray, rows: list[str], seed: int) -> np.ndarray:
        rng = random.Random(seed + 7)
        codes = self.codes(rows)
        height, width = grid.shape
        best = (self.evaluate(grid, rows), grid.copy())
        for _ in range(self.cfg["refineRounds"]):
            bad = self.bad_tiles(grid, codes)
            if not bad:
                break
            rng.shuffle(bad)
            changed = False
            for x, z in bad[:self.cfg["refinePerRound"]]:
                for patch in self.cfg["refineSizes"]:
                    h, w = min(patch, height), min(patch, width)
                    x0 = min(max(0, x - rng.randrange(w)), width - w)
                    z0 = min(max(0, z - rng.randrange(h)), height - h)
                    if self.solve_region(grid, codes, x0, z0, h, w, patch, rng, current=True):
                        changed = True
                        break
            rank = self.evaluate(grid, rows)
            if rank < best[0]:
                best = (rank, grid.copy())
            if not changed:
                break
        return best[1]

    def evaluate(self, grid: np.ndarray, rows: list[str]) -> tuple:
        """Ranking key, lower is better: route changes, overhangs, holes, joins."""
        codes = self.codes(rows)
        crit = int(self.critical_table[codes, self.char[grid]].sum())
        seams, _ = self.seams.profile_seams(grid)
        return (crit + len(self.void_exposed(grid)) + len(self.seams.bare_edges(grid))
                + len(self.seams.height_breaks(grid)),
                len(self.seams.rigid_violations(grid)),
                len(self.seams.holes(grid)), seams)

    def hard_tiles(self, grid: np.ndarray, codes: np.ndarray) -> list[tuple[int, int]]:
        """Tiles behind hard-gate problems (route changes, broken bonds, holes, void)."""
        bad = {(int(x), int(z)) for z, x in zip(*np.nonzero(self.critical_table[codes, self.char[grid]]))}
        for x, z, dx, dz in self.seams.rigid_violations(grid):
            bad |= {(x, z), (x + dx, z + dz)}
        bad |= set(self.seams.holes(grid)) | set(self.void_exposed(grid))
        for x, z in self.seams.height_breaks(grid):
            bad |= {(x, z), (x + 1, z), (x, z + 1)}
        bad = {(x, z) for x, z in bad if x < grid.shape[1] and z < grid.shape[0]}
        height, width = grid.shape
        for x, z in self.seams.bare_edges(grid):
            bad |= {(x + dx, z + dz) for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= x + dx < width and 0 <= z + dz < height}
        return sorted(bad)

    def polish(self, grid: np.ndarray, rows: list[str], seed: int) -> np.ndarray:
        """Clear the last hard problems: wide candidate pools around each, kept only if the grid ranks better."""
        rng = random.Random(seed + 13)
        codes = self.codes(rows)
        height, width = grid.shape
        rank = self.evaluate(grid, rows)
        for _ in range(self.cfg.get("polishRounds", 0)):
            hard = self.hard_tiles(grid, codes)
            if not hard:
                break
            rng.shuffle(hard)
            for x, z in hard[:60]:
                for patch in self.cfg.get("polishSizes", [4, 2, 1]):
                    h, w = min(patch, height), min(patch, width)
                    for _try in range(2):
                        x0 = min(max(0, x - rng.randrange(w)), width - w)
                        z0 = min(max(0, z - rng.randrange(h)), height - h)
                        saved = grid[z0:z0 + h, x0:x0 + w].copy()
                        # A broken overhang outranks joins in evaluate(), so let polish trade joins for it.
                        if not self.solve_region(grid, codes, x0, z0, h, w, patch, rng, current=True,
                                                 candidates=self.cfg.get("polishCandidates", 1000),
                                                 rigid_weight=self.cfg.get("polishRigidWeight"),
                                                 hard_weight=self.cfg.get("polishHardWeight")):
                            continue
                        new_rank = self.evaluate(grid, rows)
                        if new_rank < rank:
                            rank = new_rank
                        else:
                            grid[z0:z0 + h, x0:x0 + w] = saved
        return grid

    def solve(self, rows: list[str], seed: int = 0) -> list[list[int]]:
        best = None
        for patch in self.cfg["placeSizes"]:
            grid = self.polish(self.refine(self.place(rows, seed, patch), rows, seed), rows, seed)
            rank = self.evaluate(grid, rows)
            if best is None or rank < best[0]:
                best = (rank, grid)
        return best[1].tolist()


def critical_mismatches(kit: dict, grid: list[list[int]], rows: list[str]) -> list[tuple[int, int, str, str]]:
    out = []
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            got = cell_char(kit["cells"][grid[z][x]])
            if critical(rows[z][x], got):
                out.append((x, z, rows[z][x], got))
    return out


_SOLVERS: dict = {}


def solver_for(kit: dict, config: dict | None = None, exclude: frozenset = frozenset()) -> Solver:
    key = (id(kit), json.dumps(config, sort_keys=True), frozenset(exclude))
    if key not in _SOLVERS:
        _SOLVERS[key] = Solver(kit, config, exclude)
    return _SOLVERS[key]


def solve(kit: dict, rows: list[str], seed: int = 0, config: dict | None = None,
          exclude: frozenset = frozenset()) -> list[list[int]]:
    return solver_for(kit, config, exclude).solve(rows, seed)
