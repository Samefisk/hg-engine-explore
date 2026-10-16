"""Layout pre-check: find what vanilla never does before a long `generate`.

  python3 -B -m tools.maps.style precheck --layout L.txt --map 33 [--relax 1] [--json]
      [--events EVENTS.json] [--start X Z]
  python3 -B -m tools.maps.style precheck --map 33 --calibrate   # vanilla chunks, leave-one-out

Compares the layout (relaxed as `generate` would) with the class layouts of
every vanilla chunk of the map's tileset (the kit's `chunks`, '?' read as
'T'). Takes about a second; it does not solve anything.

Errors (exit 1) are findings that make a gate fail whatever the solver does:
  structure       not 32*H x 32*W rows of known characters (layout.parse)
  missing-class   a class whose tileset has no cell (water, a ledge direction,
                  walls or ground): the tile becomes a critical mismatch
  pocket          standable tiles that stay apart even if every '*' is
                  walkable: walkableComponents > 1 (or critical mismatches)
  point           a warp/start tile on a wall, water or ledge, or off the grid

Warnings (exit 0) are what vanilla never or rarely does; each one raises the
chance of a failing gate but is not certain:
  unseen-window   a 2x2 class window (all classes), or a 3x3 one with grass
                  read as ground, that no vanilla chunk of the tileset has
                  ('*' matches anything). Grouped into regions; each region
                  shows the nearest vanilla window (smallest quilt.mismatch_cost
                  sum, then most common) with its land and coordinates.
  ledge-landing   a ledge whose landing tile (one step in its direction) is not
                  open ground, grass or '*': every vanilla ledge lands on ground
  ledge-approach  a ledge whose approach tile is not walkable or '*'
  narrow          ground/grass/ledge tiles not in any 2x2 standable block
                  (paths narrower than 2); also 1-wide walls and water
  pocket-if-wild  standable regions joined only through '*' tiles
  point-soft      a warp/start tile on grass or '*'
  missing-class   grass in a tileset without grass (becomes plain ground)

Calibration (`--calibrate`, test_precheck.py) runs the same checks on every
vanilla chunk against the other chunks of its tileset.
"""

from __future__ import annotations

from collections import Counter, deque

import numpy as np

from . import layout
from .quilt import mismatch_cost

NAMES = {".": "ground", ",": "grass", "~": "water", "T": "wall", "v": "south ledge", "^": "north ledge",
         "<": "west ledge", ">": "east ledge", "*": "any"}
LEDGE_DIRS = {"v": (0, 1), "^": (0, -1), "<": (-1, 0), ">": (1, 0)}
STAND = set(".,v^<>")      # what walkableComponents counts (water and void excluded)
SOFT_CLASSES = {","}       # missing in a tileset: cosmetic (grass -> ground costs 0.25)
REDUCE = str.maketrans({",": "."})
WINDOW_CHECKS = ((2, False), (3, True))  # (size, grass read as ground)
ALPHABET = sorted(set(layout.CLASSES) | {"?"})
CODE = {ch: i for i, ch in enumerate(ALPHABET)}
COST = np.array([[mismatch_cost(w, g) for g in ALPHABET] for w in ALPHABET], dtype=np.float32)


def vanilla_rows(kit: dict) -> dict[int, list[str]]:
    """Class layout of every vanilla chunk of a kit; floorless void reads as wall."""
    return {land: [row.replace("?", "T") for row in layout.render(grid, kit)]
            for land, grid in sorted(kit["chunks"].items())}


def windows_of(rows: list[str], k: int):
    """(x, z, window string in reading order) of every k x k window."""
    for z in range(len(rows) - k + 1):
        for x in range(len(rows[0]) - k + 1):
            yield x, z, "".join(rows[z + dz][x:x + k] for dz in range(k))


