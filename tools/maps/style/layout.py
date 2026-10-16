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
    """A layout of 32*H rows by 32*W columns (H x W chunks, reading order)."""
    rows = [line.rstrip("\n") for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    widths = {len(row) for row in rows}
    if not rows or len(rows) % GRID or len(widths) != 1 or widths.pop() % GRID:
        raise LayoutError(f"a layout is a multiple of {GRID} rows by a multiple of {GRID} columns, "
                          f"all rows equal (got {len(rows)} rows, widths {sorted({len(r) for r in rows})})")
    unknown = sorted({ch for row in rows for ch in row} - set(CLASSES))
    if unknown:
        raise LayoutError(f"unknown layout characters {unknown}; allowed: {''.join(CLASSES)}")
    return rows


def chunks(rows: list[str]) -> list[tuple[int, int, list[str]]]:
    """(chunk x, chunk z, 32x32 rows) in reading order."""
    return [(cx, cz, [row[cx * GRID:(cx + 1) * GRID] for row in rows[cz * GRID:(cz + 1) * GRID]])
            for cz in range(len(rows) // GRID) for cx in range(len(rows[0]) // GRID)]


def relax(rows: list[str], depth: int = 1) -> list[str]:
    """Turn blocked tiles within `depth` of a non-blocked, non-any tile into '*'."""
    grid = [list(row) for row in rows]
    height, width = len(grid), len(grid[0])
    for _ in range(depth):
        frontier = [(x, z) for z in range(height) for x in range(width) if grid[z][x] == "T" and any(
            0 <= x + dx < width and 0 <= z + dz < height and grid[z + dz][x + dx] not in "T*"
            for dx, dz in DIRECTIONS)]
        for x, z in frontier:
            grid[z][x] = "*"
    return ["".join(row) for row in grid]


NAME_TO_CHAR = {name: ch for ch, name in CLASSES.items()}


WALKABLE_CHARS = set(".,~v^<>")


def cell_char(cell: dict) -> str:
    """A kit cell's layout character (kits may store the character or the name).

    Walkable cells without a floor (no BDHC under the tile, e.g. the void
    around cave rooms) are '?' so the solver never uses them for a path.
    """
    cls = cell["cls"]
    ch = cls if cls in CLASSES else NAME_TO_CHAR.get(cls, "?")
    if ch in WALKABLE_CHARS and "corners" in cell and (
            cell["corners"] is None or any(v is None for v in cell["corners"])):
        return "?"
    return ch


def render(grid: list[list[int]], kit: dict) -> list[str]:
    """The class layout a solved cell grid actually has (for diffs and reports)."""
    return ["".join(cell_char(kit["cells"][cell]) for cell in row) for row in grid]
