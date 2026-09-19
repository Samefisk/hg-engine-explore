"""Original 65-motion proof mapping and copied-data evaluator controls.

These controls change retained host data, never the guest or the native reader.
Only a complete independent stream replay can supply controller measurements.
"""
from copy import deepcopy
from pathlib import Path
import struct

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_contract import CASES, validate_matrix

KIND = "mounted-frame-matrix-v1"
REQUIREMENT = "legacy.mounted-frames"
RULES = (
    ("natural-input", "started-motion-count", 65),
    ("live-actor-identity", "mounted-frames-cyndaquil-identity", [1, "MOUNTED", 155, 1]),
    ("profile-resolution", "resolved-frame-counts", None),
    ("frame-pacing", "elapsed-frame-sequences", None),
    ("control-release", "completed-motion-count", 65),
    ("control-release", "terminal-mount-state", ["IDLE", 0]),
)
CLAIMS = tuple(dict.fromkeys(row[0] for row in RULES))
MEANINGS = {"matrix-missing-start": "MOTION_STARTED", "matrix-missing-commit": "LOGICAL_COMMIT",
            "matrix-missing-finish": "MOTION_FINISHED", "matrix-missing-return": "CONTROL_RETURNED"}
FAULTS = ("matrix-absent-subject", "matrix-stale-subject", "matrix-bad-raw-elapsed",
          "matrix-bad-sample", "matrix-missing-tick", "matrix-duplicate-tick", "matrix-reservation",
          "matrix-clock", "matrix-profile", "matrix-input", "matrix-canceled", *MEANINGS,
          "matrix-gate-moved", "matrix-missing-final-motion")


def need(value, reason):
    if not value:
        raise ValueError(reason)


def contract():
    result = {}
    for claim, name, expected in RULES:
        row = dict(name=name, operator="eq", type="array" if isinstance(expected, list) else "integer",
                   validator="meaningful-observation")
        if expected is None:
            aspect = "counts" if claim == "profile-resolution" else "elapsed"
            row.update(type="object", validator=KIND, aspect=aspect,
                       requiredKeys=["durations", "elapsedCounts", "diagonalAttempt"]
                       if aspect == "counts" else ["durations", "sequences"])
        else:
            row["expected"] = deepcopy(expected)
        result.setdefault(claim, []).append(row)
    return result


def measurements(replay, record):
    value = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and all(value.get(k) is True for k in ("passed", "ready", "closed"))
         and value.get("acceptedProof") is False and value.get("failures") == [],
         "Walk matrix lacks closed independent replay")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "Walk matrix private session did not close cleanly")
    need(value.get("prefixOnly") is False and value.get("expectedCases") == 65,
         "Walk matrix prefix is not the complete requirement")
    matrix = validate_matrix(value["cases"], value["diagonalAttempt"])
    initial, subject = value["initial"], value["subject"]
    selected = select_current_actor(initial, subject)
    actor = next(a for a in initial["actors"] if a["handle"] == selected["handle"])
    identity = [int(actor.get("identityVerified") is True), actor["role"], actor["species"],
                int(actor.get("presentationAttached") is True)]
    terminal_snapshot = value["terminalSnapshot"]
    selected_end = select_current_actor(terminal_snapshot, subject)
    end = next(a for a in terminal_snapshot["actors"] if a["handle"] == selected_end["handle"])
    need(end.get("motionPhase") == "IDLE" and end.get("motionKind") == "NONE"
         and end.get("reservationId") == 0, "Walk matrix terminal actor is not released")
    configurations = value["configurations"]
    need(len(configurations) == 65, "Walk matrix configuration count differs")
    previous = None
    for case, config in zip(CASES, configurations):
        profile, before = bytes.fromhex(config["profileHex"]), bytes.fromhex(config["beforeProfileHex"])
        need(config.get("caseIndex") == case["index"] and len(profile) == len(before) == 72
             and config.get("changedOffsets") == [7, 19, 50, 51], "Walk matrix configuration shape differs")
        expected = bytearray(before)
        for offset, actual in ((7, case["duration"]), (19, case["mode"]), (50, 0), (51, case["duration"])):
            expected[offset] = actual
        need(profile == bytes(expected) and (previous is None or before == previous),
             "Walk matrix configuration profile differs")
        need(config.get("bindingHex") == configurations[0].get("bindingHex")
             and config.get("sessionGeneration") == configurations[0].get("sessionGeneration"),
             "Walk matrix configuration owner differs")
        previous = profile
    need(all(motion["subject"] == subject for motion in value["cases"]), "Walk matrix case subject differs")
    need(value.get("completedCases") == 65 and value.get("startedMotions") == 65
         and value.get("completedMotions") == 65, "Walk matrix original motion count differs")
    terminal = value["terminal"]
    actuals = [65, identity, matrix["counts"], matrix["elapsed"], 65,
               [terminal.get("phase"), terminal.get("pending")]]
    result = []
    for (claim, name, expected), actual in zip(RULES, actuals):
        need(expected is None or actual == expected, "Walk matrix original metric differs: " + name)
        summary = [r for r in value["proofEvidence"].get(claim, []) if r.get("name") == name]
        need(len(summary) == 1 and summary[0].get("actual") == actual,
             "Walk matrix metric summary differs: " + name)
        result.append(dict(claim=claim, name=name, value=actual, expected=deepcopy(actual),
                           operator="eq", passed=True))
    return result


