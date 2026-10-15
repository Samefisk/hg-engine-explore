"""Exact accepted rows and copied faults for two natural population outcomes."""
from copy import deepcopy

from tools.overworld.devtools_spawn_outcome_records import need
from tools.overworld.devtools_spawn_priority_measurement import CASES, RETRY, WATER


def requirement(feature):
    return CASES[feature]["requirement"]


def claims(feature):
    return ("live-actor-identity", "population-bounds") if feature == RETRY else ("live-actor-identity", "terrain-selection")


def faults(feature):
    return ("refill-long-failed-delay", "refill-short-created-delay") if feature == RETRY else (
        "water-ready-without-constructor", "water-wrong-terrain", "water-wrong-landing-height")


def contract(feature):
    rows = (("live-actor-identity", "actual-creation-full-handle-count"),
            ("population-bounds", "failed-series-short-retry-count"),
            ("population-bounds", "actual-creation-density-delay-count")) if feature == RETRY else (
        ("live-actor-identity", "natural-water-full-handle-birth-count"),
        ("terrain-selection", "natural-water-native-height-landing-count"))
    result = {}
    for claim, name in rows:
        result.setdefault(claim, []).append(dict(name=name, operator="gte", type="integer",
            validator="meaningful-observation", minimum=1))
    return result


def measurements(feature, replay, record):
    meter = replay.get("measurements", {}).get(feature, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True and meter.get("closed") is True
         and meter.get("acceptedProof") is False and meter.get("failures") == []
         and meter.get("requirements") == [requirement(feature)]
         and meter.get("observedFrames") == sum(CASES[feature]["frames"]),
         "natural spawn proof is incomplete")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "natural spawn private session did not close cleanly")
    outcome = meter["outcomes"]
    values = (len(outcome["shortRetries"]), len(outcome["creationDelays"])) if feature == RETRY else (
        len(outcome["waterLandings"]), len(outcome["waterLandings"]))
    if feature == WATER:
        need(all(w["landing"]["passed"] is True and w["landing"]["subject"]["handle"] == w["handle"]
                 for w in outcome["waterLandings"]), "water birth and landing handles differ")
    else:
        need(all(w["delay"] == 15 and 15 <= w["actorFrameGap"] < 60 for w in outcome["shortRetries"])
             and all(w["delay"] >= 60 and w["actorFrameGap"] >= w["delay"]
                     for w in outcome["creationDelays"]), "natural refill timing witness differs")
    by_name = ({"actual-creation-full-handle-count": values[1],
        "failed-series-short-retry-count": values[0], "actual-creation-density-delay-count": values[1]}
        if feature == RETRY else {"natural-water-full-handle-birth-count": values[0],
            "natural-water-native-height-landing-count": values[1]})
    rows = [dict(claim=claim, name=row["name"], value=by_name[row["name"]],
        operator="gte", minimum=1, passed=by_name[row["name"]] >= 1)
        for claim, entries in contract(feature).items() for row in entries]
    return rows


class SpawnPriorityNegative:
    def __init__(self, feature, fault):
        need(fault in faults(feature), "unknown natural spawn copied fault")
        self.feature, self.fault, self.applied = feature, fault, False

    def mutate(self, row, subjects):
        del subjects
        if row.get("phase") != "observe" or (self.applied and self.fault != "water-ready-without-constructor"):
            return row
        result = deepcopy(row)
        for event in result.get("events", []):
            data = event.get("data", {})
            entry = data.get("entry", {})
            if self.feature == RETRY and data.get("observation") == "entry-native-control":
                op = entry.get("operation")
                failed = op == 7 and entry.get("outcome") == 2 or (
                    op == 8 and entry.get("queryOperation") == 1 and entry.get("prepareResult") == 0)
                if self.fault == "refill-long-failed-delay" and failed and entry.get("refillDelay") == 15:
                    entry["refillDelay"] = 60
                    entry["value"] = (entry["value"] & 255) | (60 << 8)
                    self.applied = True
                elif self.fault == "refill-short-created-delay" and op == 7 and entry.get("outcome") == 3:
                    entry["refillDelay"] = 15
                    entry["value"] = 3 | (15 << 8)
                    self.applied = True
            if self.feature == WATER and data.get("observation") == "spawn-prepared" \
                    and data.get("returnValue") == 1 and data.get("terrain") == 1:
                if self.fault == "water-ready-without-constructor":
                    data["returnValue"] = 0
                elif self.fault == "water-wrong-terrain":
                    data["terrain"] = 0
                else:
                    data["initialLandingHeight"]["positionAfter"]["pos_y"] += 4096
                self.applied = True
            if self.applied and self.fault != "water-ready-without-constructor":
                return result
        return result if self.applied else row


def validate_negative_result(feature, result, fault):
    need(fault in faults(feature) and result.get("passed") is False,
         "natural spawn copied control did not fail")
    reasons = {
        "refill-long-failed-delay": "failed refill ignored its decoded delay",
        "refill-short-created-delay": "success refill delay lacks its actual constructor",
        # The current native Commit receipt independently requires its owned
        # constructor before the water landing claim can run. Keep that guard.
        "water-ready-without-constructor": "Commit SUCCESS has no exact admitted constructor/world/queue",
        "water-wrong-terrain": "constructor does not consume its exact natural finalizer",
        "water-wrong-landing-height": "terminal Y differs from native landing height",
    }
    text = repr(result.get("failures", [])) + repr(result.get("measurements", {}).get(feature, {}).get("failures", []))
    need(reasons[fault] in text, "natural spawn copied control failed for an unrelated reason: " + fault)
