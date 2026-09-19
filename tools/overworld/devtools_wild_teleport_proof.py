"""Acceptance rows and copied controls for one natural Wild Teleport."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_wild_teleport_measurement import (
    IDENTITY, KIND, LIFECYCLE, REQUIREMENT,
)
from tools.overworld.normal_play_observer import complete_travel, live_identity


CLAIMS = (
    "natural-input", "live-actor-identity", "logical-commit",
    "frame-pacing", "control-release",
)
FAULTS = (
    "teleport-absent-subject",
    "teleport-stale-subject",
    "teleport-held-input",
    "teleport-missing-path",
    "teleport-early-logical",
    "teleport-wrong-commit",
    "teleport-elapsed-gap",
    "teleport-missing-finish",
    "teleport-missing-control",
)


def contract():
    return {
        "natural-input": [{
            "name": "wild-teleport-start-count", "operator": "eq",
            "type": "integer", "validator": "meaningful-observation", "expected": 1,
        }],
        "live-actor-identity": [{
            "name": "wild-gastly-identity-flags", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, "WILD", 92, 1, 1, 1, 1, 0],
        }],
        "logical-commit": [
            {
                "name": "wild-teleport-commit-and-target", "operator": "eq",
                "type": "object", "validator": "wild-teleport-terminal-v1",
                "requiredKeys": [
                    "origin", "target", "preCommit", "terminalCommit",
                    "terminalLogical",
                ],
            },
            {
                "name": "wild-teleport-path-advance-count", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation", "minimum": 1,
            },
            {
                "name": "wild-teleport-early-final-tile-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation", "expected": 0,
            },
        ],
        "frame-pacing": [{
            "name": "wild-teleport-elapsed-schedule", "operator": "eq",
            "type": "object", "validator": "contiguous-elapsed-v1",
            "requiredKeys": ["start", "duration", "elapsed"],
        }],
        "control-release": [{
            "name": "wild-teleport-terminal-control", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": ["NONE", "IDLE"],
        }],
    }


def require(value, reason):
    if not value:
        raise ValueError(reason)


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == [],
            "wild Teleport lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "wild Teleport private session did not close cleanly")
    initial, subject = meter["initial"], meter["subject"]
    selected = select_current_actor(initial, subject)
    actor = next(item for item in initial["actors"]
                 if item["handle"] == selected["handle"])
    source, engine = actor["sourceIdentity"], actor["engineIdentity"]
    require(live_identity(
        actor, source, engine, species=92, role="WILD",
        current_epoch=initial["context"]["fieldEpoch"],
    ) and actor.get("identityVerified") is True
        and actor.get("presentationAttached") is True
        and actor.get("inputOwnership") == 0,
        "wild Teleport lacks current Gastly identity")
    terminal = meter["terminal"]
    terminal_subject = select_current_actor(terminal, subject)
    end = next(item for item in terminal["actors"]
               if item["handle"] == terminal_subject["handle"])
    require(terminal["context"] == initial["context"]
            and all(end.get(key) == actor.get(key) for key in (*IDENTITY, "sourceIdentity"))
            and engine_binding_identity(end["engineIdentity"])
                == engine_binding_identity(actor["engineIdentity"])
            and end["motionKind"] == "NONE" and end["motionPhase"] == "IDLE"
            and end["reservationId"] == 0,
            "wild Teleport terminal owner or idle state differs")
    motion = meter["motion"]
    require(meter.get("completeMotions") == 1 and motion["kind"] == "TELEPORT"
            and motion["duration"] == 9 and motion["handle"] == actor["handle"]
            and motion["fingerprint"] == actor["behaviorFingerprint"]
            and complete_travel(motion)
            and motion["commitAfter"] == ((motion["commitBefore"] + 1) & 0xFFFFFFFF),
            "wild Teleport lacks one complete nine-frame motion")
    samples = meter.get("logicalSamples", [])
    require(samples and all(type(sample.get("commitSequence")) is int
                            for sample in samples),
            "wild Teleport logical samples are missing")
    target = dict(zip(("x", "y"), motion["target"]))
    precommit = [sample for sample in samples
                 if sample["commitSequence"] == motion["commitBefore"]]
    early = sum(sample.get("logical") == target
                or sample.get("engineLogical") == target for sample in precommit)
    require(precommit and early == 0 and end["logical"] == target,
            "wild Teleport logical commit boundary differs")
    traces = meter.get("traces", [])
    starts = [event for event in traces
              if event.get("data", {}).get("event") == "MOTION_STARTED"]
    paths = [event for event in traces
             if event.get("data", {}).get("event") == "PATH_ADVANCED"]
    require(len(starts) == 1 and paths,
            "wild Teleport native start or path is missing")
    named = {}
    expected = (
        ("MOTION_STARTED", "startFrame", 3, 9),
        ("LOGICAL_COMMIT", "commitFrame", motion["commitAfter"], 3),
        ("MOTION_FINISHED", "finishFrame", motion["commitAfter"], 3),
        ("CONTROL_RETURNED", "finishFrame", 0, 1),
    )
    for name, frame_key, value_a, value_b in expected:
        rows = [event for event in traces
                if event.get("data", {}).get("event") == name]
        require(len(rows) == 1, "missing native " + name)
        event, data = rows[0], rows[0]["data"]
        named[name] = data
        require(event["kind"] == "native" and event["frame"] == motion[frame_key]
                and data.get("reason") == "OK"
                and data.get("actorHandle") == actor["handle"]["value"]
                and data.get("actor") == {
                    key: value for key, value in actor["handle"].items()
                    if key != "value"
                }
                and (data.get("valueA"), data.get("valueB"))
                    == (value_a, value_b),
                "wild Teleport lifecycle differs: " + name)
    sequence = [named[name]["sequence"] for name in LIFECYCLE]
    path_sequence = [event["data"]["sequence"] for event in paths]
    require(sequence == sorted(set(sequence))
            and sequence[0] < min(path_sequence) <= max(path_sequence) < sequence[1]
            and not any(event.get("data", {}).get("event") == "MOTION_CANCELED"
                        for event in traces),
            "wild Teleport lifecycle order or cancellation differs")
    elapsed = [sample["elapsed"] for sample in motion["samples"]]
    require(elapsed == list(range(elapsed[0], motion["duration"])),
            "wild Teleport elapsed schedule differs")
    identity_flags = [
        1,
        actor["role"],
        actor["species"],
        int(actor.get("identityVerified") is True),
        int(actor.get("presentationAttached") is True),
        int(bool(source.get("active"))),
        int(engine.get("active") is True and engine.get("in_manager") is True),
        actor["inputOwnership"],
    ]
    values = (
        ("natural-input", "wild-teleport-start-count", 1, "eq"),
        ("live-actor-identity", "wild-gastly-identity-flags", identity_flags, "eq"),
        ("logical-commit", "wild-teleport-commit-and-target", {
            "origin": motion["origin"], "target": motion["target"],
            "preCommit": motion["commitBefore"],
            "terminalCommit": motion["commitAfter"],
            "terminalLogical": end["logical"],
        }, "eq"),
        ("logical-commit", "wild-teleport-path-advance-count", len(paths), "gte"),
        ("logical-commit", "wild-teleport-early-final-tile-count", early, "eq"),
        ("frame-pacing", "wild-teleport-elapsed-schedule", {
            "start": elapsed[0], "duration": motion["duration"], "elapsed": elapsed,
        }, "eq"),
        ("control-release", "wild-teleport-terminal-control",
         [end["motionKind"], end["motionPhase"]], "eq"),
    )
    return [{
        "claim": claim, "name": name, "value": deepcopy(value),
        "operator": operator, "expected": deepcopy(value), "passed": True,
    } for claim, name, value, operator in values]


class WildTeleportNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown wild Teleport fault")
        self.fault = fault
        self.applied = False

    def mutate(self, row, subjects):
        if (self.applied and self.fault != "teleport-missing-path") \
                or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is not None and self.fault == "teleport-absent-subject":
                sample["actors"].remove(actor)
                self.applied = True
            elif actor is not None and self.fault == "teleport-stale-subject":
                actor["authorityGeneration"] += 1
                self.applied = True
            elif self.fault == "teleport-held-input":
                sample["selector"]["heldKeys"] = 16
                self.applied = True
            elif actor is not None and actor.get("motionKind") == "TELEPORT" \
                    and actor.get("motionElapsed") == 2 \
                    and self.fault == "teleport-elapsed-gap":
                actor["motionElapsed"] = 3
                self.applied = True
            elif actor is not None and actor.get("motionKind") == "TELEPORT" \
                    and actor.get("motionElapsed") == 2 \
                    and self.fault == "teleport-early-logical":
                actor["logical"] = deepcopy(actor["target"])
                self.applied = True
            if self.applied:
                break
        if not self.applied or self.fault == "teleport-missing-path":
            meanings = {
                "teleport-missing-path": "PATH_ADVANCED",
                "teleport-missing-finish": "MOTION_FINISHED",
                "teleport-missing-control": "CONTROL_RETURNED",
            }
            for event in changed.get("events", []):
                data = event.get("data", {})
                if self.fault in meanings and data.get("actorHandle") in handles \
                        and data.get("event") == meanings[self.fault]:
                    data["event"] = "WORLD_EFFECT"
                    self.applied = True
                elif self.fault == "teleport-wrong-commit" \
                        and data.get("actorHandle") in handles \
                        and data.get("event") == "LOGICAL_COMMIT":
                    data["valueB"] = 2
                    self.applied = True
                if self.applied and self.fault != "teleport-missing-path":
                    break
        return changed if self.applied else row


Negative = WildTeleportNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "wild Teleport copied control did not fail")
    strings = []

    def visit(value):
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result.get("failures", []))
    visit(result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "teleport-absent-subject": "selected handle must name exactly one current active actor",
        "teleport-stale-subject": "selected actor has a stale authorityGeneration",
        "teleport-held-input": "wild Teleport requires neutral input",
        "teleport-missing-path": "missing native PATH_ADVANCED",
        "teleport-early-logical": "wild Teleport reached target before commit",
        "teleport-wrong-commit": "missing native LOGICAL_COMMIT",
        "teleport-elapsed-gap": "elapsed-gap",
        "teleport-missing-finish": "missing native MOTION_FINISHED",
        "teleport-missing-control": "missing native CONTROL_RETURNED",
    }[fault]
    require(any(expected in value for value in strings),
            "wild Teleport copied control failed for an unrelated reason: " + fault)
