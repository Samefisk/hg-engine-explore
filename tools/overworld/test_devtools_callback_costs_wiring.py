"""Exercise actual dispatch, completed sampling and cycle transport."""
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsHooks, DevtoolsFailure
from tools.overworld import test_devtools_runtime as runtime_fixtures


class CallbackCostsWiringTests(unittest.TestCase):
    def test_empty_persistent_hooks_do_not_run_the_observer_or_timer(self):
        fixture = runtime_fixtures.BridgeFixture()
        hooks = DevtoolsHooks(fixture.rt, fixture.emu)
        seen = []
        token = hooks.add(0x01FF8000, lambda: seen.append(1))
        dispatch = fixture.hooks[0x01FF8000]
        hooks.remove(token)
        for _ in range(20): dispatch(0x01FF8000, 4)
        self.assertEqual(seen, [])
        self.assertEqual(hooks.callback_costs.result(10**12)["categories"], {})
        hooks.add(0x01FF8000, lambda: seen.append(2))
        self.assertIs(fixture.hooks[0x01FF8000], dispatch)
        dispatch(0x01FF8000, 4)
        self.assertEqual(seen, [2])

    def test_native_dispatch_costs_do_not_change_callbacks_or_errors(self):
        fixture = runtime_fixtures.BridgeFixture()
        hooks = DevtoolsHooks(fixture.rt, fixture.emu)
        seen = []
        hooks.add(0x02001000, lambda: seen.append(1))
        fixture.hooks[0x02001000](0x02001000, 2)
        self.assertEqual(seen, [1])
        report = hooks.callback_costs.result(10**12)
        self.assertEqual(report["categories"]["native:0x02001000"]["calls"], 1)
        def fail(): raise ValueError("real reader error")
        hooks.add(0x02001000, fail)
        fixture.hooks[0x02001000](0x02001000, 2)
        self.assertIn("real reader error", hooks.error)
        self.assertIsNone(hooks.current_callback)
        self.assertEqual(hooks.callback_costs.result(10**12)["categories"]["native:0x02001000"]["calls"], 2)

    def test_each_cycle_keeps_total_cpu_and_separate_completed_sampler_cost(self):
        fixture = runtime_fixtures.CompletedFieldAvailabilityTests()
        self.addCleanup(fixture.doCleanups)
        session, memory, boundary, _, _, _ = fixture.fixture()
        def cycle(*args):
            session.rt.EXECUTED_FRAME_COUNT += 1
            boundary()
        session.cycle = cycle
        result = session.step(3, [], diagnostic_details=False)
        for interval in result["cycleIntervals"]:
            costs = interval["callbackCosts"]
            self.assertEqual(costs["totalCpuNs"], interval["cpuNs"])
            self.assertGreater(interval["threadCpuNs"], 0)
            resolution = interval["cpuClockResolutionNs"]
            self.assertEqual(set(resolution), {"process", "thread"})
            self.assertTrue(all(type(n) is int and n > 0 for n in resolution.values()))
            self.assertLessEqual(interval["threadCpuNs"], interval["cpuNs"] + 2 * sum(resolution.values()))
            self.assertGreater(costs["measuredCpuNs"], 0)
            self.assertLessEqual(costs["measuredCpuNs"], interval["cpuNs"])
            self.assertEqual(costs["categories"]["main-queue-sampler"]["calls"], 1)
        self.assertEqual([s["frame"] for s in result["samples"]], [4, 5, 6])

    def test_timing_failure_preserves_first_runtime_failure_and_total_cost(self):
        fixture = runtime_fixtures.CompletedFieldAvailabilityTests()
        self.addCleanup(fixture.doCleanups)
        session, *_ = fixture.fixture()
        original = DevtoolsFailure("real-native-fault", "first failure")
        def fail_cycle(*args): raise original
        def fail_cost(*args): raise ValueError("bad cost clock")
        session.cycle = fail_cycle
        session.callback_costs.result = fail_cost
        with self.assertRaises(DevtoolsFailure) as caught:
            session.step(1, [], diagnostic_details=False)
        self.assertIs(caught.exception, original)
        interval, = caught.exception.details["cycleIntervals"]
        self.assertGreater(interval["cpuNs"], 0)
        self.assertEqual(interval["callbackCostError"], "bad cost clock")

    def test_thread_clock_failure_cannot_mask_native_fault(self):
        fixture = runtime_fixtures.CompletedFieldAvailabilityTests()
        self.addCleanup(fixture.doCleanups)
        session, *_ = fixture.fixture()
        original = DevtoolsFailure("real-native-fault", "first failure")
        def fail_cycle(*args): raise original
        session.cycle = fail_cycle
        with patch("tools.overworld.devtools_runtime.time.thread_time_ns",
                   side_effect=[10, ValueError("thread clock failed")]):
            with self.assertRaises(DevtoolsFailure) as caught:
                session.step(1, [], diagnostic_details=False)
        self.assertIs(caught.exception, original)
        interval, = caught.exception.details["cycleIntervals"]
        self.assertEqual(interval["threadCostError"], "thread clock failed")

    def test_timing_failure_cannot_replace_a_captured_sampler_or_hook_fault(self):
        for owner in ("sampler", "hook"):
            with self.subTest(owner=owner):
                fixture = runtime_fixtures.CompletedFieldAvailabilityTests()
                self.addCleanup(fixture.doCleanups)
                session, *_ = fixture.fixture()
                def cycle(*args):
                    if owner == "sampler": session.sample_error = ValueError("original sampler")
                    else: session.party_getter_hooks.error = "original hook"
                def fail_cost(*args): raise ValueError("bad cost clock")
                session.cycle = cycle
                session.callback_costs.result = fail_cost
                with self.assertRaises(DevtoolsFailure) as caught:
                    session.step(1, [], diagnostic_details=False)
                self.assertEqual(caught.exception.code, "observation-failed")
                self.assertIn("original " + owner, str(caught.exception))


if __name__ == "__main__": unittest.main()
