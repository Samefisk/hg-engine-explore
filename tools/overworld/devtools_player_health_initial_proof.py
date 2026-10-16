"""Controller checks and copied-data controls for old-save HP initialization."""

from copy import deepcopy


NAMES = ("overlay-identity", "runtime-save-owner", "old-save-full-hp",
         "safe-healing-spawn", "read-only-boundary")
FAULTS = ("missing-hp", "wrong-overlay", "wrong-rom", "injured-hp",
          "invalid-checkpoint", "stale-boundary")


def contract():
    return {"engine-boundary": [
        {"name": name, "operator": "eq", "type": "integer",
         "validator": "meaningful-observation", "expected": 1}
        for name in NAMES]}


def measurements(rows, replay):
    commands = [row for row in rows if row.get("command") is not None]
    if len(commands) != 1 or commands[0].get("command") != "player-health.observe":
        raise ValueError("player HP proof changed its only read-only command")
    if replay.get("observedFrames") != 1 or replay.get("passed") is not True:
        raise ValueError("player HP proof lacks its checked field boundary")
    hp = replay.get("measurements", {}).get("player-health-initial-state-v1", {})
    if hp.get("ready") is not True or hp.get("hp") != 100 \
            or not 1 <= hp.get("checkpointSpawn", 0) <= 30:
        raise ValueError("player HP proof differs from its old-save contract")
    return {"observedFrames": 1,
            "observedFrameUnit": "read-only-completed-field-boundary",
            "measurements": [
                {"claim": "engine-boundary", "name": name, "value": 1,
                 "operator": "eq", "expected": 1} for name in NAMES]}


def faulted_rows(rows, fault):
    changed = deepcopy(rows)
    commands = [row for row in changed if row.get("command") == "player-health.observe"]
    if len(commands) != 1 or fault not in FAULTS:
        raise ValueError("player HP proof control has no exact observation")
    row = commands[0]
    if fault == "missing-hp":
        row["receipt"].pop("playerHealth")
        return changed
    hp = row["receipt"]["playerHealth"]
    if fault == "wrong-overlay":
        hp["identity"]["overlaySha256"] = "0" * 64
    elif fault == "wrong-rom":
        hp["identity"]["romSha256"] = "0" * 64
    elif fault == "injured-hp":
        hp["hp"] = 99
    elif fault == "invalid-checkpoint":
        hp["checkpointSpawn"] = 0
    else:
        hp["frame"] += 1
    return changed
