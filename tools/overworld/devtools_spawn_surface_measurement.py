"""Pure POOL metatile/surface/height check, never general geometry acceptance.

Native ABI anchors: overworld_wild_behavior_data.h; vanilla unk_02054648.s
(attribute behavior low byte, blocked bit15), map_object.h (ignore heights
bit23), and unk_0205FD20.s/sub_02061070 (height refresh). The existing POOL
ownership result stays a separate claim. This check adds no emulator or IO.
"""
from copy import deepcopy

from tools.overworld.devtools_spawn_measurement import check_pool_spawn_receipt
from tools.overworld.normal_play_observer import live_identity


LAND_BEHAVIORS = frozenset((2, 3, 5, 8, 11, 37, 112, 119, 123, 163, 164))
SURF_BEHAVIORS = frozenset((16, 18, 21, 42))
IGNORE_HEIGHTS = 1 << 23
SCOPE = "loaded metatile legality, authored surface exclusion and native terminal height; unmodeled geometry excluded"


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _int(value):
    return type(value) is int


def _engine(engine, source, world):
    _need(isinstance(engine, dict) and engine.get("pointer") == source.get("object")
          and engine.get("active") is True and engine.get("in_manager") is True
          and engine.get("object_manager") == engine.get("current_manager")
          and engine.get("object_id") == source.get("object_id")
          and engine.get("object_map_id") == world.get("mapId")
          and engine.get("current_map_id") == world.get("mapId")
          and engine.get("id_lookup", {}).get("eligible_count") == 1
          and engine.get("id_lookup", {}).get("pointer_matches") is True,
          "landing engine ownership is missing or changed")


