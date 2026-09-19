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


def _check(spawn, snapshot, source_sha256, authored_profiles, verified_stop_boundary):
    ownership = check_pool_spawn_receipt(spawn, source_sha256=source_sha256,
                                         authored_profiles=authored_profiles)
    _need(ownership["passed"], "own POOL target was not preserved")
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
                             verified_stop_boundary=None):
    """Validate native landing receipts plus a same-actor terminal snapshot.

    Caller must separately prove full motion lifecycle/coverage. Optional
    verified_stop_boundary is the existing Ledyba meter's checked stopBoundary,
    not raw input: it allows a just-started successor without requiring a new
    idle frame. This checker validates its exact endpoint but does not recreate
    that meter's predecessor lifecycle/trace proof. Unknown or
    forbidden data raises ValueError; success cannot grant controller acceptance.
    """
    try:
        return _check(spawn, terminal_snapshot, source_sha256, authored_profiles, verified_stop_boundary)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError("incomplete spawn surface evidence") from error
