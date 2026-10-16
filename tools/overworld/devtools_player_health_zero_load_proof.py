"""Accepted zero-HP Continue claims and copied-data rejection controls."""

from copy import deepcopy

from tools.overworld.devtools_player_health_zero_load_complete_measurement import KIND

CLAIMS = ("engine-boundary", "natural-input", "control-release")
NAMES = {
    "engine-boundary": ("checksum-valid-zero-at-continue", "one-stock-blackout-chain",
                        "saved-checkpoint-and-full-party", "money-and-bag-unchanged"),
    "natural-input": ("authenticated-blackout-message-a",),
    "control-release": ("field-task-ended", "normal-player-step"),
}
FAULTS = ("missing-zero", "wrong-fixture-hash", "missing-stock-task",
          "duplicate-root", "wrong-checkpoint", "changed-economy",
          "party-not-healed", "retained-task", "no-normal-step", "missing-message-input")


def contract():
    return {claim: [{"name": name, "operator": "eq", "type": "integer",
                     "validator": "meaningful-observation", "expected": 1}
                    for name in names]
            for claim, names in NAMES.items()}


def measurements(rows, replay):
    meter = replay.get("measurements", {}).get(KIND, {})
    if (replay.get("passed") is not True or meter.get("ready") is not True
            or meter.get("rootStarts") != 1 or meter.get("rootEnds") != 1
            or meter.get("messageInputSent") is not True
            or meter.get("normalStep") is not True
            or meter.get("checkpointSpawn") != 3
            or meter.get("checkpointMap") != 158
            or meter.get("hpAfterRecovery") != meter.get("hpAfterStep") != 100
            or meter.get("observedFrames", 0) < 53):
        raise ValueError("zero-load replay lacks one stock recovery and normal step")
    initial = rows[0] if rows else {}
    if initial.get("phase") != "setup" or "initialSnapshot" not in initial \
            or not isinstance(initial.get("zeroLoadFixture"), dict):
        raise ValueError("zero-load private fixture is missing from retained boot boundary")
    return {"observedFrames": meter["observedFrames"],
            "observedFrameUnit": "completed-game-frame", "subjects": [],
            "measurements": [{"claim": claim, "name": name, "value": 1,
                              "operator": "eq", "expected": 1}
                             for claim, names in NAMES.items() for name in names]}


def faulted_rows(rows, fault):
    if fault not in FAULTS:
        raise ValueError("unknown zero-load copied-data control")
    changed = deepcopy(rows)
    boot = changed[0]
    def command(action):
        found = [row for row in changed if row.get("command") is not None
                 and row.get("action") == action]
        if len(found) != 1:
            raise ValueError("zero-load control lacks its exact HP receipt")
        return found[0]
    if fault == "missing-zero":
        boot["initialSnapshot"]["bootRecovery"]["hp"] = 100
    elif fault == "wrong-fixture-hash":
        boot["zeroLoadFixture"]["fixtureSha256"] = "0" * 64
    elif fault == "missing-stock-task":
        boot["initialSnapshot"]["bootRecovery"]["preBootFrames"][-1]["stock"] = None
    elif fault == "duplicate-root":
        history = boot["initialSnapshot"]["bootRecovery"]["preBootFrames"]
        active = next(row for row in history if row["root"] is not None)
        active["root"]["pointer"] += 4
    elif fault == "wrong-checkpoint":
        command("after-recovery")["receipt"]["playerHealth"]["checkpointSpawn"] = 4
    elif fault == "changed-economy":
        command("after-recovery")["receipt"]["playerHealth"]["economy"]["money"] += 1
    elif fault == "party-not-healed":
        command("after-recovery")["snapshot"]["party"][0]["hp"] = 0
    elif fault == "retained-task":
        command("after-recovery")["snapshot"]["fieldControl"]["taskPointer"] = 0x02000000
    elif fault == "no-normal-step":
        command("after-step")["snapshot"]["nativeObservation"]["playerStepCount"] = \
            command("after-recovery")["snapshot"]["nativeObservation"]["playerStepCount"]
    else:
        changed[:] = [row for row in changed if row.get("action") != "dismiss-message"]
    return changed