def pool_fly_loaded_cell(spawn, snapshot, *, stage):
    """Reuse the shared live terrain/catalog sample at the actual POOL target."""
    target, world = spawn["position"], spawn["worldContext"]
    _need(snapshot.get("prepared") is False
          and snapshot.get("observationBoundary") == "main-task-queue-completion"
          and all(snapshot.get("context", {}).get(k) == world[k]
                  for k in ("mapId", "fieldEpoch", "mapGeneration")), "Fly In terrain boundary/world differs")
    if "poolFlyTerrain" in snapshot:
        rows = [row for row in snapshot["poolFlyTerrain"] if row.get("subject", {}).get("handle") == spawn["publicSubject"]["handle"]]
        _need(len(rows) == 1 and rows[0].get("status") == "observed" and rows[0].get("stage") == stage
              and rows[0].get("worldContext") == world and rows[0].get("target") == target
              and all(rows[0]["subject"].get(k) == spawn["publicSubject"].get(k)
                      for k in ("species", "role", "subjectIdentity", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")),
              "Fly In exact loaded POOL receipt differs")
        cells = [rows[0].get("cell")]
    else:
        cells = [cell for cell in snapshot.get("terrain", {}).get("cells", [])
                 if [cell.get("x"), cell.get("y")] == target]
    _need(len(cells) == 1, "Fly In exact loaded POOL cell is missing or duplicated")
    cell = cells[0]
    p, raw, surface = cell.get("provenance", {}), cell.get("attribute"), cell.get("surface", {})
    _need(cell.get("loaded") is True and p.get("fieldPointer") == world["fieldPointer"]
          and p.get("landDataIdentity") == "current-map-matrix"
          and p.get("store") in ("full-terrain-attributes", "rolling-land-manager")
          and _int(p.get("landDataId")) and p["landDataId"] != 0xFFFF
          and _int(p.get("attributeAddress")) and p["attributeAddress"] % 2 == 0
          and 0x02000000 <= p["attributeAddress"] < 0x02400000
          and _int(raw) and 0 <= raw <= 65535 and p.get("rawWord") == raw,
          "Fly In loaded terrain provenance differs")
    _need(all(_int(p.get(k)) and p[k] > 0 for k in ("matrixWidth", "matrixHeight"))
          and target[0] < p["matrixWidth"] * 32 and target[1] < p["matrixHeight"] * 32
          and cell.get("matrix_index") == target[1] // 32 * p["matrixWidth"] + target[0] // 32,
          "Fly In loaded matrix index differs")
    _need(cell.get("behavior") == raw & 255 and cell.get("collision") is bool(raw & 0x8000)
          and cell.get("terrain_class") == (raw >> 8) & 127 and not cell["collision"],
          "Fly In loaded tile decode/collision differs")
    allowed = LAND_BEHAVIORS if spawn["terrain"] == 0 else SURF_BEHAVIORS
    _need(spawn["terrain"] in (0, 1) and cell["behavior"] in allowed,
          "Fly In POOL tile differs from its Land/Surf encounter source")
    _need(surface.get("known") is True and surface.get("present") is False
          and _int(surface.get("catalogPointer")) and surface["catalogPointer"] % 4 == 0
          and 0x02000000 <= surface["catalogPointer"] < 0x02400000
          and surface.get("landDataId") == p["landDataId"]
          and [surface.get("localX"), surface.get("localZ")] == [n % 32 for n in target],
          "Fly In authored surface is present or unknown")
    return deepcopy(cell)


def _check_pool_fly_surface(spawn, snapshot, ownership, stop, admission_cell):
    world, target, subject = spawn["worldContext"], ownership["landingTarget"], spawn["publicSubject"]
    _need(isinstance(admission_cell, dict), "Fly In has no loaded admission cell")
    terminal_cell = pool_fly_loaded_cell(spawn, snapshot, stage="terminal")
    _need(terminal_cell == admission_cell, "Fly In loaded target changed before its terminal")
    actors = [a for a in snapshot.get("actors", []) if a.get("handle") == subject.get("handle")]
    _need(len(actors) == 1, "Fly In terminal actor is missing or duplicated")
    actor = actors[0]
    source = spawn["jumpReceipts"][0]["sourceIdentity"]
    _need(live_identity(actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                        species=165, role="WILD", current_epoch=world["fieldEpoch"])
          and actor.get("sourceIdentity") == source
          and all(actor.get(k) == subject.get(k) for k in
                  ("species", "form", "level", "subjectIdentity", "authorityGeneration",
                   "engineAnchorGeneration", "presentationGeneration")), "Fly In terminal subject differs")
    _engine(actor.get("engineIdentity"), source, world)
    _need(isinstance(stop, dict) and stop.get("frame") == snapshot["frame"], "Fly In terminal boundary is missing")
    successor = stop.get("kind") == "terminal-with-unmeasured-successor"
    if successor:
        next_motion = stop.get("successor", {})
        _need(stop.get("completedCommit") == actor["commitSequence"]
              and next_motion.get("handle") == actor["handle"] and next_motion.get("origin") == target
              and next_motion.get("kind") == actor["motionKind"]
              and next_motion.get("target") == [actor["target"][k] for k in ("x", "y")]
              and next_motion.get("elapsed") == actor["motionElapsed"] == 0
              and actor["motionPhase"] == "MOVING" and next_motion.get("countedAsComplete") is False,
              "Fly In unmeasured successor boundary differs")
    else:
        _need(stop.get("kind") == "idle" and actor["motionPhase"] == "IDLE"
              and actor["reservationId"] == 0 and actor["inputOwnership"] == 0,
              "Fly In terminal control is not returned")
    engine, base_y = actor["engineObject"], spawn["startup"]["targetBaseY"]
    _need(_int(base_y) and engine.get("pos_y") == base_y and engine.get("unk88_y") == 0,
          "Fly In terminal height differs from its actual finalized ground height")
    _need([engine.get("pos_x"), engine.get("pos_z")] == [(n << 16) + 0x8000 for n in target]
          and (successor or [actor["logical"][k] for k in ("x", "y")] == target),
          "Fly In terminal is not its POOL target center")
    for clock, snap in (("ActorFrame", "actorFrame"), ("NativeCycle", "nativeCycle")):
        _need(_int(snapshot.get(snap)) and _int(spawn.get("return" + clock))
              and snapshot[snap] >= spawn["return" + clock], "Fly In terminal clocks precede its spawn")
    return {"passed": True, "scope": SCOPE, "acceptedProof": False,
            "loadedTerrainVerified": True, "authoredSurfaceExcluded": True, "terminalHeightVerified": True,
            "subject": deepcopy(subject), "target": target, "terrain": spawn["terrain"],
            "nativeLandingY": base_y, "terminalFrame": snapshot["actorFrame"],
            "heightSource": "finalized-Fly-In-target", "nativeHeightRefreshRequired": False}


def _check(spawn, snapshot, source_sha256, authored_profiles, verified_stop_boundary, fly_admission_cell):
    ownership = check_pool_spawn_receipt(spawn, source_sha256=source_sha256,
                                         authored_profiles=authored_profiles)
    _need(ownership["passed"], "own POOL target was not preserved")
    if ownership["startupKind"] == 9:
        return _check_pool_fly_surface(spawn, snapshot, ownership, verified_stop_boundary, fly_admission_cell)
    _need(spawn["terrain"] in (0, 1), "surface witness supports only Land/Surf POOL encounters")
    jumps = spawn.get("jumpReceipts")
    _need(isinstance(jumps, list) and len(jumps) == 1, "one exact spawn jump is required")
    jump = jumps[0]
    h = jump.get("landingHeight")
    _need(isinstance(h, dict) and h.get("status") == "observed"
          and type(h.get("observationVersion")) is int and h["observationVersion"] == 1,
          "native landing height is missing")
    world, target = spawn["worldContext"], ownership["landingTarget"]
    for key in ("slot", "preparedPointer", "preparedEncounter", "worldContext"):
        _need(h.get(key) == spawn.get(key), "landing binding differs: " + key)
    _need(h.get("target") == target == jump.get("target"), "landing target differs")
    _need(h.get("nativeReturnKind") == "void" and h.get("returnValue") is None,
          "landing-height native return contract differs")
    source = h.get("sourceIdentity")
    _need(isinstance(source, dict) and source == jump.get("sourceIdentity"), "landing source differs")
    _need(all(source.get(k) == spawn["preparedEncounter"].get(k)
              for k in ("species", "form", "level", "personality")), "landing encounter differs")
    _engine(h.get("engineIdentity"), source, world)
    _engine(h.get("engineIdentityAfter"), source, world)
    _need(h["engineIdentity"] == h["engineIdentityAfter"], "native landing engine changed")
    _need(snapshot.get("observationBoundary") == "main-task-queue-completion"
          and snapshot.get("prepared") is False
          and all(snapshot.get("context", {}).get(k) == world[k]
                  for k in ("mapId", "fieldEpoch", "mapGeneration")), "terminal boundary/world differs")
    subject = spawn["publicSubject"]
    actors = [a for a in snapshot["actors"] if a.get("handle") == subject.get("handle")]
    _need(len(actors) == 1, "terminal actor is missing or duplicated")
    actor = actors[0]
    _need(live_identity(actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                        species=165, role="WILD", current_epoch=world["fieldEpoch"])
          and actor.get("sourceIdentity") == source
          and all(actor.get(k) == subject.get(k) for k in
                  ("species", "form", "level", "subjectIdentity", "authorityGeneration",
                   "engineAnchorGeneration", "presentationGeneration")), "terminal subject differs")
    _engine(actor.get("engineIdentity"), source, world)
    successor_boundary = False
    if verified_stop_boundary is not None:
        boundary = verified_stop_boundary
        _need(isinstance(boundary, dict) and boundary.get("frame") == snapshot.get("frame"),
              "verified terminal boundary frame differs")
        if boundary.get("kind") == "terminal-with-unmeasured-successor":
            successor = boundary.get("successor", {})
            _need(boundary.get("completedCommit") == actor.get("commitSequence")
                  and _int(boundary.get("completedCommit"))
                  and successor.get("handle") == actor.get("handle")
                  and successor.get("kind") == actor.get("motionKind")
                  and successor.get("kind") in ("WALK", "HOP", "TELEPORT", "REPOSITION")
                  and successor.get("origin") == target
                  and successor.get("origin") == [actor.get("origin", {}).get(k) for k in ("x", "y")]
                  and successor.get("target") == [actor.get("target", {}).get(k) for k in ("x", "y")]
                  and type(successor.get("elapsed")) is int and successor["elapsed"] == 0
                  and successor.get("countedAsComplete") is False
                  and actor.get("motionPhase") == "MOVING" and actor.get("motionElapsed") == 0,
                  "verified zero-elapsed successor boundary differs")
            successor_boundary = True
        else:
            _need(boundary.get("kind") == "idle", "unknown verified terminal boundary")
    if not successor_boundary:
        _need(actor.get("motionPhase") == "IDLE" and actor.get("reservationId") == 0
              and actor.get("inputOwnership") == 0, "terminal control is not returned")
    for suffix, snapshot_key in (("ActorFrame", "actorFrame"), ("NativeCycle", "nativeCycle")):
        values = [h.get("entry" + suffix), h.get("return" + suffix), snapshot.get(snapshot_key)]
        _need(all(_int(n) and n >= 0 for n in values) and values == sorted(values),
              "landing clocks are missing or after terminal")
    query, refresh = h.get("surfaceQuery"), h.get("heightRefresh")
    _need(isinstance(query, dict) and query.get("kind") == "surface" and query.get("point") == target
          and type(query.get("returnValue")) is int and query["returnValue"] in (0, 1),
          "native target surface query is unknown")
    # A native-ground sentinel can belong to an authored flower-bed surface.
    # Any positive authored surface is outside this legacy POOL rule.
    _need(query["returnValue"] == 0 and query.get("hit") is None,
          "POOL landing uses an authored surface")
    _need(isinstance(refresh, dict) and refresh.get("kind") == "height-refresh"
          and refresh.get("objectPointer") == source["object"]
          and type(refresh.get("returnValue")) is int and refresh["returnValue"] == 1
          and h.get("heightSource") == "native-refresh", "native height refresh did not succeed")
    flags = refresh.get("positionBefore", {}).get("flags")
    _need(_int(flags) and not flags & IGNORE_HEIGHTS, "native height refresh ignored terrain")
    for detail in (query, refresh):
        for key, suffix in (("actorFrame", "ActorFrame"), ("nativeCycle", "NativeCycle")):
            values = [h["entry" + suffix], detail.get("entry", {}).get(key),
                      detail.get("returned", {}).get(key), h["return" + suffix]]
            _need(all(_int(n) for n in values) and values == sorted(values), "native child clocks differ")
    before, after, terminal = h["positionBefore"], h["positionAfter"], actor["engineObject"]
    _need(all(_int(p.get("pos_y")) for p in (before, after, terminal)), "native Y is missing")
    _need(refresh.get("positionAfter", {}).get("pos_y") == after["pos_y"] == terminal["pos_y"],
          "terminal Y differs from native landing height")
    _need(terminal.get("unk88_y") == 0, "terminal retains a separate jump offset")
    _need(_int(terminal.get("flags")) and terminal["flags"] & 1
          and (successor_boundary or not terminal["flags"] & 2), "terminal native object is not ready")
    for pose in (after, terminal):
        _need((pose is terminal and successor_boundary or [pose.get("x"), pose.get("y")] == target)
              and [pose.get("pos_x"), pose.get("pos_z")] == [(n << 16) + 0x8000 for n in target],
              "native landing pose is not the target center")
    cells = []
    for name in ("loadedTerrainBefore", "loadedTerrain"):
        record = h.get(name, {})
        cell = record.get("cell")
        _need(record.get("status") == "observed" and isinstance(cell, dict), "loaded target terrain is unknown")
        p = cell.get("provenance", {})
        raw = cell.get("attribute")
        _need([cell.get("x"), cell.get("y")] == target and p.get("fieldPointer") == world["fieldPointer"]
              and p.get("landDataIdentity") == "current-map-matrix"
              and p.get("store") in ("full-terrain-attributes", "rolling-land-manager")
              and _int(p.get("landDataId")) and p["landDataId"] != 0xFFFF
              and _int(p.get("attributeAddress")) and p["attributeAddress"] % 2 == 0
              and 0x02000000 <= p["attributeAddress"] < 0x02400000
              and _int(raw) and 0 <= raw <= 65535 and p.get("rawWord") == raw,
              "loaded terrain provenance differs")
        _need(all(_int(p.get(k)) and p[k] > 0 for k in ("matrixWidth", "matrixHeight"))
              and target[0] < p["matrixWidth"] * 32 and target[1] < p["matrixHeight"] * 32
              and cell.get("matrix_index") == target[1] // 32 * p["matrixWidth"] + target[0] // 32,
              "loaded target matrix index differs")
        _need(cell.get("behavior") == raw & 255 and type(cell.get("collision")) is bool
              and cell["collision"] == bool(raw & 0x8000)
              and cell.get("terrain_class") == (raw >> 8) & 127, "terrain decode differs")
        _need(not cell["collision"], "POOL target has native tile collision")
        allowed = LAND_BEHAVIORS if spawn["terrain"] == 0 else SURF_BEHAVIORS
        _need(cell["behavior"] in allowed, "target differs from actual encounter source")
        cells.append(cell)
    _need(cells[0] == cells[1], "loaded terrain changed during landing height resolution")
    return {"passed": True, "scope": SCOPE, "acceptedProof": False,
            "loadedTerrainVerified": True, "authoredSurfaceExcluded": True, "terminalHeightVerified": True,
            "subject": deepcopy(subject), "target": target, "terrain": spawn["terrain"],
            "nativeLandingY": after["pos_y"], "terminalFrame": snapshot["actorFrame"]}


def check_pool_spawn_surface(spawn, terminal_snapshot, *, source_sha256, authored_profiles,
                             verified_stop_boundary=None, fly_admission_cell=None):
    """Validate native landing receipts plus a same-actor terminal snapshot.

    Caller must separately prove full motion lifecycle/coverage. Optional
    verified_stop_boundary is the existing Ledyba meter's checked stopBoundary,
    not raw input: it allows a just-started successor without requiring a new
    idle frame. This checker validates its exact endpoint but does not recreate
    that meter's predecessor lifecycle/trace proof. Unknown or
    forbidden data raises ValueError; success cannot grant controller acceptance.
    """
    try:
        return _check(spawn, terminal_snapshot, source_sha256, authored_profiles, verified_stop_boundary, fly_admission_cell)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError("incomplete spawn surface evidence") from error


def _check_natural_appear_hop_surface(spawn, terminal_snapshot, *, species, terrain, prepared):
    """Validate the first native height read for one natural Appear Hop.

    This is the current recorder-calibration path. It deliberately does not
    claim legacy POOL placement or off-screen Hop geometry.
    """
    try:
        _need(spawn.get("observation") == "spawn-prepared"
              and spawn.get("setupMode") == ("prepared" if prepared else "normal")
              and terrain in (0, 1) and spawn.get("terrain") == terrain
              and spawn.get("returnValue") == 1,
              "natural Appear Hop needs one successful normal spawn")
        _need(spawn.get("startup", {}).get("locomotion") == 7
              and spawn.get("startup", {}).get("target") == spawn.get("position")
              and spawn.get("startup", {}).get("origin") == spawn.get("position"),
              "natural Appear Hop startup differs")
        h = spawn.get("initialLandingHeight")
        _need(isinstance(h, dict) and h.get("status") == "observed"
              and h.get("observationVersion") == 1
              and h.get("initialPlacement") is True,
              "native initial landing height is missing")
        world = spawn["worldContext"]
        target = spawn["position"]
        subject = spawn["publicSubject"]
        _need(subject.get("species") == species and subject.get("role") == "WILD"
              and spawn.get("preparedEncounter", {}).get("species") == species,
              "natural Appear Hop subject differs")
        for key in ("slot", "preparedPointer", "preparedEncounter", "worldContext"):
            _need(h.get(key) == spawn.get(key), "landing binding differs: " + key)
        _need(h.get("target") == target, "landing target differs")
        _need(h.get("nativeReturnKind") == "void" and h.get("returnValue") is None,
              "landing-height native return contract differs")
        source = h.get("sourceIdentity")
        _need(isinstance(source, dict)
              and all(source.get(key) == spawn["preparedEncounter"].get(key)
                      for key in ("species", "form", "level", "personality")),
              "landing encounter differs")
        _engine(h.get("engineIdentity"), source, world)
        _engine(h.get("engineIdentityAfter"), source, world)
        _need(h["engineIdentity"] == h["engineIdentityAfter"],
              "native landing engine changed")
        _need(terminal_snapshot.get("observationBoundary") == "main-task-queue-completion"
              and terminal_snapshot.get("prepared") is prepared
              and all(terminal_snapshot.get("context", {}).get(key) == world[key]
                      for key in ("mapId", "fieldEpoch", "mapGeneration")),
              "terminal boundary/world differs")
        actors = [actor for actor in terminal_snapshot.get("actors", [])
                  if actor.get("handle") == subject.get("handle")]
        _need(len(actors) == 1, "terminal actor is missing or duplicated")
        actor = actors[0]
        _need(live_identity(actor, actor.get("sourceIdentity", {}),
                            actor.get("engineIdentity", {}), species=species,
                            role="WILD", current_epoch=world["fieldEpoch"])
              and actor.get("sourceIdentity") == source
              and all(actor.get(key) == subject.get(key) for key in
                      ("species", "form", "level", "subjectIdentity",
                       "authorityGeneration", "engineAnchorGeneration",
                       "presentationGeneration")),
              "terminal subject differs")
        _engine(actor.get("engineIdentity"), source, world)
        _need(actor.get("motionPhase") == "IDLE"
              and actor.get("reservationId") == 0
              and actor.get("inputOwnership") == 0,
              "terminal control is not returned")
        for suffix, snapshot_key in (("ActorFrame", "actorFrame"),
                                     ("NativeCycle", "nativeCycle")):
            clocks = [h.get("entry" + suffix), h.get("return" + suffix),
                      terminal_snapshot.get(snapshot_key)]
            _need(all(_int(value) and value >= 0 for value in clocks)
                  and clocks == sorted(clocks),
                  "landing clocks are missing or after terminal")
        query, refresh = h.get("surfaceQuery"), h.get("heightRefresh")
        _need(isinstance(query, dict) and query.get("kind") == "surface"
              and query.get("point") == target
              and query.get("returnValue") == 0 and query.get("hit") is None,
              "natural landing uses an unknown or authored surface")
        _need(isinstance(refresh, dict) and refresh.get("kind") == "height-refresh"
              and refresh.get("objectPointer") == source["object"]
              and refresh.get("returnValue") == 1
              and h.get("heightSource") == "native-refresh",
              "native height refresh did not succeed")
        flags = refresh.get("positionBefore", {}).get("flags")
        _need(_int(flags) and not flags & IGNORE_HEIGHTS,
              "native height refresh ignored terrain")
        for detail in (query, refresh):
            for key, suffix in (("actorFrame", "ActorFrame"),
                                ("nativeCycle", "NativeCycle")):
                clocks = [h["entry" + suffix], detail.get("entry", {}).get(key),
                          detail.get("returned", {}).get(key), h["return" + suffix]]
                _need(all(_int(value) for value in clocks)
                      and clocks == sorted(clocks), "native child clocks differ")
        before, after, terminal = h["positionBefore"], h["positionAfter"], actor["engineObject"]
        _need(all(_int(pose.get("pos_y")) for pose in (before, after, terminal)),
              "native Y is missing")
        _need(refresh.get("positionAfter", {}).get("pos_y") == after["pos_y"]
              == terminal["pos_y"], EXPECTED_HEIGHT_REASON)
        _need(terminal.get("unk88_y") == 0,
              "terminal retains a separate jump offset")
        _need(_int(terminal.get("flags")) and terminal["flags"] & 1
              and not terminal["flags"] & 2,
              "terminal native object is not ready")
        for pose in (after, terminal):
            _need([pose.get("x"), pose.get("y")] == target
                  and [pose.get("pos_x"), pose.get("pos_z")]
                      == [(coordinate << 16) + 0x8000 for coordinate in target],
                  "native landing pose is not the target center")
        cells = []
        for name in ("loadedTerrainBefore", "loadedTerrain"):
            record = h.get(name, {})
            cell = record.get("cell")
            _need(record.get("status") == "observed" and isinstance(cell, dict),
                  "loaded target terrain is unknown")
            provenance = cell.get("provenance", {})
            raw = cell.get("attribute")
            _need([cell.get("x"), cell.get("y")] == target
                  and provenance.get("fieldPointer") == world["fieldPointer"]
                  and provenance.get("landDataIdentity") == "current-map-matrix"
                  and provenance.get("store") in
                      ("full-terrain-attributes", "rolling-land-manager")
                  and _int(provenance.get("landDataId"))
                  and provenance["landDataId"] != 0xFFFF
                  and _int(provenance.get("attributeAddress"))
                  and provenance["attributeAddress"] % 2 == 0
                  and 0x02000000 <= provenance["attributeAddress"] < 0x02400000
                  and _int(raw) and 0 <= raw <= 65535
                  and provenance.get("rawWord") == raw,
                  "loaded terrain provenance differs")
            _need(cell.get("behavior") == raw & 255
                  and type(cell.get("collision")) is bool
                  and cell["collision"] == bool(raw & 0x8000)
                  and cell.get("terrain_class") == (raw >> 8) & 127,
                  "terrain decode differs")
            _need(not cell["collision"] and cell["behavior"] in (LAND_BEHAVIORS if terrain == 0 else SURF_BEHAVIORS),
                  "natural landing target is blocked or has the wrong encounter terrain")
            cells.append(cell)
        _need(cells[0] == cells[1],
              "loaded terrain changed during landing height resolution")
        return {"passed": True, "acceptedProof": False,
                "scope": "natural Appear Hop initial native height and terminal pose",
                "subject": deepcopy(subject), "target": target,
                "nativeLandingY": after["pos_y"],
                "terminalFrame": terminal_snapshot["actorFrame"]}
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError("incomplete natural Appear Hop surface evidence") from error


def check_natural_appear_hop_surface(spawn, terminal_snapshot, *, species=179):
    """Keep the existing normal LAND recorder-calibration contract."""
    return _check_natural_appear_hop_surface(spawn, terminal_snapshot,
        species=species, terrain=0, prepared=False)


def check_natural_water_surface(spawn, terminal_snapshot, *, species):
    """Same native height/ownership proof, for natural Surf in a prepared window.

    The caller must separately prove the natural finalizer and constructor.
    Prepared means the declared teleport; it grants no placement or spawn credit.
    """
    return _check_natural_appear_hop_surface(spawn, terminal_snapshot,
        species=species, terrain=1, prepared=True)


EXPECTED_HEIGHT_REASON = "terminal Y differs from native landing height"