class Vanilla:
    """What the vanilla chunks of one tileset contain: classes, pairs, k x k windows."""

    def __init__(self, lands: dict[int, list[str]], exclude: frozenset = frozenset(),
                 sizes: tuple[int, ...] = (2, 3)):
        self.lands = {land: rows for land, rows in lands.items() if land not in exclude}
        self.classes = Counter(ch for rows in self.lands.values() for row in rows for ch in row)
        self.pairs = set()
        for rows in self.lands.values():
            for z, row in enumerate(rows):
                for x, ch in enumerate(row):
                    if x + 1 < len(row):
                        self.pairs.add((ch, row[x + 1], "h"))
                    if z + 1 < len(rows):
                        self.pairs.add((ch, rows[z + 1][x], "v"))
        self.where: dict[int, dict[str, list]] = {}   # k -> window -> [(land, x, z)]
        self.arrays: dict[tuple[int, bool], tuple[list[str], np.ndarray]] = {}
        for k in sizes:
            where: dict[str, list] = {}
            for land, rows in self.lands.items():
                for x, z, w in windows_of(rows, k):
                    where.setdefault(w, []).append((land, x, z))
            self.where[k] = where
            for reduced in (False, True):
                keys = sorted({w.translate(REDUCE) if reduced else w for w in where})
                arr = np.array([[CODE[c] for c in w] for w in keys], dtype=np.int8).reshape(len(keys), k * k)
                self.arrays[(k, reduced)] = (keys, arr)
        self._seen: dict = {}

    def seen(self, window: str, k: int, reduced: bool = False) -> bool:
        """Whether some vanilla k x k window matches ('*' matches any class)."""
        key = (window, k, reduced)
        if key not in self._seen:
            w = window.translate(REDUCE) if reduced else window
            keys, arr = self.arrays[(k, reduced)]
            if "*" not in w:
                hit = w in self._keyset(k, reduced)
            else:
                mask = np.array([c != "*" for c in w])
                pat = np.array([CODE[c] for c in w], dtype=np.int8)
                hit = bool(len(arr)) and bool((arr[:, mask] == pat[mask]).all(axis=1).any())
            self._seen[key] = hit
        return self._seen[key]

    def _keyset(self, k: int, reduced: bool) -> set:
        key = ("set", k, reduced)
        if key not in self._seen:
            self._seen[key] = set(self.arrays[(k, reduced)][0])
        return self._seen[key]

    def nearest(self, window: str, k: int) -> dict | None:
        """The vanilla k x k window with the smallest class edit cost, then the most common."""
        keys, arr = self.arrays[(k, False)]
        if not keys:
            return None
        pat = np.array([CODE[c] for c in window], dtype=np.int64)
        costs = COST[pat[None, :], arr.astype(np.int64)].sum(axis=1)
        best = float(costs.min())
        ties = [keys[i] for i in np.flatnonzero(costs == best)]
        win = max(ties, key=lambda w: (len(self.where[k][w]), w))
        land, x, z = self.where[k][win][0]
        return {"cost": round(best, 2), "land": land, "x": x, "z": z, "window": win,
                "occurrences": len(self.where[k][win])}


# --- findings ---------------------------------------------------------------

def _finding(severity: str, kind: str, message: str, cells: list[tuple[int, int]], **extra) -> dict:
    xs, zs = [c[0] for c in cells], [c[1] for c in cells]
    return {"severity": severity, "kind": kind, "message": message,
            "x": min(xs), "z": min(zs), "w": max(xs) - min(xs) + 1, "h": max(zs) - min(zs) + 1,
            "tiles": len(set(cells)), **extra}


def _where(f: dict) -> str:
    if f["w"] == f["h"] == 1:
        return f"({f['x']},{f['z']})"
    return f"({f['x']},{f['z']})-({f['x'] + f['w'] - 1},{f['z'] + f['h'] - 1})"


