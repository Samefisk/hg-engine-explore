"""Accepted adjacent Ram speed-boundary claim and copied-data controls."""

from copy import deepcopy

from tools.overworld.devtools_player_health_ram_low_speed_measurement import (
    KIND, ORDER, SETUP, RAM_MASK,
)


CLAIMS = ("live-actor-identity", "engine-boundary", "natural-input",
          "control-release")
NAMES = {
    "live-actor-identity": ("current-adjacent-wild-onix",),
    "engine-boundary": ("hp-save-unchanged-at-100", "zero-accepted-hits"),
    "natural-input": ("active-ram-and-80-neutral-frames",),
    "control-release": ("no-battle-or-recovery",),
}
FAULTS = ("missing-ram", "injured-player", "accepted-hit",
          "stale-onix", "battle", "wrong-overlay")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    observed = result.get("observedFrames")
    if (replay.get("passed") is not True or result.get("ready") is not True
            or type(observed) is not int or observed < 81
            or replay.get("observedFrames") != observed
            or result.get("observedFrameUnit") != "completed-game-frame"
            or result.get("neutralFrames") != 80
            or result.get("activeFrames", 0) < 34
            or result.get("hpAfterWindow") != 100
            or result.get("acceptedHitsAfterWindow") != 0):
        raise ValueError("low-speed Ram replay lacks its adjacent no-hit boundary")
    commands = [row.get("action") for row in rows if row.get("command") is not None]
    if commands != [*SETUP, ORDER[0], ORDER[-1]]:
        raise ValueError("low-speed Ram command stream differs")
    return {"observedFrames": observed,
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["onix"]],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown low-speed Ram copied-data control")
    changed = deepcopy(rows)
    def health(action):
        matches = [row["receipt"]["playerHealth"] for row in changed
                   if row.get("action") == action
                   and row.get("command") == "player-health.observe"]
        if len(matches) != 1:
            raise ValueError("low-speed Ram control lacks its exact HP read")
        return matches[0]
    if fault in ("missing-ram", "stale-onix", "battle"):
        row = next((row for row in changed
                    if row.get("action") == "allow-adjacent-ram"
                    and row.get("samples")), None)
        if row is None:
            raise ValueError("low-speed Ram control lacks frame samples")
        sample = row["samples"][0]
        if fault == "missing-ram":
            for window in changed:
                if window.get("action") != "allow-adjacent-ram":
                    continue
                for frame in window.get("samples", []):
                    for actor in frame["actors"]:
                        if actor.get("species") == 95 and actor.get("role") == "WILD":
                            actor["matchedLayerMask"] &= ~RAM_MASK
        elif fault == "stale-onix":
            sample["actors"] = []
        else:
            sample["fieldControl"]["taskPointer"] = 1
    elif fault == "injured-player":
        hp = health("after-ram")
        hp["hp"] = hp["savedHp"] = 67
    elif fault == "accepted-hit":
        health("after-ram")["acceptedHits"] = 1
    else:
        health("after-ram")["identity"]["overlaySha256"] = "0" * 64
    return changed
