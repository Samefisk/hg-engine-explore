"""Acceptance claims and copied-data rejection controls for Wild Throw contact."""

from copy import deepcopy

from tools.overworld.devtools_player_health_throw_contact_measurement import (
    CROSS_FRAMES, KIND, MIN_FRAMES, ORDER,
)


CLAIMS = ("live-actor-identity", "engine-boundary", "natural-input",
          "control-release")
NAMES = {
    "live-actor-identity": ("current-geodude-and-weepinbell",),
    "engine-boundary": ("airborne-throw-to-player", "throw-minus-20-save-parity"),
    "natural-input": ("unforced-pickup-and-launch", "stationary-player"),
    "control-release": ("no-battle-or-blackout",),
}
FAULTS = ("early-damage", "wrong-damage", "wrong-recorded-damage",
          "wrong-flight-target", "stale-throwee", "battle-task",
          "walking-knockback", "wrong-overlay")


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
            or result.get("flightFrames", 0) < 1 \
            or result.get("landed") is not True \
            or result.get("hpAfterThrow") != 80 \
            or set(result.get("subjects", {})) != {"geodude", "weepinbell"}:
        raise ValueError("Throw replay lacks its exact actor, flight, and HP proof")
    commands = [row for row in rows if row.get("command") is not None]
    if [row.get("action") for row in commands] != [
            "throw-tile", "spawn-weepinbell", "bind-weepinbell",
            "spawn-geodude", "bind-geodude", "before-throw", "at-launch",
            "after-contact"]:
        raise ValueError("Throw actions differ from the sealed command stream")
    step_actions = [row.get("action") for row in rows if row.get("phase") == "observe"
                    and row.get("samples")]
    if step_actions.count("launch-natural-throw") < 1 \
            or step_actions.count("cross-player") < 1 \
            or any(name not in ("launch-natural-throw", "cross-player")
                   for name in step_actions):
        raise ValueError("Throw has no declared natural frame stream")
    return {"observedFrames": result["observedFrames"],
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["subjects"]["geodude"],
                         result["subjects"]["weepinbell"]],
            "launchFrame": result["launchFrame"],
            "flightFrames": result["flightFrames"],
            "crossingFrames": CROSS_FRAMES,
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Throw copied-data control")
    changed = deepcopy(rows)

    def health(name):
        matches = [row["receipt"]["playerHealth"] for row in changed
                   if row.get("command") == "player-health.observe"
                   and row.get("action") == name]
        if len(matches) != 1:
            raise ValueError("Throw control lacks its exact HP read")
        return matches[0]

    def step(name):
        matches = [row for row in changed if row.get("action") == name
                   and row.get("samples")]
        if not matches:
            raise ValueError("Throw control lacks its exact frame stream")
        return matches[0]

    if fault == "early-damage":
        hp = health("at-launch")
        hp["hp"] = hp["savedHp"] = 80
        hp["lastDamage"] = 20
        hp["acceptedHits"] = 1
    elif fault == "wrong-damage":
        hp = health("after-contact")
        hp["hp"] = hp["savedHp"] = 85
    elif fault == "wrong-recorded-damage":
        health("after-contact")["lastDamage"] = 33
    elif fault == "wrong-flight-target":
        for row in changed:
            if row.get("action") in ("launch-natural-throw", "cross-player"):
                for sample in row.get("samples", []):
                    for actor in sample["actors"]:
                        if actor.get("species") == 70 and actor.get("motionKind") == "HOP":
                            actor["target"]["y"] = 406
    elif fault == "stale-throwee":
        target = next(a for a in step("cross-player")["samples"][0]["actors"]
                      if a.get("species") == 70)
        target["subjectIdentity"] += 1
    elif fault == "battle-task":
        step("cross-player")["samples"][0]["fieldControl"]["taskPointer"] = 0x02100000
    elif fault == "walking-knockback":
        for row in changed:
            if row.get("action") == "cross-player":
                for sample in row.get("samples", []):
                    if sample["player"].get("movement_cmd") == 62:
                        sample["player"]["movement_cmd"] = 3
    else:
        health("after-contact")["identity"]["overlaySha256"] = "0" * 64
    return changed
