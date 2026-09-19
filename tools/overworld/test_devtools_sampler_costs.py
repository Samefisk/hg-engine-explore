"""Actual sampler phase attribution with fake clocks; no emulator."""
from copy import deepcopy
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from tools.overworld.devtools_callback_costs import CallbackCosts
from tools.overworld.devtools_runtime import DevtoolsFailure
from tools.overworld import test_devtools_runtime as runtime_fixtures


class SamplerCostsTests(unittest.TestCase):
    def fixture(self):
        f = runtime_fixtures.CompletedFieldAvailabilityTests(); self.addCleanup(f.doCleanups)
        session, _, boundary, reads, _, traces = f.fixture()
        ticks = iter(range(0, 10000, 10))
        session.callback_costs = CallbackCosts(clock=lambda: next(ticks))
        session.latest_profile_keys = None
        return session, boundary, reads, traces

    def test_nested_phases_are_exclusive_and_keep_same_data_and_order(self):
        session, boundary, reads, traces = self.fixture()
        boundary()
        self.assertIsNone(session.sample_error)
        self.assertEqual(reads, ["party", "field", "selector"])
        self.assertEqual(traces, [4])
        self.assertEqual(session.pending_samples, [session.latest_frame])
        self.assertIsNot(session.pending_samples[0], session.latest_frame)
        report = session.callback_costs.result(10000)
        phases = ("party-read", "snapshot", "selector", "dialogue", "profile-cache", "trace-publication", "pending-copy")
        for phase in phases:
            self.assertEqual(report["categories"]["sampler:" + phase], {"cpuNs":10,"calls":1})
        self.assertEqual(report["measuredCpuNs"], 150)
        self.assertEqual(report["categories"]["main-queue-sampler"], {"cpuNs":80,"calls":1})
        before = deepcopy(session.latest_frame)
        session.callback_costs.begin_cycle(); boundary()
        self.assertNotIn("sampler:profile-cache", session.callback_costs.result(10000)["categories"])
        self.assertEqual(before, session.pending_samples[0])

    def test_reader_error_is_same_object_charged_and_stops_later_phases(self):
        session, boundary, reads, traces = self.fixture()
        original = ValueError("native selector failed")
        def fail(): raise original
        session._selector_observation = fail
        boundary()
        self.assertIs(session.sample_error, original)
        self.assertEqual(reads, ["party", "field"])
        self.assertEqual(traces, [])
        self.assertEqual(session.pending_samples, [])
        categories = session.callback_costs.result(10000)["categories"]
        self.assertEqual(categories["sampler:selector"], {"cpuNs":10,"calls":1})
        self.assertNotIn("sampler:dialogue", categories)
        boundary()
        self.assertIs(session.sample_error, original)

    def test_gc_scope_covers_control_and_cycle_then_closes_before_report(self):
        for fails in (False, True):
            session, _, _, _ = self.fixture()
            calls = []
            original = DevtoolsFailure("original-cycle-fault", "original cycle fault")
            @contextmanager
            def probe():
                calls.append("enter")
                try: yield
                finally: calls.append("exit")
            session.callback_costs.measure_gc = probe
            real_result = session.callback_costs.result
            def report(total):
                calls.append("report")
                self.assertEqual(calls[-2], "exit")
                return real_result(total)
            session.callback_costs.result = report
            session.route_control = SimpleNamespace(before_cycle=lambda: calls.append("control"))
            def cycle(*args):
                calls.append("cycle")
                if fails: raise original
                session.completed_frames += 1
                session.latest_frame = {"frame": session.completed_frames, "fieldAvailable": True}
                session.pending_samples.append(session.latest_frame)
            session.cycle = cycle
            session.snapshot = lambda **kwargs: session.latest_frame
            session.diagnostics = lambda: {}
            if fails:
                with self.assertRaises(RuntimeError) as caught:
                    session.step(1, [], diagnostic_details=False)
                self.assertIs(caught.exception, original)
            else:
                session.step(1, [], diagnostic_details=False)
            self.assertEqual(calls, ["enter", "control", "cycle", "exit", "report"])


if __name__ == "__main__": unittest.main()
