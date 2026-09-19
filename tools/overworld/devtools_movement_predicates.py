"""Typed read-only normal-input predicates over coherent shared snapshots.

Stock sources: map_object.h; unk_02062108.s (ready/held flags);
unk_0205FD20.s:sub_02060F24 (reserve next tile, retain origin);
unk_0205CB48.s:sub_0205CFBC (idle FACE reset copies current to previous).
An admitted tile is not a completed movement. These predicates do not grant
actor identity, route coverage, healing provenance, or gameplay acceptance.
"""
from __future__ import annotations

from copy import deepcopy


MOVEMENT_PREDICATE_KINDS = frozenset({
    "player-settled-at", "player-step-count", "party-field", "selector-field",
    "dialogue-state", "follower-settled",
})
DIALOGUE_STATES = frozenset({"idle", "busy", "printing", "page-wait", "yes-no-ready", "script-button-wait"})
OPERATORS = frozenset({"eq", "ne", "gte", "lte"})
PARTY_FIELDS = {
    "slot": (int, 0, 5), "species": (int, 0, 65535),
    "personality": (int, 0, 0xFFFFFFFF), "identityVerified": (bool, 0, 1),
    "isEgg": (bool, 0, 1), "form": (int, 0, 31), "level": (int, 0, 100),
    "hp": (int, 0, 65535), "maxHp": (int, 0, 65535), "status": (int, 0, 0xFFFFFFFF),
}
SELECTOR_FIELDS = {
    **{name: (int, 0, 255) for name in ("state", "highlight", "flags",
       "activeFollowerPartySlot", "followerReleaseState", "queue.headIssued",
       "queue.headRetries", "queue.request")},
    "queue.count": (int, 0, 10), "queue.commands": (int, 0, 0xFFFFFFFF),
    **{name: (int, 0, 0xFFFFFFFF) for name in (
       "heldKeys", "newKeys", "rawHeld", "rawNew", "buttonMode", "simulatedKeys")},
    **{name: (int, 0, 65535) for name in ("physicalPressed", "keyInput", "xyKeys", "captureTargetMask")},
}
FRAME_BOUNDARY = "main-task-queue-completion"


def _int(value, label, low=0, high=0xFFFFFFFF):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in {low}..{high}")
    return value


def _shape(value, fields):
    if not isinstance(value, dict) or set(value) - fields - {"when"} or fields - set(value):
        raise ValueError("movement predicate has missing or unknown fields")


def _typed(value, spec, label):
    kind, low, high = spec
    if type(value) is not kind:
        raise ValueError(f"{label} has the wrong type")
    if kind is int:
        _int(value, label, low, high)
    return value


def validate_movement_predicate(value):
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str) \
            or value["kind"] not in MOVEMENT_PREDICATE_KINDS:
        raise ValueError("unsupported movement predicate kind")
    kind = value["kind"]
    if kind == "follower-settled":
        _shape(value, {"kind", "species", "partySlot"})
        _int(value["species"], "follower species", 1, 1075)
        _int(value["partySlot"], "follower party slot", 0, 5)
    elif kind == "dialogue-state":
        _shape(value, {"kind", "state"})
        if not isinstance(value["state"], str) or value["state"] not in DIALOGUE_STATES:
            raise ValueError("unsupported dialogue state")
    elif kind == "player-settled-at":
        _shape(value, {"kind", "map", "x", "z"})
        _int(value["map"], "map", 0, 539)
        for axis in ("x", "z"):
            _int(value[axis], axis, 0, 32767)
    else:
        fields = {"kind", "operator", "value"}
        if kind in ("party-field", "selector-field"):
            fields.add("path")
        if kind == "party-field":
            fields.add("slot")
        _shape(value, fields)
        if not isinstance(value["operator"], str) or value["operator"] not in OPERATORS:
            raise ValueError("unsupported movement predicate operator")
        if kind == "player-step-count":
            spec = (int, 0, 0xFFFFFFFF)
        else:
            allowed = PARTY_FIELDS if kind == "party-field" else SELECTOR_FIELDS
            if not isinstance(value["path"], str) or value["path"] not in allowed:
                raise ValueError("predicate path is not an allowed public field")
            spec = allowed[value["path"]]
            if kind == "party-field":
                _int(value["slot"], "party slot", 0, 5)
        _typed(value["value"], spec, "predicate value")
        if spec[0] is bool and value["operator"] not in ("eq", "ne"):
            raise ValueError("boolean fields require eq or ne")
    if value.get("when", "final") not in ("always", "final"):
        raise ValueError("predicate when must be always or final")
    return {**deepcopy(value), "when": value.get("when", "final")}


