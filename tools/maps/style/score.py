"""Numeric style and playability scores for a solved cell grid.

Gates (also in the design-map-look skill):
  criticalMismatches == 0  no wall/water/ledge where the layout wants a path, or vice versa
  walkableComponents == 1  open tiles form one region (no sealed pockets)
  rigidViolations == 0     no tree, cliff, ledge or slope cut off from the
                           neighbours its polygons reach into (seams.py)
  holes == 0               no tile left without the ground vanilla always had
  voidExposed == 0         no floorless void tile ('?') next to land the player stands on
  bareEdges == 0           no standable tile beside a tile no polygon touches (black void)
  heightBreaks == 0        neighbouring floor tiles meet at the same height (no gap between levels)
  seamRate >= 0.95         neighbour joins whose edge profiles continue or
                           that vanilla also has; the rest may show as a visible
                           texture or height break
  model bytes/polygons     within the game's buffer and DS limits (checked on write)

The same metrics on vanilla chunks are 0 / 1 / 0 / 0 / 1.0 by construction.
Informational: layoutMatch (cosmetic grass/ground swaps allowed), pairRate
and windowRate (exact vanilla pairs / 2x2 windows: how much is copied).
"""

from __future__ import annotations

from collections import Counter, deque

import numpy as np

from . import seams as seams_mod
from .layout import GRID, cell_char

GATES = {"criticalMismatches": 0, "walkableComponents": 1, "rigidViolations": 0, "holes": 0,
         "voidExposed": 0, "bareEdges": 0, "heightBreaks": 0, "seamRate": 0.95}
LAND = set(".,v^<>")


def void_exposed(kit: dict, grid: list[list[int]]) -> int:
    chars = [[cell_char(kit["cells"][c]) for c in row] for row in grid]
    height, width = len(chars), len(chars[0])
    return sum(chars[z][x] == "?" and any(
        0 <= x + dx < width and 0 <= z + dz < height and chars[z + dz][x + dx] in LAND
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))) for z in range(height) for x in range(width))


def vanilla_windows(kit: dict) -> set:
    windows = set()
    for grid in kit["chunks"].values():
        for z in range(GRID - 1):
            for x in range(GRID - 1):
                windows.add((grid[z][x], grid[z][x + 1], grid[z + 1][x], grid[z + 1][x + 1]))
    return windows


def vanilla_pairs(kit: dict) -> tuple[set, set]:
    h, v = set(), set()
    for grid in kit["chunks"].values():
        for z in range(GRID):
            for x in range(GRID):
                if x + 1 < GRID:
                    h.add((grid[z][x], grid[z][x + 1]))
                if z + 1 < GRID:
                    v.add((grid[z][x], grid[z + 1][x]))
    return h, v


def class_mix(kit: dict, grid: list[list[int]]) -> Counter:
    return Counter(cell_char(kit["cells"][c]) for row in grid for c in row)


def walkable_components(kit: dict, grid: list[list[int]]) -> int:
    # Land the player can stand on: floorless void ('?') and water (an enclosed pool is
    # scenery, reached by surfing if at all) do not count.
    open_ = [[not kit["cells"][c]["collision"] and cell_char(kit["cells"][c]) in LAND for c in row]
             for row in grid]
    height, width = len(grid), len(grid[0])
    seen, components = set(), 0
    for z in range(height):
        for x in range(width):
            if open_[z][x] and (x, z) not in seen:
                components += 1
                queue = deque([(x, z)])
                seen.add((x, z))
                while queue:
                    cx, cz = queue.popleft()
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, nz = cx + dx, cz + dz
                        if 0 <= nx < width and 0 <= nz < height and open_[nz][nx] and (nx, nz) not in seen:
                            seen.add((nx, nz))
                            queue.append((nx, nz))
    return components