def replay_records(test, rows, *, repo=None, fault=None):
    """Replay artifact-expanded raw records through the same checked evaluator."""
    from tools.overworld.devtools_test_contract import TestEvaluator
    from tools.overworld.devtools_test_inputs import measurement_inputs
    evaluator = TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(test, repo or Path(__file__).resolve().parents[2]))
    need(KIND in evaluator.measurements, "Walk matrix replay needs exact typed measurement")
    negative = MatrixNegative(fault) if fault else None
    for row in rows:
        value = negative.mutate(row, evaluator.subjects) if negative else row
        report = evaluator.observe_record(value, full_report=False)
        if report["state"] == "failed":
            break
    result = evaluator.finish()
    if negative:
        need(negative.applied, "Walk matrix copied control had no matching raw observation")
    return result


class MatrixNegative:
    """One named wrong-data control against actual retained stream records."""
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Walk matrix copied fault")
        self.fault, self.applied = fault, False
        self.configuration_count = 0
        self.final_motion = False

    def mutate(self, row, subjects):
        if self.applied and self.fault != "matrix-missing-final-motion":
            return row
        changed = deepcopy(row)
        if row.get("command") == "mount-walk.configure":
            self.configuration_count += 1
            if self.fault == "matrix-profile":
                receipt = changed.get("receipt", {})
                receipt = receipt.get("value", receipt)
                after = receipt.get("after", {})
                if "profileHex" in after:
                    raw = bytearray.fromhex(after["profileHex"])
                    raw[7] = 32 if raw[7] != 32 else 31
                    after["profileHex"] = raw.hex()
                    self.applied = True
                    return changed
        if row.get("phase") != "observe" or not subjects:
            return row
        handles = {s["handle"]["value"] for s in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((a for a in sample.get("actors", []) if a.get("handle", {}).get("value") in handles), None)
            if actor is None:
                continue
            if self.fault == "matrix-absent-subject":
                sample["actors"].remove(actor)
                self.applied = True
            elif self.fault == "matrix-stale-subject":
                actor["authorityGeneration"] += 1
                self.applied = True
            elif self.fault == "matrix-gate-moved" and self.configuration_count == 65 \
                    and sample.get("selector", {}).get("heldKeys") == 32:
                actor["logical"]["x"] += 1
                self.applied = True
            if self.applied:
                return changed
        events = changed.get("events", [])
        for index, event in enumerate(events):
            data = event.get("data", {})
            owned = data.get("actorHandle") in handles
            tick = data.get("observation") == "walk-matrix-tick" and data.get("movingWalk") is True
            if self.fault == "matrix-missing-final-motion" and self.configuration_count == 65:
                if owned and data.get("event") == "MOTION_STARTED":
                    self.final_motion = True
                if self.final_motion and (owned or tick):
                    self.applied = True
                    continue
            if self.fault in MEANINGS and owned and data.get("event") == MEANINGS[self.fault]:
                data["event"] = "WORLD_EFFECT"
                self.applied = True
            elif self.fault == "matrix-canceled" and owned and data.get("event") == "MOTION_STARTED":
                data["event"] = "MOTION_CANCELED"
                self.applied = True
            elif tick:
                if self.fault == "matrix-bad-raw-elapsed":
                    raw = bytearray.fromhex(data["before"]["rawHex"])
                    struct.pack_into("<H", raw, 40, data["before"]["elapsed"] + 1)
                    data["before"]["rawHex"] = raw.hex()
                elif self.fault == "matrix-bad-sample":
                    raw = bytearray.fromhex(data["sample"]["rawHex"])
                    struct.pack_into("<H", raw, 24, data["sample"]["elapsed"] + 1)
                    data["sample"]["rawHex"] = raw.hex()
                elif self.fault == "matrix-missing-tick":
                    events.pop(index)
                elif self.fault == "matrix-duplicate-tick":
                    events.insert(index, deepcopy(event))
                elif self.fault == "matrix-reservation":
                    for endpoint in ("before", "after"):
                        state = data[endpoint]
                        state["plan"]["reservationId"] += 1
                        raw = bytearray.fromhex(state["rawHex"])
                        struct.pack_into("<H", raw, 26, state["plan"]["reservationId"])
                        state["rawHex"] = raw.hex()
                elif self.fault == "matrix-clock":
                    data["returnClock"]["actorFrame"] += 1
                elif self.fault == "matrix-input":
                    data["input"]["heldKeys"] = data["input"]["rawHeld"] = 128
                else:
                    continue
                self.applied = True
            if self.applied and self.fault != "matrix-missing-final-motion":
                break
        if self.fault == "matrix-missing-final-motion" and self.applied:
            changed["events"] = [e for e in events if not (
                e.get("data", {}).get("actorHandle") in handles or
                e.get("data", {}).get("observation") == "walk-matrix-tick")]
        return changed if self.applied else row


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False, "Walk matrix copied control did not fail")
    failures = result.get("failures", []) + result.get("measurements", {}).get(KIND, {}).get("failures", [])
    reasons = set()
    for failure in failures:
        if isinstance(failure, str):
            reasons.add(failure)
        elif isinstance(failure, dict):
            reasons.update(failure[k] for k in ("detail", "message") if isinstance(failure.get(k), str))
    expected = {
        "matrix-absent-subject": {"selected handle must name exactly one current active actor"},
        "matrix-stale-subject": {"selected actor has a stale authorityGeneration"},
        "matrix-bad-raw-elapsed": {"matrix raw Tick bytes differ"},
        "matrix-bad-sample": {"matrix raw Tick bytes differ"},
        "matrix-missing-tick": {"matrix native sequence gap", "matrix missing native observation"},
        "matrix-duplicate-tick": {"matrix native sequence gap"},
        "matrix-reservation": {"matrix reservation changed"},
        "matrix-clock": {"matrix Tick return or clock differs"},
        "matrix-profile": {"matrix configure changed unrelated state"},
        "matrix-input": {"matrix native tick input differs"},
        "matrix-canceled": {"matrix canceled or rebound"},
        "matrix-gate-moved": {"matrix cardinal gate moved"},
        "matrix-missing-final-motion": {"matrix native sequence gap", "matrix missing native observation",
                                        "native event sequence is missing, duplicated, or reordered"},
    }
    for name, meaning in MEANINGS.items():
        expected[name] = {"Walk matrix: lifecycle count differs", "matrix exact lifecycle missing: " + meaning}
    need(bool(reasons & expected[fault]), "Walk matrix copied control failed for unrelated reason: " + fault)
