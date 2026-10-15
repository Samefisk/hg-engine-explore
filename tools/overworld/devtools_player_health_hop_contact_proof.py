"""Acceptance contract and copied-data controls for ordinary Wild Hop damage."""

from copy import deepcopy

from tools.overworld.devtools_player_health_hop_contact_measurement import (
    KIND, MIN_FRAMES,
)


CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary",
          "natural-input", "control-release")
NAMES = {
    "live-actor-identity": ("one-current-wild-mankey",),
    "profile-resolution": ("long-hop-active-contact-1-16-20",),
    "engine-boundary": ("ordinary-airborne-swept-crossing", "hop-minus-20-save-parity"),
    "natural-input": ("unforced-hop-and-stationary-player",),
    "control-release": ("no-battle-or-recovery",),
}
FAULTS = ("attack-off", "not-hop", "wrong-hp", "stale-mankey", "battle-task",
          "wrong-overlay")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    if replay.get("passed") is not True or result.get("ready") is not True \
            or replay.get("observedFrames", 0) < MIN_FRAMES \
            or result.get("observedFrames") != replay.get("observedFrames") \
            or result.get("observedFrameUnit") != "completed-game-frame" \
            or result.get("ordinaryHop") is not True \
            or result.get("flightFrames", 0) < 1 \
            or type(result.get("crossingFrame")) is not int \
            or result.get("hpAfterHop") != 80 \
            or not isinstance(result.get("subject"), dict):
        raise ValueError("Hop replay lacks one current attack-profile flight and HP result")
    commands = [row.get("action") for row in rows if row.get("command") is not None]
    if commands != ["open-area", "spawn-mankey", "bind-mankey",
                    "before-hop", "after-contact"]:
        raise ValueError("Hop proof command stream differs")
    steps = [row.get("action") for row in rows if row.get("phase") == "observe"
             and row.get("samples")]
    if steps not in (["wait-crossing-hop"],
                     ["settle-spawn", "wait-crossing-hop"]) \
            or steps == ["wait-crossing-hop"] and result.get("settledAtBind") is not True:
        raise ValueError("Hop proof lacks the bounded natural frame stream")
    return {"observedFrames": result["observedFrames"],
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["subject"]],
            "crossingFrame": result["crossingFrame"],
            "flightFrames": result["flightFrames"],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Hop copied-data control")
    changed = deepcopy(rows)
    wait = next(row for row in changed if row.get("action") == "wait-crossing-hop"
                and row.get("samples"))
    sample = wait["samples"][-1]
    actor = next(a for a in sample["actors"] if a.get("species") == 56
                 and a.get("role") == "WILD")
    end = next(row for row in changed if row.get("action") == "after-contact")
    if fault == "attack-off":
        profile = next(p for p in wait["profileCache"]["resolvedProfiles"]
                       if p.get("fingerprint") == actor.get("behaviorFingerprint"))
        raw = bytearray.fromhex(profile["resultHex"])
        raw[72] = 0
        profile["resultHex"] = raw.hex()
    elif fault == "not-hop":
        actor["motionKind"] = "WALK"
    elif fault == "wrong-hp":
        end["receipt"]["playerHealth"]["hp"] = 85
        end["receipt"]["playerHealth"]["savedHp"] = 85
    elif fault == "stale-mankey":
        actor["subjectIdentity"] += 1
    elif fault == "battle-task":
        sample["fieldControl"]["taskPointer"] = 0x02100000
    else:
        end["receipt"]["playerHealth"]["identity"]["overlaySha256"] = "0" * 64
    return changed
