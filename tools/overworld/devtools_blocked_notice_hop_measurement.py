"""Shared finite terrain path and stock walk helpers.

The Notice Player leaf was retired in TKT-0040. Held-Throw setup still uses
these existing normal-input helpers; no Notice profile is resolved here.
"""
from collections import deque
from copy import deepcopy
from tools.overworld.devtools_profile_feature_measurement import require
from tools.overworld.devtools_movement_predicates import player_settled_at

def _cell(terrain, tile):
    cells = [c for c in terrain["cells"]
             if (c["x"], c.get("z", c.get("y"))) == tuple(tile)]
    require(len(cells) == 1 and cells[0].get("loaded") is True
            and cells[0].get("surface", {}).get("known") is True,
            "blocked Hop endpoint terrain is unknown")
    return cells[0]


def _current_cell_owner(snapshot, pot, cell):
    """Each loaded chunk belongs to the same current native map matrix.

    A radius can cross a 32-tile chunk edge; each chunk has its own land-data
    member. The existing reader authenticates that member and loaded tag.
    """
    p, current = cell.get("provenance", {}), pot.get("provenance", {})
    if not all(p.get(k) == current.get(k) for k in
               ("mapMatrixPointer", "matrixId", "matrixWidth", "matrixHeight", "readerPointer", "store")):
        return False
    width, height = p.get("matrixWidth"), p.get("matrixHeight")
    x, z = cell["x"], cell.get("z", cell.get("y"))
    if (p.get("fieldPointer") != snapshot["fieldControl"]["fieldPointer"]
            or type(p.get("mapMatrixPointer")) is not int or not 0x02000000 <= p["mapMatrixPointer"] < 0x02400000
            or type(p.get("matrixId")) is not int or not 0 <= p["matrixId"] <= 255
            or type(width) is not int or type(height) is not int or not 0 < width * height <= 900
            or not 0 <= x < width * 32 or not 0 <= z < height * 32
            or cell.get("matrix_index") != (z // 32) * width + x // 32
            or p.get("landDataIdentity") != "current-map-matrix"
            or type(p.get("landDataId")) is not int or not 0 <= p["landDataId"] < 0xffff):
        return False
    if p.get("store") == "rolling-land-manager":
        return (p.get("readerPointer") == 0x020547D9
                and p.get("chunkMatrixIndex") == cell["matrix_index"] and p.get("chunkModelLoaded") == 1)
    return p.get("store") == "full-terrain-attributes" and p.get("readerPointer") == 0x02054825


def clear_path(snapshot, fixture, terrain):
    """A bounded setup path over authenticated clear loaded ground."""
    start = tuple(snapshot["player"][k] for k in ("x", "y"))
    target = tuple(fixture["neighbor"])
    blocked = {tuple(a["logical"][k] for k in ("x", "y"))
               for a in snapshot["actors"] if a.get("active") is True}
    clear = {(c["x"], c.get("z", c.get("y"))) for c in terrain["cells"]
             if c.get("loaded") is True and c.get("collision") is False
             and c.get("surface", {}).get("known") is True
             and c["surface"].get("present") is False
             and _current_cell_owner(snapshot, fixture["pot"], c)}
    clear -= blocked
    require(start in clear and target in clear, "blocked Hop setup path has unknown or blocked ground")
    previous, queue = {start: None}, deque([start])
    while queue and target not in previous:
        x,z = queue.popleft()
        for dx,dz in ((0,1),(-1,0),(1,0),(0,-1)):
            p = (x+dx,z+dz)
            if p in clear and p not in previous:
                previous[p] = (x,z); queue.append(p)
    require(target in previous, "blocked Hop setup has no clear normal walking path")
    path, tile = [], target
    while tile is not None:
        path.append(list(tile)); tile = previous[tile]
    path.reverse()
    require(len(path) <= 21, "blocked Hop normal walking path exceeds its bound")
    return path


def _key(origin, target):
    return {(0,-1):"UP",(0,1):"DOWN",(-1,0):"LEFT",(1,0):"RIGHT"}[
        (target[0]-origin[0],target[1]-origin[1])]


def walk_leg(step, map_id, key, target, *, max_phase_frames=16):
    """Existing stock input boundary: admit target, release, then finish."""
    for _ in range(max_phase_frames):
        endpoint = step([key])
        if [endpoint["player"][k] for k in ("x", "y")] == list(target):
            break
    else:
        require(False, "normal walking step did not admit its tile")
    for _ in range(max_phase_frames):
        endpoint = step([])
        if player_settled_at(endpoint, map_id, *target):
            return endpoint
    require(False, "normal walking step did not settle")


