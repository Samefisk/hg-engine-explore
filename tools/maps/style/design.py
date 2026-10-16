"""Design a map from gameplay intent: brief -> intent map -> semantic map.

  python3 -B -m tools.maps.style.design --brief B.json --out S.txt [--plan P.json] [--preview]

A brief (JSON) says what the map is for; the designer decides where things go:

  {"template": 33,                 # map whose tileset (look) the map uses
   "kind": "route",                # "route" (outdoor) or "cave"
   "chunks": [2, 2],               # width, height in 32-tile chunks
   "seed": 3,
   "exits": [{"side": "south", "at": 32, "width": 2}, {"side": "north", "at": 20}],
   "wander": 0.6,                  # 0 straight .. 1 very winding route
   "width": [3, 6],                # corridor half-width range (tiles)
   "clearings": 3,                 # wide open spots along the route
   "grass": 4,                     # tall-grass patches (encounters)
   "pond": 1, "flowers": 3, "clumps": 4, "ledge": 1, "path": "exits" | "full" | "none",
   "trainers": 2, "items": 2}

1. plan(): an intent map, one char per tile from INTENTS, drawn with
   smooth noise so edges are organic, never rulers and rectangles. Outdoor
   blocked land is trees (T), snapped to 2x2 blocks, the size of a vanilla tree;
   a cave's blocked land is rock mass (X), which refine turns into wall bands,
   rims and the dark outside.
2. refine(): the intent map becomes a full semantic map (semantic.py) by
   copying label arrangements from the template tileset's vanilla chunks
   (texture-by-numbers at label level, like paint.py at cell level). This is
   what adds a cave's wall band and rim around the floor, or the shape of a
   pond's shore, exactly as vanilla draws them. Every 2x2 label window must be
   one vanilla uses (else no cells exist for it): refine moves an edge by a
   tile rather than keep a window the painter cannot realise.
3. check(): gameplay facts on the result: every exit reaches every other
   (ledges are one-way), tall grass amount, trainer sight lines, item spots.
   The plan (exits, trainers, items) is written as JSON for the events step.

Everything is seeded: the same brief gives the same map.
"""

from __future__ import annotations

import argparse
import heapq
import json
import random
import sys
from collections import Counter, deque
from pathlib import Path

import numpy as np

from .. import world
from . import kit as kits
from . import semantic

REPO = Path(__file__).resolve().parents[3]
GRID = 32
BLOCKED, TREES, GROUND, PATH, TALL, FLOWERS, LIGHT, WATER, ROCK = "X", "T", ".", "=", ",", "*", "g", "~", "o"
LEDGES = "v^<>"
RIVER, SEA, OUTSIDE = "%", "s", "R"
INTENTS = OUTSIDE + BLOCKED + TREES + GROUND + PATH + TALL + FLOWERS + LIGHT + WATER + RIVER + SEA + ROCK + LEDGES + "bO"
WALKABLE_INTENTS = set(GROUND + PATH + TALL + FLOWERS + LIGHT + "bO")
CAVE_GAP = 6  # rock rows a cave needs between two open areas (face + rim)
CAVE_SIDE = 3  # rock columns between two open areas
CAVE_ISLAND = 6
NORTH_BORDER = 5  # tiles of border the camera needs beyond open land on a standalone map
SOUTH_BORDER = 5
SIDE_BORDER = 3
LEDGE_STEP = {"v": (0, 1), "^": (0, -1), "<": (-1, 0), ">": (1, 0)}


# --- intents of vanilla labels ------------------------------------------------

def intent_of(kind: str, walk: str) -> str:
    """The designer-level intent a vanilla label realises."""
    if walk in LEDGES:
        return walk
    if walk == "~":
        return kind if kind in (RIVER, SEA) else WATER
    if walk in "T?":
        if kind == "o":
            return ROCK
        if kind == OUTSIDE:
            return OUTSIDE
        return TREES if kind in ("T", "Y") else BLOCKED
    # Walkable tiles keep their look: grass ground, a cave's floor and a dark floor differ.
    if kind in (semantic.VOID[1], "?", "T", "Y", "#", "W", "~", "%", "s"):
        return GROUND
    return kind


# --- noise and geometry -------------------------------------------------------

def smooth_noise(shape, scale: float, rng: random.Random) -> np.ndarray:
    """Value noise in [0, 1] with features about `scale` tiles across."""
    h, w = shape
    gh, gw = int(h / scale) + 3, int(w / scale) + 3
    base = np.array([[rng.random() for _ in range(gw)] for _ in range(gh)])
    zs, xs = np.arange(h) / scale, np.arange(w) / scale
    z0, x0 = zs.astype(int), xs.astype(int)
    tz, tx = zs - z0, xs - x0
    tz, tx = tz * tz * (3 - 2 * tz), tx * tx * (3 - 2 * tx)
    a = base[z0][:, x0] * (1 - tx) + base[z0][:, x0 + 1] * tx
    b = base[z0 + 1][:, x0] * (1 - tx) + base[z0 + 1][:, x0 + 1] * tx
    return a * (1 - tz)[:, None] + b * tz[:, None]


