"""Solve a layout into vanilla cells joined only along vanilla edges.

Adjacency is edge matching (Wang tiles). Every cell side gets an edge label;
labels are merged with union-find over every neighbour pair seen in vanilla.
Two cells may touch when their facing edges share a label, so if A and A'
were both seen left of B, A' may stand wherever A's right edge fits. Exact
vanilla pairs (`strict=True`) copy vanilla strips almost verbatim and rarely
solve new layouts; edge labels generalize while seams still only join edges
vanilla joins.

Cells are filled in reading order. A candidate must fit the cell to its
left and the cell above, any pinned edge cells, and the layout class. Sets
are Python int bitmasks, so each step is a few ANDs. Dead ends backtrack a
bounded number of steps; the run then restarts with the next seed. A failure
reports where and between which classes it got stuck.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .layout import CLASSES, GRID, cell_char


@dataclass
class Model:
    right: list[int]        # cell -> mask of cells allowed to its right
    down: list[int]         # cell -> mask of cells allowed below it
    left: list[int]
    up: list[int]
    by_char: dict[str, int]  # layout char -> mask of cells of that class
    weights: list[int]
    count: int
    seen_right: list[int]   # exact vanilla pairs, for scoring
    seen_down: list[int]


def _vanilla_pairs(kit: dict, n: int):
    right, down = [0] * n, [0] * n
    pairs_h, pairs_v = set(), set()
    for grid in kit["chunks"].values():
        for z in range(GRID):
            for x in range(GRID):
                a = grid[z][x]
                if x + 1 < GRID:
                    right[a] |= 1 << grid[z][x + 1]
                    pairs_h.add((a, grid[z][x + 1]))
                if z + 1 < GRID:
                    down[a] |= 1 << grid[z + 1][x]
                    pairs_v.add((a, grid[z + 1][x]))
    return right, down, pairs_h, pairs_v


def _edge_masks(n: int, pairs: set) -> tuple[list[int], list[int]]:
    """forward[a] = cells whose near edge shares a's far edge label (and reverse)."""
    parent = list(range(2 * n))  # node a: far edge of a; node n+b: near edge of b

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        ra, rb = find(a), find(n + b)
        if ra != rb:
            parent[ra] = rb
    near_groups: dict[int, int] = {}
    far_groups: dict[int, int] = {}
    for cell in range(n):
        near_groups[find(n + cell)] = near_groups.get(find(n + cell), 0) | 1 << cell
        far_groups[find(cell)] = far_groups.get(find(cell), 0) | 1 << cell
    forward = [near_groups.get(find(cell), 0) for cell in range(n)]
    backward = [far_groups.get(find(n + cell), 0) for cell in range(n)]
    return forward, backward


def learn(kit: dict, strict: bool = False) -> Model:
    n = len(kit["cells"])
    seen_right, seen_down, pairs_h, pairs_v = _vanilla_pairs(kit, n)
    if strict:
        right, down = seen_right, seen_down
        left, up = [0] * n, [0] * n
        for a, b in pairs_h:
            left[b] |= 1 << a
        for a, b in pairs_v:
            up[b] |= 1 << a
    else:
        right, left = _edge_masks(n, pairs_h)
        down, up = _edge_masks(n, pairs_v)
    by_char = {ch: 0 for ch in CLASSES}
    for index, cell in enumerate(kit["cells"]):
        ch = cell_char(cell)
        if ch in by_char:
            by_char[ch] |= 1 << index
        by_char["*"] |= 1 << index
    return Model(right, down, left, up, by_char, [max(1, c.get("count", 1)) for c in kit["cells"]], n,
                 seen_right, seen_down)


class SolveError(RuntimeError):
    def __init__(self, message: str, where: tuple[int, int] | None = None):
        super().__init__(message)
        self.where = where


def _bits(mask: int) -> list[int]:
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def _pick(rng: random.Random, mask: int, weights: list[int]) -> list[int]:
    """Candidates in weighted-random order (vanilla frequency)."""
    cells = _bits(mask)
    keys = [rng.random() ** (1.0 / weights[c]) for c in cells]  # weighted shuffle
    return [c for _, c in sorted(zip(keys, cells), reverse=True)]


def _groups(rel: list[int]) -> list[tuple[int, int]]:
    """(cells sharing one relation mask, that mask): far fewer than cells."""
    by_mask: dict[int, int] = {}
    for cell, mask in enumerate(rel):
        if mask:
            by_mask[mask] = by_mask.get(mask, 0) | 1 << cell
    return [(cells, mask) for mask, cells in by_mask.items()]


