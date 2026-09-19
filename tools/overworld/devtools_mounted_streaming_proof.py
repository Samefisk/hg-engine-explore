"""Acceptance rows and copied-data controls for mounted public streaming."""
from copy import deepcopy

from tools.overworld.devtools_mounted_streaming_measurement import (
    IDENTITY,
    KIND,
    LIFECYCLE,
    REQUIREMENT,
    compact,
    require,
)
from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import complete_travel


CLAIMS = ("natural-input", "live-actor-identity", "streaming-path")
FAULTS = (
    "mounted-streaming-absent-subject",
    "mounted-streaming-stale-subject",
    "mounted-streaming-missing-path",
    "mounted-streaming-wrong-diagonal",
    "mounted-streaming-missing-stream-state",
    "mounted-streaming-missing-return",
)


def contract():
    return {
        "natural-input": [{
            "name": "completed-diagonal-motion-count", "operator": "eq",
            "type": "integer", "validator": "meaningful-observation", "expected": 2,
        }],
        "live-actor-identity": [{
            "name": "diagonal-streaming-ledyba-identity", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, "MOUNTED", 165, 1],
        }],
        "streaming-path": [
            {
                "name": "horizontal-path-advance-count", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation", "minimum": 2,
            },
            {
                "name": "vertical-path-advance-count", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation", "minimum": 2,
            },
            {
                "name": "public-stream-lifecycle", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, 1, 1],
            },
            {
                "name": "ordered-path-advance-observation", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, 1],
            },
        ],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT],
            "mounted streaming lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "mounted streaming private session did not close cleanly")
    initial, terminal = meter["initial"], meter["terminal"]
    subject = meter["subject"]
    initial_selected = select_current_actor(initial, subject)
    terminal_selected = select_current_actor(terminal, subject)
    before = next(item for item in initial["actors"]
                  if item.get("handle") == initial_selected["handle"])
    after = next(item for item in terminal["actors"]
                 if item.get("handle") == terminal_selected["handle"])
    require(all(before.get(key) == after.get(key) for key in IDENTITY)
            and before.get("active") is True and after.get("active") is True
            and before.get("identityVerified") is True
            and after.get("identityVerified") is True
            and before.get("presentationAttached") is True
            and after.get("presentationAttached") is True
            and before.get("inputOwnership") == after.get("inputOwnership") == 1
            and before.get("role") == after.get("role") == "MOUNTED"
            and before.get("species") == after.get("species") == 165
            and before.get("sourceIdentity") == after.get("sourceIdentity")
            and engine_binding_identity(before.get("engineIdentity"))
                == engine_binding_identity(after.get("engineIdentity"))
            and initial.get("context") == terminal.get("context"),
            "mounted streaming lacks one current Ledyba identity")
    motions = meter.get("motions", [])
    require(len(motions) == 2 and all(
        motion.get("kind") == "WALK" and motion.get("duration") == 8
        and complete_travel(motion)
        and motion.get("handle") == before["handle"]
        and motion.get("fingerprint") == before["behaviorFingerprint"]
        and motion.get("commitAfter") == (motion.get("commitBefore") + 1) & 0xFFFFFFFF
        for motion in motions), "mounted streaming lacks two complete authored Walks")
    deltas = [[target - origin for origin, target in zip(motion["origin"], motion["target"])]
              for motion in motions]
    require(deltas == [[1, -1], [1, -1]],
            "mounted streaming proof path is not two diagonal advances")
    traces = meter.get("traces", [])
    grouped = {name: [event for event in traces if event.get("data", {}).get("event") == name]
               for name in LIFECYCLE}
    require(all(len(grouped[name]) == 2 for name in LIFECYCLE),
            "mounted streaming proof lifecycle count differs")
    ordered = []
    for index, motion in enumerate(motions):
        events = [grouped[name][index] for name in LIFECYCLE]
        sequences = [event["data"]["sequence"] for event in events]
        ordered.append(int(sequences == sorted(set(sequences))
                           and events[1]["frame"] < events[2]["frame"]
                           and events[2]["frame"] == motion["commitFrame"]))
    samples = meter.get("streamSamples", [])
    lifecycles = [compact([sample["streamState"] for sample in samples
                           if motion["startFrame"] <= sample["frame"] <= motion["finishFrame"]])
                  for motion in motions]
    require(lifecycles == [[0, 1, 2, 0], [0, 1, 2, 0]]
            and after.get("motionKind") == "NONE"
            and after.get("motionPhase") == "IDLE"
            and after.get("streamState") == 0
            and after.get("reservationId") == 0
            and after.get("logical") == {"x": 596, "y": 401}
            and [terminal["player"]["x"], terminal["player"]["y"]] == [596, 401],
            "mounted streaming proof lacks public lifecycle and idle return")
    horizontal = sum(abs(delta[0]) for delta in deltas)
    vertical = sum(abs(delta[1]) for delta in deltas)
    values = (
        ("natural-input", "completed-diagonal-motion-count", len(motions), "eq", 2),
        ("live-actor-identity", "diagonal-streaming-ledyba-identity",
         [1, after["role"], after["species"], int(after["identityVerified"] is True)],
         "eq", [1, "MOUNTED", 165, 1]),
        ("streaming-path", "horizontal-path-advance-count", horizontal, "gte", 2),
        ("streaming-path", "vertical-path-advance-count", vertical, "gte", 2),
        ("streaming-path", "public-stream-lifecycle", [1, 1, 1], "eq", [1, 1, 1]),
        ("streaming-path", "ordered-path-advance-observation", ordered, "eq", [1, 1]),
    )
    return [{
        "claim": claim, "name": name, "value": deepcopy(value),
        "operator": operator, "expected": deepcopy(expected), "passed": True,
    } for claim, name, value, operator, expected in values]


class MountedStreamingNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown mounted streaming fault")
        self.fault = fault
        self.applied = False

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handle = next(iter(subjects.values()))["handle"]
        row_changed = False
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle") == handle), None)
            if actor is None:
                continue
            if self.fault == "mounted-streaming-absent-subject" and not self.applied:
                sample["actors"].remove(actor)
                row_changed = True
            elif self.fault == "mounted-streaming-stale-subject" and not self.applied:
                actor["authorityGeneration"] += 1
                row_changed = True
            elif self.fault == "mounted-streaming-wrong-diagonal" and not self.applied \
                    and actor.get("motionKind") == "WALK":
                actor["target"]["y"] = actor["origin"]["y"]
                row_changed = True
            elif self.fault == "mounted-streaming-missing-stream-state" \
                    and actor.get("streamState") == 1:
                actor["streamState"] = 0
                row_changed = True
            if row_changed and self.fault != "mounted-streaming-missing-stream-state":
                break
        for event in changed.get("events", []):
            data = event.get("data", {})
            if data.get("actorHandle") != handle["value"]:
                continue
            if self.fault == "mounted-streaming-missing-path" \
                    and data.get("event") == "PATH_ADVANCED" and not self.applied:
                data["event"] = "WORLD_EFFECT"
                row_changed = True
                break
            if self.fault == "mounted-streaming-missing-return" \
                    and data.get("event") == "CONTROL_RETURNED" and not self.applied:
                data["event"] = "WORLD_EFFECT"
                row_changed = True
                break
        if row_changed:
            self.applied = True
        return changed if row_changed else row


Negative = MountedStreamingNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "mounted streaming copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "mounted-streaming-absent-subject": "selected handle must name exactly one current active actor",
        "mounted-streaming-stale-subject": "selected actor has a stale authorityGeneration",
        "mounted-streaming-missing-path": "mounted streaming lifecycle count differs",
        "mounted-streaming-wrong-diagonal": "mounted streaming Walk",
        "mounted-streaming-missing-stream-state": "mounted streaming public stream lifecycle differs",
        "mounted-streaming-missing-return": "mounted streaming lifecycle count differs",
    }[fault]
    require(expected in text,
            "mounted streaming copied control failed for an unrelated reason: " + fault)
