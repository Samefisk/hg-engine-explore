"""Accepted HP save/reload claims and copied-data controls."""

from copy import deepcopy

from tools.overworld.devtools_player_health_save_reload_measurement import (
    KIND, OBSERVED_FRAMES, ORDER, SETUP, STEPS,
)


CLAIMS = ("live-actor-identity", "engine-boundary", "natural-input",
          "control-release")
NAMES = {
    "live-actor-identity": ("current-wild-onix",),
    "engine-boundary": ("stock-state-12-write", "matching-export-and-load",
                        "injured-hp-and-bar-after-reload"),
    "natural-input": ("one-normal-onix-ram", "normal-save-menu-input"),
    "control-release": ("field-resumes-after-save-and-reload",),
}
FAULTS = ("wrong-reloaded-hp", "wrong-reloaded-fill", "no-stock-write",
          "wrong-loaded-save", "false-ram")


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
            or (result.get("hpBeforeSave"), result.get("hpBeforeReload"),
                result.get("hpAfterReload"), result.get("fillAfterReload"))
                != (67, 67, 67, 30)
            or result.get("saveWritten") is not True
            or result.get("saveReloaded") is not True):
        raise ValueError("HP save/reload replay lacks its exact native write and load sequence")
    commands = [row.get("action") for row in rows if row.get("command") is not None]
    expected = list(SETUP) + [action for action in ORDER if action not in STEPS]
    if commands != expected:
        raise ValueError("HP save/reload command stream differs from the sealed recipe")
    return {"observedFrames": OBSERVED_FRAMES,
            "observedFrameUnit": "completed-game-frame",
            "subjects": [result["onix"]],
            "measurements": [
                {"claim": claim, "name": name, "value": 1,
                 "operator": "eq", "expected": 1}
                for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown HP save/reload copied-data control")
    changed = deepcopy(rows)
    def command(action):
        matches = [row for row in changed if row.get("command") is not None
                   and row.get("action") == action]
        if len(matches) != 1:
            raise ValueError("HP save/reload control lacks its checkpoint")
        return matches[0]
    if fault == "wrong-reloaded-hp":
        command("after-reload")["receipt"]["playerHealth"]["hp"] = 100
    elif fault == "wrong-reloaded-fill":
        command("after-reload")["receipt"]["playerHealth"]["barDraw"]["drawnFill"] = 44
    elif fault == "no-stock-write":
        command("wait-flash")["receipt"]["observedWriteState12"] = False
    elif fault == "wrong-loaded-save":
        command("reload")["receipt"]["saveReload"]["loaded"]["sha256"] = "0" * 64
    else:
        command("before-save")["receipt"]["playerHealth"]["lastDamage"] = 0
    return changed
