"""T85 current saved-follower Hop/rebind acceptance and copied faults."""
from copy import deepcopy
from tools.overworld.devtools_spawn_outcome_records import need
from tools.overworld.devtools_goldenrod_follower_measurement import KIND, REQUIREMENT, PID, MIN_FRAMES

CLAIMS = ("natural-input", "live-actor-identity", "logical-commit", "rendered-motion", "world-transition", "control-release")
FAULTS = ("follower-still", "follower-wrong-party", "follower-stale-rebind", "follower-empty-mask",
          "follower-coverage-gap", "follower-frame-gap", "follower-extra-command",
          "follower-bad-endpoint", "follower-wrong-motion", "follower-dropped-travel",
          "follower-unexpected-epoch", "follower-trace-loss")


def contract():
    names = ("saved-mankey-normal-input", "saved-mankey-three-current-contexts", "three-context-shared-hop-commits",
             "three-context-shared-hop-travel", "goldenrod-route34-goldenrod", "three-settled-control-checkpoints")
    values = (["normal", 56, 2, PID], [56, PID, 3], [1, 1, 1], [1, 1, 1], [76, 38, 76], 3)
    return {claim: [dict(name=name, operator="eq", type="integer" if type(value) is int else "array",
                        validator="meaningful-observation", expected=value)]
            for claim, name, value in zip(CLAIMS, names, values)}


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == [] and meter.get("passed") is True
         and meter.get("ready") is True and meter.get("closed") is True and meter.get("acceptedProof") is False
         and meter.get("failures") == [] and meter.get("requirements") == [REQUIREMENT]
         and meter.get("observedFrames", 0) >= MIN_FRAMES, "Goldenrod follower Hop/rebind proof is incomplete")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "Goldenrod follower private session did not close cleanly")
    rebinds, hops = meter.get("rebinds", []), meter.get("hops", {})
    need([(r["fromMap"], r["toMap"]) for r in rebinds] == [(76, 38), (38, 76)]
         and all(r["before"]["subjectIdentity"] == r["after"]["subjectIdentity"] == PID
                 and r["before"]["handle"] != r["after"]["handle"] for r in rebinds)
         and set(hops) == {"0", "1", "2"} and all(hops[k] for k in hops),
         "Goldenrod follower proof lacks current handles or three real Hop windows")
    subject = meter["subject"]
    actual = ([meter["mode"], subject["species"], meter["partySlot"], subject["subjectIdentity"]],
              [subject["species"], subject["subjectIdentity"], len(rebinds) + 1],
              [int(bool(hops[str(i)])) for i in range(3)],
              [int(all(m["travelFrames"] > 0 and m["duration"] > 0 for m in hops[str(i)])) for i in range(3)],
              [rebinds[0]["fromMap"], *[r["toMap"] for r in rebinds]], len(hops))
    rows = []
    for (claim, specs), value in zip(contract().items(), actual):
        expected = specs[0]["expected"]
        need(value == expected, "Goldenrod follower accepted values differ from its measured route")
        rows.append(dict(claim=claim, name=specs[0]["name"], operator="eq", expected=expected, value=value, passed=True))
    return rows


class GoldenrodFollowerNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Goldenrod follower copied fault")
        self.fault, self.applied, self.seen_motion = fault, False, False

    def mutate(self, row, subjects):
        del subjects
        if self.fault == "follower-empty-mask" and "initialSnapshot" in row:
            changed = deepcopy(row)
            sample = changed["initialSnapshot"]
            actor = next(a for a in sample["actors"] if a.get("role") == "FOLLOWER")
            for profile in sample["nativeObservation"]["resolvedProfiles"]:
                if profile["fingerprint"] != actor["behaviorFingerprint"]: continue
                lane = bytearray.fromhex(profile["lanes"][0]); lane[32:34] = bytes(2)
                profile["lanes"][0] = lane.hex(); self.applied = True
            return changed
        if row.get("phase") != "observe" or not row.get("samples"):
            return row
        changed = deepcopy(row)
        if self.fault in ("follower-unexpected-epoch", "follower-trace-loss"):
            for event in changed.get("events", []):
                data = event.get("data", {})
                code = "field-epoch-changed" if self.fault == "follower-unexpected-epoch" else "ring-overwrite"
                if event.get("kind") != "trace-status" or data.get("code") != code: continue
                if self.fault == "follower-unexpected-epoch": data["fieldEpoch"] += 1
                else: data["unreadEventsLost"] = 1
                self.applied = True
                break
        elif self.fault == "follower-extra-command":
            changed["command"] = "party"; self.applied = True
        elif self.fault == "follower-frame-gap":
            changed["samples"][0]["frame"] += 1; self.applied = True
        else:
            for sample in changed["samples"]:
                actors = [a for a in sample.get("actors", []) if a.get("role") == "FOLLOWER"]
                if self.fault == "follower-still":
                    for actor in actors: actor.update(motionKind="NONE", motionPhase="IDLE")
                elif self.fault == "follower-wrong-party":
                    sample["party"][2]["personality"] ^= 1
                elif self.fault == "follower-stale-rebind":
                    if sample.get("context", {}).get("mapId") != 38: continue
                    for actor in actors: actor["handle"]["fieldEpoch"] -= 1
                elif self.fault in ("follower-bad-endpoint", "follower-wrong-motion", "follower-dropped-travel"):
                    for actor in actors:
                        if actor.get("motionKind") == "HOP":
                            self.seen_motion = True
                            if self.fault == "follower-wrong-motion": actor["motionKind"] = "REPOSITION"
                            elif self.fault == "follower-dropped-travel" and actor.get("motionElapsed", 0) == 2:
                                actor["motionElapsed"] = 3
                        elif self.fault == "follower-bad-endpoint" and self.seen_motion and actor.get("motionPhase") == "IDLE":
                            actor["engineObject"]["pos_z"] += 65536
                    if not self.seen_motion: continue
                elif self.fault == "follower-coverage-gap":
                    sample["nativeObservation"]["coverageComplete"] = False
                else:
                    continue
                self.applied = True
        return changed if self.applied else row


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False, "Goldenrod follower copied control did not fail")
    text = repr(result.get("failures", [])) + repr(result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {"follower-still": "Goldenrod initial walk lacks a completed shared Hop",
        "follower-wrong-party": "party-slot2 Mankey identity", "follower-stale-rebind": "stale fieldEpoch",
        "follower-empty-mask": "current Hop mask has no permitted destination", "follower-coverage-gap": "coverage is incomplete",
        "follower-frame-gap": "skip, duplicate or reverse", "follower-extra-command": "no setup mutation or extra command",
        "follower-bad-endpoint": "terminal-render-target", "follower-wrong-motion": "initial walk lacks a completed shared Hop",
        "follower-dropped-travel": "elapsed-gap", "follower-unexpected-epoch": "trace or field coverage incomplete",
        "follower-trace-loss": "trace or field coverage incomplete"}[fault]
    need(expected in text, "Goldenrod follower copied fault failed for an unrelated reason: " + fault)