def _support(domain: int, rel: list[int], groups: list[tuple[int, int]]) -> int:
    """Union of rel[c] over c in domain, by whichever loop is shorter."""
    out = 0
    if domain.bit_count() * 4 <= len(groups):
        for cell in _bits(domain):
            out |= rel[cell]
    else:
        for cells, mask in groups:
            if cells & domain:
                out |= mask
    return out


def solve(kit: dict, rows: list[str], seed: int = 0, edges: dict | None = None,
          model: Model | None = None, restarts: int = 8, backtrack_budget: int = 4000) -> list[list[int]]:
    """Return a 32x32 grid of kit cell indices for the layout (wave function collapse).

    edges: optional {"west"|"east"|"north"|"south": [cell index] * 32}, the
    neighbouring chunk's border cells (west = its east column, and so on).
    Collapse picks the most constrained tile, chooses a cell weighted by
    vanilla frequency, propagates arc consistency, and backtracks on a
    contradiction; after the budget it restarts with the next seed.
    """
    model = model or learn(kit)
    edges = edges or {}
    size = GRID * GRID
    initial = [0] * size
    for z in range(GRID):
        for x in range(GRID):
            mask = model.by_char[rows[z][x]]
            if x == 0 and "west" in edges:
                mask &= model.right[edges["west"][z]]
            if x == GRID - 1 and "east" in edges:
                mask &= model.left[edges["east"][z]]
            if z == 0 and "north" in edges:
                mask &= model.down[edges["north"][x]]
            if z == GRID - 1 and "south" in edges:
                mask &= model.up[edges["south"][x]]
            if not mask:
                raise SolveError(f"no vanilla cell of class {rows[z][x]!r} fits tile ({x}, {z}) "
                                 "with the pinned edges", (x, z))
            initial[z * GRID + x] = mask
    groups = {name: _groups(getattr(model, name)) for name in ("right", "left", "down", "up")}
    links = []  # per tile: (neighbour index, relation name)
    for index in range(size):
        x, z = index % GRID, index // GRID
        links.append([(index + dx + dz * GRID, name) for dx, dz, name in
                      ((1, 0, "right"), (-1, 0, "left"), (0, 1, "down"), (0, -1, "up"))
                      if 0 <= x + dx < GRID and 0 <= z + dz < GRID])

    def propagate(domains: list[int], queue: list[int]) -> int | None:
        """Arc consistency; returns the index of an emptied tile, or None."""
        pending = set(queue)
        while queue:
            index = queue.pop()
            pending.discard(index)
            for neighbour, name in links[index]:
                allowed = _support(domains[index], getattr(model, name), groups[name])
                narrowed = domains[neighbour] & allowed
                if narrowed != domains[neighbour]:
                    if not narrowed:
                        return neighbour
                    domains[neighbour] = narrowed
                    if neighbour not in pending:
                        pending.add(neighbour)
                        queue.append(neighbour)
        return None

    domains0 = list(initial)
    empty = propagate(domains0, list(range(size)))
    if empty is not None:
        x, z = empty % GRID, empty // GRID
        raise SolveError(f"the layout cannot be satisfied around tile ({x}, {z}) class {rows[z][x]!r}: "
                         "vanilla never joins these classes this way. Widen the transition with '*' "
                         "or use layout.relax().", (x, z))

    worst = None
    for attempt in range(restarts):
        rng = random.Random(seed * 1000 + attempt)
        domains = list(domains0)
        stack = []  # (snapshot before the choice, tile, chosen cell)
        budget = backtrack_budget
        while True:
            open_tiles = [(domains[i].bit_count(), i) for i in range(size) if domains[i] & (domains[i] - 1)]
            if not open_tiles:
                return [[_bits(domains[z * GRID + x])[0] for x in range(GRID)] for z in range(GRID)]
            fewest = min(count for count, _ in open_tiles)
            index = rng.choice([i for count, i in open_tiles if count == fewest])
            choice = _pick(rng, domains[index], model.weights)[0]
            snapshot = list(domains)
            domains[index] = 1 << choice
            stack.append((snapshot, index, choice))
            failed = propagate(domains, [index])
            while failed is not None:
                if worst is None or len(stack) < worst[0]:
                    worst = (len(stack), failed)
                budget -= 1
                if not stack or budget <= 0:
                    break
                snapshot, index, choice = stack.pop()
                domains = snapshot
                domains[index] &= ~(1 << choice)
                failed = index if not domains[index] else propagate(domains, [index])
            if failed is not None:
                break  # restart
    index = worst[1] if worst else 0
    x, z = index % GRID, index // GRID
    raise SolveError(f"no vanilla arrangement found after {restarts} restarts; contradictions centre "
                     f"on tile ({x}, {z}) class {rows[z][x]!r}. Widen transitions near it with '*' "
                     "or use layout.relax().", (x, z))
