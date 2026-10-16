"""Paint a semantic map with vanilla cells: texture-by-numbers over a kit.

Each target tile gets a vanilla *occurrence* (a source chunk position), and
its cell is the cell vanilla had there. The solve minimises one energy:

* label: the occurrence's own semantic label (semantic.py: kind, floor
  level, walk class, shore) must equal the target's, and its eight neighbours'
  labels should equal the target's neighbours. This picks the edge, corner
  and inner-corner variants, like an autotiler learned from vanilla.
* join: zero where a neighbour continues the same source chunk at the same
  offset (a copied vanilla arrangement), small where the source changes
  across a join seams.py accepts, large where it does not.
* overhang: a cell whose polygons reach into other tiles (tree billboards,
  cliff faces) needs the neighbours vanilla gave it (seams.rigid).
* bare: a cell that vanilla always showed under some neighbour's overhang (a
  tree's shadow disc under its billboard) needs such an overhang again, or
  it shows a stump or a gap.
* void: polygon coverage is kept as two counting rasters (coverage.py's
  per-cell masks: straight down, and at the field camera's pitch). A tile
  whose target is not void but whose pixels nothing covers shows black.

Coherent copying means whole runs of vanilla (a tree belt, a cave wall band,
a pond's shore) come across intact, and new seams fall where the kit says
they are invisible. The solve is greedy in reading order, then sweeps of
single-tile changes and block copies (whole source blocks pasted over costly
tiles) until nothing improves.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from . import coverage
from . import seams as seams_mod
from . import semantic

DIRS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
DIRS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


@dataclass
class Weights:
    walk: float = 200.0       # wrong walk class: changes where the player can go (outranks every look term)
    kind: float = 12.0        # wrong look
    level: float = 30.0       # wrong floor height
    shore: float = 12.0       # a bank where none was asked for, or none where one was
    context: float = 1.5      # per neighbour label that differs from the target's
    seam: float = 1.0         # a new (compatible) join
    bad_seam: float = 25.0    # a join seams.py rejects
    rigid: float = 25.0       # an overhang into a neighbour vanilla never had there
    bare: float = 25.0        # a tile vanilla always overhung, without its overhang
    tree: float = 80.0        # the same two for tree cells: a sliced tree or a stump is glaring,
                              # while 80 on cave walls trades their cuts for void (rebuild bench)
    void_top: float = 30.0    # a tile with black void seen from above (not asked for)
    void_camera: float = 12.0 # a tile with black void seen from the game camera's pitch
    candidates: int = 48      # best label matches considered per tile
    blocks: tuple = (6, 4, 3, 2)   # block-copy sizes tried around costly tiles
    block_tries: int = 12     # source blocks tried per costly tile and size
    hot: float = 4.0          # tile energy above which block copies are tried
    sweeps: int = 6


class Source:
    """Every vanilla occurrence of a kit (minus excluded lands), with its labels."""

    def __init__(self, kit: dict, exclude: frozenset = frozenset()):
        self.kit = kit
        self.seams = seams_mod.for_kit(kit, exclude)
        excluded = frozenset(exclude) | frozenset(self.seams.self_excluded)
        self.lands = [land for land in sorted(kit["chunks"]) if land not in excluded]
        self.labels: dict[tuple, int] = {}
        cells, labels, nbrs, where = [], [], [], []
        self.index = {}  # (land, x, z) -> occurrence id
        for land in self.lands:
            grid = np.array(kit["chunks"][land])
            sem = semantic.extract(kit, grid)
            h, w = grid.shape
            lab = np.array([[self.label_id(sem.label(x, z)) for x in range(w)] for z in range(h)])
            for z in range(h):
                for x in range(w):
                    self.index[(land, x, z)] = len(cells)
                    cells.append(grid[z, x])
                    labels.append(lab[z, x])
                    nbrs.append([lab[z + dz, x + dx] if 0 <= x + dx < w and 0 <= z + dz < h else -1
                                 for dx, dz in DIRS8])
                    where.append((land, x, z))
        self.cell = np.array(cells, dtype=np.int64)
        self.lab = np.array(labels, dtype=np.int64)
        self.nbr = np.array(nbrs, dtype=np.int64)
        self.where = where
        self.parts = {i: key for key, i in self.labels.items()}  # label id -> (kind, level, walk)
        n = len(kit["cells"])
        self.reach_in = [tuple((dx, dz) for dx, dz in self.seams.occupies[c] if (dx, dz) != (0, 0))
                         for c in range(n)]
        self.rigid = [{(dx, dz): ok for dx, dz, ok in self.seams.rigid[c]} for c in range(n)]
        seen = np.zeros(n, dtype=np.int64)
        overlapped = np.zeros(n, dtype=np.int64)
        for land in self.lands:
            grid = np.array(kit["chunks"][land])
            h, w = grid.shape
            over = np.zeros((h, w), dtype=bool)
            for z in range(h):
                for x in range(w):
                    for dx, dz in self.reach_in[grid[z, x]]:
                        if 0 <= x + dx < w and 0 <= z + dz < h:
                            over[z + dz, x + dx] = True
            inner = grid[2:-2, 2:-2]  # chunk edges may be overlapped from the next chunk
            np.add.at(seen, inner.ravel(), 1)
            np.add.at(overlapped, inner.ravel(), over[2:-2, 2:-2].ravel().astype(np.int64))
        self.needs_overlap = (seen >= 2) & (overlapped == seen)

    def label_id(self, label: tuple) -> int:
        return self.labels.setdefault(label, len(self.labels))

    def split_kits(self) -> tuple[dict, dict]:
        """(kit without roof polygons, kit of roof polygons only): coverage views of the kit."""
        if not hasattr(self, "_split"):
            mats = self.kit["materials"]
            roof = {key for key, m in mats.items() if semantic.material_kind(m) == "roof"}
            def keep(pred):
                return {"materials": mats, "cells": [
                    {**c, "polys": [p for p in c.get("polys", ()) if pred(p["mat"] in roof)]}
                    if "polys" in c else c for c in self.kit["cells"]]}
            self._split = (keep(lambda r: not r), keep(lambda r: r))
        return self._split

    def shifted(self, occ: int, dx: int, dz: int) -> int | None:
        land, x, z = self.where[occ]
        return self.index.get((land, x + dx, z + dz))


_SOURCES: dict = {}


def source_for(kit: dict, exclude: frozenset = frozenset()) -> Source:
    key = (id(kit), frozenset(exclude))
    if key not in _SOURCES:
        _SOURCES[key] = Source(kit, frozenset(exclude))
    return _SOURCES[key]


class Painter:
    def __init__(self, source: Source, target: semantic.SemanticMap, weights: Weights | None = None,
                 seed: int = 0):
        self.s, self.t, self.w = source, target, weights or Weights()
        self.rng = random.Random(seed)
        self.h, self.wd = target.shape
        s = source
        self.tkind = np.array([[target.kind[z][x] for x in range(self.wd)] for z in range(self.h)])
        self.tlevel = target.level
        self.twalk = np.array([[target.walk[z][x] for x in range(self.wd)] for z in range(self.h)])
        self.tshore = np.array([[target.shore[z][x] for x in range(self.wd)] for z in range(self.h)])
        self.tlab = np.array([[s.labels.get(target.label(x, z), -2) for x in range(self.wd)]
                              for z in range(self.h)])
        parts = [s.parts[i] for i in range(len(s.parts))]
        self.okind = np.array([p[0] for p in parts])[s.lab]
        self.olevel = np.array([p[1] for p in parts])[s.lab]
        self.owalk = np.array([p[2] for p in parts])[s.lab]
        self.oshore = np.array([p[3] for p in parts])[s.lab]
        self.unary_rows: dict[tuple, np.ndarray] = {}
        self.cands: dict[tuple, np.ndarray] = {}
        self.occ = np.full((self.h, self.wd), -1, dtype=np.int64)
        self.grid = np.full((self.h, self.wd), -1, dtype=np.int64)
        self.cover = np.zeros((self.h, self.wd), dtype=np.int64)
        self.incoming: dict[tuple, set] = defaultdict(set)  # tile -> tiles whose cell constrains it
        self._init_cover()
        trees = np.array([bool(k & {"tree", "roundtree"}) for k in semantic.facts(s.kit).kinds])
        self.rigid_w = np.where(trees, self.w.tree, self.w.rigid)
        sm = s.seams
        self.H, self.V = sm.H, sm.V
        self.pe, self.pw, self.ps, self.pn = sm.prof["east"], sm.prof["west"], sm.prof["south"], sm.prof["north"]

    # --- coverage rasters ----------------------------------------------------------

    PPT = coverage.PPT
    PAD = 20  # tiles of raster beyond the grid: overhangs and tall walls project past it

    def _init_cover(self) -> None:
        p, pad = self.PPT, self.PAD
        cover_kit, roof_kit = self.s.split_kits()
        self.cov = coverage._for_kit(cover_kit, p)
        self.roof_cov = coverage._for_kit(roof_kit, p)
        shape = ((self.h + 2 * pad) * p, (self.wd + 2 * pad) * p)
        # top, camera: polygons that show something; roof_top, roof_camera: black roof polygons
        # (d_ro: how vanilla paints a cave's outside), which hide what lies under them.
        self.rasters = [np.zeros(shape, dtype=np.int32) for _ in range(4)]
        tiles = (shape[0] // p, shape[1] // p)
        self.counts = [np.full(tiles, p * p, dtype=np.int32), np.full(tiles, p * p, dtype=np.int32),
                       np.zeros(tiles, dtype=np.int32), np.zeros(tiles, dtype=np.int32)]
        floor = self.tlevel[self.tlevel != semantic.VOID_LEVEL]
        floor_y = float(np.median(floor)) * semantic.HEIGHT_STEP if floor.size else 0.0
        # Camera raster rows are floor-plane z at height 0; the floor seen through a sample lies
        # floor_y * SLOPE further south.
        self.cam_shift = int(round(floor_y * coverage.SLOPE / coverage.TILE * p))
        dark = (semantic.VOID[1], semantic.CHAR["roof"])
        self.want_open = np.array([[self.t.kind[z][x] not in dark for x in range(self.wd)]
                                   for z in range(self.h)])
        self.want_cover = self.want_open  # void and roof tiles are dark on purpose
        self.mask_tiles: dict[int, tuple] = {}
        self.taboo: dict[tuple, int] = {}

    def _masks(self, cell: int):
        return (*self.cov.get(int(cell)), *self.roof_cov.get(int(cell)))

    def _stamp(self, x: int, z: int, cell: int, sign: int) -> None:
        """Add (sign 1) or remove (-1) a cell's masks, keeping per-tile pixel counts current:
        counts[0..1] = uncovered pixels (top, camera), counts[2..3] = roof pixels."""
        p, pad = self.PPT, self.PAD
        for i, (ras, m) in enumerate(zip(self.rasters, self._masks(cell))):
            if m is None:
                continue
            c0, r0, mask = m
            # Camera masks are stored shifted so a tile's camera pixels are its own block.
            r0, c0 = r0 + (z + pad) * p + (self.cam_shift if i % 2 else 0), c0 + (x + pad) * p
            a0, b0 = max(0, r0), max(0, c0)
            a1, b1 = min(ras.shape[0], r0 + mask.shape[0]), min(ras.shape[1], c0 + mask.shape[1])
            if a0 >= a1 or b0 >= b1:
                continue
            A0, B0 = a0 // p * p, b0 // p * p
            A1, B1 = -(-a1 // p) * p, -(-b1 // p) * p
            region = ras[A0:A1, B0:B1]
            shape = ((A1 - A0) // p, p, (B1 - B0) // p, p)
            before = ((region == 0) if i < 2 else (region > 0)).reshape(shape).sum(axis=(1, 3))
            ras[a0:a1, b0:b1] += sign * mask[a0 - r0:a1 - r0, b0 - c0:b1 - c0]
            after = ((region == 0) if i < 2 else (region > 0)).reshape(shape).sum(axis=(1, 3))
            self.counts[i][A0 // p:A1 // p, B0 // p:B1 // p] += after - before

    def _cell_tiles(self, cell: int) -> tuple:
        """Tile offsets whose void state this cell's masks can change."""
        if cell not in self.mask_tiles:
            p = self.PPT
            out = set()
            for i, m in enumerate(self._masks(cell)):
                if m is None:
                    continue
                c0, r0, mask = m
                shift = self.cam_shift if i % 2 else 0
                for dz in range((r0 + shift) // p, (r0 + mask.shape[0] - 1 + shift) // p + 1):
                    for dx in range(c0 // p, (c0 + mask.shape[1] - 1) // p + 1):
                        out.add((dx, dz))
            self.mask_tiles[cell] = tuple(out)
        return self.mask_tiles[cell]

    def mark_bad(self, tiles) -> None:
        """Tiles the real renderer saw void at: their current cells are charged as void
        until replaced (the coverage rasters missed them)."""
        for x, z in tiles:
            if self._inside(x, z) and self.grid[z, x] >= 0:
                self.taboo[(x, z)] = int(self.grid[z, x])

    def void(self, x: int, z: int) -> float:
        if self.grid[z, x] < 0:
            return 0.0
        if self.taboo and self.taboo.get((x, z)) == self.grid[z, x]:
            return 2 * self.w.void_top
        tz, tx = z + self.PAD, x + self.PAD
        top, cam, roof_top, roof_cam = (c[tz, tx] for c in self.counts)
        # The camera looks north and down: void at the north edge is the next chunk's to cover.
        cam_ok = z >= 2
        cost = 0.0
        limit = self.PPT * self.PPT // 4
        if self.want_cover[z, x]:
            if top:
                cost += self.w.void_top
            if cam_ok and cam:
                cost += self.w.void_camera
        if self.want_open[z, x]:
            if roof_top > limit:
                cost += self.w.void_top
            if cam_ok and roof_cam > limit:
                cost += self.w.void_camera
        return cost

    # --- state ----------------------------------------------------------------

    def _inside(self, x: int, z: int) -> bool:
        return 0 <= x < self.wd and 0 <= z < self.h

    def place(self, x: int, z: int, occ: int) -> None:
        old = self.grid[z, x]
        if old >= 0:
            self._stamp(x, z, old, -1)
            for dx, dz in self.s.reach_in[old]:
                if self._inside(x + dx, z + dz):
                    self.cover[z + dz, x + dx] -= 1
            for dx, dz in self.s.rigid[old]:
                self.incoming[(x + dx, z + dz)].discard((x, z))
        self.occ[z, x] = occ
        cell = self.s.cell[occ] if occ >= 0 else -1
        self.grid[z, x] = cell
        if cell >= 0:
            self._stamp(x, z, cell, 1)
            for dx, dz in self.s.reach_in[cell]:
                if self._inside(x + dx, z + dz):
                    self.cover[z + dz, x + dx] += 1
            for dx, dz in self.s.rigid[cell]:
                if self._inside(x + dx, z + dz):
                    self.incoming[(x + dx, z + dz)].add((x, z))

    # --- energy terms ---------------------------------------------------------

    def unary_row(self, x: int, z: int) -> np.ndarray:
        """Label + context cost of every occurrence at target (x, z)."""
        if (x, z) in self.unary_rows:
            return self.unary_rows[(x, z)]
        w = self.w
        level_off = (self.olevel != self.tlevel[z, x]) & (self.tlevel[z, x] != semantic.VOID_LEVEL)
        cost = (w.walk * (self.owalk != self.twalk[z, x]) + w.kind * (self.okind != self.tkind[z, x])
                + w.level * level_off + w.shore * (self.oshore != self.tshore[z, x])).astype(np.float32)
        for k, (dx, dz) in enumerate(DIRS8):
            if not self._inside(x + dx, z + dz):
                continue
            got = self.s.nbr[:, k]
            cost += w.context * ((got != self.tlab[z + dz, x + dx]) * np.where(got < 0, 0.5, 1.0)).astype(np.float32)
        self.unary_rows[(x, z)] = cost
        return cost

    def candidates(self, x: int, z: int) -> np.ndarray:
        if (x, z) not in self.cands:
            u = self.unary_row(x, z)
            k = min(self.w.candidates * 4, len(u) - 1)
            best = np.argpartition(u, k)[:k]
            order = best[np.argsort(u[best], kind="stable")]
            _, first = np.unique(self.s.cell[order], return_index=True)  # one per distinct cell
            self.cands[(x, z)] = order[np.sort(first)][: self.w.candidates]
        return self.cands[(x, z)]

    def join(self, x: int, z: int, dx: int, dz: int) -> float:
        """Cost of the join between (x, z) and (x + dx, z + dz), dx/dz in {0, 1}."""
        nx, nz = x + dx, z + dz
        if not self._inside(nx, nz):
            return 0.0
        a_occ, b_occ = self.occ[z, x], self.occ[nz, nx]
        if a_occ < 0 or b_occ < 0:
            return 0.0
        if self.s.shifted(int(a_occ), dx, dz) == b_occ:
            return 0.0
        a, b = self.grid[z, x], self.grid[nz, nx]
        ok = self.H[self.pe[a], self.pw[b]] if dx else self.V[self.ps[a], self.pn[b]]
        return self.w.seam if ok else self.w.bad_seam

    def rigid_out(self, x: int, z: int) -> float:
        cell = self.grid[z, x]
        if cell < 0:
            return 0.0
        bad = 0
        for (dx, dz), ok in self.s.rigid[cell].items():
            if self._inside(x + dx, z + dz):
                other = self.grid[z + dz, x + dx]
                bad += other >= 0 and other not in ok
        return bad * self.rigid_w[cell]

    def rigid_edge(self, src: tuple, dst: tuple) -> float:
        cell, other = self.grid[src[1], src[0]], self.grid[dst[1], dst[0]]
        if cell < 0 or other < 0:
            return 0.0
        ok = self.s.rigid[cell].get((dst[0] - src[0], dst[1] - src[1]))
        return self.rigid_w[cell] if ok is not None and other not in ok else 0.0

    def bare(self, x: int, z: int) -> float:
        cell = self.grid[z, x]
        return self.rigid_w[cell] if cell >= 0 and self.s.needs_overlap[cell] and self.cover[z, x] == 0 else 0.0

    def energy(self, block: set, around: set) -> float:
        """Every term that changes when the tiles in `block` change; `around` = tiles whose
        cover those changes can affect (reach-in targets of the old and new cells)."""
        total = 0.0
        for x, z in block:
            occ = self.occ[z, x]
            if occ >= 0:
                total += float(self.unary_row(x, z)[occ])
            for dx, dz in ((1, 0), (0, 1)):
                total += self.join(x, z, dx, dz)
            for dx, dz in ((-1, 0), (0, -1)):
                if (x + dx, z + dz) not in block and self._inside(x + dx, z + dz):
                    total += self.join(x + dx, z + dz, -dx, -dz)
            total += self.rigid_out(x, z)
            for src in self.incoming.get((x, z), ()):
                if src not in block:
                    total += self.rigid_edge(src, (x, z))
        for x, z in block | around:
            total += self.bare(x, z) + self.void(x, z)
        return total

    def _around(self, tiles, cells) -> set:
        out = set()
        for (x, z), cell in zip(tiles, cells):
            if cell >= 0:
                for dx, dz in self.s.reach_in[cell] + self._cell_tiles(cell):
                    if self._inside(x + dx, z + dz):
                        out.add((x + dx, z + dz))
        return out

    def tile_energy(self, x: int, z: int) -> float:
        return self.energy({(x, z)}, self._around([(x, z)], [self.grid[z, x]]))

    # --- moves -----------------------------------------------------------------

    def options(self, x: int, z: int) -> set[int]:
        opts = {int(o) for o in self.candidates(x, z)}
        for dx, dz in DIRS8:
            if self._inside(x + dx, z + dz) and self.occ[z + dz, x + dx] >= 0:
                cont = self.s.shifted(int(self.occ[z + dz, x + dx]), -dx, -dz)
                if cont is not None:
                    opts.add(cont)
        return opts

    def pair_cost(self, a_occ: int, b_occ: int, dx: int, dz: int) -> float:
        """Join cost of occurrence a_occ with b_occ at offset (dx, dz) in {(1, 0), (0, 1)}."""
        if a_occ < 0 or b_occ < 0 or self.s.shifted(a_occ, dx, dz) == b_occ:
            return 0.0
        a, b = self.s.cell[a_occ], self.s.cell[b_occ]
        ok = self.H[self.pe[a], self.pw[b]] if dx else self.V[self.ps[a], self.pn[b]]
        return self.w.seam if ok else self.w.bad_seam

    def bound(self, new: dict) -> float:
        """Lower bound of the energy after placing `new` ({tile: occ}): its label costs and its
        joins (inside and with the unchanged neighbours). Every other term is non-negative."""
        total = 0.0
        for (x, z), o in new.items():
            total += float(self.unary_row(x, z)[o])
            for dx, dz in ((1, 0), (0, 1)):
                n = (x + dx, z + dz)
                if self._inside(*n):
                    total += self.pair_cost(o, new.get(n, int(self.occ[n[1], n[0]])), dx, dz)
            for dx, dz in ((-1, 0), (0, -1)):
                n = (x + dx, z + dz)
                if n not in new and self._inside(*n):
                    total += self.pair_cost(int(self.occ[n[1], n[0]]), o, -dx, -dz)
        return total

    def choose(self, x: int, z: int) -> bool:
        current = int(self.occ[z, x])
        opts = self.options(x, z)
        cells = {o: int(self.s.cell[o]) for o in opts}
        around = self._around([(x, z)] * (len(opts) + 1), [self.grid[z, x], *cells.values()])
        block = {(x, z)}
        best, best_cost = current, self.energy(block, around) if current >= 0 else float("inf")
        ranked = sorted((self.bound({(x, z): o}), o) for o in opts if o != current)
        for low, o in ranked:
            if low >= best_cost - 1e-6:
                break
            self.place(x, z, o)
            cost = self.energy(block, around)
            if cost < best_cost - 1e-6:
                best, best_cost = o, cost
        if self.occ[z, x] != best:
            self.place(x, z, best)
        return best != current

    def try_block(self, x0: int, z0: int, size: int, start: int) -> bool:
        """Paste the size x size source block whose top-left is occurrence `start`."""
        new = {}
        for z in range(z0, min(self.h, z0 + size)):
            for x in range(x0, min(self.wd, x0 + size)):
                o = self.s.shifted(start, x - x0, z - z0)
                if o is None:
                    return False
                new[(x, z)] = o
        if all(self.occ[z, x] == o for (x, z), o in new.items()):
            return False
        block = set(new)
        old = {(x, z): int(self.occ[z, x]) for (x, z) in new}
        around = self._around(list(new) * 2, [self.grid[z, x] for x, z in new]
                              + [int(self.s.cell[o]) for o in new.values()])
        before = self.energy(block, around)
        if self.bound(new) >= before - 1e-6:  # most tries end here without touching the state
            return False
        for (x, z), o in new.items():
            self.place(x, z, o)
        if self.energy(block, around) < before - 1e-6:
            return True
        for (x, z), o in old.items():
            self.place(x, z, o)
        return False

    def block_pass(self) -> int:
        changed = 0
        for size in self.w.blocks:
            hot = [(x, z) for z in range(self.h) for x in range(self.wd) if self.tile_energy(x, z) > self.w.hot]
            self.rng.shuffle(hot)
            for x, z in hot:
                if self.tile_energy(x, z) <= self.w.hot:
                    continue
                for ox, oz in {(size // 2, size // 2), (0, 0), (size - 1, size - 1), (0, size - 1), (size - 1, 0)}:
                    x0, z0 = max(0, x - ox), max(0, z - oz)
                    done = False
                    for o in self.candidates(x, z)[: self.w.block_tries]:
                        start = self.s.shifted(int(o), x0 - x, z0 - z)
                        if start is not None and self.try_block(x0, z0, size, start):
                            changed += 1
                            done = True
                            break
                    if done:
                        break
        return changed

    def relaxed_candidates(self, x: int, z: int, count: int = 40) -> np.ndarray:
        """Occurrences ranked as candidates() but with the look nearly free: what a repair may
        try where no exact-label arrangement closes a gap."""
        u = self.unary_row(x, z) - (self.w.kind - 1.0) * (self.okind != self.tkind[z, x])
        k = min(count * 6, len(u) - 1)
        best = np.argpartition(u, k)[:k]
        order = best[np.argsort(u[best], kind="stable")]
        _, first = np.unique(self.s.cell[order], return_index=True)
        return order[np.sort(first)][:count]

    def repair_pass(self, only=None) -> int:
        """Blocks from relaxed candidates around tiles that show void or a bad seam
        (or around `only`, tiles and their neighbours)."""
        changed = 0
        if only is not None:
            hot = sorted({(x + dx, z + dz) for x, z in only for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                          if self._inside(x + dx, z + dz)})
        else:
            hot = [(x, z) for z in range(self.h) for x in range(self.wd)
                   if self.void(x, z) > 0 or any(self.join(x, z, dx, dz) >= self.w.bad_seam for dx, dz in ((1, 0), (0, 1)))]
        self.rng.shuffle(hot)
        for x, z in hot:
            done = False
            for size in (2, 3, 4):
                for ox, oz in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1), (size // 2, size // 2)):
                    x0, z0 = max(0, x - ox), max(0, z - oz)
                    for o in self.relaxed_candidates(x, z):
                        start = self.s.shifted(int(o), x0 - x, z0 - z)
                        if start is not None and self.try_block(x0, z0, size, start):
                            changed += 1
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
        return changed

    def solve(self) -> np.ndarray:
        for z in range(self.h):
            for x in range(self.wd):
                self.choose(x, z)
        for sweep in range(self.w.sweeps):
            order = [(x, z) for z in range(self.h) for x in range(self.wd)]
            if sweep % 2:
                order.reverse()
            changed = sum(self.choose(x, z) for x, z in order)
            changed += self.block_pass()
            if not changed:
                break
        for _ in range(3):
            if not self.repair_pass():
                break
        return self.grid.copy()

    def report(self) -> dict:
        """Defect counts of the current grid (what the energy charges for)."""
        labels = walks = levels = seams = rigid = bare = void = 0
        for z in range(self.h):
            for x in range(self.wd):
                o = int(self.occ[z, x])
                walks += self.owalk[o] != self.twalk[z, x]
                labels += self.okind[o] != self.tkind[z, x]
                levels += (self.olevel[o] != self.tlevel[z, x]) and self.tlevel[z, x] != semantic.VOID_LEVEL
                seams += sum(self.join(x, z, dx, dz) >= self.w.bad_seam for dx, dz in ((1, 0), (0, 1)))
                rigid += self.rigid_out(x, z) > 0
                bare += self.bare(x, z) > 0
                void += self.void(x, z) > 0
        return {"walkMismatches": int(walks), "kindMismatches": int(labels), "levelMismatches": int(levels),
                "badSeams": int(seams), "overhangViolations": int(rigid), "bareTiles": int(bare),
                "voidTiles": int(void)}

    def cost_map(self) -> np.ndarray:
        return np.array([[self.tile_energy(x, z) for x in range(self.wd)] for z in range(self.h)])


def paint(kit: dict, target: semantic.SemanticMap, exclude: frozenset = frozenset(), seed: int = 0,
          weights: Weights | None = None) -> np.ndarray:
    """A grid of kit cell ids realising the semantic map."""
    return Painter(source_for(kit, exclude), target, weights, seed).solve()


def paint_with_report(kit: dict, target: semantic.SemanticMap, seed: int = 0) -> tuple[np.ndarray, dict]:
    painter = Painter(source_for(kit), target, None, seed)
    grid = painter.solve()
    return grid, painter.report()


def rank(report: dict) -> tuple:
    """Seed ranking, lower is better: route changes, then void, then visible breaks."""
    return (report["walkMismatches"], report["voidTiles"], report["overhangViolations"] + report["bareTiles"],
            report["badSeams"], report["kindMismatches"] + report["levelMismatches"])