def _path(value, path):
    for name in path.split("."):
        if not isinstance(value, dict) or name not in value:
            raise ValueError("required public field is missing: " + path)
        value = value[name]
    return value


def _coherent(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("observationBoundary") != FRAME_BOUNDARY:
        raise ValueError("predicate needs a completed-main-queue snapshot")
    return _int(snapshot.get("frame"), "snapshot frame")


def player_settled_at(snapshot, map_id, x, z):
    """Exact ground pose plus stock ready flags, not a reserved logical tile.

    During a finished held move previous remains its cardinal origin. It need
    not equal current until the idle/FACE reset runs. A bare current/previous
    coordinate match or command255 does not establish readiness.
    """
    _coherent(snapshot)
    player = _path(snapshot, "player")
    observed = {key: _int(_path(player, key), "player." + key, -0x80000000, 0x7FFFFFFF)
                for key in ("x", "y", "x_prev", "y_prev", "pos_x", "pos_z", "unk88_y")}
    flags = _int(_path(player, "flags"), "player.flags")
    command = _int(_path(player, "movement_cmd"), "player.movement_cmd", 0, 255)
    current_map = _int(_path(snapshot, "context.mapId"), "current map", 0, 539)
    task = _int(_path(snapshot, "fieldControl.taskPointer"), "field task")
    # MapObject_AreBitsSetForMovementScriptInit, stock0x02062108.
    ready = bool(flags & 1) and not flags & 2 and (not flags & 0x10 or bool(flags & 0x20))
    center = (x * 0x10000 + 0x8000, z * 0x10000 + 0x8000)
    if not ready or task or current_map != map_id or (observed["x"], observed["y"]) != (x, z) \
            or (observed["pos_x"], observed["pos_z"]) != center or observed["unk88_y"] != 0:
        return False
    previous_distance = abs(observed["x_prev"] - x) + abs(observed["y_prev"] - z)
    if command in (0, 1, 2, 3, 255):
        return previous_distance == 0
    # Stock held commands are 0..0x70. The finished bit must be observed;
    # accepting a stale movement command on cleared flags would hide a reset.
    return command < 0x71 and flags & 0x30 == 0x30 and previous_distance <= 1


def follower_settled(snapshot, species, party_slot):
    from tools.overworld.devtools_records import select_current_actor
    from tools.overworld.spawn_identity import live_spawn_flags
    frame = _coherent(snapshot)
    provenance = _path(snapshot, "partyObservation")
    if _int(_path(provenance, "frame"), "party frame") != frame or _path(provenance, "boundary") != FRAME_BOUNDARY:
        raise ValueError("follower party observation is stale")
    party = _path(snapshot, "party")
    if not isinstance(party, list) or len(party) > 6 or any(
            not isinstance(mon, dict) or type(mon.get("slot")) is not int or mon["slot"] != index
            for index, mon in enumerate(party)) or party_slot >= len(party):
        raise ValueError("follower party layout differs")
    mon = party[party_slot]
    for key in ("species", "personality", "identityVerified", "isEgg", "form", "level", "hp", "maxHp", "status"):
        _typed(_path(mon, key), PARTY_FIELDS[key], "follower party " + key)
    if mon["identityVerified"] is not True or mon["species"] != species or mon["hp"] > mon["maxHp"]:
        raise ValueError("follower party identity differs")
    if mon["isEgg"] or mon["hp"] == 0:
        return False
    actors = _path(snapshot, "actors")
    if not isinstance(actors, list) or any(not isinstance(actor, dict) for actor in actors):
        raise ValueError("follower actor list is malformed")
    followers = [actor for actor in actors if actor.get("active") is True and actor.get("role") == "FOLLOWER"]
    if len(followers) > 1:
        raise ValueError("multiple active followers")
    if not followers:
        return False
    actor = followers[0]
    select_current_actor(snapshot, actor)
    active_slot = _int(_path(snapshot, "selector.activeFollowerPartySlot"), "active follower party slot", 0, 255)
    if active_slot != party_slot:
        return False
    if actor["handle"]["slot"] != 7 or any(actor.get(key) != mon[key]
            for key in ("species", "form", "level")) or actor.get("subjectIdentity") != mon["personality"]:
        raise ValueError("current follower differs from the selected party subject")
    source, engine = _path(actor, "sourceIdentity"), _path(actor, "engineIdentity")
    if not live_spawn_flags(source.get("active")) or any(source.get(key) != mon[key]
            for key in ("species", "form", "level", "personality")) \
            or source.get("object") != engine.get("pointer") or engine.get("in_manager") is not True \
            or engine.get("active") is not True or engine.get("object_manager") != engine.get("current_manager") \
            or source.get("object_id") != 231 or engine.get("object_id") != 231 \
            or source.get("encounter_generation") != actor["handle"]["encounterGeneration"] \
            or source.get("map_id") != snapshot["context"].get("mapId") \
            or engine.get("script_id") != 2074:
        raise ValueError("follower native source and engine identity differ")
    for key in ("pointer", "object_manager", "current_manager"):
        pointer = _int(engine.get(key), "follower " + key, 0x02000000, 0x023FFFFC)
        if pointer % 4: raise ValueError("follower engine pointer is unaligned")
    phase = _path(actor, "motionPhase")
    if phase not in ("IDLE", "PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING", "SUSPENDED", "CANCELED"):
        raise ValueError("unknown follower motion phase")
    reservation = _int(_path(actor, "reservationId"), "follower reservation")
    return phase == "IDLE" and reservation == 0 and _path(actor, "motionKind") == "NONE"


def check_movement_predicate(value, snapshot):
    value = validate_movement_predicate(value)
    frame = _coherent(snapshot)
    kind = value["kind"]
    if kind == "follower-settled":
        return follower_settled(snapshot, value["species"], value["partySlot"])
    if kind == "dialogue-state":
        dialogue = _path(snapshot, "dialogue")
        if _int(_path(dialogue, "frame"), "dialogue frame") != frame \
                or _path(dialogue, "boundary") != FRAME_BOUNDARY \
                or _int(_path(dialogue, "fieldPointer"), "dialogue field") != _int(
                    _path(snapshot, "fieldControl.fieldPointer"), "current field"):
            raise ValueError("dialogue observation is stale or from the wrong field/boundary")
        return dialogue.get("known") is True and dialogue.get("state") == value["state"]
    if kind == "player-settled-at":
        return player_settled_at(snapshot, value["map"], value["x"], value["z"])
    if kind == "player-step-count":
        observation = _path(snapshot, "nativeObservation")
        if _path(observation, "coverageComplete") is not True \
                or _int(_path(observation, "playerStepFrame"), "player step frame") != frame:
            raise ValueError("player step counter is missing or not current/coherent")
        actual = _int(_path(observation, "playerStepCount"), "player step count")
    elif kind == "party-field":
        provenance = _path(snapshot, "partyObservation")
        if _int(_path(provenance, "frame"), "party frame") != frame or _path(provenance, "boundary") != FRAME_BOUNDARY:
            raise ValueError("party observation is stale or from the wrong boundary")
        party = _path(snapshot, "party")
        if not isinstance(party, list) or len(party) > 6 \
                or any(not isinstance(mon, dict) or type(mon.get("slot")) is not int
                       or mon["slot"] != index for index, mon in enumerate(party)):
            raise ValueError("party observation has an invalid slot layout")
        if value["slot"] >= len(party):
            raise ValueError("required party slot is absent")
        mon = party[value["slot"]]
        if mon.get("identityVerified") is not True:
            raise ValueError("party subject identity is not verified")
        actual = _typed(_path(mon, value["path"]), PARTY_FIELDS[value["path"]], "party field")
    else:
        actual = _typed(_path(_path(snapshot, "selector"), value["path"]),
                        SELECTOR_FIELDS[value["path"]], "selector field")
    expected = value["value"]
    return {"eq": lambda: actual == expected, "ne": lambda: actual != expected,
            "gte": lambda: actual >= expected, "lte": lambda: actual <= expected}[value["operator"]]()
