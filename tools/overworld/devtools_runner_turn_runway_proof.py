"""Acceptance rows and copied controls for a blocked-runway Runner turn."""

from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_runner_turn_runway_measurement import (
    IDENTITY, KIND, POST_SKID_FLAGS, REQUIREMENT, RUNNER_LANE_HEX,
    STRAIGHT_FLAGS, TURN_FLAGS, decode_call, direction_delta,
)
from tools.overworld.normal_play_observer import complete_travel, live_identity


CLAIMS = (
    "natural-input", "live-actor-identity", "profile-resolution",
    "collision-decision", "engine-boundary", "logical-commit",
    "rendered-motion", "frame-pacing", "control-release",
)
FAULTS = (
    "runner-turn-absent-subject", "runner-turn-stale-subject",
    "runner-turn-held-input", "runner-turn-profile-plan-disabled",
    "runner-turn-straight-not-blocked", "runner-turn-not-accepted",
    "runner-turn-recovery-direction", "runner-turn-missing-control",
)


def contract():
    simple = lambda name, expected: [{"name": name, "operator": "eq", "type": (
        "integer" if type(expected) is int else "array"),
        "validator": "meaningful-observation", "expected": expected}]
    return {
        "natural-input": simple("runner-turn-natural-motion-count", 2),
        "live-actor-identity": simple("runner-turn-stantler-identity-flags",
                                      [1, "WILD", 234, 1, 1, 1, 1, 0]),
        "profile-resolution": simple("runner-turn-profile-lane",
                                      [2279901407, 98312, 8, 1, 4, 193, 1]),
        "collision-decision": simple("runner-turn-runway-decisions", [2, 0, 1, 1]),
        "engine-boundary": simple("runner-turn-policy-boundaries",
                                   [129, 4, 1, 131, 5, 1, 161, 5, 1]),
        "logical-commit": [{"name": "runner-turn-terminal-boundaries-and-target",
            "operator": "eq", "type": "object", "validator": "terminal-boundary-target-v1",
            "requiredCount": 2, "requiredKeys": ["boundaryCount", "final", "target"]}],
        "rendered-motion": simple("runner-turn-skid-recovery-and-corner", [8, 6, 1]),
        "frame-pacing": simple("runner-turn-motion-schedules", [list(range(8)), list(range(6))]),
        "control-release": simple("runner-turn-control-return-count", 2),
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
            "Runner turn runway lacks closed independent replay")
    require(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"),
                                               "closed": True, "errors": []},
            "Runner turn-runway private session did not close cleanly")
    initial, subject = meter["initial"], meter["subject"]
    selected = select_current_actor(initial, subject)
    actor = next(item for item in initial["actors"] if item["handle"] == selected["handle"])
    source, engine = actor["sourceIdentity"], actor["engineIdentity"]
    require(live_identity(actor, source, engine, species=234, role="WILD",
                          current_epoch=initial["context"]["fieldEpoch"])
            and actor.get("identityVerified") is True
            and actor.get("presentationAttached") is True and actor.get("inputOwnership") == 0,
            "Runner turn runway lacks current Stantler identity")
    terminal_subject = select_current_actor(meter["terminal"], subject)
    end = next(item for item in meter["terminal"]["actors"]
               if item["handle"] == terminal_subject["handle"])
    require(all(end.get(key) == actor.get(key) for key in (*IDENTITY, "sourceIdentity"))
            and engine_binding_identity(end["engineIdentity"])
                == engine_binding_identity(actor["engineIdentity"]),
            "Runner turn-runway terminal owner differs")
    require(meter.get("profileLaneHex") == RUNNER_LANE_HEX,
            "Runner turn-runway retained profile differs")
    straight = decode_call(meter["straightInput"]["responseHex"])
    blocked = decode_call(meter["blockedResult"]["responseHex"])
    turn = decode_call(meter["turnInput"]["responseHex"])
    accepted = decode_call(meter["turnResult"]["responseHex"])
    recovery = decode_call(meter["postSkidResult"]["responseHex"])
    require(straight[20] == STRAIGHT_FLAGS and straight[24:26] == bytes((4, 1))
            and blocked[15] == 2 and blocked[16] == 0
            and turn[20] == TURN_FLAGS and turn[24:26] == bytes((5, 1))
            and accepted[15:17] == bytes((1, 1))
            and recovery[20] == POST_SKID_FLAGS and recovery[15:17] == bytes((1, 1))
            and recovery[24:26] == bytes((5, 1)),
            "Runner turn-runway policy transaction differs")
    motions = meter["motions"]
    require(len(motions) == 2 and [motion["duration"] for motion in motions] == [8, 6]
            and all(complete_travel(motion) for motion in motions)
            and motions[0]["target"] == motions[1]["origin"]
            and all(motion["commitAfter"] == ((motion["commitBefore"] + 1) & 0xFFFFFFFF)
                    for motion in motions),
            "Runner turn-runway lacks its two complete motions")
    old_direction, turn_direction = meter["oldDirection"], meter["turnDirection"]
    old_delta, turn_delta = direction_delta(old_direction), direction_delta(turn_direction)
    require(sum(a * b for a, b in zip(old_delta, turn_delta)) == 0
            and [target - origin for origin, target in zip(motions[0]["origin"], motions[0]["target"])] == old_delta
            and [target - origin for origin, target in zip(motions[1]["origin"], motions[1]["target"])] == turn_delta,
            "Runner turn-runway did not turn through a clear perpendicular corridor")
    lifecycle = meter["lifecycle"]
    names = [event["data"]["event"] for event in lifecycle]
    require(len(lifecycle) == 8 and names.count("MOTION_STARTED") == 2
            and names.count("LOGICAL_COMMIT") == 2 and names.count("MOTION_FINISHED") == 2
            and names.count("CONTROL_RETURNED") == 2,
            "Runner turn-runway native lifecycle differs")
    identity = [1, actor["role"], actor["species"], int(actor.get("identityVerified") is True),
                int(actor.get("presentationAttached") is True), int(bool(source.get("active"))),
                int(engine.get("active") is True and engine.get("in_manager") is True),
                actor["inputOwnership"]]
    final = motions[1]["terminalLogical"]
    values = (
        ("natural-input", "runner-turn-natural-motion-count", 2),
        ("live-actor-identity", "runner-turn-stantler-identity-flags", identity),
        ("profile-resolution", "runner-turn-profile-lane",
         [actor["behaviorFingerprint"], actor["matchedLayerMask"], 8, 1, 4, 193, 1]),
        ("collision-decision", "runner-turn-runway-decisions",
         [blocked[15], blocked[16], accepted[15], recovery[15]]),
        ("engine-boundary", "runner-turn-policy-boundaries",
         [straight[20], straight[24], straight[25], turn[20], turn[24], turn[25],
          recovery[20], recovery[24], recovery[25]]),
        ("logical-commit", "runner-turn-terminal-boundaries-and-target",
         {"boundaryCount": 2, "final": final, "target": motions[1]["target"]}),
        ("rendered-motion", "runner-turn-skid-recovery-and-corner", [8, 6, 1]),
        ("frame-pacing", "runner-turn-motion-schedules",
         [[sample["elapsed"] for sample in motion["samples"]] for motion in motions]),
        ("control-release", "runner-turn-control-return-count", 2),
    )
    return [{"claim": claim, "name": name, "value": deepcopy(value), "operator": "eq",
             "expected": deepcopy(value), "passed": True} for claim, name, value in values]


class RunnerTurnRunwayNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown Runner turn-runway fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or not subjects:
            return row
        one_shot = self.fault in ("runner-turn-absent-subject", "runner-turn-stale-subject",
                                  "runner-turn-held-input")
        if one_shot and self.applied:
            return row
        changed, touched = deepcopy(row), False
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is not None and self.fault == "runner-turn-absent-subject":
                sample["actors"].remove(actor); touched = True; break
            if actor is not None and self.fault == "runner-turn-stale-subject":
                actor["authorityGeneration"] += 1; touched = True; break
            if self.fault == "runner-turn-held-input":
                sample["selector"]["heldKeys"] = 16; touched = True; break
        for event in changed.get("events", []):
            data = event.get("data", {})
            if data.get("actorHandle") in handles and self.fault == "runner-turn-missing-control" \
                    and data.get("event") == "CONTROL_RETURNED":
                data["event"] = "WORLD_EFFECT"; touched = True
            if event.get("kind") != "native-observation" \
                    or data.get("observation") != "walk-policy" \
                    or data.get("publicSubject", {}).get("handle", {}).get("value") not in handles:
                continue
            request = bytearray.fromhex(data["requestHex"])
            response = bytearray.fromhex(data["responseHex"])
            if self.fault == "runner-turn-profile-plan-disabled" and data.get("operation") == 1:
                lane = bytearray.fromhex(data["laneHex"]); lane[69] &= 0x7F
                data["laneHex"] = lane.hex(); touched = True
            elif self.fault == "runner-turn-straight-not-blocked" and data.get("operation") == 2 \
                    and request[20] == STRAIGHT_FLAGS and request[15] == 2:
                request[15] = response[15] = 1; response[16] = 1; touched = True
            elif self.fault == "runner-turn-not-accepted" and data.get("operation") == 2 \
                    and request[20] == TURN_FLAGS and request[15] == 1:
                request[15] = response[15] = 2; response[16] = 0; touched = True
            elif self.fault == "runner-turn-recovery-direction" and data.get("operation") == 2 \
                    and request[20] == POST_SKID_FLAGS:
                request[17] = response[17] = request[10]; touched = True
            else:
                continue
            data["requestHex"], data["responseHex"] = request.hex(), response.hex()
        self.applied = self.applied or touched
        return changed if touched else row


Negative = RunnerTurnRunwayNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "Runner turn-runway copied control did not fail")
    text = str(result.get("failures", [])) + str(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "runner-turn-absent-subject": "selected handle must name exactly one current active actor",
        "runner-turn-stale-subject": "selected actor has a stale authorityGeneration",
        "runner-turn-held-input": "requires neutral input",
        "runner-turn-profile-plan-disabled": "profile lane differs",
        "runner-turn-straight-not-blocked": "was not completed",
        "runner-turn-not-accepted": "alternate turn was not accepted",
        "runner-turn-recovery-direction": "recovery start differs",
        "runner-turn-missing-control": "lacks native CONTROL_RETURNED",
    }[fault]
    require(expected in text,
            "Runner turn-runway copied control failed for an unrelated reason: " + fault)