def distance(mask: np.ndarray) -> np.ndarray:
    """Chessboard-ish (8-way BFS) distance of every tile to the nearest True tile."""
    h, w = mask.shape
    dist = np.full((h, w), 10 ** 6, dtype=np.int64)
    q = deque()
    for z, x in zip(*np.nonzero(mask)):
        dist[z, x] = 0
        q.append((int(z), int(x)))
    while q:
        z, x = q.popleft()
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nz, nx = z + dz, x + dx
                if 0 <= nz < h and 0 <= nx < w and dist[nz, nx] > dist[z, x] + 1:
                    dist[nz, nx] = dist[z, x] + 1
                    q.append((nz, nx))
    return dist


def cheapest_path(cost: np.ndarray, start, goal) -> list[tuple[int, int]]:
    """4-way Dijkstra over a positive cost field; (x, z) tuples from start to goal."""
    h, w = cost.shape
    best = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        d, (x, z) = heapq.heappop(heap)
        if (x, z) == goal:
            break
        if d > best.get((x, z), float("inf")):
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if 0 <= nx < w and 0 <= nz < h:
                nd = d + float(cost[nz, nx])
                if nd < best.get((nx, nz), float("inf")):
                    best[(nx, nz)] = nd
                    prev[(nx, nz)] = (x, z)
                    heapq.heappush(heap, (nd, (nx, nz)))
    out = [goal]
    while out[-1] != start:
        out.append(prev[out[-1]])
    return out[::-1]


def _l_path(a, b, rng: random.Random) -> list[tuple[int, int]]:
    """Tiles of an L from a to b (x, z): one horizontal and one vertical leg, either order."""
    (ax, az), (bx, bz) = a, b
    corner = (bx, az) if rng.random() < 0.5 else (ax, bz)
    out = [a]
    for start, end in ((a, corner), (corner, b)):
        x, z = start
        while (x, z) != end:
            x += int(np.sign(end[0] - x))
            z += int(np.sign(end[1] - z))
            out.append((x, z))
    return out


