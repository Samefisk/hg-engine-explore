"""Acceptance rows and copied controls for one natural Runner stop skid."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_runner_stop_skid_measurement import (
    IDENTITY, KIND, REQUIREMENT, STOP_STEP_FLAGS, STEP_PLANNED_SKID_PATH,
    decode_call,
)
from tools.overworld.normal_play_observer import complete_travel, live_identity


CLAIMS = (
    "natural-input", "live-actor-identity", "engine-boundary",
    "logical-commit", "rendered-motion", "frame-pacing", "control-release",
)
FAULTS = (
    "runner-stop-absent-subject",
    "runner-stop-stale-subject",
    "runner-stop-held-input",
    "runner-stop-not-none",
    "runner-stop-chain-action",
    "runner-stop-blocked",
    "runner-stop-wrong-time",
    "runner-stop-missing-control",
)


def contract():
    return {
        "natural-input": [{
            "name": "runner-stop-start-count", "operator": "eq",
            "type": "integer", "validator": "meaningful-observation", "expected": 1,
        }],
        "live-actor-identity": [{
            "name": "runner-stantler-identity-flags", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, "WILD", 234, 1, 1, 1, 1, 0],
        }],
        "engine-boundary": [{
            "name": "runner-stop-normal-none-boundary", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [255, 3, 1, 8, 7, 135, 0, 0],
        }],
        "logical-commit": [{
            "name": "runner-stop-commit-and-target", "operator": "eq",
            "type": "object", "validator": "wild-teleport-terminal-v1",
            "requiredKeys": [
                "origin", "target", "preCommit", "terminalCommit",
                "terminalLogical",
            ],
        }],
        "rendered-motion": [{
            "name": "runner-stop-one-tile-eight-frame-walk", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, 8],
        }],
        "frame-pacing": [{
            "name": "runner-stop-elapsed-schedule", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": list(range(9)),
        }],
        "control-release": [{
            "name": "runner-stop-terminal-control", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": ["NONE", "IDLE", 0],
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
            "Runner stop skid lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "Runner stop-skid private session did not close cleanly")

    initial, subject = meter["initial"], meter["subject"]
    selected = select_current_actor(initial, subject)
    actor = next(item for item in initial["actors"]
                 if item["handle"] == selected["handle"])
    source, engine = actor["sourceIdentity"], actor["engineIdentity"]
    require(live_identity(
        actor, source, engine, species=234, role="WILD",
        current_epoch=initial["context"]["fieldEpoch"],
    ) and actor.get("identityVerified") is True
        and actor.get("presentationAttached") is True
        and actor.get("inputOwnership") == 0,
        "Runner stop skid lacks current Stantler identity")

    terminal = meter["terminal"]
    terminal_subject = select_current_actor(terminal, subject)
    end = next(item for item in terminal["actors"]
               if item["handle"] == terminal_subject["handle"])
    require(terminal["context"] == initial["context"]
            and all(end.get(key) == actor.get(key)
                    for key in (*IDENTITY, "sourceIdentity"))
            and engine_binding_identity(end["engineIdentity"])
                == engine_binding_identity(actor["engineIdentity"])
            and end["motionKind"] == "NONE" and end["motionPhase"] == "IDLE"
            and end["reservationId"] == 0,
            "Runner stop-skid terminal owner or idle state differs")

    proposal = decode_call(meter["policyInput"]["responseHex"])
    started = decode_call(meter["startResult"]["responseHex"])
    require(meter.get("stopSpeed") == 4
            and proposal[10] == 0xFF and proposal[13] == 3
            and proposal[11] == 1 and proposal[19] == 8
            and proposal[20] == STOP_STEP_FLAGS
            and started[20] == (STOP_STEP_FLAGS | STEP_PLANNED_SKID_PATH)
            and started[25] == 1
            and all(raw[22] == 0 and raw[23] == 0
                    for raw in (proposal, started)),
            "Runner stop skid is not a normal NONE request independent of Movement Chain")

    motion = meter["motion"]
    require(meter.get("completeMotions") == 1
            and motion["kind"] == "WALK" and motion["duration"] == 8
            and motion["handle"] == actor["handle"]
            and motion["fingerprint"] == actor["behaviorFingerprint"]
            and complete_travel(motion)
            and motion["commitAfter"] == ((motion["commitBefore"] + 1) & 0xFFFFFFFF),
            "Runner stop skid lacks one complete eight-frame Walk")
    delta = [target - origin
             for origin, target in zip(motion["origin"], motion["target"])]
    require(sum(abs(value) for value in delta) == 1,
            "Runner stop skid did not move exactly one tile")
    elapsed = [sample["elapsed"] for sample in motion["samples"]]
    require(elapsed == list(range(8))
            and motion.get("travelEnd", {}).get("elapsed") == 8,
            "Runner stop-skid elapsed schedule differs")

    traces = meter["traces"]
    starts = [event for event in traces
              if event["frame"] == meter["policyFrame"]
              and event["data"].get("event") == "MOTION_STARTED"
              and (event["data"].get("valueA"), event["data"].get("valueB"))
                  == (1, 8)]
    require(len(starts) == 1,
            "Runner stop skid lacks its native motion start")
    start_sequence = starts[0]["data"]["sequence"]
    lifecycle = (
        ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 1),
        ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 1),
        ("CONTROL_RETURNED", motion["finishFrame"], 0, motion["commitAfter"]),
    )
    sequences = [start_sequence]
    for name, frame, value_a, value_b in lifecycle:
        rows = [event for event in traces
                if event["data"].get("sequence", 0) > start_sequence
                and event["data"].get("event") == name]
        require(len(rows) == 1 and rows[0]["frame"] == frame
                and rows[0]["data"].get("reason") == "OK"
                and (rows[0]["data"].get("valueA"),
                     rows[0]["data"].get("valueB")) == (value_a, value_b),
                "Runner stop skid lacks native " + name)
        sequences.append(rows[0]["data"]["sequence"])
    require(sequences == sorted(set(sequences))
            and not any(event["data"].get("event") == "MOTION_CANCELED"
                        and start_sequence < event["data"].get("sequence", 0)
                            <= sequences[-1]
                        for event in traces),
            "Runner stop-skid native lifecycle differs")

    identity_flags = [
        1, actor["role"], actor["species"],
        int(actor.get("identityVerified") is True),
        int(actor.get("presentationAttached") is True),
        int(bool(source.get("active"))),
        int(engine.get("active") is True and engine.get("in_manager") is True),
        actor["inputOwnership"],
    ]
    values = (
        ("natural-input", "runner-stop-start-count", 1),
        ("live-actor-identity", "runner-stantler-identity-flags", identity_flags),
        ("engine-boundary", "runner-stop-normal-none-boundary", [
            proposal[10], proposal[13], proposal[11], proposal[19], proposal[20],
            started[20], started[22], started[23],
        ]),
        ("logical-commit", "runner-stop-commit-and-target", {
            "origin": motion["origin"], "target": motion["target"],
            "preCommit": motion["commitBefore"],
            "terminalCommit": motion["commitAfter"],
            "terminalLogical": end["logical"],
        }),
        ("rendered-motion", "runner-stop-one-tile-eight-frame-walk", [1, 8]),
        ("frame-pacing", "runner-stop-elapsed-schedule", elapsed + [8]),
        ("control-release", "runner-stop-terminal-control",
         [end["motionKind"], end["motionPhase"], end["reservationId"]]),
    )
    return [{
        "claim": claim, "name": name, "value": deepcopy(value),
        "operator": "eq", "expected": deepcopy(value), "passed": True,
    } for claim, name, value in values]


class RunnerStopSkidNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown Runner stop-skid fault")
        self.fault = fault
        self.applied = False
        self.stop_started = False

    def mutate(self, row, subjects):
        if self.applied or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is not None and self.fault == "runner-stop-absent-subject":
                sample["actors"].remove(actor)
                self.applied = True
            elif actor is not None and self.fault == "runner-stop-stale-subject":
                actor["authorityGeneration"] += 1
                self.applied = True
            elif self.fault == "runner-stop-held-input":
                sample["selector"]["heldKeys"] = 16
                self.applied = True
            if self.applied:
                break
        if not self.applied:
            for event in changed.get("events", []):
                data = event.get("data", {})
                if event.get("kind") == "native-observation" \
                        and data.get("observation") == "walk-policy" \
                        and data.get("publicSubject", {}).get("handle", {}).get("value") \
                            in handles \
                        and data.get("operation") == 2:
                    response = bytearray.fromhex(data["responseHex"])
                    if response[15] == 1 \
                            and response[20] & STOP_STEP_FLAGS == STOP_STEP_FLAGS:
                        self.stop_started = True
                if self.stop_started \
                        and data.get("actorHandle") in handles \
                        and self.fault == "runner-stop-missing-control" \
                        and data.get("event") == "CONTROL_RETURNED":
                    data["event"] = "WORLD_EFFECT"
                    self.applied = True
                    break
                if event.get("kind") != "native-observation" \
                        or data.get("observation") != "walk-policy" \
                        or data.get("publicSubject", {}).get("handle", {}).get("value") \
                            not in handles:
                    continue
                operation = data.get("operation")
                request = bytearray.fromhex(data["requestHex"])
                response = bytearray.fromhex(data["responseHex"])
                if operation == 1 and response[10] == 0xFF \
                        and response[20] & STOP_STEP_FLAGS == STOP_STEP_FLAGS:
                    if self.fault == "runner-stop-not-none":
                        request[10] = response[10] = 0
                    elif self.fault == "runner-stop-chain-action":
                        request[22] = response[22] = 1
                    elif self.fault == "runner-stop-wrong-time":
                        response[19] = 7
                    else:
                        continue
                elif operation == 2 and self.fault == "runner-stop-blocked" \
                        and response[20] & STOP_STEP_FLAGS == STOP_STEP_FLAGS:
                    request[15] = response[15] = 2
                else:
                    continue
                data["requestHex"] = request.hex()
                data["responseHex"] = response.hex()
                self.applied = True
                break
        return changed if self.applied else row


Negative = RunnerStopSkidNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "Runner stop-skid copied control did not fail")
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
        "runner-stop-absent-subject": "selected handle must name exactly one current active actor",
        "runner-stop-stale-subject": "selected actor has a stale authorityGeneration",
        "runner-stop-held-input": "Runner stop skid requires neutral input",
        "runner-stop-not-none": "Runner stop skid was not completed",
        "runner-stop-chain-action": "used a Movement Chain action or pause action",
        "runner-stop-blocked": "start was not one accepted planned tile",
        "runner-stop-wrong-time": "normal NONE proposal differs",
        "runner-stop-missing-control": "lacks native CONTROL_RETURNED",
    }[fault]
    require(any(expected in value for value in strings),
            "Runner stop-skid copied control failed for an unrelated reason: " + fault)
