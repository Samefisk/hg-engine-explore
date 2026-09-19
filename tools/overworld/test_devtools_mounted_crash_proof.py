"""Host-only checks for the mounted Crash proof adapter."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_crash_proof import (
    CLAIMS, FAULTS, KIND, REQUIREMENT, RULES, CrashNegative,
    MountedCrashNegative, contract, measurements,
    validate_negative_result,
)
from tools.overworld.devtools_mounted_crash_measurement import MountedCrashMeasurement


ROOT = Path(__file__).resolve().parents[2]
RECORDING = ROOT / "build/overworld-devtools/session-6sz_20x4/recording-9c4fc720fd37.json"
RECORDING_SHA = "aa6ccff48bee0f4e2154248f6a205b76594d72d0c07fecbe287b9ee9e7794b1e"


def _recording():
    raw = RECORDING.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECORDING_SHA:
        raise ValueError("retained natural Crash recording hash differs")
    value = json.loads(raw)
    if value.get("truncated") is not False:
        raise ValueError("retained natural Crash recording is truncated")
    events = []
    for event in value["events"]:
        event = deepcopy(event)
        artifact = event.get("data", {}).get("artifact")
        if event.get("data", {}).get("detailsOmitted"):
            path = RECORDING.parent / Path(artifact["path"]).name
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != artifact["sha256"]:
                raise ValueError("retained Crash event hash differs")
            event["data"] = json.loads(payload)
        events.append(event)
    return value, events


def actual_replay(fault=None):
    """Replay every actual measured frame through the unchanged pure meter.

    The saved recording begins at the arm boundary and includes the fresh
    neutral completed queue. Only the final zero-advance close is a host
    lifecycle fixture. The result remains acceptedProof:false.
    """
    recording, all_events = _recording()
    snapshots = {sample["frame"]: deepcopy(sample) for sample in recording["snapshots"]}
    events = {frame: [] for frame in snapshots}
    for event in all_events:
        if event["kind"] in ("native", "native-observation"):
            events[event["frame"]].append(deepcopy(event))
    meter = MountedCrashMeasurement(120)
    initial = snapshots[784]
    subject = initial["crashFeedback"]["subject"]
    meter.arm(subject, initial, initial["crashFeedback"])
    negative = MountedCrashNegative(fault) if fault else None
    start = 784
    for count, keys in ((16, ["UP"]), (32, []), (8, ["RIGHT"]), (8, [])):
        meter.command({"op": "step", "startFrame": start,
                       "args": {"frames": count, "keys": keys}},
                      {"requestedGameFrames": count, "completedGameFrames": count,
                       "observedFieldFrames": count})
        for frame in range(start + 1, start + count + 1):
            row = {"phase": "observe", "samples": [snapshots[frame]],
                   "events": events[frame]}
            if negative:
                row = negative.mutate(row, {"cyndaquil": subject})
            meter.observe(row["samples"][0], row["events"])
            if meter.failures:
                break
        start += count
        if meter.failures:
            break
    if not meter.failures and meter.ready:
        terminal = snapshots[848]
        meter.close({"closed": True, "advancedFrames": 0, "acceptedProof": False,
                     "snapshot": deepcopy(terminal),
                     "crashFeedback": {**deepcopy(terminal["crashFeedback"]), "closed": True}},
                    terminal)
    result = meter.finish()
    if negative and not negative.applied:
        raise ValueError("Crash copied control had no matching raw observation")
    return {"passed": result["passed"], "acceptedProof": False,
            "failures": deepcopy(result["failures"]), "measurements": {KIND: result}}


class MountedCrashProofTests(unittest.TestCase):
    def test_contract_is_verbatim_registry_mapping(self):
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(REQUIREMENT, "legacy.crash")
        self.assertEqual(list(CLAIMS), registry["runners"][REQUIREMENT])
        self.assertEqual(contract(), registry["measurementContracts"][REQUIREMENT])
        self.assertEqual(len(RULES), 6)
        self.assertIs(CrashNegative, MountedCrashNegative)

    def test_hash_checked_actual_stream_replays_through_typed_evaluator(self):
        replay = actual_replay()
        self.assertTrue(replay["passed"], replay["failures"])
        self.assertFalse(replay["measurements"][KIND]["acceptedProof"])
        record = {"sessionId": "retained-host", "sessionCleanup": {
            "sessionId": "retained-host", "closed": True, "errors": []}}
        measured = measurements(replay, record)
        self.assertEqual(len(measured), 6)
        self.assertEqual([(row["claim"], row["name"]) for row in measured],
                         [(claim, spec["name"]) for claim, spec in RULES])

    def test_all_copied_faults_fail_for_the_named_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                failed = actual_replay(fault)
                validate_negative_result(failed, fault)

    def test_summary_and_cleanup_are_fail_closed(self):
        replay = actual_replay()
        record = {"sessionId": "retained-host", "sessionCleanup": {
            "sessionId": "retained-host", "closed": True, "errors": []}}
        for fault in ("summary", "claim", "counts", "cleanup"):
            changed, seal = deepcopy(replay), deepcopy(record)
            meter = changed["measurements"][KIND]
            if fault == "summary":
                meter["proofEvidence"]["feedback-effect"][0]["actual"] = [1, 0]
            elif fault == "claim":
                meter["proofEvidence"]["other"] = []
            elif fault == "counts":
                meter["counts"]["presentation"] = 31
            else:
                seal["sessionCleanup"]["closed"] = False
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                measurements(changed, seal)

    def test_missing_match_and_unrelated_failure_are_not_controls(self):
        for fault in FAULTS:
            negative = MountedCrashNegative(fault)
            row = {"phase": "observe", "samples": [], "events": []}
            self.assertIs(negative.mutate(row, {}), row)
            self.assertFalse(negative.applied)
            with self.assertRaisesRegex(ValueError, "unrelated"):
                validate_negative_result({"passed": False, "failures": ["generic failure"]}, fault)


if __name__ == "__main__":
    unittest.main()
