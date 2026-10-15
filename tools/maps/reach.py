"""Walkable reachability over a map matrix, for lint.

A flood fill over the matrix's tiles, seeded from every warp tile of every
map using that matrix (and the open tiles beside them, since door warps sit
on blocked tiles). Moves are the four directions. Blocked tiles stop the
walk, ledges (TILE_BEHAVIOR_JUMP_*) can only be crossed in their direction
and land one tile beyond, and water is open (Surf is assumed). Height layers
and bridges are ignored, so this over-approximates; lint only reports
results that vanilla does not have, which keeps the approximation useful.
"""

from __future__ import annotations

from collections import deque

from . import codecs

# behavior -> (dx, dz) a ledge can be jumped in
JUMPS = {56: (1, 0), 57: (-1, 0), 58: (0, -1), 59: (0, 1)}
# Blocked tiles the player can still cross: Rock Climb (75, 76), Whirlpool
# (17), Waterfall (19) with their HMs, and behavior 128. 128 is unnamed in
# the decomp; it is calibrated from data and is likely a height transition
# (unverified in game). With this set, vanilla has 86 unreachable events
# (gym puzzles, special dungeons) instead of 388.
PASSABLE_WHEN_BLOCKED = frozenset({17, 19, 75, 76, 128})
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Grid:
    """Collision and behavior for one matrix, flattened for fast lookup."""

    def __init__(self, world, matrix_id: int):
        matrix = world.member("matrix", matrix_id)
        self.width = matrix["width"] * codecs.TILE_GRID
        self.height = matrix["height"] * codecs.TILE_GRID
        size = self.width * self.height
        self.blocked = bytearray(b"\x01") * size   # no land = blocked
        self.behavior = bytearray(size)
        for cz, row in enumerate(matrix["landData"]):
            for cx, land_id in enumerate(row):
                if land_id == 0xFFFF or land_id >= len(world.raw["land"]):
                    continue
                tiles = world.member("land", land_id)["tiles"]
                for lz in range(codecs.TILE_GRID):
                    base = (cz * codecs.TILE_GRID + lz) * self.width + cx * codecs.TILE_GRID
                    collision = tiles["collision"][lz]
                    behaviors = bytes.fromhex(tiles["behavior"][lz].replace(" ", ""))
                    for lx in range(codecs.TILE_GRID):
                        self.behavior[base + lx] = behaviors[lx]
                        self.blocked[base + lx] = (collision[lx] == "#"
                                                   and behaviors[lx] not in PASSABLE_WHEN_BLOCKED)

    def inside(self, x: int, z: int) -> bool:
        return 0 <= x < self.width and 0 <= z < self.height

    def open(self, x: int, z: int) -> bool:
        return self.inside(x, z) and not self.blocked[z * self.width + x]

    def reachable(self, seeds) -> bytearray:
        seen = bytearray(self.width * self.height)
        queue = deque()

        def visit(x, z):
            index = z * self.width + x
            if not seen[index]:
                seen[index] = 1
                queue.append((x, z))

        for x, z in seeds:
            if not self.inside(x, z):
                continue
            visit(x, z)  # the warp tile itself counts even when blocked
            for dx, dz in DIRECTIONS:
                if self.open(x + dx, z + dz):
                    visit(x + dx, z + dz)
        while queue:
            x, z = queue.popleft()
            if self.blocked[z * self.width + x] and (x, z) not in seeds:
                continue  # a blocked seed is entered, not walked through
            for dx, dz in DIRECTIONS:
                nx, nz = x + dx, z + dz
                if not self.inside(nx, nz):
                    continue
                jump = JUMPS.get(self.behavior[nz * self.width + nx])
                if jump is not None:
                    if jump == (dx, dz) and self.open(nx + dx, nz + dz):
                        visit(nx + dx, nz + dz)
                    continue
                if self.open(nx, nz):
                    visit(nx, nz)
        return seen


def reachable_by_matrix(world) -> dict[int, tuple[Grid, bytearray]]:
    seeds: dict[int, set] = {}
    for entry in world.headers:
        if entry["matrixId"] >= len(world.raw["matrix"]) or entry["eventsBank"] >= len(world.raw["events"]):
            continue
        for warp in world.member("events", entry["eventsBank"])["warps"]:
            seeds.setdefault(entry["matrixId"], set()).add((warp["x"], warp["z"]))
    out = {}
    for matrix_id, points in seeds.items():
        grid = Grid(world, matrix_id)
        out[matrix_id] = (grid, grid.reachable(points))
    return out


def near_reachable(grid: Grid, seen: bytearray, x: int, z: int) -> bool:
    """True if the tile or a 4-neighbour can be stood on (talk/read/enter)."""
    for dx, dz in ((0, 0), *DIRECTIONS):
        nx, nz = x + dx, z + dz
        if grid.inside(nx, nz) and seen[nz * grid.width + nx]:
            return True
    return False
