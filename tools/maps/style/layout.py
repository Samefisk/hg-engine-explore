"""ASCII layouts: the intent an agent writes for a 32x32 map chunk.

32 lines of 32 characters; see documentation/map-system/style-system.md for the
class table. Lines starting with '#' are comments. `relax` frees blocked tiles
that touch other classes, so the solver can pick vanilla tree/cliff edges.
"""

from __future__ import annotations

GRID = 32
CLASSES = {".": "open", ",": "grass", "~": "water", "T": "blocked",
           "v": "ledge-south", "^": "ledge-north", "<": "ledge-west", ">": "ledge-east", "*": "any"}
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class LayoutError(ValueError):
    pass


def parse(text: str) -> list[str]:
    rows = [line.rstrip("\n") for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    if len(rows) != GRID or any(len(row) != GRID for row in rows):
        raise LayoutError(f"a layout is {GRID} rows of {GRID} characters "
                          f"(got {len(rows)} rows: {sorted({len(r) for r in rows})} wide)")
    unknown = sorted({ch for row in rows for ch in row} - set(CLASSES))
    if unknown:
        raise LayoutError(f"unknown layout characters {unknown}; allowed: {''.join(CLASSES)}")
    return rows


def relax(rows: list[str], depth: int = 1) -> list[str]:
    """Turn blocked tiles within `depth` of a non-blocked, non-any tile into '*'."""
    grid = [list(row) for row in rows]
    for _ in range(depth):
        frontier = [(x, z) for z in range(GRID) for x in range(GRID) if grid[z][x] == "T" and any(
            0 <= x + dx < GRID and 0 <= z + dz < GRID and grid[z + dz][x + dx] not in "T*"
            for dx, dz in DIRECTIONS)]
        for x, z in frontier:
            grid[z][x] = "*"
    return ["".join(row) for row in grid]


NAME_TO_CHAR = {name: ch for ch, name in CLASSES.items()}


def cell_char(cell: dict) -> str:
    """A kit cell's layout character (kits may store the character or the name)."""
    cls = cell["cls"]
    return cls if cls in CLASSES else NAME_TO_CHAR.get(cls, "?")


def render(grid: list[list[int]], kit: dict) -> list[str]:
    """The class layout a solved cell grid actually has (for diffs and reports)."""
    return ["".join(cell_char(kit["cells"][cell]) for cell in row) for row in grid]
