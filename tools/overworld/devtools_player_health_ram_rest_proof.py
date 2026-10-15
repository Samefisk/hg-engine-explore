"""Exact acceptance claims and copied-data controls for Ram/rest gameplay."""

from copy import deepcopy

from tools.overworld.devtools_player_health_ram_rest_measurement import KIND, ORDER, STEPS


CLAIMS = ("live-actor-identity", "engine-boundary", "natural-input",
          "control-release")
NAMES = {
    "live-actor-identity": ("current-wild-onix",),
    "engine-boundary": ("current-hp-save-owner", "ram-minus-33",
                        "rest-five-seconds", "rest-plus-10", "movement-keeps-healing"),
    "natural-input": ("normal-onix-ram", "neutral-rest-frames"),
    "control-release": ("no-battle-or-blackout",),
}
FAULTS = ("missing-ram", "wrong-damage", "missing-fast-tile", "false-rest-heal",
          "missing-heal", "movement-resets-clock", "stale-onix",
          "player-left-rest-tile", "wrong-overlay")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    if replay.get("passed") is not True or result.get("ready") is not True \
            or replay.get("observedFrames") != sum(STEPS.values()) \
            or result.get("observedFrames") != sum(STEPS.values()) \
            or result.get("observedFrameUnit") != "completed-game-frame" \
            or result.get("hpAfterRam") != 67 \
            or not any(1 <= row.get("travelTime", 0) <= 32
                       and row.get("minimumImpactSpeed", 0) > 0
                       and 256 // row["travelTime"] >= row["minimumImpactSpeed"]
                       for row in result.get("completedChargeThresholds", [])) \
            or result.get("hpAfterRest") != 77 \
            or result.get("movementHealing") is not True:
        raise ValueError("Ram/rest replay lacks its exact game-frame and HP proof")
    commands = [row for row in rows if row.get("command") is not None]
    if [row.get("action") for row in commands] != [
            "ram-tile", "spawn-onix", "bind-onix", *[
                action for action in ORDER if action not in STEPS]]:
        raise ValueError("Ram/rest actions differ from the sealed command stream")
    return {"observedFrames": sum(STEPS.values()),
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["onix"]],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Ram/rest copied-data control")
    changed = deepcopy(rows)
    def health(name):
        matches = [row["receipt"]["playerHealth"] for row in changed
                   if row.get("command") == "player-health.observe"
                   and row.get("action") == name]
        if len(matches) != 1:
            raise ValueError("Ram/rest control lacks its exact health action")
        return matches[0]
    if fault == "missing-ram":
        health("after-ram")["lastDamage"] = 0
    elif fault == "wrong-damage":
        hp = health("after-ram")
        hp["hp"] = hp["savedHp"] = 80
    elif fault == "missing-fast-tile":
        for row in changed:
            if row.get("action") != "allow-natural-ram":
                continue
            for sample in row.get("samples", []):
                for actor in sample.get("actors", []):
                    if actor.get("motionDuration") == 8:
                        actor["motionDuration"] = 12
            for event in row.get("events", []):
                data = event.get("data", {})
                if event.get("kind") == "native-observation" and data.get("observation") == "walk-policy" \
                        and data.get("operation") == 3:
                    raw = bytearray.fromhex(data["policyBeforeHex"])
                    raw[2] = raw[25] = 32
                    data["policyBeforeHex"] = raw.hex()
                    data["publicSubject"]["motionDuration"] = 32
                    data["publicSubject"]["motionElapsed"] = 32
    elif fault == "false-rest-heal":
        hp = health("after-five-seconds")
        hp["hp"] = hp["savedHp"] = 68
    elif fault == "missing-heal":
        hp = health("after-heal")
        hp["hp"] = hp["savedHp"] = 67
    elif fault == "movement-resets-clock":
        health("after-move")["restFrames"] = 0
    elif fault == "stale-onix":
        rows = [row for row in changed if row.get("action") == "allow-natural-ram"
                and row.get("samples")]
        if not rows:
            raise ValueError("Ram/rest control lacks Onix frame samples")
        rows[0]["samples"][0]["actors"] = []
    elif fault == "player-left-rest-tile":
        rows = [row for row in changed if row.get("action") == "stand-five-seconds"
                and row.get("samples")]
        if not rows:
            raise ValueError("Ram/rest control lacks rest frame samples")
        rows[0]["samples"][0]["player"]["x"] += 1
    else:
        health("after-ram")["identity"]["overlaySha256"] = "0" * 64
    return changed
