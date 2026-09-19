"""A declared trace stream at sequence zero has emitted no missing events."""
from copy import deepcopy
import unittest

from tools.overworld.test_devtools_walk_policy_control_measurement import fixture, replay


def empty_stream_case(sequence=0):
    test, rows = fixture()
    action = dict(id="prepare", op="teleport", args=dict(map=34, x=0, z=0, facing=0),
                  budget=dict(maxSeconds=10, maxFrames=10, noProgressFrames=10))
    test["setup"].insert(0, action)
    snapshot = deepcopy(rows[0]["initialSnapshot"])
    snapshot["prepared"] = True
    rows[1]["snapshot"]["prepared"] = True
    receipt = dict(preparedOnly=True, snapshot=deepcopy(snapshot), events=[],
        setupBoundary=dict(eventsDrained=True, traceSequences={"1": sequence}, frame=snapshot["frame"],
                           nativeCycle=snapshot["nativeCycle"], endpointNativeCycle=snapshot["nativeCycle"]))
    rows.insert(1, dict(phase="setup", action="prepare", command="teleport", snapshot=snapshot, receipt=receipt))
    return test, rows


class EmptyTraceBoundaryTests(unittest.TestCase):
    def test_zero_stream_keeps_complete_motion_and_no_setup_credit(self):
        test, rows = empty_stream_case()
        result = replay(test, rows).finish()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["observedFrames"], 10)

    def test_missing_positive_sequence_and_invalid_values_still_fail(self):
        for sequence in (1, -1, True, "0", 0x100000000):
            test, rows = empty_stream_case(sequence)
            with self.subTest(sequence=sequence):
                self.assertTrue(replay(test, rows).failures)

    def test_invalid_stream_names_cannot_hide_behind_zero(self):
        for stream in ("0", "01", "-1", "1.0", "١", "1000001", "4294967296", "", 1):
            test, rows = empty_stream_case()
            rows[1]["receipt"]["setupBoundary"]["traceSequences"] = {stream: 0}
            with self.subTest(stream=stream):
                self.assertTrue(replay(test, rows).failures)


if __name__ == "__main__":
    unittest.main()
