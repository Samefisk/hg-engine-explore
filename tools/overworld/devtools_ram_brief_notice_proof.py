"""Registered native proof for a brief Ram notice during an ordinary Walk."""

from copy import deepcopy

from tools.overworld.devtools_profile_feature_proof import _spec, need
from tools.overworld.devtools_ram_brief_notice_measurement import (
    ACTIVE, BRIEF_WINDOW_FRAMES, KIND, REQUIREMENT, PENDING, UNTIL_CRASH,
)


CLAIMS = ("live-actor-identity", "terrain-selection", "profile-resolution",
          "engine-boundary", "logical-commit", "rendered-motion", "frame-pacing")
FAULTS = (KIND + ":missing-pending", KIND + ":stale-notice-owner")
CONTRACT = {
    "live-actor-identity": [_spec("brief-ram-current-onix", [1, "WILD", 95, 1, 1])],
    "terrain-selection": [_spec("brief-ram-clear-native-line", 6)],
    "profile-resolution": [_spec("brief-ram-pending-after-exit", 1),
                           _spec("brief-ram-real-until-crash", [1, 1, 1])],
    "engine-boundary": [_spec("brief-ram-east-heading-locked", [1, 0])],
    "logical-commit": [_spec("brief-ram-ordinary-and-charge-walks", [1, 1])],
    "rendered-motion": [_spec("brief-ram-complete-native-walks", [1, 1])],
    "frame-pacing": [_spec("brief-ram-notice-before-ordinary-end", 1),
                     _spec("brief-ram-next-intent-delay", 1, operator="lte")],
}


def contract():
    return deepcopy(CONTRACT)


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True
         and meter.get("failures") == [], "brief Ram notice replay failed")
    need(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"),
                                          "closed": True, "errors": []},
         "owned brief Ram session cleanup is missing")
    subject = meter["subjects"]["onix"]
    actor = next(a for a in meter["terminal"]["actors"]
                 if a.get("handle") == subject["handle"])
    ordinary, charge = meter["ordinaryComplete"], meter["chargeComplete"]
    trigger = meter["trigger"]
    activation = meter["activationState"]
    offline = meter["offLineActive"]
    presentation = meter["presentation"]
    terrain = meter["terrainWitness"]
    line_entry = meter["lineEntry"]
    line_player = line_entry["player"]
    observation = terrain["observation"]
    need(terrain["frame"] <= line_entry["frame"] == meter["lineFrame"]
         and terrain["context"] == meter["terminal"]["context"]
         and terrain["romSha256"] == meter["terminal"]["romSha256"]
         and observation["boundary"] == "paused-native-cycle-end"
         and observation["nativeCycle"] == terrain["nativeCycle"]
         and observation["lastCompletedGameFrame"] == terrain["frame"]
         and observation["context"] == terrain["context"]
         and observation["center"] == {"x": 603, "z": 402}
         and [cell["x"] for cell in terrain["cells"]] == list(range(601, 607))
         and all(cell["y"] == 402 and cell["loaded"] is True
                 and cell["collision"] is False
                 and cell["provenance"]["mapHeaderId"] == 33
                 and cell["provenance"]["landDataIdentity"] == "current-map-matrix"
                 for cell in terrain["cells"])
         and (line_player["x"], line_player["y"], line_player["x_prev"],
              line_player["y_prev"], line_player["movement_cmd"],
              line_player["movement_step"], line_player["facing"])
             == (606, 402, 606, 403, 88, 1, 0)
         and (402 << 16) + 0x8000 < line_player["pos_z"]
             < (403 << 16) + 0x8000,
         "brief Ram lacks the current native terrain and normal logical sight entry")
    lifetime = ("targetKind", "targetSlot", "targetGeneration",
                "targetEncounterGeneration", "activeUntil", "cooldownUntil")
    need(trigger.get("source") == "authenticated-prepared-state"
         and meter["lineFrame"] <= trigger["frame"] == meter["pendingFrame"]
             <= meter["lineFrame"] + BRIEF_WINDOW_FRAMES
         and trigger["frame"] < meter["offLineFrame"] < ordinary["finishFrame"]
         and all(activation.get(key) == offline.get(key)
                 == presentation["state"].get(key) for key in lifetime)
         and activation["activeUntil"] == 0
         and all(state["flags"] & (ACTIVE | UNTIL_CRASH)
                 == ACTIVE | UNTIL_CRASH for state in
                 (activation, offline, presentation["state"]))
         and activation["flags"] & PENDING
         and offline["flags"] & PENDING
         and not presentation["state"]["flags"] & PENDING
         and presentation["intent"]["data"].get("event") == "INTENT_CREATED"
         and ordinary["finishFrame"] <= presentation["frame"]
             <= meter["firstCharge"]["frame"],
         "brief Ram did not stay active from sight through presentation admission")
    actual = {
        "brief-ram-current-onix": [1, actor["role"], actor["species"],
                                   int(actor["identityVerified"]),
                                   int(actor["presentationAttached"])],
        "brief-ram-clear-native-line": len(terrain["cells"]),
        "brief-ram-pending-after-exit": int(meter["pendingAfterExit"]),
        "brief-ram-real-until-crash": [int(trigger["untilCrash"]),
                                       int(trigger["active"]), trigger["targetKind"]],
        "brief-ram-east-heading-locked": list(meter["chargeHeading"]),
        "brief-ram-ordinary-and-charge-walks": [ordinary["commitAfter"] - ordinary["commitBefore"],
                                               charge["commitAfter"] - charge["commitBefore"]],
        "brief-ram-complete-native-walks": [int(bool(ordinary.get("finishFrame"))),
                                             int(bool(charge.get("finishFrame")))],
        "brief-ram-notice-before-ordinary-end": int(trigger["frame"]
            < meter["offLineFrame"] < ordinary["finishFrame"]),
        "brief-ram-next-intent-delay": meter["firstCharge"]["frame"]
            - presentation["frame"],
    }
    rows = []
    for claim, specs in CONTRACT.items():
        for spec in specs:
            value = actual[spec["name"]]
            expected = spec.get("expected", spec.get("minimum"))
            passed = value == expected if spec["operator"] == "eq" else value <= expected
            need(passed, "brief Ram metric differs: " + spec["name"])
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"], "expected": deepcopy(expected),
                         "passed": True})
    return rows


class RamBriefNoticeNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown brief Ram copied-data fault")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False

    def mutate(self, row, subjects):
        if self.applied:
            return row
        changed = deepcopy(row)
        for sample in changed.get("samples", []):
            data = sample.get("pokemonAppearance", {}).get("conditions", {})
            condition = data.get("0", data.get(0, {}))
            states = condition.get("states", [])
            ram = next((s for s in states if s.get("conditionId") == 20305
                        and s.get("flags", 0) & PENDING), None)
            if ram is None:
                continue
            if self.fault == "missing-pending":
                ram["flags"] &= ~PENDING
            else:
                condition["owner"]["actor"]["handle"]["generation"] += 1
            self.applied = True
            return changed
        return row


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False
         and bool(result.get("failures")),
         "brief Ram copied-data control did not fail")
