"""Acceptance claims and copied-data controls for Ambush Jump1 knockback."""

from copy import deepcopy

from tools.overworld.devtools_player_health_ambush_jump_measurement import (
    JUMP_FRAMES, KIND, MIN_FRAMES,
)


CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary",
          "natural-input", "control-release")
NAMES = {
    "live-actor-identity": ("one-current-wild-weepinbell",),
    "profile-resolution": ("active-ambush-contact-and-jump1",),
    "engine-boundary": ("airborne-ambush-minus-20", "one-tile-player-jump"),
    "natural-input": ("unforced-ambush-hop",),
    "control-release": ("no-battle-or-blackout",),
}
FAULTS = ("attack-off", "wrong-damage", "no-jump-arc", "walking-jump",
          "stale-weepinbell", "battle-task", "wrong-overlay")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    if (replay.get("passed") is not True or result.get("ready") is not True
            or result.get("observedFrames") != replay.get("observedFrames")
            or replay.get("observedFrames", 0) < MIN_FRAMES
            or result.get("observedFrameUnit") != "completed-game-frame"
            or type(result.get("crossingFrame")) is not int
            or result.get("flightFrames", 0) < 1
            or result.get("hpAfter") != 80
            or result.get("finalTile") != [585, 408]
            or result.get("jumpArcSeen") is not True
            or result.get("stationaryCommandSeen") is not True
            or not isinstance(result.get("subject"), dict)):
        raise ValueError("Ambush replay lacks exact HP and player jump proof")
    commands = [row.get("action") for row in rows
                if row.get("command") is not None]
    if commands != ["ambush-tile", "spawn-weepinbell", "bind-weepinbell",
                    "before-contact", "at-contact", "after-jump"]:
        raise ValueError("Ambush command stream differs")
    steps = [row.get("action") for row in rows
             if row.get("phase") == "observe" and row.get("samples")]
    if steps.count("wait-ambush-contact") < 1 \
            or steps.count("finish-player-jump") < 1 \
            or any(name not in ("wait-ambush-contact", "finish-player-jump")
                   for name in steps):
        raise ValueError("Ambush has no bounded normal Hop and jump frames")
    return {"observedFrames": result["observedFrames"],
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["subject"]],
            "crossingFrame": result["crossingFrame"],
            "jumpFrames": JUMP_FRAMES,
            "finalTile": result["finalTile"],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Ambush copied-data control")
    changed = deepcopy(rows)
    crossing = next(row for row in reversed(changed)
                    if row.get("action") == "wait-ambush-contact"
                    and row.get("samples") and row.get("profileCache"))
    sample = crossing["samples"][-1]
    actor = next(a for a in sample["actors"]
                 if a.get("species") == 70 and a.get("role") == "WILD")
    end = next(row for row in changed if row.get("action") == "after-jump")
    jump = next(row for row in changed if row.get("action") == "finish-player-jump"
                and row.get("samples"))
    if fault == "attack-off":
        profile = next(p for p in crossing["profileCache"]["resolvedProfiles"]
                       if p.get("fingerprint") == actor.get("behaviorFingerprint"))
        raw = bytearray.fromhex(profile["resultHex"])
        raw[72] = 0
        profile["resultHex"] = raw.hex()
    elif fault == "wrong-damage":
        end["receipt"]["playerHealth"]["hp"] = 85
        end["receipt"]["playerHealth"]["savedHp"] = 85
    elif fault == "no-jump-arc":
        for row in changed:
            if row.get("action") == "finish-player-jump":
                for pose in row.get("samples", []):
                    pose["player"]["face_y"] = 0
    elif fault == "walking-jump":
        for row in changed:
            if row.get("action") == "finish-player-jump":
                for pose in row.get("samples", []):
                    if pose["player"].get("movement_cmd") == 62:
                        pose["player"]["movement_cmd"] = 3
    elif fault == "stale-weepinbell":
        actor["subjectIdentity"] += 1
    elif fault == "battle-task":
        jump["samples"][0]["fieldControl"]["taskPointer"] = 0x02100000
    else:
        end["receipt"]["playerHealth"]["identity"]["overlaySha256"] = "0" * 64
    return changed
