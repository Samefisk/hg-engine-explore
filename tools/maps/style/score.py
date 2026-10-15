"""Numeric style and playability scores for a solved cell grid.

Gates (also in the design-map-look skill):
  criticalMismatches == 0  no wall/water/ledge where the layout wants a path, or vice versa
  walkableComponents == 1  open tiles form one region (no sealed pockets)
  edgeRate >= 0.93         neighbour pairs joined along a vanilla edge label;
                           the rest are seams where a visible join can appear
  model bytes/polygons     within the game's buffer and DS limits (checked on write)

Informational: layoutMatch (cosmetic grass/ground swaps allowed), pairRate
and windowRate (exact vanilla pairs / 2x2 windows: how much is copied).
"""

from __future__ import annotations

from collections import Counter, deque

from .layout import GRID
from .wfc import Model, cell_char, learn

GATES = {"criticalMismatches": 0, "walkableComponents": 1, "edgeRate": 0.93}


def vanilla_windows(kit: dict) -> set:
    windows = set()
    for grid in kit["chunks"].values():
        for z in range(GRID - 1):
            for x in range(GRID - 1):
                windows.add((grid[z][x], grid[z][x + 1], grid[z + 1][x], grid[z + 1][x + 1]))
    return windows


def class_mix(kit: dict, grid: list[list[int]]) -> Counter:
    return Counter(cell_char(kit["cells"][c]) for row in grid for c in row)


def vanilla_class_mix(kit: dict) -> Counter:
    total = Counter()
    for grid in kit["chunks"].values():
        total += class_mix(kit, grid)
    return total


def walkable_components(kit: dict, grid: list[list[int]]) -> int:
    open_ = [[not kit["cells"][c]["collision"] for c in row] for row in grid]
    seen, components = set(), 0
    for z in range(GRID):
        for x in range(GRID):
            if open_[z][x] and (x, z) not in seen:
                components += 1
                queue = deque([(x, z)])
                seen.add((x, z))
                while queue:
                    cx, cz = queue.popleft()
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, nz = cx + dx, cz + dz
                        if 0 <= nx < GRID and 0 <= nz < GRID and open_[nz][nx] and (nx, nz) not in seen:
                            seen.add((nx, nz))
                            queue.append((nx, nz))
    return components


def score(kit: dict, grid: list[list[int]], rows: list[str] | None = None,
          model: Model | None = None, windows: set | None = None) -> dict:
    model = model or learn(kit)
    windows = windows if windows is not None else vanilla_windows(kit)
    pairs = seen_pairs = edge_ok = 0
    for z in range(GRID):
        for x in range(GRID):
            a = grid[z][x]
            for b, allowed, seen in ((grid[z][x + 1] if x + 1 < GRID else None, model.right, model.seen_right),
                                     (grid[z + 1][x] if z + 1 < GRID else None, model.down, model.seen_down)):
                if b is None:
                    continue
                pairs += 1
                edge_ok += bool(allowed[a] >> b & 1)
                seen_pairs += bool(seen[a] >> b & 1)
    window_total = (GRID - 1) ** 2
    window_seen = sum((grid[z][x], grid[z][x + 1], grid[z + 1][x], grid[z + 1][x + 1]) in windows
                      for z in range(GRID - 1) for x in range(GRID - 1))
    mix = class_mix(kit, grid)
    result = {
        "edgeRate": round(edge_ok / pairs, 4),
        "pairRate": round(seen_pairs / pairs, 4),
        "windowRate": round(window_seen / window_total, 4),
        "walkableComponents": walkable_components(kit, grid),
        "classMix": dict(mix),
        "distinctCells": len({c for row in grid for c in row}),
    }
    if rows is not None:
        match = sum(rows[z][x] == "*" or cell_char(kit["cells"][grid[z][x]]) == rows[z][x]
                    for z in range(GRID) for x in range(GRID))
        result["layoutMatch"] = round(match / (GRID * GRID), 4)
        from .quilt import critical_mismatches
        result["criticalMismatches"] = len(critical_mismatches(kit, grid, rows))
    return result


def passes(result: dict) -> list[str]:
    """Names of failed gates (empty = pass)."""
    failed = []
    if result["edgeRate"] < GATES["edgeRate"]:
        failed.append("edgeRate")
    if result.get("criticalMismatches", 0) > GATES["criticalMismatches"]:
        failed.append("criticalMismatches")
    if result["walkableComponents"] > GATES["walkableComponents"]:
        failed.append("walkableComponents")
    return failed
