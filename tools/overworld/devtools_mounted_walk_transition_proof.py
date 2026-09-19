"""Acceptance rows and copied-data controls for mounted Walk transition."""
from copy import deepcopy

from tools.overworld.devtools_mounted_walk_transition_measurement import (
    KIND,
    LIFECYCLE,
    ORIGIN,
    RECOVERY_TARGET,
    REQUIREMENT,
    TRANSITION_ORIGIN,
    TRANSITION_TARGET,
    require,
    same_lifetime,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import complete_travel


CLAIMS = (
    "natural-input",
    "live-actor-identity",
    "logical-commit",
    "rendered-motion",
    "frame-pacing",
    "world-transition",
    "control-release",
)
FAULTS = (
    "mounted-walk-transition-absent-subject",
    "mounted-walk-transition-stale-subject",
    "mounted-walk-transition-missing-context",
    "mounted-walk-transition-missing-commit",
    "mounted-walk-transition-bad-pair",
    "mounted-walk-transition-missing-return",
)


def contract():
    return {
        "natural-input": [{
            "name": "mounted-walk-transition-route-milestones", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, [671, 402], 1],
        }],
        "live-actor-identity": [{
            "name": "mounted-walk-transition-identity-flags", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, "MOUNTED", 155, 1, 1, 1],
        }],
        "logical-commit": [{
            "name": "mounted-walk-transition-boundary-and-target", "operator": "eq",
            "type": "object", "validator": "terminal-boundary-target-v1",
            "requiredCount": 1,
            "requiredKeys": ["boundaryCount", "final", "target"],
        }],
        "rendered-motion": [{
            "name": "mounted-walk-transition-pair-samples", "operator": "eq",
            "type": "integer", "validator": "meaningful-observation", "minimum": 1,
        }],
        "frame-pacing": [
            {
                "name": "mounted-walk-transition-elapsed-schedule", "operator": "eq",
                "type": "object", "validator": "contiguous-elapsed-v1",
                "requiredKeys": ["start", "duration", "elapsed"],
            },
            {
                "name": "mounted-walk-transition-maximum-callback-gap", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation", "maximum": 3,
            },
        ],
        "world-transition": [{
            "name": "mounted-walk-map-change", "operator": "eq",
            "type": "array", "validator": "meaningful-observation", "expected": [33, 60],
        }],
        "control-release": [{
            "name": "mounted-walk-transition-recovery-state", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": ["IDLE", 0, 1, 1],
        }],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == [] and meter.get("requirements") == [REQUIREMENT],
            "mounted Walk transition lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "mounted Walk transition private session did not close cleanly")
    initial, transition, terminal = meter["initial"], meter["transition"], meter["terminal"]
    before = next(actor for actor in initial["actors"]
                  if actor["handle"] == select_current_actor(initial, meter["initialSubject"])["handle"])
    rebound = next(actor for actor in transition["actors"]
                   if actor["handle"] == select_current_actor(transition, meter["subject"])["handle"])
    after = next(actor for actor in terminal["actors"]
                 if actor["handle"] == select_current_actor(terminal, meter["subject"])["handle"])
    require(all(actor.get("active") is True and actor.get("role") == "MOUNTED"
                and actor.get("species") == 155 and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True and actor.get("inputOwnership") == 1
                for actor in (before, rebound, after))
            and before.get("subjectIdentity") == rebound.get("subjectIdentity") == after.get("subjectIdentity")
            and same_lifetime(before["handle"], rebound["handle"])
            and rebound["handle"] == after["handle"]
            and initial["context"]["mapId"] == 33
            and transition["context"]["mapId"] == terminal["context"]["mapId"] == 60,
            "mounted Walk transition lacks one rebound Cyndaquil identity")
    motions = meter.get("motions", [])
    require(len(motions) == 2 and all(
        motion.get("kind") == "WALK" and complete_travel(motion)
        and motion.get("handle") == rebound["handle"]
        and motion.get("commitAfter") == (motion.get("commitBefore") + 1) & 0xFFFFFFFF
        for motion in motions), "mounted Walk transition lacks two complete Walks")
    crossing, recovery = motions
    require(crossing["origin"] == list(TRANSITION_ORIGIN)
            and crossing["target"] == list(TRANSITION_TARGET)
            and recovery["origin"] == list(TRANSITION_TARGET)
            and recovery["target"] == list(RECOVERY_TARGET)
            and [terminal["player"]["x"], terminal["player"]["y"]] == list(RECOVERY_TARGET),
            "mounted Walk transition proof route differs")
    traces = meter.get("traces", [])
    require(all(sum(event.get("data", {}).get("event") == name for event in traces) == 2
                for name in LIFECYCLE), "mounted Walk transition proof lifecycle differs")
    pair = [sample for sample in meter.get("pairSamples", [])
            if crossing["startFrame"] <= sample["frame"] <= crossing["finishFrame"]]
    require(pair and all(sample["player"] == sample["mount"] for sample in pair),
            "mounted Walk transition lacks paired rendered samples")
    frames = [sample["frame"] for sample in pair]
    maximum_gap = max((right - left for left, right in zip(frames, frames[1:])), default=0)
    schedule = {
        "start": crossing["samples"][0]["elapsed"],
        "duration": crossing["duration"],
        "elapsed": [sample["elapsed"] for sample in crossing["samples"]],
    }
    boundary = {
        "boundaryCount": 1,
        "final": list(TRANSITION_TARGET),
        "target": list(TRANSITION_TARGET),
    }
    identity = [1, after["role"], after["species"],
                int(after["identityVerified"] is True),
                int(after["presentationAttached"] is True),
                int(same_lifetime(before["handle"], after["handle"]))]
    values = (
        ("natural-input", "mounted-walk-transition-route-milestones",
         [1, list(ORIGIN), 1], "eq", [1, [671, 402], 1]),
        ("live-actor-identity", "mounted-walk-transition-identity-flags",
         identity, "eq", [1, "MOUNTED", 155, 1, 1, 1]),
        ("logical-commit", "mounted-walk-transition-boundary-and-target",
         boundary, "eq", None),
        ("rendered-motion", "mounted-walk-transition-pair-samples",
         len(pair), "eq", None),
        ("frame-pacing", "mounted-walk-transition-elapsed-schedule",
         schedule, "eq", None),
        ("frame-pacing", "mounted-walk-transition-maximum-callback-gap",
         maximum_gap, "lte", 3),
        ("world-transition", "mounted-walk-map-change", [33, 60], "eq", [33, 60]),
        ("control-release", "mounted-walk-transition-recovery-state",
         [after["motionPhase"], after["reservationId"], after["inputOwnership"], 1],
         "eq", ["IDLE", 0, 1, 1]),
    )
    return [{
        "claim": claim, "name": name, "value": deepcopy(value),
        "operator": operator, "expected": deepcopy(expected), "passed": True,
    } for claim, name, value, operator, expected in values]


class MountedWalkTransitionNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown mounted Walk transition fault")
        self.fault = fault
        self.applied = False
        self.initial_handle = None

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        subject = next(iter(subjects.values()))
        if self.initial_handle is None:
            self.initial_handle = deepcopy(subject["handle"])
        identity = subject.get("subjectIdentity")
        row_changed = False
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("subjectIdentity") == identity
                          and item.get("role") == "MOUNTED"), None)
            if actor is None:
                continue
            if self.fault == "mounted-walk-transition-absent-subject" and not self.applied:
                sample["actors"].remove(actor)
                row_changed = True
            elif self.fault == "mounted-walk-transition-stale-subject" and not self.applied:
                actor["authorityGeneration"] += 1
                row_changed = True
            elif self.fault == "mounted-walk-transition-bad-pair" and not self.applied:
                actor["engineObject"]["pos_x"] += 1
                row_changed = True
            if row_changed:
                break
        if not row_changed:
            for event in changed.get("events", []):
                data = event.get("data", {})
                name = data.get("event")
                handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
                selected_lifetime = same_lifetime(handle, self.initial_handle)
                if self.fault == "mounted-walk-transition-missing-context" \
                        and name == "CONTEXT_CHANGED" and selected_lifetime:
                    data["event"] = "WORLD_EFFECT"
                    row_changed = True
                elif self.fault == "mounted-walk-transition-missing-commit" \
                        and name == "LOGICAL_COMMIT" and selected_lifetime \
                        and handle.get("fieldEpoch") != self.initial_handle["fieldEpoch"]:
                    data["event"] = "WORLD_EFFECT"
                    row_changed = True
                elif self.fault == "mounted-walk-transition-missing-return" \
                        and name == "CONTROL_RETURNED" and selected_lifetime \
                        and handle.get("fieldEpoch") != self.initial_handle["fieldEpoch"]:
                    data["event"] = "WORLD_EFFECT"
                    row_changed = True
                if row_changed:
                    break
        if row_changed:
            self.applied = True
        return changed if row_changed else row


Negative = MountedWalkTransitionNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "mounted Walk transition copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "mounted-walk-transition-absent-subject": "selected handle must name exactly one current active actor",
        "mounted-walk-transition-stale-subject": "selected actor has a stale authorityGeneration",
        "mounted-walk-transition-missing-context": "context lifecycle differs",
        "mounted-walk-transition-missing-commit": "lifecycle count differs",
        "mounted-walk-transition-bad-pair": "identity or paired pose differs",
        "mounted-walk-transition-missing-return": "lifecycle count differs",
    }[fault]
    require(expected in text,
            "mounted Walk transition copied control failed for an unrelated reason: " + fault)
