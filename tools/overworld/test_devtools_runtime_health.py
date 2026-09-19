"""Pure host checks; no emulator or game proof."""
import unittest

from tools.overworld.devtools_runtime_health import RuntimeHealthFailure, RuntimeHealthMonitor


class RuntimeHealthTests(unittest.TestCase):
    def test_frozen_queue_fails_at_exact_120_cycle_boundary_across_calls(self):
        monitor = RuntimeHealthMonitor(20, 1000)
        for cycle in range(1001, 1120):
            monitor.observe(cycle, 20, 0x1F)
        with self.assertRaises(RuntimeHealthFailure) as caught:
            monitor.observe(1120, 20, 0x1F)
        self.assertEqual(caught.exception.code, "main-queue-stalled")
        self.assertEqual(caught.exception.details["nativeCyclesWithoutProgress"], 120)
        self.assertEqual(caught.exception.details["lastProgressNativeCycle"], 1000)

    def test_abort_and_undefined_fail_first_cycle_even_with_queue_progress(self):
        for mode, code in ((0x17, "arm9-abort"), (0x1B, "arm9-undefined")):
            with self.subTest(mode=mode):
                monitor = RuntimeHealthMonitor(10, 200)
                with self.assertRaises(RuntimeHealthFailure) as caught:
                    monitor.observe(201, 11, 0x80000000 | mode)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.details["mode"], mode)
                self.assertEqual(caught.exception.details["completedFrame"], 11)

    def test_normal_two_cycles_per_frame_allows_non_fault_modes(self):
        monitor = RuntimeHealthMonitor(0, 0)
        modes = (0x10, 0x11, 0x12, 0x13, 0x1F)
        for cycle in range(1, 10001):
            monitor.observe(cycle, cycle // 2, modes[cycle % len(modes)])

    def test_host_pause_and_duplicate_sample_do_not_spend_cycle_budget(self):
        monitor = RuntimeHealthMonitor(0, 0)
        for _ in range(1000):
            monitor.observe(0, 0, 0x1F)
        monitor.observe(119, 0, 0x1F)
        for _ in range(1000):
            monitor.observe(119, 0, 0x1F)
        monitor.observe(120, 1, 0x1F)

    def test_progress_resets_deadline_but_not_each_observe_call(self):
        monitor = RuntimeHealthMonitor(0, 0)
        monitor.observe(119, 1, 0x1F)
        monitor.observe(238, 1, 0x1F)
        with self.assertRaises(RuntimeHealthFailure) as caught:
            monitor.observe(239, 1, 0x1F)
        self.assertEqual(caught.exception.details["lastProgressNativeCycle"], 119)

    def test_counter_rollback_is_invalid(self):
        for cycle, frame in ((9, 20), (10, 19)):
            with self.subTest(cycle=cycle, frame=frame):
                monitor = RuntimeHealthMonitor(20, 10)
                with self.assertRaises(RuntimeHealthFailure) as caught:
                    monitor.observe(cycle, frame, 0x1F)
                self.assertEqual(caught.exception.code, "invalid-sample")

    def test_invalid_types_and_ranges_are_rejected(self):
        for values in ((True, 0, 31), (0, -1, 31), (0, 0, True),
                       (0, 0, -1), (0, 0, 1 << 32), (None, 0, 31)):
            with self.subTest(values=values):
                with self.assertRaises(RuntimeHealthFailure) as caught:
                    RuntimeHealthMonitor(0, 0).observe(*values)
                self.assertEqual(caught.exception.code, "invalid-sample")
        for values in ((True, 0), (0, -1), (None, 0)):
            with self.subTest(initial=values):
                with self.assertRaises(RuntimeHealthFailure):
                    RuntimeHealthMonitor(*values)

    def test_long_native_call_is_excluded(self):
        monitor = RuntimeHealthMonitor(0, 0)
        monitor.begin_native_call(0, 0, 31)
        monitor.complete_native_call(1000, 0, 31)
        monitor.observe(1001, 0, 31)
        monitor.observe(1002, 1, 31)

    def test_native_call_preserves_preexisting_stall_debt(self):
        for returned_frame in (0, 1):
            with self.subTest(returned_frame=returned_frame):
                monitor = RuntimeHealthMonitor(0, 0)
                monitor.begin_native_call(119, 0, 31)
                monitor.complete_native_call(1119, returned_frame, 31)
                with self.assertRaises(RuntimeHealthFailure) as caught:
                    monitor.observe(1120, returned_frame, 31)
                self.assertEqual(caught.exception.code, "main-queue-stalled")
                self.assertEqual(caught.exception.details["nativeCyclesWithoutProgress"], 120)

    def test_native_call_end_rejects_fault_and_rollback(self):
        for cycle, frame, mode, code in ((1001, 0, 23, "arm9-abort"),
                                       (1001, 0, 27, "arm9-undefined"),
                                       (9, 0, 31, "invalid-sample"),
                                       (1001, -1, 31, "invalid-sample")):
            with self.subTest(cycle=cycle, mode=mode):
                monitor = RuntimeHealthMonitor(0, 10)
                monitor.begin_native_call(10, 0, 31)
                with self.assertRaises(RuntimeHealthFailure) as caught:
                    monitor.complete_native_call(cycle, frame, mode)
                self.assertEqual(caught.exception.code, code)

    def test_unmatched_or_nested_native_calls_are_rejected(self):
        monitor = RuntimeHealthMonitor(0, 0)
        with self.assertRaises(RuntimeHealthFailure):
            monitor.complete_native_call(0, 0, 31)
        monitor = RuntimeHealthMonitor(0, 0)
        monitor.begin_native_call(0, 0, 31)
        with self.assertRaises(RuntimeHealthFailure):
            monitor.begin_native_call(0, 0, 31)

    def test_failed_monitor_cannot_be_cleared_by_native_call(self):
        monitor = RuntimeHealthMonitor(0, 0)
        with self.assertRaises(RuntimeHealthFailure) as first:
            monitor.observe(120, 0, 31)
        for method in (monitor.begin_native_call, monitor.complete_native_call):
            with self.assertRaises(RuntimeHealthFailure) as caught:
                method(1120, 1, 31)
            self.assertIs(caught.exception, first.exception)

    def test_fault_is_latched_no_later_progress_can_recover(self):
        monitor = RuntimeHealthMonitor(0, 0)
        with self.assertRaises(RuntimeHealthFailure) as first:
            monitor.observe(120, 0, 31)
        with self.assertRaises(RuntimeHealthFailure) as second:
            monitor.observe(121, 1, 31)
        self.assertIs(first.exception, second.exception)


if __name__ == "__main__":
    unittest.main()