def exit_tiles(exit_: dict, w: int, h: int) -> list[tuple[int, int]]:
    """Edge tiles of an exit, (x, z)."""
    width = exit_.get("width", 2)
    at = exit_["at"]
    side = exit_["side"]
    span = range(at - width // 2, at - width // 2 + width)
    if side == "north":
        return [(x, 0) for x in span]
    if side == "south":
        return [(x, h - 1) for x in span]
    if side == "west":
        return [(0, z) for z in span]
    if side == "east":
        return [(w - 1, z) for z in span]
    raise ValueError(f"exit side must be north/south/east/west, not {side!r}")


def _inward(side: str) -> tuple[int, int]:
    return {"north": (0, 1), "south": (0, -1), "west": (1, 0), "east": (-1, 0)}[side]


def _rects(shape, centre, radius: float, rng: random.Random, parts: int = 2) -> np.ndarray:
    """Union of 1..parts axis-aligned rectangles around centre, about 2*radius across.
    Vanilla draws ponds, tall grass and flower beds as rectangles: an organic outline
    asks for edge pieces vanilla does not have."""
    h, w = shape
    out = np.zeros(shape, dtype=bool)
    cx, cz = centre
    for i in range(rng.randint(1, parts)):
        rw = max(1, round(radius * rng.uniform(0.7, 1.2)))
        rh = max(1, round(radius * rng.uniform(0.6, 1.0)))
        ox = 0 if i == 0 else rng.randint(-rw, rw)
        oz = 0 if i == 0 else rng.randint(-rh, rh)
        out[max(0, cz + oz - rh):min(h, cz + oz + rh), max(0, cx + ox - rw):min(w, cx + ox + rw)] = True
    return out


def _blob(shape, centre, radius: float, rng: random.Random, rough: float = 0.35) -> np.ndarray:
    h, w = shape
    noise = smooth_noise(shape, max(2.0, radius / 1.5), rng)
    zs, xs = np.mgrid[0:h, 0:w]
    d = np.hypot(xs - centre[0], zs - centre[1])
    return d < radius * (1 - rough + 2 * rough * noise)


# --- plan -------------------------------------------------------------------------

class Plan:
    def __init__(self, intent: np.ndarray, level: np.ndarray, route: list, exits: list, notes: dict):
        self.intent, self.level, self.route, self.exits, self.notes = intent, level, route, exits, notes

    def text(self) -> str:
        return "\n".join("".join(row) for row in self.intent)


def plan(brief: dict, ground: str = GROUND, base_level: int = 0, water_kind: str = WATER) -> Plan:
    rng = random.Random(brief.get("seed", 0))
    cw, ch = brief.get("chunks", [1, 1])
    w, h = cw * GRID, ch * GRID
    kind = brief.get("kind", "route")
    exits = brief["exits"]
    if len(exits) < 1:
        raise ValueError("a brief needs at least one exit")
    mass = BLOCKED if kind == "cave" else TREES  # what fills everything that is not open
    intent = np.full((h, w), mass, dtype="<U1")
    margin = 3
    # Route: exits joined in order through random waypoints, over a noisy cost field.
    wander = float(brief.get("wander", 0.5))
    noise = smooth_noise((h, w), 6.0, rng)
    cost = 1.0 + wander * 12.0 * noise
    cost[:margin, :] += 50
    cost[-margin:, :] += 50
    cost[:, :margin] += 50
    cost[:, -margin:] += 50
    ends = []
    for e in exits:
        tiles = exit_tiles(e, w, h)
        mid = tiles[len(tiles) // 2]
        dx, dz = _inward(e["side"])
        ends.append((mid, (mid[0] + dx * (margin + 1), mid[1] + dz * (margin + 1)), tiles))
    clearings = int(brief.get("clearings", 2))
    # Waypoints spread over the map (farthest-point sampling): the route uses the space.
    waypoints = []
    pool = [(x, z) for z in range(margin + 6, h - margin - 6, 2) for x in range(margin + 6, w - margin - 6, 2)]
    anchors = [e[1] for e in ends]
    for _ in range(max(clearings, 1 if len(ends) < 2 else 0)):
        if not pool:
            break
        far = sorted(pool, key=lambda p: -min(abs(p[0] - a[0]) + abs(p[1] - a[1]) for a in anchors + waypoints))
        pick = far[rng.randrange(min(4, len(far)))]
        waypoints.append(pick)
    stops = [ends[0][1]]
    rest = waypoints[:]
    for e in ends[1:]:
        # Visit waypoints roughly on the way: nearest first.
        while rest:
            here = stops[-1]
            nxt = min(rest, key=lambda p: abs(p[0] - here[0]) + abs(p[1] - here[1]))
            if abs(nxt[0] - e[1][0]) + abs(nxt[1] - e[1][1]) > abs(here[0] - e[1][0]) + abs(here[1] - e[1][1]) + 12 \
                    and len(rest) <= len(waypoints) // 2:
                break
            stops.append(nxt)
            rest.remove(nxt)
        stops.append(e[1])
    stops += rest
    route = []
    for a, b in zip(stops, stops[1:]):
        # Caves are dug in straight runs (vanilla cave walls are long and square-cornered):
        # an L of a horizontal and a vertical leg. Outdoor routes wander over the noise.
        seg = _l_path(a, b, rng) if kind == "cave" else cheapest_path(cost, a, b)
        route += seg if not route else seg[1:]
    for mid, inner, tiles in ends:
        for t in tiles:
            x, z = t
            while (x, z) != inner and 0 <= x < w and 0 <= z < h:
                route.append((x, z))
                x += int(np.sign(inner[0] - x)) if (x, z)[0] != inner[0] else 0
                z += int(np.sign(inner[1] - z)) if (x, z)[1] != inner[1] else 0
            route.append(inner)
    on_route = np.zeros((h, w), dtype=bool)
    for x, z in route:
        on_route[z, x] = True
    lo, hi = brief.get("width", [2, 5] if kind == "cave" else [3, 6])
    if kind == "cave":
        # Corridors of one width per leg, rectangular rooms at the waypoints.
        open_ = np.zeros((h, w), dtype=bool)
        half = max(1, int(hi) // 2)
        for x, z in route:
            open_[max(0, z - half):z + half + 1, max(0, x - half):x + half + 1] = True
        for wx, wz in waypoints[:clearings]:
            rw, rh = rng.randint(3, 5), rng.randint(3, 5)
            open_[max(0, wz - rh):wz + rh + 1, max(0, wx - rw):wx + rw + 1] = True
    else:
        # Corridor: route dilated by a noisy half-width; clearings at the waypoints.
        dist = distance(on_route)
        width_noise = smooth_noise((h, w), 8.0, rng)
        open_ = dist <= lo + (hi - lo) * width_noise
        for wp in waypoints[:clearings]:
            open_ |= _blob((h, w), wp, rng.uniform(5, 8), rng)
    for mid, inner, tiles in ends:
        for x, z in tiles:
            open_[z, x] = True
    keep = np.zeros((h, w), dtype=bool)
    keep[1:-1, 1:-1] = True
    # The field camera looks north past the top rows and sees a few rows past the others:
    # a standalone map needs that much border, or the void beyond its edge shows.
    keep[:NORTH_BORDER, :] = False
    keep[-SOUTH_BORDER:, :] = False
    keep[:, :SIDE_BORDER] = keep[:, -SIDE_BORDER:] = False
    keep |= distance(on_route) <= 1  # an exit's way in crosses the border
    keep[0, :] = keep[-1, :] = False  # but the edge itself opens only at exit tiles
    keep[:, 0] = keep[:, -1] = False
    for _, _, tiles in ends:
        for x, z in tiles:
            keep[z, x] = True
    open_ &= keep
    if kind == "cave":
        # A wall between two open areas needs room for the north area's front face and the
        # south area's rim: vanilla never puts corridors closer than CAVE_GAP rows apart.
        # A thinner rock strip in a column becomes floor (the corridors merge into a room).
        for x in range(w):
            z = 0
            while z < h:
                if not open_[z, x]:
                    start = z
                    while z < h and not open_[z, x]:
                        z += 1
                    if start > 0 and z < h and z - start < CAVE_GAP:
                        open_[start:z, x] = True
                else:
                    z += 1
        for z in range(h):  # side walls need a face and a rim too: at least CAVE_SIDE columns
            x = 0
            while x < w:
                if not open_[z, x]:
                    start = x
                    while x < w and not open_[z, x]:
                        x += 1
                    if start > 0 and x < w and x - start < CAVE_SIDE:
                        open_[z, start:x] = True
                else:
                    x += 1
        # Rock islands smaller than CAVE_ISLAND tiles are not vanilla walls: floor them.
        seen = np.zeros_like(open_)
        for z0, x0 in zip(*np.nonzero(~open_)):
            if seen[z0, x0]:
                continue
            comp, q = [], deque([(z0, x0)])
            seen[z0, x0] = True
            while q:
                z, x = q.popleft()
                comp.append((z, x))
                for nz, nx in ((z + 1, x), (z - 1, x), (z, x + 1), (z, x - 1)):
                    if 0 <= nz < h and 0 <= nx < w and not open_[nz, nx] and not seen[nz, nx]:
                        seen[nz, nx] = True
                        q.append((nz, nx))
            if len(comp) < CAVE_ISLAND:
                for z, x in comp:
                    open_[z, x] = True
        open_ &= keep
    if kind != "cave":
        # Vanilla trees stand on 2x2 tiles: snap open land to 2x2 blocks, aligned to the grid.
        blocks = open_.reshape(h // 2, 2, w // 2, 2).any(axis=(1, 3))
        open_ = np.repeat(np.repeat(blocks, 2, axis=0), 2, axis=1) & keep
        for _, _, tiles in ends:  # exits keep their exact width
            for x, z in tiles:
                open_[z, x] = True
    intent[open_] = ground
    level = np.full((h, w), base_level, dtype=np.int64)
    notes = {"routeTiles": len(set(route))}
    route_set = set(route)
    near_route = distance(on_route)

    def free_spot(min_route: int, max_route: int, radius: int, tries: int = 200):
        for _ in range(tries):
            x, z = rng.randrange(4, w - 4), rng.randrange(4, h - 4)
            if not (min_route <= near_route[z, x] <= max_route):
                continue
            zz, xx = slice(max(0, z - radius), z + radius + 1), slice(max(0, x - radius), x + radius + 1)
            if (intent[zz, xx] == ground).all():
                return x, z
        return None

    # Ponds: water near the route in a clearing of their own (ground ring), joined to the route.
    for n in range(int(brief.get("pond", 0))):
        radius = float(brief.get("pondSize", 4.0)) * rng.uniform(0.8, 1.25)
        spots = [(x, z) for z in range(margin + 4, h - margin - 4) for x in range(margin + 4, w - margin - 4)
                 if radius + 3 <= near_route[z, x] <= radius + 8 and (intent[z, x] in (ground, mass))]
        if not spots:
            continue
        spot = spots[rng.randrange(len(spots))]
        water = _rects((h, w), spot, radius, rng, parts=1)
        ring = (distance(water) <= 2) & ~water
        inner = np.zeros((h, w), dtype=bool)
        inner[margin:h - margin, margin:w - margin] = True
        water &= inner
        intent[ring & inner & (intent == mass)] = ground
        intent[water] = water_kind
        # A trodden way from the pond's ring to the route.
        ring_tiles = list(zip(*np.nonzero(ring & inner)))
        if ring_tiles:
            rz, rx = min(ring_tiles, key=lambda t: near_route[t[0], t[1]])
            target = min(route, key=lambda p: abs(p[0] - rx) + abs(p[1] - rz))
            for x, z in cheapest_path(np.where(intent == WATER, 1000.0, 1.0), (int(rx), int(rz)), target):
                for dz in (0, 1):
                    for dx in (0, 1):
                        if 0 <= x + dx < w and 0 <= z + dz < h and intent[z + dz, x + dx] == mass:
                            intent[z + dz, x + dx] = ground
        notes["ponds"] = notes.get("ponds", 0) + 1
    # Tall grass beside and across the route: encounter zones.
    for _ in range(int(brief.get("grass", 2))):
        spot = free_spot(0, 4, 1)
        if spot:
            patch = _rects((h, w), spot, rng.uniform(2.5, 4.5), rng) & (intent == ground)
            intent[patch] = TALL
    for _ in range(int(brief.get("flowers", 0))):
        spot = free_spot(1, 8, 1)
        if spot:
            intent[_rects((h, w), spot, rng.uniform(1.0, 2.0), rng, parts=1) & (intent == ground)] = FLOWERS
    # Tree clumps / rock piles inside open land, never on the route.
    for _ in range(int(brief.get("clumps", 0))):
        spot = free_spot(3, 10, 2)
        if spot:
            x, z = spot[0] // 2 * 2, spot[1] // 2 * 2
            size = rng.choice([2, 2, 4])
            box = (slice(z, z + size), slice(x, x + size))
            if (intent[box] == ground).all() and not any((xx, zz) in route_set for zz in range(z, z + size)
                                                           for xx in range(x, x + size)):
                intent[box] = TREES if kind != "cave" else ROCK
    if kind == "cave":
        for _ in range(int(brief.get("rocks", 3))):
            spot = free_spot(2, 6, 1)
            if spot:
                intent[spot[1], spot[0]] = ROCK
    # Path: the trodden route near the exits (or all of it).
    path_mode = brief.get("path", "exits" if kind != "cave" else "none")
    if path_mode != "none":
        steps = {p: i for i, p in enumerate(route)}
        for (x, z), i in steps.items():
            if path_mode == "full" or any(abs(x - t[0]) + abs(z - t[1]) <= 10 for _, _, ts in ends for t in ts):
                for dz in (0, 1):
                    for dx in (0, 1):
                        nx, nz = x + dx, z + dz
                        if 0 <= nx < w and 0 <= nz < h and intent[nz, nx] in (ground, TALL):
                            intent[nz, nx] = PATH
    # Ledge: a one-way drop across part of a wide open stretch, with a way around.
    for _ in range(int(brief.get("ledge", 0))):
        placed = False
        for _ in range(300):
            z = rng.randrange(6, h - 6)
            row = intent[z]
            runs, start = [], None
            for x in range(w + 1):
                inside = x < w and row[x] in (ground, TALL) and _walkable(intent[z - 1, x]) and _walkable(intent[z + 1, x])
                if inside and start is None:
                    start = x
                if not inside and start is not None:
                    runs.append((start, x))
                    start = None
            runs = [r for r in runs if r[1] - r[0] >= 8]
            if not runs:
                continue
            a, b = rng.choice(runs)
            cut = rng.randrange(a + 3, b - 3)
            span = range(a, cut) if rng.random() < 0.5 else range(cut, b)
            trial = intent.copy()
            for x in span:
                trial[z, x] = "v"
            if _reaches_all(trial, ends, ground):
                intent = trial
                placed = True
                notes.setdefault("ledgeTiles", []).append([[x, z] for x in span])
                break
        notes.setdefault("ledges", 0)
        notes["ledges"] += placed
    if kind == "cave":
        # Rock beyond the wall band is the dark outside (vanilla's d_ro), not more wall.
        far = distance(intent != BLOCKED) > 3
        intent[far & (intent == BLOCKED)] = OUTSIDE
    return Plan(intent, level, route, ends, notes)


# --- walking ------------------------------------------------------------------

def _walkable(c: str) -> bool:
    return c in WALKABLE_INTENTS or c in LEDGES


def reachable(intent: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    """Tiles reachable from start; a ledge is entered only moving in its direction and
    carries the player one tile further (the game's jump)."""
    h, w = intent.shape
    seen = np.zeros((h, w), dtype=bool)
    q = deque([start])
    seen[start[1], start[0]] = True
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (0 <= nx < w and 0 <= nz < h):
                continue
            c = intent[nz, nx]
            if c in LEDGES:
                if LEDGE_STEP[c] != (dx, dz):
                    continue
                nx, nz = nx + dx, nz + dz
                if not (0 <= nx < w and 0 <= nz < h) or not _walkable(intent[nz, nx]) or intent[nz, nx] in LEDGES:
                    continue
            elif not _walkable(c):
                continue
            if not seen[nz, nx]:
                seen[nz, nx] = True
                q.append((nx, nz))
    return seen


def _reaches_all(intent: np.ndarray, ends, ground: str) -> bool:
    for i, (_, _, a) in enumerate(ends):
        seen = reachable(intent, a[0])
        for j, (_, _, b) in enumerate(ends):
            if i != j and not seen[b[0][1], b[0][0]]:
                return False
    return True


# --- refine: intents -> semantic labels -------------------------------------------

class LabelSource:
    """Vanilla semantic labels of a tileset's chunks, as occurrences (like paint.Source)."""

    DIRS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

    def __init__(self, kit: dict, exclude: frozenset = frozenset(), own: frozenset = frozenset()):
        """own: the template map's chunks; their arrangements are preferred (OWN_BONUS)."""
        self.labels: dict[tuple, int] = {}
        self.own = frozenset(own)
        labs, where, self.index = [], [], {}
        self.maps = {}
        for land in sorted(kit["chunks"]):
            if land in exclude:
                continue
            sem = semantic.extract(kit, kit["chunks"][land])
            self.maps[land] = sem
            for z in range(GRID):
                for x in range(GRID):
                    self.index[(land, x, z)] = len(labs)
                    labs.append(self.labels.setdefault(sem.label(x, z), len(self.labels)))
                    where.append((land, x, z))
        self.lab = np.array(labs)
        self.where = where
        self.parts = {i: k for k, i in self.labels.items()}
        intent_of_label = np.array([intent_of(k[0], k[2]) for k in (self.parts[i] for i in range(len(self.parts)))])
        level_of_label = np.array([self.parts[i][1] for i in range(len(self.parts))])
        self.intent = intent_of_label[self.lab]
        self.level = level_of_label[self.lab]
        nbr = []
        for land, x, z in where:
            row = []
            for dx, dz in self.DIRS8:
                o = self.index.get((land, x + dx, z + dz))
                row.append(self.intent[o] if o is not None else "")
            nbr.append(row)
        self.nbr = np.array(nbr)
        self.h_pairs, self.v_pairs = set(), set()
        for land, sem in self.maps.items():
            for z in range(GRID):
                for x in range(GRID):
                    a = self.labels[sem.label(x, z)]
                    if x + 1 < GRID:
                        self.h_pairs.add((a, self.labels[sem.label(x + 1, z)]))
                    if z + 1 < GRID:
                        self.v_pairs.add((a, self.labels[sem.label(x, z + 1)]))
        self.windows = Counter()  # 2x2 label windows (nw, ne, sw, se) vanilla uses
        self.windows3 = set()  # 3x3 label windows, row by row
        for land, sem in self.maps.items():
            lab = [[self.labels[sem.label(x, z)] for x in range(GRID)] for z in range(GRID)]
            for z in range(GRID - 1):
                for x in range(GRID - 1):
                    self.windows[(lab[z][x], lab[z][x + 1], lab[z + 1][x], lab[z + 1][x + 1])] += 1
            for z in range(GRID - 2):
                for x in range(GRID - 2):
                    self.windows3.add(tuple(lab[z + i][x + j] for i in range(3) for j in range(3)))
        self.counts = Counter(self.intent.tolist())
        mine = np.array([w[0] in self.own for w in where])
        self.foreign = ~mine if mine.any() else np.zeros(len(where), dtype=bool)
        self.own_counts = Counter(self.intent[mine].tolist()) if mine.any() else self.counts
        self.own_level = self.level[mine] if mine.any() else self.level
        self.own_intent = self.intent[mine] if mine.any() else self.intent

    def shifted(self, occ: int, dx: int, dz: int):
        land, x, z = self.where[occ]
        return self.index.get((land, x + dx, z + dz))

    def ground_intent(self) -> str:
        """The template map's most common walkable look (grass outdoors, a cave's floor)."""
        walk = {k: v for k, v in self.own_counts.items() if k not in (BLOCKED, OUTSIDE, TREES, ROCK, WATER, RIVER, SEA)
                and k not in LEDGES and k not in (TALL, FLOWERS, LIGHT)}
        return max(walk, key=walk.get) if walk else GROUND

    def water_intent(self) -> str:
        """The template's own water look (Union Cave's water is sea-kind, a route's a pond)."""
        water = {k: v for k, v in self.own_counts.items() if k in (WATER, RIVER, SEA)}
        return max(water, key=water.get) if water else WATER

    def base_level(self, ground: str) -> int:
        levels = Counter(self.own_level[self.own_intent == ground].tolist())
        return levels.most_common(1)[0][0] if levels else 0


def refine(source: LabelSource, intent: np.ndarray, level: np.ndarray | None = None, seed: int = 0,
           sweeps: int = 6, candidates: int = 40) -> semantic.SemanticMap:
    """Semantic labels realising an intent map, copied from vanilla label arrangements."""
    rng = random.Random(seed)
    h, w = intent.shape
    s = source
    W_INTENT, W_LEVEL, W_CTX, W_SEAM, W_BAD, W_WINDOW, W_FOREIGN = 30.0, 20.0, 1.5, 1.0, 12.0, 20.0, 3.0
    W_WINDOW3 = 8.0
    unary_rows, cands = {}, {}

    def unary_row(x, z):
        if (x, z) not in unary_rows:
            want = intent[z, x]
            c = W_INTENT * (s.intent != want).astype(np.float32) + W_FOREIGN * s.foreign
            if level is not None and want not in (BLOCKED, OUTSIDE):
                c += W_LEVEL * (s.level != level[z, x])
            for k, (dx, dz) in enumerate(LabelSource.DIRS8):
                nx, nz = x + dx, z + dz
                if 0 <= nx < w and 0 <= nz < h:
                    got = s.nbr[:, k]
                    c += W_CTX * ((got != intent[nz, nx]) * np.where(got == "", 0.5, 1.0)).astype(np.float32)
            unary_rows[(x, z)] = c
        return unary_rows[(x, z)]

    def cand(x, z):
        if (x, z) not in cands:
            u = unary_row(x, z)
            k = min(candidates * 6, len(u) - 1)
            best = np.argpartition(u, k)[:k]
            order = best[np.argsort(u[best], kind="stable")]
            _, first = np.unique(s.lab[order], return_index=True)
            cands[(x, z)] = order[np.sort(first)][:candidates]
        return cands[(x, z)]

    occ = np.full((h, w), -1, dtype=np.int64)

    def join(x, z, dx, dz):
        nx, nz = x + dx, z + dz
        if not (0 <= nx < w and 0 <= nz < h) or occ[z, x] < 0 or occ[nz, nx] < 0:
            return 0.0
        if s.shifted(int(occ[z, x]), dx, dz) == occ[nz, nx]:
            return 0.0
        pair = (int(s.lab[occ[z, x]]), int(s.lab[occ[nz, nx]]))
        return W_SEAM if pair in (s.h_pairs if dx else s.v_pairs) else W_BAD

    def window(x, z):
        """A 2x2 label window vanilla never uses: the cells for it do not exist."""
        if not (0 <= x < w - 1 and 0 <= z < h - 1):
            return 0.0
        o = (occ[z, x], occ[z, x + 1], occ[z + 1, x], occ[z + 1, x + 1])
        if min(o) < 0:
            return 0.0
        return 0.0 if s.windows.get(tuple(int(s.lab[i]) for i in o)) else W_WINDOW

    def window3(x, z):
        """A 3x3 label window vanilla never uses (a T-junction no chunk has)."""
        if not (0 <= x < w - 2 and 0 <= z < h - 2):
            return 0.0
        o = occ[z:z + 3, x:x + 3]
        if (o < 0).any():
            return 0.0
        return 0.0 if tuple(int(s.lab[i]) for i in o.ravel()) in s.windows3 else W_WINDOW3

    def energy(tiles):
        total = 0.0
        for wx, wz in {(x + dx, z + dz) for x, z in tiles for dx in (-1, 0) for dz in (-1, 0)}:
            total += window(wx, wz)
        for wx, wz in {(x + dx, z + dz) for x, z in tiles for dx in (-2, -1, 0) for dz in (-2, -1, 0)}:
            total += window3(wx, wz)
        for x, z in tiles:
            if occ[z, x] >= 0:
                total += float(unary_row(x, z)[occ[z, x]])
            for dx, dz in ((1, 0), (0, 1)):
                total += join(x, z, dx, dz)
            for dx, dz in ((-1, 0), (0, -1)):
                if (x + dx, z + dz) not in tiles:
                    total += join(x + dx, z + dz, -dx, -dz)
        return total

    def choose(x, z):
        opts = {int(o) for o in cand(x, z)}
        for dx, dz in LabelSource.DIRS8:
            nx, nz = x + dx, z + dz
            if 0 <= nx < w and 0 <= nz < h and occ[nz, nx] >= 0:
                c = s.shifted(int(occ[nz, nx]), -dx, -dz)
                if c is not None:
                    opts.add(c)
        cur = int(occ[z, x])
        best, best_e = cur, energy({(x, z)}) if cur >= 0 else float("inf")
        for o in opts:
            occ[z, x] = o
            e = energy({(x, z)})
            if e < best_e - 1e-6:
                best, best_e = o, e
        occ[z, x] = best
        return best != cur

    def try_block(x0, z0, size, start):
        new = {}
        for z in range(z0, min(h, z0 + size)):
            for x in range(x0, min(w, x0 + size)):
                o = s.shifted(start, x - x0, z - z0)
                if o is None:
                    return False
                new[(x, z)] = o
        tiles = set(new)
        before = energy(tiles)
        if sum(float(unary_row(x, z)[o]) for (x, z), o in new.items()) >= before - 1e-6:
            return False
        old = {t: int(occ[t[1], t[0]]) for t in tiles}
        for (x, z), o in new.items():
            occ[z, x] = o
        if energy(tiles) < before - 1e-6:
            return True
        for (x, z), o in old.items():
            occ[z, x] = o
        return False

    for z in range(h):
        for x in range(w):
            choose(x, z)
    for sweep in range(sweeps):
        order = [(x, z) for z in range(h) for x in range(w)]
        if sweep % 2:
            order.reverse()
        changed = sum(choose(x, z) for x, z in order)
        for size in (6, 4, 2):
            hot = [(x, z) for z in range(h) for x in range(w) if energy({(x, z)}) > 3.0]
            rng.shuffle(hot)
            for x, z in hot:
                if energy({(x, z)}) <= 3.0:
                    continue
                x0, z0 = max(0, x - size // 2), max(0, z - size // 2)
                for o in cand(x, z)[:10]:
                    start = s.shifted(int(o), x0 - x, z0 - z)
                    if start is not None and try_block(x0, z0, size, start):
                        changed += 1
                        break
        if not changed:
            break
    labels = [[s.parts[int(s.lab[occ[z, x]])] for x in range(w)] for z in range(h)]
    kind = ["".join(labels[z][x][0] for x in range(w)) for z in range(h)]
    lev = np.array([[labels[z][x][1] for x in range(w)] for z in range(h)])
    walk = ["".join(labels[z][x][2] for x in range(w)) for z in range(h)]
    shore = ["".join(labels[z][x][3] for x in range(w)) for z in range(h)]
    return semantic.SemanticMap(kind, lev, walk, shore)


# --- gameplay checks and content plan ----------------------------------------------

def intent_of_map(sem: semantic.SemanticMap) -> np.ndarray:
    h, w = sem.shape
    return np.array([[intent_of(sem.kind[z][x], sem.walk[z][x]) for x in range(w)] for z in range(h)])


def check(sem: semantic.SemanticMap, plan_: Plan, brief: dict) -> dict:
    """Gameplay facts of a refined map, and spots for trainers and items."""
    rng = random.Random(brief.get("seed", 0) + 1)
    got = intent_of_map(sem)
    h, w = got.shape
    problems = []
    exits = [e[2] for e in plan_.exits]
    for i, a in enumerate(exits):
        if not _walkable(got[a[0][1], a[0][0]]):
            problems.append(f"exit {i} at {a[0]} is not walkable")
            continue
        seen = reachable(got, a[0])
        for j, b in enumerate(exits):
            if i != j and not seen[b[0][1], b[0][0]]:
                problems.append(f"exit {j} cannot be reached from exit {i}")
    mismatch = int((got != plan_.intent).sum())
    route = set(plan_.route)
    seen = reachable(got, exits[0][0]) if exits else np.zeros_like(got, dtype=bool)
    # Trainers: open tiles beside the route that see across it for 3+ tiles.
    trainers = []
    candidates = [(x, z) for z in range(2, h - 2) for x in range(2, w - 2)
                  if seen[z, x] and (x, z) not in route and got[z, x] in WALKABLE_INTENTS]
    rng.shuffle(candidates)
    for x, z in candidates:
        if len(trainers) >= int(brief.get("trainers", 0)):
            break
        for facing, (dx, dz) in (("down", (0, 1)), ("up", (0, -1)), ("left", (-1, 0)), ("right", (1, 0))):
            sight, crosses = 0, False
            nx, nz = x + dx, z + dz
            while 0 <= nx < w and 0 <= nz < h and got[nz, nx] in WALKABLE_INTENTS and sight < 5:
                sight += 1
                crosses |= (nx, nz) in route
                nx, nz = nx + dx, nz + dz
            if sight >= 3 and crosses and all(abs(x - t["x"]) + abs(z - t["z"]) > 8 for t in trainers):
                trainers.append({"x": x, "z": z, "facing": facing, "sight": sight})
                break
    # Items: reachable dead ends or nooks far from the route.
    near = distance(_mask(route, got.shape))
    items = []
    spots = [(x, z) for z in range(h) for x in range(w) if seen[z, x] and got[z, x] in (GROUND, TALL, LIGHT, PATH)]
    spots.sort(key=lambda p: -near[p[1], p[0]])
    for x, z in spots:
        if len(items) >= int(brief.get("items", 0)):
            break
        if all(abs(x - i["x"]) + abs(z - i["z"]) > 10 for i in items):
            items.append({"x": x, "z": z, "fromRoute": int(near[z, x])})
    tall = int((got == TALL).sum())
    if brief.get("grass", 0) and not tall:
        problems.append("no tall grass: no wild encounters")
    return {"problems": problems, "intentMismatches": mismatch, "tallGrassTiles": tall,
            "reachableTiles": int(seen.sum()), "trainers": trainers, "items": items,
            "exits": [{"side": e["side"], "tiles": [list(t) for t in exit_tiles(e, w, h)]} for e in brief["exits"]]}


def _mask(points, shape) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    for x, z in points:
        m[z, x] = True
    return m


# --- entry points -----------------------------------------------------------------

def label_source(template_map: int) -> tuple[dict, LabelSource]:
    from .cli import _base, _tileset_of_map
    base = _base()
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), _tileset_of_map(base, template_map))
    matrix = base.matrix_for(template_map)
    own = {land for z, row in enumerate(matrix["landData"]) for x, land in enumerate(row)
           if land in kit["chunks"] and (matrix["headers"] is None or matrix["headers"][z][x] in (0, template_map))}
    return kit, LabelSource(kit, own=frozenset(own))


def design(brief: dict) -> tuple[semantic.SemanticMap, Plan, dict]:
    _, source = label_source(brief["template"])
    ground = source.ground_intent()
    plan_ = plan(brief, ground, source.base_level(ground), source.water_intent())
    sem = refine(source, plan_.intent, plan_.level, seed=brief.get("seed", 0))
    return sem, plan_, check(sem, plan_, brief)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.maps.style.design", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path, help="semantic map text (input of style paint)")
    ap.add_argument("--plan", type=Path, help="gameplay plan JSON (exits, trainers, items)")
    args = ap.parse_args(argv)
    brief = json.loads(args.brief.read_text())
    sem, plan_, facts = design(brief)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(f"# designed from {args.brief.name} (template map {brief['template']}, seed "
                        f"{brief.get('seed', 0)})\n" + sem.to_text())
    report = {"brief": brief, "intent": plan_.text().splitlines(), **facts, "notes": plan_.notes,
              "route": [list(p) for p in plan_.route]}
    if args.plan:
        args.plan.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("problems", "intentMismatches", "tallGrassTiles", "trainers", "items")}))
    print(plan_.text())
    return 1 if facts["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
