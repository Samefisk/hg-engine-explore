"""Retained memory replay; the final close wrapper is host-only, not live proof."""
from copy import deepcopy
import unittest

from .devtools_mounted_crash_control_measurement import MountedCrashControlMeasurement
from .devtools_mounted_crash_control_proof import (
    KIND, CONTROL_FAULTS, CrashControlNegative, measurements, validate_negative_result,
)
from .test_devtools_crash_typed_integration import (
    NATURAL, NATURAL_SHA, CONTROL, CONTROL_SHA, load_recording, replay,
)


def retained_control(fault=None):
    snapshots, events = load_recording(NATURAL, NATURAL_SHA)
    post, _ = load_recording(CONTROL, CONTROL_SHA)
    meter = MountedCrashControlMeasurement(600)
    replay(meter.natural, snapshots, events)
    terminal = post[-1]
    receipt = dict(prepared=True, acceptedProof=False, advancedFrames=0,
                   terminalGuard=True, snapshot=deepcopy(terminal),
                   crashFeedback=deepcopy(terminal["crashFeedback"]),
                   calibration=deepcopy(terminal["crashFeedback"]["calibration"]))
    row = dict(command="crash.calibrate", receipt=receipt)
    if fault:
        negative = CrashControlNegative(fault)
        row = negative.mutate(row, {"cyndaquil": meter.subject})
        if not negative.applied:
            raise ValueError("control copied fault did not apply")
    try:
        meter.calibrate(row["receipt"], terminal)
        meter.close(dict(closed=True, advancedFrames=0, acceptedProof=False,
                         snapshot=deepcopy(terminal), crashFeedback=deepcopy(terminal["crashFeedback"])), terminal)
    except ValueError as error:
        meter._failures.append(str(error))
    result = meter.finish()
    return dict(passed=result["passed"], failures=result["failures"], measurements={KIND: result})


class CrashControlProofTests(unittest.TestCase):
    def test_retained_control_maps_exact_rows_without_natural_close(self):
        result = retained_control()
        self.assertTrue(result["passed"], result["failures"])
        self.assertFalse(result["measurements"][KIND]["natural"]["closed"])
        seal = dict(sessionId="host-only", sessionCleanup=dict(sessionId="host-only", closed=True, errors=[]))
        self.assertEqual(len(measurements(result, seal)), 3)
        self.assertFalse(result["measurements"][KIND]["acceptedProof"])

    def test_each_control_mutation_has_its_exact_failure(self):
        for fault in CONTROL_FAULTS:
            with self.subTest(fault=fault):
                validate_negative_result(retained_control(fault), fault)

    def test_missing_session_cleanup_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "private session"):
            measurements(retained_control(), dict(sessionId="host-only"))


if __name__ == "__main__":
    unittest.main()
