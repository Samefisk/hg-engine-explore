"""Exact legacy.crash proof rows and copied-stream evaluator controls.

The gameplay result must come from the typed shared-test evaluator.  These
controls alter copied host records only; the separate live Crash reader
control remains required for controller acceptance.
"""
from copy import deepcopy
from pathlib import Path

from tools.overworld.devtools_mounted_crash_measurement import KIND


REQUIREMENT = "legacy.crash"
RULES = (
    ("natural-input", {
        "name": "crash-held-input-hit-frame", "operator": "gt", "type": "integer",
        "validator": "meaningful-observation", "minimum": 1,
    }),
    ("live-actor-identity", {
        "name": "crash-cyndaquil-identity-flags", "operator": "eq", "type": "array",
        "validator": "meaningful-observation", "expected": [1, "MOUNTED", 155, 1, 1],
    }),
    ("engine-boundary", {
        "name": "single-stationary-crash", "operator": "eq", "type": "array",
        "validator": "stationary-single-crash-v1",
    }),
    ("frame-pacing", {
        "name": "crash-presentation-elapsed-schedule", "operator": "eq", "type": "array",
        "validator": "meaningful-observation", "expected": list(range(1, 33)),
    }),
    ("feedback-effect", {
        "name": "crash-sound-and-shake", "operator": "eq", "type": "array",
        "validator": "meaningful-observation", "expected": [1, 1],
    }),
    ("control-release", {
        "name": "crash-reset-and-recovery-state", "operator": "eq", "type": "array",
        "validator": "meaningful-observation", "expected": ["IDLE", 0, 1, 0, 1],
    }),
)
CLAIMS = tuple(dict.fromkeys(claim for claim, _ in RULES))
MEANINGS = {
    "crash-missing-start": "MOTION_STARTED",
    "crash-missing-commit": "LOGICAL_COMMIT",
    "crash-missing-finish": "MOTION_FINISHED",
    "crash-missing-return": "CONTROL_RETURNED",
}
FAULTS = (
    "crash-wrong-subject", "crash-stale-generation", "crash-input",
    "crash-native-counts", "crash-sound", "crash-presentation", "crash-state",
    *MEANINGS,
)
EXPECTED_COUNTS = {
    "start": 1, "update": 33, "presentation": 32, "finish": 1,
    "crashSound": 1, "sound": 1, "soundStart": 1,
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def contract():
    """Return the six registry rows without weakening or normalizing them."""
    result = {}
    for claim, specification in RULES:
        result.setdefault(claim, []).append(deepcopy(specification))
    return result


def _actuals(value):
    evidence = value.get("proofEvidence")
    need(isinstance(evidence, dict) and tuple(evidence) == CLAIMS,
         "Crash proof evidence claim set differs")
    actuals = []
    for claim, specification in RULES:
        rows = evidence.get(claim)
        need(isinstance(rows, list) and len(rows) == 1
             and rows[0].get("name") == specification["name"]
             and set(rows[0]) == {"name", "actual"},
             "Crash metric summary differs: " + specification["name"])
        actuals.append(deepcopy(rows[0]["actual"]))
    return actuals


def measurements(replay, record):
    value = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and all(value.get(key) is True for key in ("passed", "ready", "closed"))
         and value.get("acceptedProof") is False and value.get("failures") == [],
         "Crash lacks closed independent typed replay")
    need(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": []},
        "Crash private session did not close cleanly")
    return validate_baseline(value)


