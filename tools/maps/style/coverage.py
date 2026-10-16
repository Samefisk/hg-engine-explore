"""Render void from kit geometry: black void the player can see, without textures.

The judge's version of `tools.maps.render.voids`. A cell grid is drawn as
polygon coverage only (no textures, no light) at a few samples per tile:

- `top`: straight down. A tile with any uncovered sample shows void.
- `camera`: an orthographic view at the field camera's pitch (preset 0,
  angle.x 0xDD62, about 48.7 degrees down; `render.camera_preset(0)`). Each
  uncovered sample is traced along the view direction to the median floor
  height; the tile it lands on shows void there (a missing wall face or a
  floor edge seen against nothing).

Both apply the renderer's face culling (material front/back bits; front faces
wind counter-clockwise on screen) and skip invisible materials (alpha 0).
Only void tiles beside ground count: a tile within one tile (8 directions) of
an open land, ledge or water tile connected to land (as `tools.maps.reach`,
which walks water and HM-passable blocks; a pool sealed in by walls is
scenery). The grid's outer `margin` tiles are skipped, as render.voids skips
the map edge, whose void neighbouring maps cover. For the same reason a camera
sample whose ray runs into the north margin before reaching the grid's lowest
geometry is skipped: the camera looks north and down, so that void is the
neighbour's. Texture transparency is not modelled (render.voids sees void
through alpha-0 texels, e.g. river edges laid over nothing).

Vanilla chunks with buildings are not judged (`building_lands`): their props
stand over polygon-less holes, and render.voids skips them too.

Rasterizing is per distinct cell and cached per kit, so scoring a 32x32 chunk
costs milliseconds once its cells are cached.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from .layout import cell_char

TILE = 16.0
PPT = 4
# gFieldCameraPresets[0].angle.x (render.camera_preset(0)): the camera looks this far below level.
PITCH = 2 * math.pi - 0xDD62 / 65536 * 2 * math.pi
SLOPE = math.cos(PITCH) / math.sin(PITCH)  # floor-plane shift north per unit of height
GROUND = set(".,v^<>~")
LAND = set(".,v^<>")
PASSABLE_WHEN_BLOCKED = frozenset({17, 19, 75, 76, 128})  # tools.maps.reach


def _triangles(kit: dict, cell: dict) -> np.ndarray:
    """Visible-material triangles of a cell, (n, 3, 3) xyz in tile-local world units."""
    out = []
    for poly in cell.get("polys", ()):
        attr = kit["materials"][poly["mat"]]["polyAttr"]
        if not (attr >> 16) & 31:  # alpha 0: not drawn
            continue
        vs = [v[:3] for v in poly["verts"]]
        for k in range(1, len(vs) - 1):
            out.append((vs[0], vs[k], vs[k + 1], attr))
    if not out:
        return np.zeros((0, 3, 3)), np.zeros(0, np.int64)
    return np.array([t[:3] for t in out], float), np.array([t[3] for t in out], np.int64)


def _raster(tris: np.ndarray, ppt: int) -> tuple[int, int, np.ndarray] | None:
    """Coverage of 2D triangles (tile units) sampled at pixel centres (i + 0.5) / ppt.

    Returns (first column, first row, bool mask) in pixels, or None."""
    if not len(tris):
        return None
    lo = np.floor(tris.reshape(-1, 2).min(axis=0) * ppt).astype(int)
    hi = np.ceil(tris.reshape(-1, 2).max(axis=0) * ppt).astype(int)
    w, h = hi - lo
    if w <= 0 or h <= 0:
        return None
    px, py = np.meshgrid((np.arange(lo[0], hi[0]) + 0.5) / ppt, (np.arange(lo[1], hi[1]) + 0.5) / ppt)
    mask = np.zeros((h, w), bool)
    for t in tris:
        area = (t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])
        if area == 0:
            continue
        inside = np.ones((h, w), bool)
        for a, c in ((1, 2), (2, 0), (0, 1)):
            b = ((t[c, 0] - t[a, 0]) * (py - t[a, 1]) - (t[c, 1] - t[a, 1]) * (px - t[a, 0])) / area
            inside &= b >= -1e-9
        mask |= inside
    return (int(lo[0]), int(lo[1]), mask) if mask.any() else None


def _visible(tris2d: np.ndarray, attrs: np.ndarray) -> np.ndarray:
    """Faces the renderer draws: screen y grows with z, front faces have negative signed area."""
    t = tris2d
    area = ((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
            - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
    front, back = (attrs >> 7) & 1, (attrs >> 6) & 1
    return ((area < 0) & (front == 1)) | ((area > 0) & (back == 1))


class _CellCoverage:
    def __init__(self, kit: dict, ppt: int):
        self.kit, self.ppt = kit, ppt
        self.top: dict = {}
        self.camera: dict = {}
        self.ys: dict = {}

    def get(self, cell_id: int):
        if cell_id not in self.top and "polys" not in self.kit["cells"][cell_id]:
            # No geometry known (synthetic kits): assume it covers its own tile, as seams.occupies does.
            self.ys[cell_id] = np.zeros(0)
            self.top[cell_id] = self.camera[cell_id] = (0, 0, np.ones((self.ppt, self.ppt), bool))
        if cell_id not in self.top:
            tris, attrs = _triangles(self.kit, self.kit["cells"][cell_id])
            self.ys[cell_id] = tris[:, :, 1].ravel()
            views = []
            for plane in (tris[:, :, [0, 2]], np.stack([tris[:, :, 0], tris[:, :, 2] - tris[:, :, 1] * SLOPE], -1)):
                plane = plane / TILE
                views.append(_raster(plane[_visible(plane, attrs)], self.ppt) if len(plane) else None)
            self.top[cell_id], self.camera[cell_id] = views
        return self.top[cell_id], self.camera[cell_id]


_CACHE: dict = {}


def _for_kit(kit: dict, ppt: int) -> _CellCoverage:
    key = (id(kit), ppt)
    if key not in _CACHE:
        _CACHE[key] = _CellCoverage(kit, ppt)
    return _CACHE[key]


def _tables(kit: dict) -> tuple[np.ndarray, np.ndarray]:
    key = id(kit)
    if key not in _TABLES:
        cells = kit["cells"]
        open_ = np.array([cell_char(c) in GROUND and (not c["collision"] or c.get("behavior") in PASSABLE_WHEN_BLOCKED)
                          for c in cells])
        land = open_ & np.array([cell_char(c) in LAND for c in cells])
        _TABLES[key] = (open_, land)
    return _TABLES[key]


_TABLES: dict = {}


def ground(kit: dict, grid: np.ndarray) -> np.ndarray:
    """Tiles the player can reach: open land, ledges and water (Surf), and HM-passable blocks,
    connected to land the player stands on. The grid has no warps, so every land region counts
    as entered; a pool sealed off by walls is scenery (render.voids' reachability skips it too)."""
    g = np.asarray(grid)
    open_t, land_t = _tables(kit)
    valid = g >= 0
    open_ = open_t[np.maximum(g, 0)] & valid
    seen = land_t[np.maximum(g, 0)] & valid
    height, width = g.shape
    queue = deque(zip(*np.nonzero(seen)))
    while queue:
        z, x = queue.popleft()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nz, nx = z + dz, x + dx
            if 0 <= nz < height and 0 <= nx < width and open_[nz, nx] and not seen[nz, nx]:
                seen[nz, nx] = True
                queue.append((nz, nx))
    return seen


def render_void(kit: dict, grid, margin: int = 2, ppt: int = PPT) -> dict:
    """{"top": [(x, z)], "camera": [(x, z)]}: tiles beside ground where the black void shows."""
    g = np.asarray(grid, dtype=np.int64)
    height, width = g.shape
    cache = _for_kit(kit, ppt)
    top = np.zeros((height * ppt, width * ppt), bool)
    pieces = []
    for z in range(height):
        for x in range(width):
            c = int(g[z, x])
            if c < 0:
                continue
            t, cam = cache.get(c)
            if t is not None:
                c0, r0, m = t
                c0, r0 = c0 + x * ppt, r0 + z * ppt
                cs, rs = max(0, -c0), max(0, -r0)
                ce, re = min(m.shape[1], width * ppt - c0), min(m.shape[0], height * ppt - r0)
                if cs < ce and rs < re:
                    top[r0 + rs:r0 + re, c0 + cs:c0 + ce] |= m[rs:re, cs:ce]
            if cam is not None:
                pieces.append((cam[0] + x * ppt, cam[1] + z * ppt, cam[2]))
    # The renderer traces void to the median vertex height of everything drawn.
    used, counts = np.unique(g[g >= 0], return_counts=True)
    all_y = np.concatenate([np.tile(cache.ys[int(c)], int(n)) for c, n in zip(used, counts)] or [np.zeros(0)])
    floor = float(np.median(all_y)) if len(all_y) else 0.0
    # Camera view in floor-plane rows: a sample at row j lands on tile row floor((j + .5) / ppt + floor * SLOPE / TILE).
    shift = floor * SLOPE / TILE
    j_lo = math.floor((0 - shift) * ppt) - 1
    j_hi = math.ceil((height - shift) * ppt) + 1
    camera = np.zeros((j_hi - j_lo, width * ppt), bool)
    for c0, r0, m in pieces:
        r0 -= j_lo
        cs, rs = max(0, -c0), max(0, -r0)
        ce, re = min(m.shape[1], width * ppt - c0), min(m.shape[0], camera.shape[0] - r0)
        if cs < ce and rs < re:
            camera[r0 + rs:r0 + re, c0 + cs:c0 + ce] |= m[rs:re, cs:ce]

    stand = ground(kit, g)
    near = np.zeros_like(stand)
    for dz in (-1, 0, 1):
        for dx in (-1, 0, 1):
            near[max(0, dz):height + min(0, dz), max(0, dx):width + min(0, dx)] |= \
                stand[max(0, -dz):height - max(0, dz), max(0, -dx):width - max(0, dx)]
    inner = np.zeros_like(stand)
    inner[margin:height - margin, margin:width - margin] = True
    counted = near & inner

    top_void = ~top.reshape(height, ppt, width, ppt).all(axis=(1, 3))
    plane = (np.arange(j_lo, j_hi) + 0.5) / ppt  # floor-plane z at height 0, in tiles
    rows = np.floor(plane + shift).astype(int)
    # A sample's ray meets geometry of height y at z = plane + y * SLOPE: it runs north as it falls.
    # If it reaches the north margin before the grid's lowest geometry, what shows there is the
    # neighbouring chunk's (as the top view skips the margin). Southward the ray only climbs past
    # possible occluders, which would hide void, not fill it, so the south needs no such rule.
    y_lo = float(all_y.min()) if len(all_y) else 0.0
    inside = plane + y_lo * SLOPE / TILE >= margin
    cam_void = np.zeros((height, width), bool)
    js, cols = np.nonzero(~camera & inside[:, None])
    tz, tx = rows[js], cols // ppt
    ok = (tz >= 0) & (tz < height)
    cam_void[tz[ok], tx[ok]] = True

    def tiles(mask):
        zs, xs = np.nonzero(mask & counted)
        return sorted(zip(xs.tolist(), zs.tolist()))
    return {"top": tiles(top_void), "camera": tiles(cam_void), "floor": floor}


def render_void_tiles(kit: dict, grid, margin: int = 2) -> list[tuple[int, int]]:
    """Tiles flagged from above or from the camera (the renderVoid gate counts these)."""
    found = render_void(kit, grid, margin)
    return sorted(set(found["top"]) | set(found["camera"]))


def building_lands(world_base, kit: dict) -> set[int]:
    """Vanilla chunks with building props. Their props are not land geometry (houses, rocks in water
    stand over polygon-less holes), so the vanilla judge skips them, as render.voids does."""
    return {land for land in kit["chunks"] if world_base.member("land", land)["buildings"]}