def score(kit: dict, grid: list[list[int]], rows: list[str] | None = None,
          exclude: frozenset = frozenset(), windows: set | None = None, pairs: tuple | None = None) -> dict:
    s = seams_mod.for_kit(kit, frozenset(exclude))
    g = np.array(grid, dtype=np.int64)
    height, width = g.shape
    bad, total = s.profile_seams(g)
    windows = windows if windows is not None else vanilla_windows(kit)
    h_pairs, v_pairs = pairs if pairs is not None else vanilla_pairs(kit)
    seen = sum((grid[z][x], grid[z][x + 1]) in h_pairs for z in range(height) for x in range(width - 1))
    seen += sum((grid[z][x], grid[z + 1][x]) in v_pairs for z in range(height - 1) for x in range(width))
    window_seen = sum((grid[z][x], grid[z][x + 1], grid[z + 1][x], grid[z + 1][x + 1]) in windows
                      for z in range(height - 1) for x in range(width - 1))
    result = {
        "seamRate": round(1 - bad / total, 4),
        "badSeams": bad,
        "rigidViolations": len(s.rigid_violations(g)),
        "holes": len(s.holes(g)),
        "walkableComponents": walkable_components(kit, grid),
        "voidExposed": void_exposed(kit, grid),
        "bareEdges": len(s.bare_edges(g)),
        "heightBreaks": len(s.height_breaks(g)),
        "pairRate": round(seen / total, 4),
        "windowRate": round(window_seen / ((height - 1) * (width - 1)), 4),
        "classMix": dict(class_mix(kit, grid)),
        "distinctCells": len({c for row in grid for c in row}),
    }
    if rows is not None:
        match = sum(rows[z][x] == "*" or cell_char(kit["cells"][grid[z][x]]) == rows[z][x]
                    for z in range(height) for x in range(width))
        result["layoutMatch"] = round(match / (height * width), 4)
        from .quilt import critical_mismatches
        result["criticalMismatches"] = len(critical_mismatches(kit, grid, rows))
    return result


def passes(result: dict) -> list[str]:
    """Names of failed gates (empty = pass)."""
    failed = []
    if result["seamRate"] < GATES["seamRate"]:
        failed.append("seamRate")
    for name in ("criticalMismatches", "rigidViolations", "holes", "voidExposed", "bareEdges", "heightBreaks"):
        if result.get(name, 0) > GATES[name]:
            failed.append(name)
    if result["walkableComponents"] > GATES["walkableComponents"]:
        failed.append("walkableComponents")
    return failed


def hotspots(kit: dict, grid: list[list[int]], exclude: frozenset = frozenset(), size: int = 8,
             limit: int = 5) -> list[dict]:
    """The size x size areas with the most problems: where to look in game first."""
    s = seams_mod.for_kit(kit, frozenset(exclude))
    g = np.array(grid, dtype=np.int64)
    weight = s.seam_map(g).astype(float)
    for x, z, _, _ in s.rigid_violations(g):
        weight[z, x] += 3
    for x, z in s.holes(g) + s.bare_edges(g) + s.height_breaks(g):
        weight[z, x] += 3
    out = []
    for z0 in range(0, g.shape[0], size):
        for x0 in range(0, g.shape[1], size):
            value = float(weight[z0:z0 + size, x0:x0 + size].sum())
            if value:
                out.append({"x": [x0, x0 + size - 1], "z": [z0, z0 + size - 1], "problems": value})
    return sorted(out, key=lambda a: -a["problems"])[:limit]


# --- benchmark quality (the improvement loop's single number) ----------------

HARD_GATES = ("criticalMismatches", "rigidViolations", "holes", "voidExposed", "bareEdges", "heightBreaks",
              "walkableComponents")
GATE_PENALTY = 0.05


def summarize(cases: list[dict]) -> dict:
    """quality = mean seamRate - GATE_PENALTY per failed hard gate, over every case and seed."""
    values, failures, seconds = [], 0, 0.0
    for case in cases:
        for s in case["seeds"]:
            hard = [g for g in s["failed"] if g in HARD_GATES]
            failures += len(hard)
            values.append(s["seamRate"] - GATE_PENALTY * len(hard))
            seconds += s["seconds"]
    return {"quality": round(sum(values) / len(values), 5), "hardGateFailures": failures,
            "meanSeamRate": round(sum(s["seamRate"] for c in cases for s in c["seeds"]) / len(values), 5),
            "seconds": round(seconds, 1)}
