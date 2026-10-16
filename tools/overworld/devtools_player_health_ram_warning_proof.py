"""Accepted active Ram amber warning and copied-receipt controls."""

from copy import deepcopy

from tools.overworld.devtools_player_health_ram_warning_measurement import (
    KIND, ORDER, SETUP, RAM_MASK,
)


CLAIMS = ("live-actor-identity", "engine-boundary", "natural-input",
          "control-release")
NAMES = {
    "live-actor-identity": ("current-wild-onix",),
    "engine-boundary": ("amber-full-bar-during-charge",),
    "natural-input": ("normal-active-ram-walk",),
    "control-release": ("no-hit-or-battle-before-warning",),
}
FAULTS = ("missing-amber", "not-ram", "stale-onix", "wrong-overlay")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    observed = result.get("observedFrames")
    if (replay.get("passed") is not True or result.get("ready") is not True
            or type(observed) is not int or observed < 2
            or replay.get("observedFrames") != observed
            or result.get("observedFrameUnit") != "completed-game-frame"
            or result.get("warningSubmitted") is not True
            or type(result.get("chargeFrame")) is not int):
        raise ValueError("Ram warning replay lacks its active-charge amber receipt")
    commands = [row.get("action") for row in rows if row.get("command") is not None]
    if commands != [*SETUP, ORDER[-1]]:
        raise ValueError("Ram warning command stream differs")
    return {"observedFrames": observed,
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["onix"]],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown Ram warning copied-data control")
    changed = deepcopy(rows)
    charge = next((row for row in changed
                   if row.get("action") == "read-charge-warning"), None)
    if charge is None:
        raise ValueError("Ram warning control lacks its HP read")
    if fault == "missing-amber":
        charge["receipt"]["playerHealth"]["barDraw"]["danger"] = False
    elif fault == "not-ram":
        handle = next(row["receipt"]["handle"] for row in changed
                      if row.get("action") == "bind-onix")
        actor = next(actor for actor in charge["snapshot"]["actors"]
                     if actor.get("handle") == handle)
        actor["matchedLayerMask"] &= ~RAM_MASK
    elif fault == "stale-onix":
        charge["snapshot"]["actors"] = []
    else:
        charge["receipt"]["playerHealth"]["identity"]["overlaySha256"] = "0" * 64
    return changed
