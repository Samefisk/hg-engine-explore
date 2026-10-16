"""Native proof that a Throw notice cannot strand an accepted Wild Walk."""

from copy import deepcopy

from tools.overworld.devtools_profile_feature_proof import _spec, need
from tools.overworld.devtools_throw_notice_walk_commit_measurement import (
    KIND, NOTICE, POST_FRAMES, REQUIREMENT, THROW_APPLICATION,
)


CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary",
          "logical-commit", "rendered-motion", "control-release")
FAULTS = (KIND + ":missing-control-return", KIND + ":stale-notice-plan")
CONTRACT = {
    "live-actor-identity": [_spec("throw-notice-current-bound-geodude", [1, "WILD", 74, 1, 1])],
    "profile-resolution": [_spec("throw-notice-current-player-binding", [NOTICE, THROW_APPLICATION, 1]),
                           _spec("throw-notice-resolved-speed", 8)],
    "engine-boundary": [_spec("throw-notice-same-accepted-walk", 1)],
    "logical-commit": [_spec("throw-notice-logical-commit", 1)],
    "rendered-motion": [_spec("throw-notice-motion-finished", 1)],
    "control-release": [_spec("throw-notice-control-returned", 1),
                        _spec("throw-notice-clean-frames", minimum=POST_FRAMES)],
}


def contract():
    return deepcopy(CONTRACT)


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True
         and meter.get("failures") == [] and meter.get("requirements") == [REQUIREMENT],
         "Throw notice Walk replay failed")
    need(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"),
                                          "closed": True, "errors": []},
         "owned Throw notice session cleanup is missing")
    walk, notice, returned = meter["walk"], meter["notice"], meter["returned"]
    subject = meter["walkSubject"]
    actor = next(a for a in meter["terminal"]["actors"]
                 if a.get("handle") == subject["handle"])
    trigger = notice["trigger"]
    event = notice["event"]
    terminal_events = returned["events"]
    need(actor["handle"] == walk["handle"] == subject["handle"]
         and actor["subjectIdentity"] == walk["subjectIdentity"]
         and walk["plan"]["reservationId"] == walk["token"]
         and walk["plan"]["duration"] == 16
         and notice["frame"] == walk["frame"] + 1
         and event["data"]["event"] == "CONDITIONAL_RESOLVED"
         and event["data"]["actorHandle"] == walk["handle"]["value"]
         and event["data"]["valueA"] == NOTICE
         and trigger["target"]["kind"] == "PLAYER"
         and trigger["sourceConditionId"] == NOTICE
         and trigger["sourceApplication"] == THROW_APPLICATION
         and notice["resolvedSpeed"] == 8
         and returned["frame"] <= walk["frame"] + 17
         and [e["data"]["event"] for e in terminal_events]
             == ["LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"]
         and all(e["data"]["actorHandle"] == walk["handle"]["value"]
                 for e in terminal_events)
         and terminal_events[0]["data"]["sequence"]
             < terminal_events[1]["data"]["sequence"]
             < terminal_events[2]["data"]["sequence"]
         and meter["postFrames"] >= POST_FRAMES
         and not (actor.get("motionPhase") == "COMMIT_PENDING"
                  and actor.get("reservationId") == walk["token"]),
         "Throw notice accepted Walk or owner receipt differs")
    actual = {
        "throw-notice-current-bound-geodude": [1, actor["role"], actor["species"],
                                               int(actor["identityVerified"]),
                                               int(actor["presentationAttached"])],
        "throw-notice-current-player-binding": [trigger["sourceConditionId"],
                                                 trigger["sourceApplication"],
                                                 int(trigger["targetCurrent"])],
        "throw-notice-resolved-speed": notice["resolvedSpeed"],
        "throw-notice-same-accepted-walk": int(notice["frame"] == walk["frame"] + 1
                                              and walk["plan"]["reservationId"] == walk["token"]),
        "throw-notice-logical-commit": terminal_events[0]["data"]["valueA"]
                                            - walk["commitBefore"],
        "throw-notice-motion-finished": int(terminal_events[1]["data"]["valueA"]
                                                == walk["commitBefore"] + 1),
        "throw-notice-control-returned": int(terminal_events[2]["data"]["valueB"]
                                                == walk["commitBefore"] + 1),
        "throw-notice-clean-frames": meter["postFrames"],
    }
    rows = []
    for claim, specs in CONTRACT.items():
        for spec in specs:
            value = actual[spec["name"]]
            expected = spec.get("expected", spec.get("minimum"))
            need(value == expected if spec["operator"] == "eq" else value >= expected,
                 "Throw notice metric differs: " + spec["name"])
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"], "expected": deepcopy(expected),
                         "passed": True})
    return rows


class ThrowNoticeWalkCommitNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Throw notice copied-data fault")
        self.fault = fault.rsplit(":", 1)[1]
        self.owner = None
        self.applied = False

    def mutate(self, row, subjects):
        if self.applied:
            return row
        changed = deepcopy(row)
        for event in changed.get("events", []):
            data = event.get("data", {})
            if (event.get("kind") == "native"
                    and data.get("event") == "CONDITIONAL_RESOLVED"
                    and data.get("valueA") == NOTICE):
                self.owner = data.get("actorHandle")
        if self.owner is None:
            return row
        if self.fault == "missing-control-return":
            for event in changed.get("events", []):
                data = event.get("data", {})
                if (event.get("kind") == "native"
                        and data.get("event") == "CONTROL_RETURNED"
                        and data.get("actorHandle") == self.owner):
                    data["event"] = "WORLD_EFFECT"
                    data["eventId"] = 14
                    self.applied = True
                    return changed
        else:
            for sample in changed.get("samples", []):
                actor = next((a for a in sample.get("actors", [])
                              if a.get("handle", {}).get("value") == self.owner), None)
                if actor is None or actor.get("motionElapsed") != 1:
                    continue
                targets = sample.get("pokemonCombat", {}).get("targets", [])
                native = next((t for t in targets
                               if t.get("handle", {}).get("value") == self.owner), None)
                if native is None:
                    continue
                native["motion"]["plan"]["reservationId"] += 1
                self.applied = True
                return changed
        return row


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False
         and bool(result.get("failures")),
         "Throw notice copied-data control did not fail")
