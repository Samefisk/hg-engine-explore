"""Acceptance rows for the controlled live Wild condition caller.

Copied mutations below test this evaluator only.  They do not replace the live
reader, its callback authentication, or a final-ROM scenario run.
"""
from __future__ import annotations

from copy import deepcopy

from tools.overworld.devtools_condition_controller import KIND, REQUIREMENT
from tools.overworld.devtools_condition_controller_measurement import (
    ConditionControllerMeasurement,
)


RULES = (
    ("live-actor-identity", "live-wild-condition-subject"),
    ("profile-resolution", "conditional-profile-and-target-used"),
    ("engine-boundary", "conditions-only-at-intent-boundaries"),
    ("controlled-action", "stale-condition-target-fails-closed"),
    ("logical-commit", "conditional-hop-commit"),
    ("control-release", "control-return-before-stale-recheck"),
)
CLAIMS = tuple(claim for claim, _name in RULES)
FAULTS = (
    "condition-controller-absent-subject",
    "condition-controller-stale-subject",
)


def require(value, reason):
    if not value:
        raise ValueError("condition live controller proof: " + reason)


def contract():
    return {
        claim: [{
            "name": name,
            "operator": "eq",
            "type": "integer",
            "validator": "meaningful-observation",
            "minimum": 1,
        }]
        for claim, name in RULES
    }


def _action(test, operation):
    matches = [item for item in test.get("actions", [])
               if item.get("op") == operation]
    require(len(matches) == 1, "missing exact " + operation + " action")
    return matches[0]


def _events_by_frame(events):
    result = {}
    for event in events:
        require(isinstance(event, dict) and type(event.get("frame")) is int,
                "event lacks a completed frame")
        result.setdefault(event["frame"], []).append(event)
    return result


def replay(test, rows):
    """Replay bounded raw rows through the same meter used by the controller."""
    require(test.get("mode") == "prepared"
            and test.get("requirements") == [REQUIREMENT]
            and test.get("measurements") == [{
                "kind": KIND, "subject": "weepinbell"}],
            "recipe identity differs")
    require(test.get("subjects") == [{
        "id": "weepinbell", "species": 70,
        "role": "WILD", "acquire": "spawn"}],
        "recipe subject differs")
    arm = _action(test, "condition-controller.arm")
    wait = _action(test, "wait")
    close = _action(test, "condition-controller.close")
    wait_predicate = wait.get("args", {}).get("predicate", {})
    require([item.get("op") for item in test.get("actions", [])]
            == ["condition-controller.arm", "wait",
                "condition-controller.close"]
            and arm.get("args") == {"subject": "weepinbell"}
            and close.get("args") == {}
            and wait_predicate.get("kind") == "measurement-stage"
            and wait_predicate.get("measurement") == KIND
            and wait_predicate.get("stage") == "stale-target-observed"
            and wait_predicate.get("when") in (None, "final")
            and set(wait_predicate) <= {
                "kind", "measurement", "stage", "when"},
            "recipe observation window differs")

    action_ids = {arm["id"], wait["id"], close["id"]}
    saved = [row for row in rows
             if row.get("phase") == "observe"
             and row.get("action") in action_ids]
    require(3 <= len(saved) <= test["budgets"]["maxFrames"] + 2,
            "raw stream is missing or unbounded")
    arm_rows = [row for row in saved
                if row.get("action") == arm["id"]
                and row.get("command") == "condition-controller.arm"]
    wait_rows = [row for row in saved
                 if row.get("action") == wait["id"]
                 and row.get("command") in (None, "wait")]
    close_rows = [row for row in saved
                  if row.get("action") == close["id"]
                  and row.get("command") == "condition-controller.close"]
    require(len(arm_rows) == len(close_rows) == 1
            and 1 <= len(wait_rows) <= test["budgets"]["maxFrames"],
            "raw stream lacks one arm, bounded wait, and close row")

    arm_row, close_row = arm_rows[0], close_rows[0]
    for row, action in ((arm_row, arm), (close_row, close)):
        require(row.get("phase") == "observe"
                and row.get("action") == action["id"],
                "raw row does not name its declared action")
    require(all(row.get("phase") == "observe"
                and row.get("action") == wait["id"]
                for row in wait_rows),
            "wait row does not name its declared action")

    receipt = arm_row.get("receipt", {})
    reader = receipt.get("conditionController", receipt)
    subject = reader.get("subject")
    meter = ConditionControllerMeasurement(
        test, max_frames=test["budgets"]["maxFrames"])
    meter.arm(subject, arm_row["snapshot"], receipt)

    samples = [sample for row in wait_rows
               for sample in row.get("samples", [])]
    require(isinstance(samples, list)
            and test["budgets"]["minObservedFrames"]
                <= len(samples) <= test["budgets"]["maxFrames"],
            "wait row frame count differs")
    by_frame = _events_by_frame([
        event for row in wait_rows for event in row.get("events", [])])
    for snapshot in samples:
        meter.observe(snapshot, by_frame.pop(snapshot.get("frame"), []))
    require(not by_frame, "events exist outside retained completed frames")
    meter.close(close_row["snapshot"], close_row.get("receipt", {}))
    return meter.result()


def measurements(result, record):
    require(result.get("passed") is True
            and result.get("ready") is True
            and result.get("closed") is True
            and result.get("acceptedProof") is False
            and result.get("failures") == [],
            "closed independent replay is missing")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"),
        "closed": True,
        "errors": [],
    }, "private session did not close cleanly")
    values = (
        1,
        sum(item.get("status") == 0 for item in result["evaluations"]),
        len(result["evaluations"]),
        int(result["targetFault"]["bytesWritten"] == 2),
        sum(item["data"].get("event") == "LOGICAL_COMMIT"
            for item in result["traces"]),
        sum(item["data"].get("event") == "CONTROL_RETURNED"
            for item in result["traces"]),
    )
    require(values[1] >= 2 and values[2] >= 3
            and values[3:] == (1, 1, 1),
            "accepted observation counts differ")
    return [{
        "claim": claim,
        "name": name,
        "value": value,
        "operator": "eq",
        "expected": value,
        "passed": True,
    } for (claim, name), value in zip(RULES, values)]


def condition_controller_measurements(test, rows, record, _repo):
    result = replay(test, rows)
    return measurements(result, record), {
        "measurement": result,
        "scope": ("one live Wild caller with one live Follower target; "
                  "no Follower-caller or mounted-target-exclusion credit"),
    }


class ConditionControllerNegative:
    """Change one copied completed-frame identity input for replay controls."""

    def __init__(self, fault):
        require(fault in FAULTS, "unknown condition controller fault")
        self.fault = fault
        self.applied = False

    def mutate(self, row, subjects):
        if self.applied or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {value["handle"]["value"] for value in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is None:
                continue
            if self.fault == "condition-controller-absent-subject":
                sample["actors"].remove(actor)
            else:
                actor["authorityGeneration"] += 1
            self.applied = True
            break
        return changed if self.applied else row


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "condition controller copied control did not fail")
    values = []

    def visit(value):
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result.get("failures", []))
    visit(result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = ("selected handle must name exactly one current active actor"
                if fault.endswith("absent-subject")
                else "selected actor has a stale authorityGeneration")
    require(any(expected in value for value in values),
            "condition controller copied control failed for an unrelated reason")


def copied_control_scope():
    return "copied evaluator controls only; not live reader calibration"
