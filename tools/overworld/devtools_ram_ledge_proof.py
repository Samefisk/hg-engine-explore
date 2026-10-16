"""Exact ledge claims; shared motion and Ram readers own the native facts."""
from copy import deepcopy
from tools.overworld.devtools_ram_ledge_measurement import KIND, REQUIREMENT
from tools.overworld.devtools_profile_feature_proof import _spec, need

CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary", "logical-commit",
          "rendered-motion", "frame-pacing", "control-release")
FAULTS = tuple(KIND + ":" + name for name in (
    "stale-owner", "early-end", "reset", "turned-hop", "missing-commit", "crash"))
CONTRACT = {
    "live-actor-identity": [_spec("ram-ledge-current-onix", [95, "WILD", 1, 1])],
    "profile-resolution": [_spec("ram-ledge-until-crash-capture", [1, 1, 0])],
    "engine-boundary": [_spec("ram-ledge-preserved-heading-and-acceleration", [1, 1])],
    "logical-commit": [_spec("ram-ledge-hop-and-resumed-walk-committed", [1, 1])],
    "rendered-motion": [_spec("ram-ledge-complete-south-crossing", [[590, 395], [590, 397]])],
    "frame-pacing": [_spec("ram-ledge-resume-after-landing-frames", 1, operator="lte")],
    "control-release": [_spec("ram-ledge-real-finish-control-without-crash", [1, 1])],
}


def contract(): return deepcopy(CONTRACT)


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == [] and meter.get("passed") is True
         and meter.get("ready") is True and meter.get("failures") == [], "Ram ledge replay failed")
    need(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"), "closed": True, "errors": []},
         "owned session cleanup is missing")
    subject = meter["subjects"]["onix"]
    actor = next(a for a in meter["terminal"]["actors"] if a["handle"] == subject["handle"])
    trigger, hop = meter["trigger"], meter["completeHop"]
    crashes = [e for e in meter["events"] if e.get("kind") == "native"
               and e.get("data", {}).get("actorHandle") == subject["handle"]["value"]
               and e["data"].get("event") == "WORLD_EFFECT" and e["data"].get("valueA") == 3]
    actual = {
        "ram-ledge-current-onix": [actor["species"], actor["role"], int(actor["identityVerified"]), int(actor["presentationAttached"])],
        "ram-ledge-until-crash-capture": [int(trigger["untilCrash"]), trigger["targetKind"], trigger["activeUntil"]],
        "ram-ledge-preserved-heading-and-acceleration": [meter["heading"], int(bool(meter["hopMomentumHex"]))],
        "ram-ledge-hop-and-resumed-walk-committed": [int(bool(hop)), int(bool(meter["completeResumedWalk"]))],
        "ram-ledge-complete-south-crossing": [hop["motion"]["origin"], hop["motion"]["target"]],
        "ram-ledge-resume-after-landing-frames": meter["resumed"]["frame"] - hop["motion"]["finishFrame"],
        "ram-ledge-real-finish-control-without-crash": [int(len(hop["events"]) == 4), int(not crashes)],
    }
    rows = []
    for claim, specs in CONTRACT.items():
        for spec in specs:
            value, expected = actual[spec["name"]], spec["expected"]
            need(value <= expected if spec["operator"] == "lte" else value == expected, "Ram ledge metric differs")
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"], "expected": deepcopy(expected), "passed": True})
    return rows


class RamLedgeNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Ram ledge copied fault")
        self.fault, self.applied = fault.rsplit(":", 1)[1], False

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        handle = subjects.get("onix", {}).get("handle", {}).get("value")
        for sample in changed.get("samples", []):
            actor = next((a for a in sample.get("actors", []) if a.get("handle", {}).get("value") == handle), None)
            if actor is None or actor.get("motionKind") != "HOP" or actor.get("origin") != {"x":590,"y":395}: continue
            if self.fault == "stale-owner": actor["handle"]["encounterGeneration"] += 1
            elif self.fault == "early-end": actor["matchedLayerMask"] = 0
            elif self.fault == "turned-hop": actor["target"] = {"x":592,"y":395}
            else: continue
            self.applied = True; return changed
        for event in changed.get("events", []):
            data = event.get("data", {})
            if self.fault == "reset" and event.get("kind") == "native-observation" \
                    and data.get("observation") == "walk-policy" and data.get("slot") == (handle & 0xffff) and data.get("operation") == 3:
                data["operation"] = 0
                for key in ("requestHex", "responseHex"):
                    packet = bytearray.fromhex(data[key]); packet[9] = 0; data[key] = packet.hex()
                self.applied = True; return changed
            if event.get("kind") != "native" or data.get("actorHandle") != handle: continue
            if self.fault == "missing-commit" and data.get("event") == "LOGICAL_COMMIT":
                data["event"] = "WORLD_EFFECT"; data["valueA"] = 0; self.applied = True
            elif self.fault == "crash" and data.get("event") == "MOTION_STARTED" and data.get("valueA") == 2:
                data["event"] = "WORLD_EFFECT"; data["valueA"] = 3; self.applied = True; return changed
        return changed if self.applied else row


def validate_negative_result(result, fault):
    expected = {"stale-owner": "selected handle must name exactly one current active actor",
                "early-end": "Ram ended across a successful ledge",
                "reset": "Ram reset momentum before Crash",
                "turned-hop": "Ram ledge did not keep its South heading",
                "missing-commit": "profile feature did not complete",
                "crash": "Ram ledge canceled or published Crash"}
    meter = result.get("measurements", {}).get(KIND, {})
    need(fault in FAULTS and result.get("passed") is False and result.get("failures")
         and meter.get("passed") is False
         and any(expected[fault.rsplit(":", 1)[1]] in failure for failure in meter.get("failures", [])),
         "Ram ledge fault did not fail at its named guard")
