"""Actual installed queue sampler clock receipts; host-only transport proof."""
from copy import deepcopy
import unittest
from tools.overworld.test_devtools_runtime import CompletedFieldAvailabilityTests


class QueueClockTests(unittest.TestCase):
    def fixture(self):
        helper = CompletedFieldAvailabilityTests()
        self.addCleanup(helper.doCleanups)
        return helper.fixture()

    def test_present_absent_and_retained_receipts_are_detached(self):
        session, memory, boundary, _, _, _ = self.fixture()
        clock = session.emu.guest_clock()
        session.emu.guest_clock = lambda: clock
        boundary()
        self.assertIsNone(session.sample_error)
        first = deepcopy(session.pending_samples[0])
        self.assertEqual(first["guestQueueClock"], clock)
        self.assertIsNot(session.latest_frame["guestQueueClock"], clock)
        clock["arm9Timestamp"] += 100
        clock["arm7Timestamp"] += 50
        clock["frameSequence"] += 1
        memory[0x02001000] = 0
        boundary()
        self.assertIsNone(session.sample_error)
        self.assertEqual(session.pending_samples[0], first)
        self.assertFalse(session.pending_samples[-1]["fieldAvailable"])
        self.assertEqual(session.pending_samples[-1]["guestQueueClock"], clock)
        clock["arm9Timestamp"] += 100
        self.assertNotEqual(session.latest_frame["guestQueueClock"], clock)
        # Endpoint builder cannot label an unobserved time as a queue callback.
        self.assertNotIn("guestQueueClock", session._snapshot(0))

    def test_invalid_clock_fails_before_field_reads_and_stays_latched(self):
        faults = [("version", True), ("version", 2), ("running", False),
                  ("scope", "host-cpu"), ("arm9Timestamp", -1),
                  ("arm7Timestamp", 1 << 64), ("arm7Timestamp", True),
                  ("frameSequence", None), ("frameSequence", 1 << 64)]
        for key, value in faults:
            for absent in (False, True):
                with self.subTest(key=key, value=value, absent=absent):
                    session, memory, boundary, reads, _, _ = self.fixture()
                    clock = session.emu.guest_clock(); clock[key] = value
                    session.emu.guest_clock = lambda: clock
                    if absent: memory[0x02001000] = 0
                    boundary()
                    self.assertIn("guest queue clock", str(session.sample_error))
                    error = session.sample_error
                    self.assertEqual(session.pending_samples, [])
                    self.assertEqual(reads, [])
                    boundary()
                    self.assertIs(session.sample_error, error)

    def test_native_clock_exception_is_not_replaced_with_endpoint(self):
        session, _, boundary, reads, _, _ = self.fixture()
        error = RuntimeError("native clock unavailable")
        def fail(): raise error
        session.emu.guest_clock = fail
        boundary()
        self.assertIs(session.sample_error, error)
        self.assertEqual(session.pending_samples, [])
        self.assertEqual(reads, [])


if __name__ == "__main__": unittest.main()
