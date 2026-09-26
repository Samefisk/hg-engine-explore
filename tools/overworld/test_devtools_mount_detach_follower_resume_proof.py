import unittest

from tools.overworld.devtools_mount_detach_follower_resume import (
    MountDetachFollowerResumeMeasurement,
)
from tools.overworld.devtools_mount_detach_follower_resume_proof import (
    FAULTS, MountDetachFollowerResumeNegative, contract, measurements,
    validate_negative_result,
)
from tools.overworld.test_devtools_mount_detach_follower_resume import (
    DetachResumeFixture, completed_meter,
)


class MountDetachFollowerResumeProofTests(unittest.TestCase):
    def test_rows_are_recomputed_from_complete_motion(self):
        meter, _ = completed_meter()
        replay = {"passed": True, "failures": [], "measurements": {
            "mount-detach-follower-resume-v1": meter,
        }}
        record = {"sessionId": "test", "sessionCleanup": {
            "sessionId": "test", "closed": True, "errors": [],
        }}
        rows = measurements(replay, record)
        self.assertEqual(len(rows), sum(map(len, contract().values())))
        self.assertTrue(all(row["passed"] for row in rows))

    def test_each_copied_data_control_fails_for_its_named_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                fixture = DetachResumeFixture()
                meter = MountDetachFollowerResumeMeasurement()
                meter.arm(fixture.subject, fixture.snapshot)
                negative = MountDetachFollowerResumeNegative(fault)
                for snapshot, events in (*fixture.detach(),
                                         *fixture.separate_and_walk()):
                    row = negative.mutate({
                        "phase": "observe", "samples": [snapshot],
                        "events": events,
                    }, {"cyndaquil": fixture.subject})
                    meter.observe(row["samples"][0], row["events"])
                result = meter.finish()
                self.assertTrue(negative.applied)
                validate_negative_result(result, fault)

    def test_unrelated_failure_is_not_a_negative_pass(self):
        with self.assertRaisesRegex(ValueError, "unrelated reason"):
            validate_negative_result(
                {"passed": False, "failures": ["different failure"]},
                FAULTS[0],
            )


if __name__ == "__main__":
    unittest.main()