def validate_baseline(value):
    """Validate completed gameplay; terminal reader closure is the caller's gate."""
    need(value.get("ready") is True and value.get("acceptedProof") is False
         and value.get("failures") == [], "Crash baseline is incomplete")
    subject = value.get("subject")
    handle = subject.get("handle", {}) if isinstance(subject, dict) else {}
    need(isinstance(subject, dict) and subject.get("species") == 155
         and subject.get("role") == "MOUNTED" and subject.get("identityVerified") is True
         and all(type(handle.get(key)) is int and handle[key] > 0 for key in
                 ("value", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")),
         "Crash bound mounted Cyndaquil identity differs")
    need(value.get("stage") == "recovered" and value.get("frames") == 64
         and value.get("counts") == EXPECTED_COUNTS
         and type(value.get("restoredFrame")) is int,
         "Crash complete window, native counts or restoration differs")

    actuals = _actuals(value)
    hit, identity, stationary, elapsed, feedback, release = actuals
    need(type(hit) is int and hit > 1, "Crash held-input hit frame differs")
    need(identity == [1, "MOUNTED", 155, 1, 1], "Crash identity metric differs")
    need(isinstance(stationary, list) and len(stationary) == 3 and stationary[0] == 1
         and isinstance(stationary[1], list) and len(stationary[1]) == 4
         and all(type(item) is int for item in stationary[1])
         and stationary[1] == stationary[2], "Crash stationary metric differs")
    need(elapsed == list(range(1, 33)), "Crash elapsed metric differs")
    need(feedback == [1, 1], "Crash feedback metric differs")
    need(release == ["IDLE", 0, 1, 0, 1], "Crash release metric differs")

    rows = []
    for (claim, specification), actual in zip(RULES, actuals):
        expected = specification.get("expected", specification.get("minimum", actual))
        rows.append({"claim": claim, "name": specification["name"], "value": actual,
                     "expected": deepcopy(expected), "operator": specification["operator"],
                     "passed": True})
    return rows


def replay_records(test, rows, *, repo=None, fault=None):
    """Replay artifact-expanded rows through the actual typed job evaluator."""
    from tools.overworld.devtools_test_contract import TestEvaluator
    from tools.overworld.devtools_test_inputs import measurement_inputs
    evaluator = TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(
        test, repo or Path(__file__).resolve().parents[2]))
    need(KIND in evaluator.measurements, "Crash replay needs exact typed measurement")
    negative = MountedCrashNegative(fault) if fault else None
    for row in rows:
        value = negative.mutate(row, evaluator.subjects) if negative else row
        report = evaluator.observe_record(value, full_report=False)
        if report["state"] == "failed":
            break
    result = evaluator.finish()
    if negative:
        need(negative.applied, "Crash copied control had no matching raw observation")
    return result


class MountedCrashNegative:
    """Apply one named fault to a copied raw observation, once."""
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Crash copied fault")
        self.fault, self.applied = fault, False
        self.restored_frame = None
        self.preserved_bootstrap = False

    def mutate(self, row, subjects):
        if self.applied or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is None:
                continue
            if self.fault in ("crash-stale-generation", "crash-input",
                              "crash-native-counts") and not self.preserved_bootstrap:
                # The first neutral queue proves that Crash armed the same
                # bound actor. Change the first real trigger sample so copied
                # controls test the named runtime fact, not bootstrap.
                self.preserved_bootstrap = True
                return row
            if self.fault == "crash-stale-generation":
                actor["authorityGeneration"] += 1
            elif self.fault == "crash-input":
                sample["selector"]["heldKeys"] = sample["selector"]["rawHeld"] = 128
            elif self.fault == "crash-native-counts":
                sample["crashFeedback"]["counts"]["presentation"] += 1
            else:
                continue
            self.applied = True
            return changed

        for event in changed.get("events", []):
            data = event.get("data", {})
            observation = data.get("observation", "")
            if observation == "mounted-crash-update" and data.get("before", {}).get("mode") == 3 \
                    and data.get("before", {}).get("elapsed") == 32 \
                    and data.get("after", {}).get("mode") == 0:
                self.restored_frame = event["frame"]
            if self.fault in MEANINGS and self.restored_frame is not None \
                    and event["frame"] > self.restored_frame and data.get("actorHandle") in handles \
                    and data.get("event") == MEANINGS[self.fault]:
                data["event"] = "WORLD_EFFECT"
            elif self.fault == "crash-wrong-subject" \
                    and observation.startswith("mounted-crash-"):
                current = data.get("before", {}).get("current", {})
                subject = current.get("subject")
                if not isinstance(subject, dict) or not isinstance(subject.get("handle"), dict):
                    continue
                subject["handle"]["value"] += 1
            elif self.fault == "crash-sound" and observation == "mounted-crash-sound":
                data["args"][0] = 2183
            elif self.fault == "crash-presentation" \
                    and observation == "mounted-crash-presentation":
                data["after"]["pose"]["mount"]["face_z"] += 1
            elif self.fault == "crash-state" \
                    and observation == "mounted-crash-presentation":
                data["after"]["elapsed"] += 1
            else:
                continue
            self.applied = True
            return changed
        return row


# Keep the short adapter-table name while retaining the feature-specific API.
CrashNegative = MountedCrashNegative


def _failure_text(result):
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
    return strings


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False,
         "Crash copied control did not fail")
    expected = {
        "crash-wrong-subject": "native subject differs",
        "crash-stale-generation": "stale authorityGeneration",
        "crash-input": "held keys differ from normal command",
        "crash-native-counts": "reader coverage/counts differ",
        "crash-sound": "wrong crash sound ID",
        "crash-presentation": "sound/shake displacement differs",
        "crash-state": "presentation elapsed schedule differs",
        "crash-missing-start": "recovery lifecycle differs",
        "crash-missing-commit": "recovery lifecycle differs",
        "crash-missing-finish": "recovery lifecycle differs",
        "crash-missing-return": (
            "incomplete crash/restoration/recovery",
            "requires complete natural crash and recovery",
        ),
    }[fault]
    expected = (expected,) if isinstance(expected, str) else expected
    need(any(fragment in text for fragment in expected for text in _failure_text(result)),
         "Crash copied control failed for unrelated reason: " + fault)
