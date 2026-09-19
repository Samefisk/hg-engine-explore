"""Acceptance rows and copied-data controls for held cardinal streaming."""
from copy import deepcopy

from tools.overworld.devtools_mounted_cardinal_streaming_measurement import (
    IDENTITY,
    KIND,
    LIFECYCLE,
    MAX_SKID_MOVES,
    MIN_SKID_MOVES,
    ORIGIN,
    REQUIREMENT,
    ROUTE_MOVES,
    TARGET,
    require,
)
from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import complete_travel


CLAIMS = ("natural-input", "live-actor-identity", "streaming-path")
FAULTS = (
    "cardinal-streaming-absent-subject",
    "cardinal-streaming-stale-subject",
    "cardinal-streaming-missing-path",
    "cardinal-streaming-custom-stream-state",
    "cardinal-streaming-missing-return",
)


def contract():
    return {
        "natural-input": [{
            "name": "held-input-terminal-x", "operator": "eq",
            "type": "array", "validator": "stream-target-reached-v1", "distance": 20,
        }],
        "live-actor-identity": [{
            "name": "streaming-cyndaquil-identity", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, "MOUNTED", 155, 1],
        }],
        "streaming-path": [{
            "name": "native-stream-contract", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, 0, 0],
        }],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT],
            "cardinal streaming lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "cardinal streaming private session did not close cleanly")
    initial, target = meter["initial"], meter["target"]
    route_terminal, terminal = meter["routeTerminal"], meter["terminal"]
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
            and before.get("species") == after.get("species") == 155
            and before.get("sourceIdentity") == after.get("sourceIdentity")
            and engine_binding_identity(before.get("engineIdentity"))
                == engine_binding_identity(after.get("engineIdentity"))
            and initial.get("context") == target.get("context")
                == route_terminal.get("context") == terminal.get("context"),
            "cardinal streaming lacks one current Cyndaquil identity")
    motions = meter.get("motions", [])
    route_x = route_terminal["player"]["x"]
    route_motion_count = meter.get("routeMotionCount")
    require(type(route_motion_count) is int and 1 <= route_motion_count < len(motions),
            "cardinal streaming lacks the stop boundary")
    route_motions = motions[:route_motion_count]
    skid_count = sum(motion.get("kind") == "SKID" for motion in route_motions)
    route_count = len(route_motions) - skid_count
    require(route_count in (ROUTE_MOVES, ROUTE_MOVES + 1)
            and skid_count in range(MIN_SKID_MOVES, MAX_SKID_MOVES + 1)
            and route_x == ORIGIN[0] + route_count + skid_count
            and len(motions) == route_motion_count + 1 and all(
        complete_travel(motion)
        and motion.get("handle") == before["handle"]
        and motion.get("fingerprint") == before["behaviorFingerprint"]
        and motion.get("commitAfter") == (motion.get("commitBefore") + 1) & 0xFFFFFFFF
        for motion in motions),
        "cardinal streaming lacks complete held-route motions")
    route = motions[:route_count]
    skid = motions[route_count:route_motion_count]
    recovery = motions[-1]
    require([motion["origin"] for motion in route]
                == [[ORIGIN[0] + index, ORIGIN[1]] for index in range(route_count)]
            and [motion["target"] for motion in route]
                == [[ORIGIN[0] + index + 1, ORIGIN[1]] for index in range(route_count)]
            and [motion["origin"] for motion in skid]
                == [[ORIGIN[0] + route_count + index, ORIGIN[1]]
                    for index in range(skid_count)]
            and [motion["target"] for motion in skid]
                == [[ORIGIN[0] + route_count + index + 1, ORIGIN[1]]
                    for index in range(skid_count)]
            and all(motion["kind"] == "WALK" for motion in route + [recovery])
            and all(motion["kind"] == "SKID" for motion in skid)
            and recovery["origin"] == [route_x, ORIGIN[1]]
            and recovery["target"] == [route_x - 1, ORIGIN[1]]
            and [target["player"]["x"], target["player"]["y"]] == list(TARGET)
            and [terminal["player"]["x"], terminal["player"]["y"]]
                == [route_x - 1, ORIGIN[1]],
            "cardinal streaming proof route differs")
    traces = meter.get("traces", [])
    grouped = {name: [event for event in traces
                      if event.get("data", {}).get("event") == name]
               for name in LIFECYCLE}
    require(all(len(grouped[name]) == route_count + skid_count + 1
                for name in LIFECYCLE),
            "cardinal streaming proof lifecycle count differs")
    for index, motion in enumerate(motions):
        events = [grouped[name][index] for name in LIFECYCLE]
        sequences = [event["data"]["sequence"] for event in events]
        require(sequences == sorted(set(sequences))
                and events[1]["frame"] < events[2]["frame"]
                and events[1]["data"].get("valueB")
                    == (4 if motion["kind"] == "SKID" else 1)
                and events[2]["frame"] == motion["commitFrame"],
                "cardinal streaming proof path order differs")
    samples = meter.get("streamSamples", [])
    lifecycles = [[sample["streamState"] for sample in samples
                   if motion["startFrame"] <= sample["frame"] <= motion["finishFrame"]]
                  for motion in motions]
    require(samples and all(states and set(states).issubset({0, 1, 2})
                            and 1 in states and 2 in states
                            and states.index(1) < states.index(2)
                            for states in lifecycles)
            and after.get("motionKind") == "NONE"
            and after.get("motionPhase") == "IDLE"
            and after.get("streamState") == 0
            and after.get("reservationId") == 0
            and after.get("logical") == {"x": route_x - 1, "y": ORIGIN[1]},
            "cardinal streaming proof lacks public lifecycle or idle control")
    values = (
        ("natural-input", "held-input-terminal-x",
         [ORIGIN[0], TARGET[0], route_x], "eq", None),
        ("live-actor-identity", "streaming-cyndaquil-identity",
         [1, after["role"], after["species"], int(after["identityVerified"] is True)],
         "eq", [1, "MOUNTED", 155, 1]),
        # Every public stream cycle completed, no other role took ownership,
        # and every policy-facing lifecycle transition was ordered and valid.
        ("streaming-path", "native-stream-contract", [1, 0, 0], "eq", [1, 0, 0]),
    )
    return [{
        "claim": claim, "name": name, "value": deepcopy(value),
        "operator": operator, "expected": deepcopy(expected), "passed": True,
    } for claim, name, value, operator, expected in values]


class MountedCardinalStreamingNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown cardinal streaming fault")
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
            if self.fault == "cardinal-streaming-absent-subject" and not self.applied:
                sample["actors"].remove(actor)
                row_changed = True
            elif self.fault == "cardinal-streaming-stale-subject" and not self.applied:
                actor["authorityGeneration"] += 1
                row_changed = True
            elif self.fault == "cardinal-streaming-custom-stream-state" and not self.applied:
                actor["streamState"] = 3
                row_changed = True
            if row_changed:
                break
        for event in changed.get("events", []):
            data = event.get("data", {})
            if data.get("actorHandle") != handle["value"]:
                continue
            if self.fault == "cardinal-streaming-missing-path" \
                    and data.get("event") == "PATH_ADVANCED" and not self.applied:
                data["event"] = "WORLD_EFFECT"
                row_changed = True
                break
            if self.fault == "cardinal-streaming-missing-return" \
                    and data.get("event") == "CONTROL_RETURNED" and not self.applied:
                data["event"] = "WORLD_EFFECT"
                row_changed = True
                break
        if row_changed:
            self.applied = True
        return changed if row_changed else row


Negative = MountedCardinalStreamingNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "cardinal streaming copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "cardinal-streaming-absent-subject": "selected handle must name exactly one current active actor",
        "cardinal-streaming-stale-subject": "selected actor has a stale authorityGeneration",
        "cardinal-streaming-missing-path": "cardinal streaming lifecycle count differs",
        "cardinal-streaming-custom-stream-state": "cardinal streaming used an invalid path or public stream state",
        "cardinal-streaming-missing-return": "cardinal streaming lifecycle count differs",
    }[fault]
    require(expected in text,
            "cardinal streaming copied control failed for an unrelated reason: " + fault)
