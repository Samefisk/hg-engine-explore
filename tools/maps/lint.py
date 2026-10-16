"""Map lint: rules over a decoded World, reported relative to vanilla.

Vanilla HeartGold already breaks some of these rules on purpose (NPCs behind
counters stand on blocked tiles, several doors share one return warp). So lint
reports only findings that the edited world has and the base world does not.
Finding keys use coordinates and targets rather than list positions, so
reordering events does not create noise.

Errors block `apply`; warnings are printed only. A finding can be waived by
listing its key with a reason in data/maps/lint_waivers.json:

  {"waivers": [{"key": "object-blocked:33:600:395", "reason": "NPC behind counter"}]}
"""

from __future__ import annotations

import json
from pathlib import Path

import hashlib

from . import codecs, nsbmd, reach
from .world import World

# Land models the game never binds the area animation to (field_terrain.c
# MapModelNo_HasNoAreaMapAnimation, table _020FC5FC).
NO_AREA_ANIMATION = {0xD0, 0xD2, 0xD3}
_MATERIAL_NAMES: dict[str, list[str] | None] = {}


def land_material_names(data: bytes) -> list[str] | None:
    key = hashlib.sha1(data).hexdigest()
    if key not in _MATERIAL_NAMES:
        try:
            model = nsbmd.parse(codecs.decode_land(data)[1])["models"][0]
            _MATERIAL_NAMES[key] = [m["name"] for m in model["materials"]]
        except Exception:  # not a parseable model: other checks report it
            _MATERIAL_NAMES[key] = None
    return _MATERIAL_NAMES[key]

DYNAMIC_WARP_HEADER = 0xFFF  # vanilla "return to the previous map" warps
ERROR, WARNING = "error", "warning"
WAIVER_FILE = "lint_waivers.json"


def key_text(key: tuple) -> str:
    return ":".join(str(part) for part in key)


