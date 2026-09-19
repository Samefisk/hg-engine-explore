"""Synthetic native read controls through the unchanged surface checker."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_spawn_height_control_measurement import (
    LiveSpawnHeightControlMeasurement, HEIGHT_ENVELOPE, EXPECTED_REASON,
)
from tools.overworld.test_devtools_spawn_surface_integration import surface_stream
from tools.overworld.test_devtools_spawn_measurement import SCHEMA, SOURCE, AUTHORED


def control_stream():
    stream = surface_stream()
    for snapshot, events in stream.items:
        if snapshot["frame"] < 2:
            continue
        snapshot["nativeObservation"]["sequence"] += 1
        for event in events:
            data = event["data"]
            if event["kind"] == "native-observation" and data["sequence"] >= 2:
                data["sequence"] += 1
                if data.get("observation") == "spawn-prepared":
                    data["jumpReceipts"][0]["landingHeight"]["sequence"] += 1
    height = next(e["data"] for e in stream.items[1][1]
                  if e["data"].get("observation") == "spawn-landing-height")
    guest_timing = {"scope": "test-envelope", "arm9Ticks": 123}
    height["guestTiming"] = deepcopy(guest_timing)
    spawn = next(e["data"] for _, events in stream.items for e in events
                 if e["data"].get("observation") == "spawn-prepared")
    spawn["jumpReceipts"][0]["landingHeight"]["guestTiming"] = deepcopy(guest_timing)
    clean = {key: deepcopy(value) for key, value in height.items() if key not in HEIGHT_ENVELOPE}
    bad = deepcopy(clean)
    bad["positionAfter"]["pos_y"] += 4096
    data = {"observation": "spawn-height-read-control", "sequence": 2, "setupMode": "normal",
        **{key: height[key] for key in ("entryActorFrame", "entryNativeCycle", "returnActorFrame", "returnNativeCycle")},
        "state": "complete", "scope": "native-observer-control-only", "acceptedProof": False,
        "failure": None, "cleanupPending": False, "delta": 4096, "writes": 2,
        "frame": 1, "nativeCycle": 2, "clean": clean, "bad": bad, "restored": deepcopy(clean)}
    stream.items[1][1].insert(1, {"kind": "native-observation", "frame": 2, "data": data})
    return stream, data


class SpawnHeightControlMeasurementTests(unittest.TestCase):
    def run_stream(self, stream):
        meter = LiveSpawnHeightControlMeasurement(SCHEMA, SOURCE, max_frames=100, authored_profiles=AUTHORED)
        for snapshot, events in stream.items:
            meter.observe(snapshot, events)
        return meter, meter.finish()

    def test_real_checker_detects_only_bad_y_after_full_clean_spawn(self):
        stream, receipt = control_stream()
        before = deepcopy(stream.items)
        meter = LiveSpawnHeightControlMeasurement(SCHEMA, SOURCE, max_frames=100, authored_profiles=AUTHORED)
        for snapshot, events in stream.items[:-1]:
            result = meter.observe(snapshot, events)
            self.assertFalse(result["ready"])
            self.assertEqual(result["detections"], {})
        self.assertTrue(meter.observe(*stream.items[-1])["ready"])
        result = meter.finish()
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["baseline"]["passed"])
        self.assertTrue(result["baseline"]["placement"]["passed"])
        self.assertTrue(result["baseline"]["surface"]["passed"])
        self.assertEqual(result["detections"]["spawn-height-read"]["reason"], EXPECTED_REASON)
        self.assertEqual(result["cleanup"]["receipt"], receipt)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(stream.items, before)

    def test_missing_control_fails_at_first_complete_surface(self):
        _, result = self.run_stream(surface_stream())
        self.assertFalse(result["passed"])
        self.assertTrue(result["baseline"]["passed"])
        self.assertIn("control is missing", str(result["failures"]))

    def test_control_clock_envelope_matches_exact_native_height_callback(self):
        fields = ("entryActorFrame", "entryNativeCycle", "returnActorFrame", "returnNativeCycle")
        for field in ("frame", *fields):
            for fault in ("stale", "future", "missing", "boolean"):
                with self.subTest(field=field, fault=fault):
                    stream, receipt = control_stream()
                    if fault == "stale": receipt[field] -= 1
                    elif fault == "future": receipt[field] += 1
                    elif fault == "missing": del receipt[field]
                    else: receipt[field] = True
                    _, result = self.run_stream(stream)
                    self.assertFalse(result["passed"], {"field": field, "fault": fault})
                    self.assertTrue(result["baseline"]["passed"])
                    self.assertEqual(result["detections"], {})
                    self.assertIn("height read boundary", str(result["failures"]))

    def test_native_control_bad_data_cannot_pass(self):
        for fault in ("unchanged-bad", "wrong-delta", "other-change", "unrestored", "wrong-source",
                      "wrong-world", "wrong-point", "stale-clock", "future-frame", "cleanup-pending",
                      "failure", "writes", "bool-writes", "scope", "accepted", "missing-clean"):
            with self.subTest(fault=fault):
                stream, receipt = control_stream()
                if fault == "unchanged-bad": receipt["bad"] = deepcopy(receipt["clean"])
                elif fault == "wrong-delta": receipt["bad"]["positionAfter"]["pos_y"] += 1
                elif fault == "other-change": receipt["bad"]["positionAfter"]["pos_x"] += 1
                elif fault == "unrestored": receipt["restored"] = deepcopy(receipt["bad"])
                elif fault == "wrong-source":
                    for key in ("clean", "bad", "restored"): receipt[key]["sourceIdentity"]["personality"] += 1
                elif fault == "wrong-world":
                    for key in ("clean", "bad", "restored"): receipt[key]["worldContext"]["fieldEpoch"] += 1
                elif fault == "wrong-point":
                    for key in ("clean", "bad", "restored"): receipt[key]["target"][0] += 1
                elif fault == "stale-clock": receipt["nativeCycle"] = 0
                elif fault == "future-frame": receipt["frame"] = 99
                elif fault == "cleanup-pending": receipt["cleanupPending"] = True
                elif fault == "failure": receipt["failure"] = "restore failed"
                elif fault == "writes": receipt["writes"] = 1
                elif fault == "bool-writes": receipt["writes"] = True
                elif fault == "scope": receipt["scope"] = "normal-play"
                elif fault == "accepted": receipt["acceptedProof"] = True
                elif fault == "missing-clean": del receipt["clean"]
                _, result = self.run_stream(stream)
                self.assertFalse(result["passed"], result)
                self.assertEqual(result["detections"], {})
                self.assertIsNone(result["cleanup"])
                self.assertTrue(result["baseline"]["passed"], result)

    def test_control_cannot_replace_missing_spawn_terminal(self):
        stream, _ = control_stream()
        stream.items.pop()
        _, result = self.run_stream(stream)
        self.assertFalse(result["passed"])
        self.assertFalse(result["baseline"]["passed"])
        self.assertEqual(result["detections"], {})

    def test_missing_surface_meaning_never_counts_as_bad_y_detection(self):
        stream, receipt = control_stream()
        # The bad row is not just a Y fault when another native meaning is lost.
        receipt["bad"]["surfaceQuery"] = None
        _, result = self.run_stream(stream)
        self.assertFalse(result["passed"])
        self.assertIn("change only preparation Y", str(result["failures"]))
        self.assertEqual(result["detections"], {})

    def test_result_is_detached_and_closed_measurement_rejects_more_frames(self):
        stream, _ = control_stream()
        meter, result = self.run_stream(stream)
        result["cleanup"]["receipt"]["restored"]["positionAfter"]["pos_y"] = 999
        self.assertEqual(meter.result()["cleanup"]["receipt"]["restored"]["positionAfter"]["pos_y"], 0)
        with self.assertRaisesRegex(ValueError, "closed"):
            meter.observe(*stream.items[-1])

    def test_duplicate_control_after_detection_is_not_accepted(self):
        stream, receipt = control_stream()
        sample = deepcopy(stream.items[-1][0])
        sample["frame"] += 1; sample["actorFrame"] += 1; sample["nativeCycle"] += 2
        sample["nativeObservation"]["sequence"] += 1
        duplicate = deepcopy(receipt)
        duplicate["sequence"] = sample["nativeObservation"]["sequence"]
        stream.items.append((sample, [{"kind": "native-observation", "frame": sample["frame"], "data": duplicate}]))
        _, result = self.run_stream(stream)
        self.assertFalse(result["passed"])
        self.assertIn("control is duplicated", str(result["failures"]))

    def test_later_identity_loss_is_not_hidden_by_complete_calibration(self):
        stream, _ = control_stream()
        sample = deepcopy(stream.items[-1][0])
        sample["frame"] += 1; sample["actorFrame"] += 1; sample["nativeCycle"] += 2
        sample["actors"][0]["subjectIdentity"] += 1
        stream.items.append((sample, []))
        _, result = self.run_stream(stream)
        self.assertFalse(result["passed"])
        self.assertTrue(result["failures"])
        self.assertFalse(result["baseline"]["passed"])


if __name__ == "__main__":
    unittest.main()
