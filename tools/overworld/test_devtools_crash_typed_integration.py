"""Typed Crash recipes replay the retained natural and same-reader control data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from . import devtools_crash_test_support as support
from .devtools_mounted_crash_control_measurement import MountedCrashControlMeasurement
from .devtools_test_contract import TestEvaluator, validate_test
from .devtools_test_inputs import measurement_inputs


ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "build/overworld-devtools/session-6sz_20x4"
NATURAL = SESSION / "recording-9c4fc720fd37.json"
NATURAL_SHA = "aa6ccff48bee0f4e2154248f6a205b76594d72d0c07fecbe287b9ee9e7794b1e"
CONTROL = SESSION / "recording-d48e170fa316.json"
CONTROL_SHA = "f29a66c1820b7b4283033a8f6051ac748ecbae0e027a50739f56683fa794b594"


def load_recording(path, expected_sha):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Crash retained fixture hash differs")
    value = json.loads(raw)
    if value.get("truncated") is not False:
        raise ValueError("Crash retained fixture is truncated")
    events = {sample["frame"]: [] for sample in value["snapshots"]}
    for original in value["events"]:
        event = deepcopy(original)
        data = event["data"]
        if data.get("detailsOmitted"):
            artifact = data["artifact"]
            adjacent = path.parent / Path(artifact["path"]).name
            expanded = adjacent.read_bytes()
            if hashlib.sha256(expanded).hexdigest() != artifact["sha256"]:
                raise ValueError("Crash retained event detail hash differs")
            event["data"] = json.loads(expanded)
        events[event["frame"]].append(event)
    return deepcopy(value["snapshots"]), events


def configuration(snapshot, subject, raw_source=None):
    """Host-only receipt fixture with exact native before/after bytes."""
    current = (raw_source or snapshot)["crashFeedback"]["latestCompleted"]
    after_raw = bytes.fromhex(current["mountStateHex"])
    before_raw = bytearray(after_raw)
    before_raw[8 + 65] &= ~0x11
    actor = next(a for a in snapshot["actors"] if a["handle"] == subject["handle"])
    readiness = {"subject": deepcopy(subject), "actor": deepcopy(actor),
                 "snapshot": {k: deepcopy(snapshot[k]) for k in
                              ("frame", "nativeCycle", "actorFrame", "context", "player")}}
    before = dict(readiness=deepcopy(readiness), mountStateHex=bytes(before_raw).hex(),
                  profileHex=bytes(before_raw[8:80]).hex(), bindingHex=bytes(before_raw[80:96]).hex(),
                  sessionGeneration=struct.unpack_from("<I", before_raw, 96)[0],
                  clock={k: snapshot[k] for k in ("frame", "nativeCycle")})
    after = dict(readiness=deepcopy(readiness), mountStateHex=after_raw.hex(),
                 profileHex=after_raw[8:80].hex(), bindingHex=after_raw[80:96].hex(),
                 sessionGeneration=struct.unpack_from("<I", after_raw, 96)[0],
                 clock={k: snapshot[k] for k in ("frame", "nativeCycle")})
    return dict(completed=True, prepared=True, acceptedProof=False, guestAdvanced=False,
                scope="prepared-idle-mounted-walk-fixture", subject=deepcopy(subject),
                directionMode=0, travelTime=None, turning="locked", crashSound="wall-hit",
                changedOffsets=[19, 65], before=before, after=after,
                expectedStateHex=after_raw.hex())


def replay(meter, snapshots, events):
    pending, first = snapshots[0], snapshots[1]
    subject = pending["crashFeedback"]["subject"]
    support.feed_configuration(meter, configuration(pending, subject, first), pending, subject)
    arm = dict(armed=True, prepared=True, advancedFrames=0, acceptedProof=False,
               snapshot=deepcopy(pending), crashFeedback=deepcopy(pending["crashFeedback"]))
    support.feed_command(meter, "crash.arm", arm, pending, subject=subject)
    offset = 1
    for count, keys in ((1, []), (16, ["UP"]), (32, []), (8, ["RIGHT"]), (8, [])):
        chunk = snapshots[offset:offset + count]
        request = dict(op="step", startFrame=snapshots[offset - 1]["frame"],
                       args=dict(frames=count, keys=keys))
        receipt = dict(requestedGameFrames=count, completedGameFrames=count,
                       observedFieldFrames=count)
        support.feed_chunk(meter, request, receipt, chunk,
                           [event for sample in chunk for event in events[sample["frame"]]])
        offset += count
    if offset != len(snapshots):
        raise ValueError("Crash retained replay did not consume every sample")
    return meter


class CrashTypedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.natural, cls.events = load_recording(NATURAL, NATURAL_SHA)
        cls.control, cls.control_events = load_recording(CONTROL, CONTROL_SHA)

    def test_exact_gameplay_and_control_recipes_validate(self):
        for name, kind, requirement in (
                ("walk.crash.feedback", support.KIND, "legacy.crash"),
                ("observation.crash-reader-control", "live-crash-control-v1",
                 "shared.crash-recorder-control-v1")):
            path = ROOT / "tests/overworld/test-recipes" / (name + ".json")
            value = validate_test(json.loads(path.read_text()))
            self.assertEqual(value["measurements"], [{"kind": kind, "subject": "cyndaquil"}])
            self.assertEqual(value["requirements"], [requirement])
            self.assertEqual([a["op"] for a in value["actions"]],
                ["crash.arm", "step", "step", "step", "step", "step",
                 *(["crash.calibrate"] if kind == "live-crash-control-v1" else []), "crash.close"])

    def test_natural_retained_replay_keeps_all_six_legacy_rows(self):
        meter = replay(support.create_meter(support.CONTRACT_INPUT, 600),
                       deepcopy(self.natural), deepcopy(self.events))
        terminal = self.natural[-1]
        close = dict(closed=True, advancedFrames=0, acceptedProof=False,
                     snapshot=deepcopy(terminal),
                     crashFeedback=dict(terminal["crashFeedback"], closed=True))
        support.feed_command(meter, "crash.close", close, terminal)
        result = meter.finish()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["frames"], 64)
        self.assertEqual([(claim, rows[0]["name"])
                          for claim, rows in result["proofEvidence"].items()],
                         list(support.MEASUREMENTS))

    def test_test_evaluator_uses_the_same_retained_raw_path(self):
        path = ROOT / "tests/overworld/test-recipes/walk.crash.feedback.json"
        test = validate_test(json.loads(path.read_text()))
        evaluator = TestEvaluator(test)
        evaluator.install_measurements(measurement_inputs(test, ROOT))
        snapshots, events = deepcopy(self.natural), deepcopy(self.events)
        pending, first = snapshots[0], snapshots[1]
        subject = pending["crashFeedback"]["subject"]
        evaluator.latest = deepcopy(pending)
        evaluator.first_handles = {tuple(a["handle"][k] for k in
            ("value", "slot", "generation", "encounterGeneration", "fieldEpoch", "mapGeneration"))
            for a in pending["actors"] if a.get("active") is True}
        evaluator.subjects["cyndaquil"] = deepcopy(subject)
        configure = {"phase": "setup", "action": "locked-wall-crash",
                     "command": "mount-walk.configure",
                     "receipt": configuration(pending, subject, first), "snapshot": deepcopy(pending)}
        self.assertEqual(evaluator.observe_record(configure)["state"], "running")
        arm = dict(armed=True, prepared=True, advancedFrames=0, acceptedProof=False,
                   snapshot=deepcopy(pending), crashFeedback=deepcopy(pending["crashFeedback"]))
        self.assertEqual(evaluator.observe_record({"phase": "observe", "action": "arm-crash",
            "command": "crash.arm", "receipt": arm, "snapshot": deepcopy(pending)})["state"], "running")
        offset = 1
        windows = (("fresh-neutral-boundary", 1), ("hit-north-wall", 16),
                   ("finish-crash", 32), ("recover-right", 8), ("settle-recovery", 8))
        for action, count in windows:
            chunk = snapshots[offset:offset + count]
            raw_events = [event for sample in chunk for event in events[sample["frame"]]]
            record = dict(phase="observe", action=action, samples=chunk, events=raw_events,
                          requestedGameFrames=count, completedGameFrames=count,
                          observedFieldFrames=count)
            rows = [(sample, events[sample["frame"]], []) for sample in chunk]
            with patch("tools.overworld.devtools_raw_chunk.validate_raw_chunk", return_value=rows):
                report = evaluator.observe_record(record, full_report=False)
            self.assertNotEqual(report["state"], "failed", report)
            offset += count
        terminal = snapshots[-1]
        close = dict(closed=True, advancedFrames=0, acceptedProof=False,
                     snapshot=deepcopy(terminal),
                     crashFeedback=dict(terminal["crashFeedback"], closed=True))
        report = evaluator.observe_record({"phase": "observe", "action": "close-crash",
            "command": "crash.close", "receipt": close, "snapshot": deepcopy(terminal)})
        self.assertNotEqual(report["state"], "failed", report)
        result = evaluator.finish()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["measurements"][support.KIND]["frames"], 64)

    def test_postcontrol_is_terminal_same_boundary_not_gameplay(self):
        meter = MountedCrashControlMeasurement(600)
        replay(meter.natural, deepcopy(self.natural), deepcopy(self.events))
        post = deepcopy(self.control[-1])
        receipt = dict(prepared=True, acceptedProof=False, advancedFrames=0,
                       terminalGuard=True, snapshot=deepcopy(post),
                       crashFeedback=deepcopy(post["crashFeedback"]),
                       calibration=deepcopy(post["crashFeedback"]["calibration"]))
        result = meter.calibrate(receipt, post)
        self.assertTrue(result["ready"], result)
        self.assertEqual(result["frames"], 64)
        self.assertEqual(result["natural"]["terminalSnapshot"]["frame"], 848)
        close = dict(closed=True, advancedFrames=0, acceptedProof=False,
                     snapshot=deepcopy(post), crashFeedback=deepcopy(post["crashFeedback"]))
        meter.close(close, post)
        self.assertTrue(meter.finish()["passed"])

    def test_fixture_rejects_timing_or_acceleration_changes(self):
        snapshot = deepcopy(self.natural[1])
        subject = snapshot["crashFeedback"]["subject"]
        for field, value in (("travelTime", 8), ("changedOffsets", [7, 19, 50, 51, 65])):
            meter = support.create_meter(support.CONTRACT_INPUT, 600)
            receipt = configuration(snapshot, subject)
            receipt[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "fixed lane fixture"):
                support.feed_configuration(meter, receipt, snapshot, subject)


if __name__ == "__main__":
    unittest.main()