def findings(world: World) -> dict[tuple, tuple[str, str]]:
    """key -> (severity, message)."""
    out: dict[tuple, tuple[str, str]] = {}
    counts = {kind: len(members) for kind, members in world.raw.items()}

    for entry in world.headers:
        map_id = entry["id"]
        for field, kind in (("matrixId", "matrix"), ("areaDataBank", "area"), ("eventsBank", "events")):
            if entry[field] >= counts[kind]:
                out[("header-ref", map_id, field)] = (ERROR, f"map {map_id} {field}={entry[field]} past {kind} ({counts[kind]})")
        # Counts include the banks the hg-engine build adds (world.apply_repo_banks).
        for field, kind in (("scriptsBank", "scripts"), ("scriptHeaderBank", "scripts"), ("msgBank", "text")):
            if kind in world.archive_counts and entry[field] >= world.archive_counts[kind]:
                out[("header-ref", map_id, field)] = (ERROR, f"map {map_id} {field}={entry[field]} past "
                                                             f"{kind} ({world.archive_counts[kind]})")

    for index, data in enumerate(world.raw["matrix"]):
        land = world.member("matrix", index)["landData"]
        bad = sorted({land_id for row in land for land_id in row if land_id != 0xFFFF and land_id >= counts["land"]})
        if bad:
            out[("matrix-land", index)] = (ERROR, f"matrix {index} uses land {bad} past land ({counts['land']})")

    # The area's land texture animation binds by material index: land models must
    # start with its materials in order, or other materials (paths, cliffs) scroll.
    checked = set()
    for entry in world.headers:
        if entry.get("alias") or entry["areaDataBank"] >= counts["area"] or entry["matrixId"] >= counts["matrix"]:
            continue
        anim_id = world.member("area", entry["areaDataBank"])["dynamicTextureType"]
        if anim_id >= len(world.land_anims) or not world.land_anims[anim_id]:
            continue
        want = world.land_anims[anim_id]
        matrix = world.matrix_for(entry["id"])
        for z, row in enumerate(matrix["landData"]):
            for x, land_id in enumerate(row):
                owner = matrix["headers"][z][x] if matrix["headers"] else 0
                if land_id in (0xFFFF,) or land_id >= counts["land"] or land_id in NO_AREA_ANIMATION:
                    continue
                if owner and owner != entry["id"]:
                    continue
                if (land_id, anim_id) in checked:
                    continue
                checked.add((land_id, anim_id))
                names = land_material_names(world.raw["land"][land_id])
                if names is not None and names[:len(want)] != want:
                    out[("land-anim-order", land_id, anim_id)] = (
                        ERROR, f"land {land_id} (map {entry['id']}) materials start {names[:len(want)]}, but area "
                               f"animation {anim_id} binds by index to {want}: other materials would animate")

    reachable = reach.reachable_by_matrix(world)

    for entry in world.headers:
        map_id = entry["id"]
        bank = entry["eventsBank"]
        if bank >= counts["events"] or entry["matrixId"] >= counts["matrix"]:
            continue
        events = world.member("events", bank)

        def where(kind, item):
            return f"map {map_id} ({entry['name']}) {kind} at ({item['x']}, {item['z']})"

        for kind in ("objects", "bgs", "warps"):
            for item in events[kind]:
                tile = world.tile(map_id, item["x"], item["z"])
                if tile is None:
                    out[("outside-land", map_id, kind, item["x"], item["z"])] = (ERROR, f"{where(kind, item)} is outside loaded land")
                elif kind == "objects" and tile[0]:
                    out[("object-blocked", map_id, item["x"], item["z"])] = (ERROR, f"{where(kind, item)} stands on a blocked tile")
        for item in events["coords"]:
            for corner in ((item["x"], item["z"]), (item["x"] + item["w"] - 1, item["z"] + item["h"] - 1)):
                if world.tile(map_id, *corner) is None:
                    out[("outside-land", map_id, "coords", item["x"], item["z"])] = (ERROR, f"{where('coords', item)} reaches outside loaded land")

        if entry["matrixId"] in reachable:
            grid, seen = reachable[entry["matrixId"]]
            for kind in ("objects", "bgs", "warps", "coords"):
                for item in events[kind]:
                    if kind == "coords":
                        tiles = [(item["x"] + dx, item["z"] + dz)
                                 for dz in range(max(item["h"], 1)) for dx in range(max(item["w"], 1))]
                    else:
                        tiles = [(item["x"], item["z"])]
                    if world.tile(map_id, *tiles[0]) is None:
                        continue  # already reported as outside-land
                    if not any(reach.near_reachable(grid, seen, x, z) for x, z in tiles):
                        out[("unreachable", map_id, kind, item["x"], item["z"])] = (
                            ERROR, f"{where(kind, item)} cannot be reached on foot or by Surf from any warp")

        local_limit = world.script_ranges[-1][0] if world.script_ranges else None
        bank = entry["scriptsBank"]
        known = bank < len(world.script_entries) and world.script_entries[bank] is not None
        if local_limit is not None and known:
            available = world.script_entries[bank]
            for kind in ("objects", "bgs", "coords"):
                for item in events[kind]:
                    script = item["scriptId"]
                    if 1 <= script < local_limit and script - 1 >= available:
                        out[("script-ref", map_id, kind, item["x"], item["z"], script)] = (
                            ERROR, f"{where(kind, item)} runs local script {script}, but scr_seq {bank} "
                                   f"has {available} scripts")

        object_ids = [item["id"] for item in events["objects"]]
        for duplicate in sorted({i for i in object_ids if object_ids.count(i) > 1}):
            out[("object-id-duplicate", map_id, duplicate)] = (ERROR, f"map {map_id} has several objects with id {duplicate}")

        for item in events["warps"]:
            dest, anchor = item["header"], item["anchor"]
            key = (map_id, item["x"], item["z"], dest, anchor)
            if dest == DYNAMIC_WARP_HEADER:
                continue
            if dest >= len(world.headers):
                out[("warp-dest", *key)] = (ERROR, f"{where('warps', item)} targets map {dest}, past the header table")
                continue
            dest_bank = world.headers[dest]["eventsBank"]
            if dest_bank >= counts["events"]:
                continue
            dest_warps = world.member("events", dest_bank)["warps"]
            if anchor >= len(dest_warps):
                out[("warp-anchor", *key)] = (ERROR, f"{where('warps', item)} targets warp {anchor} of map {dest}, "
                                                     f"which has {len(dest_warps)} warps")
                continue
            back = dest_warps[anchor]
            if back["header"] not in (map_id, DYNAMIC_WARP_HEADER):
                out[("warp-unpaired", *key)] = (WARNING, f"{where('warps', item)} -> map {dest} warp {anchor}, "
                                                         f"which leads to map {back['header']}, not back here")
    return out


def load_waivers(overrides: Path) -> dict[str, str]:
    path = overrides / WAIVER_FILE
    if not path.exists():
        return {}
    entries = json.loads(path.read_text()).get("waivers", [])
    missing_reason = [entry.get("key") for entry in entries if not entry.get("reason")]
    if missing_reason:
        raise ValueError(f"{WAIVER_FILE}: waivers need a reason: {missing_reason}")
    return {entry["key"]: entry["reason"] for entry in entries}


def lint(world: World, base: World, waivers: dict[str, str] | None = None) -> dict:
    """New findings split by severity, plus waived and resolved counts."""
    waivers = waivers or {}
    edited, vanilla = findings(world), findings(base)
    result = {ERROR: [], WARNING: [], "waived": [], "resolved": sum(1 for key in vanilla if key not in edited)}
    for key, (severity, message) in sorted(edited.items(), key=lambda kv: str(kv[0])):
        if key in vanilla:
            continue
        text = key_text(key)
        if text in waivers:
            result["waived"].append(f"{message} [{text}] waived: {waivers[text]}")
        else:
            result[severity].append(f"{message} [{text}]")
    return result