def _groups(cells: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """8-connected groups of cells, in reading order of their first cell."""
    out, seen = [], set()
    for start in sorted(cells, key=lambda c: (c[1], c[0])):
        if start in seen:
            continue
        group, queue = [], deque([start])
        seen.add(start)
        while queue:
            x, z = queue.popleft()
            group.append((x, z))
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (x + dx, z + dz)
                    if n in cells and n not in seen:
                        seen.add(n)
                        queue.append(n)
        out.append(group)
    return out


def check_classes(rows: list[str], vanilla: Vanilla) -> list[dict]:
    out = []
    for ch in sorted({c for row in rows for c in row} - {"*"}):
        if vanilla.classes[ch]:
            continue
        cells = [(x, z) for z, row in enumerate(rows) for x, c in enumerate(row) if c == ch]
        if ch in SOFT_CLASSES:
            out.append(_finding("warning", "missing-class", f"the tileset has no {NAMES[ch]} cells: "
                                f"{len(cells)} '{ch}' tiles become plain ground", cells))
        else:
            out.append(_finding("error", "missing-class", f"the tileset has no {NAMES[ch]} cells: "
                                f"{len(cells)} '{ch}' tiles are certain critical mismatches", cells))
    return out


def _describe(rows: list[str], cells: set, vanilla: Vanilla) -> str:
    """Name the class contacts of a region that vanilla never has, else its classes."""
    contacts = []
    for x, z in sorted(cells, key=lambda c: (c[1], c[0])):
        a = rows[z][x]
        for (dx, dz, axis) in ((1, 0, "h"), (0, 1, "v")):
            if (x + dx, z + dz) not in cells:
                continue
            b = rows[z + dz][x + dx]
            if "*" in (a, b) or a == b or (a, b, axis) in vanilla.pairs:
                continue
            side = "east" if axis == "h" else "south"
            text = f"{NAMES[b]} directly {side} of {NAMES[a]}"
            if text not in contacts:
                contacts.append(text)
    if contacts:
        return "; ".join(contacts[:3])
    classes = sorted({rows[z][x] for x, z in cells} - {"*"}, key=ALPHABET.index)
    return "arrangement of " + ", ".join(NAMES[c] for c in classes) + " vanilla never uses"


def context(rows: list[str], x: int, z: int, k: int, margin: int = 1) -> list[str]:
    """The window plus `margin` tiles around it (' ' outside the grid)."""
    out = []
    for zz in range(z - margin, z + k + margin):
        out.append("".join(rows[zz][xx] if 0 <= zz < len(rows) and 0 <= xx < len(rows[0]) else " "
                           for xx in range(x - margin, x + k + margin)))
    return out


def check_windows(rows: list[str], vanilla: Vanilla, checks=WINDOW_CHECKS) -> list[dict]:
    """Unseen k x k windows, grouped into regions, each with its nearest vanilla window."""
    missing = {ch for ch in layout.CLASSES if ch != "*" and not vanilla.classes[ch]}
    unseen: list[tuple[int, int, int, str]] = []  # (k, x, z, window)
    for k, reduced in checks:
        for x, z, w in windows_of(rows, k):
            if missing & set(w):
                continue  # already a missing-class finding
            if not vanilla.seen(w, k, reduced):
                unseen.append((k, x, z, w))
    cells = {(x + dx, z + dz) for k, x, z, _ in unseen for dx in range(k) for dz in range(k)}
    out = []
    for group in _groups(cells):
        members = set(group)
        wins = [u for u in unseen if (u[1], u[2]) in members]
        rep = min(wins, key=lambda u: (u[0], u[2], u[1]))  # smallest, then first: most specific
        k, x, z, w = rep
        near = vanilla.nearest(w, k)
        example = None
        if near:
            vrows = vanilla.lands[near["land"]]
            example = {**near, "context": context(vrows, near["x"], near["z"], k)}
        out.append(_finding("warning", "unseen-window", _describe(rows, members, vanilla), group,
                            windows=len(wins), sizes=sorted({u[0] for u in wins}),
                            window={"k": k, "x": x, "z": z, "context": context(rows, x, z, k)},
                            example=example))
    return out


def check_ledges(rows: list[str]) -> list[dict]:
    height, width = len(rows), len(rows[0])
    bad = {"ledge-landing": [], "ledge-approach": []}
    for z, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in LEDGE_DIRS:
                continue
            dx, dz = LEDGE_DIRS[ch]
            for kind, (nx, nz) in (("ledge-landing", (x + dx, z + dz)), ("ledge-approach", (x - dx, z - dz))):
                if not (0 <= nx < width and 0 <= nz < height) or rows[nz][nx] not in ".,*":
                    bad[kind].append((x, z))
    out = []
    for kind, cells in bad.items():
        for group in _groups(set(cells)):
            x, z = group[0]
            dx, dz = LEDGE_DIRS[rows[z][x]]
            sx, sz = (x + dx, z + dz) if kind == "ledge-landing" else (x - dx, z - dz)
            other = rows[sz][sx] if 0 <= sx < width and 0 <= sz < height else None
            what = NAMES.get(other, "the grid edge") if other else "the grid edge"
            verb = "lands on" if kind == "ledge-landing" else "is approached from"
            out.append(_finding("warning", kind, f"{len(group)} ledge tile(s) {verb} {what} "
                                f"(every vanilla ledge has ground on both sides)", group))
    return out


def check_narrow(rows: list[str]) -> list[dict]:
    """Tiles of a class group not inside any 2x2 block of that group (or '*')."""
    height, width = len(rows), len(rows[0])
    out = []
    for label, group in (("path", STAND), ("wall", {"T"}), ("water", {"~"})):
        def ok(x, z):
            return 0 <= x < width and 0 <= z < height and (rows[z][x] in group or rows[z][x] == "*")
        cells = {(x, z) for z in range(height) for x in range(width) if rows[z][x] in group and not any(
            ok(x + a, z + b) and ok(x + a + 1, z + b) and ok(x + a, z + b + 1) and ok(x + a + 1, z + b + 1)
            for a in (-1, 0) for b in (-1, 0))}
        for g in _groups(cells):
            out.append(_finding("warning", "narrow", f"{label} 1 tile wide ({len(g)} tiles)", g))
    return out


def _components(rows: list[str], passable: set) -> list[list[tuple[int, int]]]:
    """Connected standable tiles; '*' tiles in `passable` connect but are not counted."""
    height, width = len(rows), len(rows[0])
    seen, comps = set(), []
    for z in range(height):
        for x in range(width):
            if rows[z][x] not in STAND or (x, z) in seen:
                continue
            comp, queue = [], deque([(x, z)])
            seen.add((x, z))
            while queue:
                cx, cz = queue.popleft()
                if rows[cz][cx] in STAND:
                    comp.append((cx, cz))
                for dx, dz in layout.DIRECTIONS:
                    nx, nz = cx + dx, cz + dz
                    if 0 <= nx < width and 0 <= nz < height and (nx, nz) not in seen and rows[nz][nx] in passable:
                        seen.add((nx, nz))
                        queue.append((nx, nz))
            comps.append(comp)
    return sorted(comps, key=len, reverse=True)


def check_pockets(rows: list[str]) -> list[dict]:
    def regions(comps):  # touching pockets (e.g. a diagonal pattern) are reported together
        pocket_of = {cell: i for i, comp in enumerate(comps) for cell in comp}
        for group in _groups(set(pocket_of)):
            yield group, len({pocket_of[c] for c in group})

    out = []
    optimistic = _components(rows, STAND | {"*"})
    for group, n in regions(optimistic[1:]):
        out.append(_finding("error", "pocket", f"{n} sealed standable pocket(s), {len(group)} tiles, apart from "
                            f"the main area even if every '*' is walkable (walkableComponents > 1)", group))
    if len(optimistic) == 1:
        for group, n in regions(_components(rows, STAND)[1:]):
            out.append(_finding("warning", "pocket-if-wild", f"{n} standable region(s), {len(group)} tiles, reach "
                                f"the main area only through '*' tiles; the solver may wall them in", group))
    return out


def check_points(rows: list[str], points: list[tuple[int, int, str]]) -> list[dict]:
    out = []
    for x, z, label in points:
        if not (0 <= z < len(rows) and 0 <= x < len(rows[0])):
            out.append(_finding("error", "point", f"{label} at ({x},{z}) is outside the layout", [(x, z)]))
            continue
        ch = rows[z][x]
        if ch == ".":
            continue
        if ch in ",*":
            out.append(_finding("warning", "point-soft", f"{label} at ({x},{z}) is on {NAMES[ch]}, not '.'",
                                [(x, z)]))
        else:
            out.append(_finding("error", "point", f"{label} at ({x},{z}) is on {NAMES[ch]}; it must be '.'",
                                [(x, z)]))
    return out


def check_rows(rows: list[str], vanilla: Vanilla, points=()) -> list[dict]:
    """Every check on parsed (and relaxed) rows."""
    findings = check_classes(rows, vanilla) + check_pockets(rows) + check_points(rows, list(points))
    findings += check_windows(rows, vanilla) + check_ledges(rows) + check_narrow(rows)
    order = {"error": 0, "warning": 1}
    return sorted(findings, key=lambda f: (order[f["severity"]], f["kind"], f["z"], f["x"]))


def check_text(text: str, vanilla: Vanilla, relax_depth: int = 0, points=()) -> tuple[list[str] | None, list[dict]]:
    try:
        rows = layout.parse(text)
    except layout.LayoutError as error:
        return None, [{"severity": "error", "kind": "structure", "message": str(error),
                       "x": 0, "z": 0, "w": 0, "h": 0, "tiles": 0}]
    if relax_depth:
        rows = layout.relax(rows, relax_depth)
    return rows, check_rows(rows, vanilla, points)


def summary(findings: list[dict]) -> dict:
    return {"errors": sum(f["severity"] == "error" for f in findings),
            "warnings": sum(f["severity"] == "warning" for f in findings),
            "byKind": dict(Counter(f["kind"] for f in findings))}


def format_text(findings: list[dict], header: str) -> str:
    lines = [header]
    for f in findings:
        tag = "ERROR" if f["severity"] == "error" else "warn "
        extra = f" [{f['windows']} window(s), k={'/'.join(map(str, f['sizes']))}]" if "windows" in f else ""
        lines.append(f"{tag} {f['kind']:<15}{f['message']} at {_where(f)}{extra}")
        if f.get("window"):
            mine, ex = f["window"], f.get("example")
            left = [f"yours ({mine['x']},{mine['z']})"] + mine["context"]
            right = ([f"vanilla land {ex['land']} ({ex['x']},{ex['z']}) cost {ex['cost']} seen {ex['occurrences']}x"]
                     + ex["context"]) if ex else ["no vanilla window"]
            width = max(len(s) for s in left) + 4
            for i in range(max(len(left), len(right))):
                a = left[i] if i < len(left) else ""
                b = right[i] if i < len(right) else ""
                lines.append("      " + a.ljust(width) + b)
    s = summary(findings)
    lines.append(f"{s['errors']} error(s), {s['warnings']} warning(s)")
    return "\n".join(lines)


def calibrate(lands: dict[int, list[str]]) -> dict[int, dict]:
    """Each vanilla chunk checked against the other chunks (leave-one-out).

    Vanilla chunks join neighbours outside the chunk, so pockets there are
    expected; the window counts are the false-positive baseline.
    """
    out = {}
    for land, rows in lands.items():
        findings = check_rows(rows, Vanilla(lands, exclude=frozenset({land})))
        out[land] = summary(findings)["byKind"]
    return out


# --- kit-backed entry point (cli.py `precheck`) --------------------------------

def load_vanilla(map_id: int) -> tuple[int, dict[int, list[str]]]:
    from .. import world
    from . import kit as kits
    from .cli import REPO, _base, _tileset_of_map
    tileset = _tileset_of_map(_base(), map_id)
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    return tileset, vanilla_rows(kit)


def points_from(events: dict | None, starts) -> list[tuple[int, int, str]]:
    points = [(int(x), int(z), "start") for x, z in starts or ()]
    for i, warp in enumerate((events or {}).get("warps", [])):
        points.append((int(warp["x"]), int(warp["z"]), f"warp {i}"))
    return points
