"""Accepted rows and copied faults for the three natural T79 spawn paths."""
from copy import deepcopy

from tools.overworld.devtools_goldenrod_spawn_measurement import CASES, BEHIND, RAISED, UNDERGROUND, FRAMES
from tools.overworld.devtools_spawn_outcome_records import need


def requirement(feature): return CASES[feature]["requirement"]
def claims(feature): return ("live-actor-identity", "profile-resolution", "terrain-selection")
def faults(feature): return ("goldenrod-wrong-map", "goldenrod-wrong-mask", "goldenrod-wrong-target", "goldenrod-wrong-height",
                            "goldenrod-repeated-preparation", "goldenrod-missing-preparation",
                            "goldenrod-stale-attempt", "goldenrod-cache-mismatch")


def contract(feature):
    del feature
    return {claim: [dict(name=name, operator="gte", type="integer", validator="meaningful-observation", minimum=1)]
        for claim, name in (("live-actor-identity", "natural-goldenrod-full-handle-birth-count"),
            ("profile-resolution", "natural-goldenrod-scoped-placement-count"),
            ("terrain-selection", "natural-goldenrod-native-landing-count"))}


def measurements(feature, replay, record):
    meter = replay.get("measurements", {}).get(feature, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True and meter.get("closed") is True
         and meter.get("acceptedProof") is False and meter.get("failures") == []
         and meter.get("requirements") == [requirement(feature)] and meter.get("observedFrames") == FRAMES,
         "Goldenrod natural proof is incomplete")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "Goldenrod natural private session did not close cleanly")
    landings = meter["outcomes"]["landings"]
    need(landings and all(w["landing"]["passed"] is True and w["landing"]["subject"]["handle"] == w["handle"]
        and w["mapId"] == CASES[feature]["start"][0] for w in landings), "Goldenrod birth and landing handles or maps differ")
    return [dict(claim=claim, name=spec["name"], value=len(landings), operator="gte", minimum=1, passed=True)
        for claim, rows in contract(feature).items() for spec in rows]


class GoldenrodSpawnNegative:
    def __init__(self, feature, fault):
        need(fault in faults(feature), "unknown Goldenrod copied fault")
        self.feature, self.fault, self.applied = feature, fault, False

    def mutate(self, row, subjects):
        del subjects
        if row.get("phase") not in ("setup", "observe") or row.get("phase") == "setup" \
                and self.fault in ("goldenrod-wrong-target", "goldenrod-wrong-height"):
            return row
        result = deepcopy(row)
        changed = False
        for event in result.get("events", []):
            data = event.get("data", {})
            name = data.get("observation")
            if self.fault in ("goldenrod-repeated-preparation", "goldenrod-missing-preparation",
                              "goldenrod-stale-attempt", "goldenrod-cache-mismatch"):
                final = data if name == "spawn-finalized" else data.get("finalization", {}).get("receipt", {})
                if name not in ("spawn-finalized", "spawn-prepared"): continue
                receipts = final.get("resolverReceipts", [])
                if self.fault == "goldenrod-cache-mismatch":
                    cache = final.get("queueAfter", {})
                    raw = bytearray.fromhex(cache.get("preparedHex", ""))
                    if len(raw) != 260: continue
                    raw[36] ^= 1; cache["preparedHex"] = raw.hex()
                elif not receipts: continue
                elif self.fault == "goldenrod-repeated-preparation": final["resolverReceipts"] += deepcopy(receipts)
                elif self.fault == "goldenrod-missing-preparation": final["resolverReceipts"] = []
                else: final["spawnAttemptId"] += 65536
                changed = True
                continue
            if self.fault in ("goldenrod-wrong-map", "goldenrod-wrong-mask"):
                # Rewrite both retained copies even when finalization and its
                # constructor are in different raw chunks. Pairing must stay
                # exact, so the copied fault reaches the placement check.
                final = data if name == "spawn-finalized" else data.get("finalization", {}).get("receipt", {})
                if name not in ("spawn-finalized", "spawn-prepared"):
                    continue
                for receipt in final.get("resolverReceipts", []):
                    key, index, length = (("requestHex", 2, 44) if self.fault == "goldenrod-wrong-map"
                                          else ("resultHex", 52, 216))
                    raw = bytearray.fromhex(receipt[key])
                    need(len(raw) == length, "Goldenrod copied profile extent differs")
                    raw[index] ^= 1
                    receipt[key] = raw.hex()
                    changed = True
                continue
            if name != "spawn-prepared" or data.get("returnValue") != 1:
                continue
            species = data.get("preparedEncounter", {}).get("species")
            height = data.get("initialLandingHeight", {})
            hit = height.get("surfaceQuery", {}).get("hit")
            eligible = (species in (52,19,568,88,479) if self.feature == BEHIND else
                        species in (19,88) if self.feature == UNDERGROUND else
                        species in (519,198) and isinstance(hit,dict) and hit.get("surfaceType") in (0,4))
            if not eligible:
                continue
            if self.fault == "goldenrod-wrong-target":
                height["target"] = [data["position"][0] + 1, data["position"][1]]
            else:
                height["positionAfter"]["pos_y"] += 4096
            changed = True
        self.applied |= changed
        return result if changed else row


def validate_negative_result(feature, result, fault):
    need(fault in faults(feature) and result.get("passed") is False, "Goldenrod copied control did not fail")
    reasons = {"goldenrod-wrong-map": "Goldenrod native placement mask/map differs",
        "goldenrod-wrong-mask": "Goldenrod native placement mask/map differs",
        "goldenrod-wrong-target": "landing target differs", "goldenrod-wrong-height": "terminal Y differs from native landing height",
        "goldenrod-repeated-preparation": "single initial profile preparation",
        "goldenrod-missing-preparation": "single initial profile preparation",
        "goldenrod-stale-attempt": "single initial profile preparation",
        "goldenrod-cache-mismatch": "cached profile differs from its one preparation"}
    text = repr(result.get("failures", [])) + repr(result.get("measurements", {}).get(feature, {}).get("failures", []))
    need(reasons[fault] in text, "Goldenrod copied control failed for an unrelated reason: " + fault)
