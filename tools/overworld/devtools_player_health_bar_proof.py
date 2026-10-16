"""Accepted native HP-bar claims and copied-receipt controls."""

from copy import deepcopy

from tools.overworld.devtools_player_health_bar_measurement import (
    KIND, OBSERVED_FRAMES, ORDER, SETUP, STEPS,
)


CLAIMS = ("live-actor-identity", "engine-boundary", "natural-input",
          "control-release")
NAMES = {
    "live-actor-identity": ("current-wild-onix",),
    "engine-boundary": ("full-44-native-submission", "ram-30-native-submission"),
    "natural-input": ("one-normal-onix-ram",),
    "control-release": ("no-battle-or-recovery",),
}
FAULTS = ("missing-full-submission", "wrong-injured-fill", "false-ram",
          "wrong-overlay", "black-palette")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    result = replay.get("measurements", {}).get(KIND, {})
    if (replay.get("passed") is not True or result.get("ready") is not True
            or replay.get("observedFrames") != OBSERVED_FRAMES
            or result.get("observedFrames") != OBSERVED_FRAMES
            or result.get("observedFrameUnit") != "completed-game-frame"
            or result.get("hpAfterRam") != 67
            or result.get("fullFill") != 44
            or result.get("injuredFill") != 30):
        raise ValueError("HP bar replay lacks its exact native submission sequence")
    commands = [row.get("action") for row in rows if row.get("command") is not None]
    expected = [action for action in SETUP if action not in STEPS]
    expected += [action for action in ORDER if action not in STEPS]
    if commands != expected:
        raise ValueError("HP bar command stream differs from the sealed recipe")
    return {"observedFrames": OBSERVED_FRAMES,
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["onix"]],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown HP bar copied-data control")
    changed = deepcopy(rows)
    def health(action):
        matches = [row["receipt"]["playerHealth"] for row in changed
                   if row.get("command") == "player-health.observe"
                   and row.get("action") == action]
        if len(matches) != 1:
            raise ValueError("HP bar control lacks its exact checkpoint")
        return matches[0]
    if fault == "missing-full-submission":
        health("before-ram")["barDraw"]["submittedSprites"] = 0
    elif fault == "wrong-injured-fill":
        health("after-ram")["barDraw"]["drawnFill"] = 44
    elif fault == "false-ram":
        health("after-ram")["lastDamage"] = 0
    elif fault == "black-palette":
        health("before-ram")["barResources"]["paletteVramMatchesSource"] = False
    else:
        health("after-ram")["identity"]["overlaySha256"] = "0" * 64
    return changed
