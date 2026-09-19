from copy import deepcopy
from itertools import count
import unittest
from unittest.mock import patch

from tools.overworld.devtools_dispatch_counts import SCOPE, validate_dispatch_counts
from tools.overworld.devtools_runtime import DevtoolsFailure
from tools.overworld.test_devtools_runtime import CompletedFieldAvailabilityTests


def counts(sequence=100, complete=True):
    return dict(version=1, enabled=True, complete=complete, frameSequence=sequence,
                arm9=120, arm7=80, scope=SCOPE)


class DispatchCountsTests(unittest.TestCase):
    def test_exact_schema_and_incomplete_frames(self):
        self.assertEqual(validate_dispatch_counts(counts()), counts())
        for key, value in (("version", True), ("enabled", False), ("complete", False),
                           ("frameSequence", 0), ("arm9", -1), ("arm7", True), ("scope", "cycles")):
            with self.subTest(key=key):
                bad = counts(); bad[key] = value
                with self.assertRaises(ValueError): validate_dispatch_counts(bad)
        validate_dispatch_counts(counts(complete=False), require_complete=False)

    def fixture(self):
        # This test checks count transport, not OS clock granularity. Keep its
        # process/thread brackets deterministic; production timers stay intact.
        for name, stride in (("process_time_ns", 100_000_000), ("thread_time_ns", 1_000_000)):
            clock = patch("tools.overworld.devtools_runtime.time." + name, side_effect=count(0, stride))
            clock.start()
            self.addCleanup(clock.stop)
        fixture = CompletedFieldAvailabilityTests()
        self.addCleanup(fixture.doCleanups)
        session, _, boundary, *_ = fixture.fixture()
        state = dict(enabled=False, sequence=100, complete=False, toggles=[])
        def enable(value):
            old = state["enabled"]; state["enabled"] = value
            state["toggles"].append(value)
            return old
        def read():
            return {**counts(state["sequence"], state["complete"]), "enabled": state["enabled"]}
        def cycle(*args):
            state["sequence"] += 1; state["complete"] = True
            session.rt.EXECUTED_FRAME_COUNT += 1
            boundary()
        session.emu.enable_dispatch_counts = enable
        session.emu.dispatch_counts = read
        session.cycle = cycle
        return session, state

    def test_actual_step_scopes_counts_and_keeps_every_cycle(self):
        session, state = self.fixture()
        result = session.step(3, [], diagnostic_details=False)
        self.assertEqual(state["toggles"], [True, False])
        self.assertEqual([i["guestDispatches"]["frameSequence"] for i in result["cycleIntervals"]], [101, 102, 103])
        self.assertTrue(all(i["cpuNs"] > 0 for i in result["cycleIntervals"]))
        for i in result["cycleIntervals"]: validate_dispatch_counts(i["guestDispatches"])

    def test_host_work_probe_brackets_cycle_without_becoming_guest_time(self):
        from tools.overworld.devtools_host_probe import measure_host_probe
        probe = measure_host_probe(clock=iter([0, 100]).__next__)
        session, _ = self.fixture()
        run_cycle = session.cycle
        order = []
        def cycle(*args):
            order.append("cycle")
            return run_cycle(*args)
        def work():
            order.append("probe")
            return deepcopy(probe)
        session.cycle = cycle
        with patch("tools.overworld.devtools_runtime.measure_host_probe", side_effect=work):
            result = session.step(2, [], diagnostic_details=False)
        self.assertEqual(order, ["probe", "cycle", "probe"] * 2)
        for interval in result["cycleIntervals"]:
            self.assertEqual(interval["hostWorkProbe"], dict(before=probe, after=probe))
            self.assertEqual(interval["cpuNs"], 100_000_000)

    def test_probe_failure_cannot_replace_native_fault(self):
        from tools.overworld.devtools_host_probe import measure_host_probe
        probe = measure_host_probe(clock=iter([0, 100]).__next__)
        session, state = self.fixture()
        original = DevtoolsFailure("native-fault", "original")
        def cycle(*args):
            state["sequence"] += 1
            raise original
        session.cycle = cycle
        with patch("tools.overworld.devtools_runtime.measure_host_probe", side_effect=[probe, ValueError("bad probe")]):
            with self.assertRaises(DevtoolsFailure) as caught:
                session.step(1, [], diagnostic_details=False)
        self.assertIs(caught.exception, original)
        self.assertEqual(original.details["cycleIntervals"][0]["hostWorkProbeError"], "bad probe")

    def test_native_failure_retains_partial_count_and_restores_state(self):
        session, state = self.fixture()
        original = DevtoolsFailure("native-fault", "original")
        def fail(*args):
            state["sequence"] += 1
            raise original
        session.cycle = fail
        with self.assertRaises(DevtoolsFailure) as caught:
            session.step(1, [], diagnostic_details=False)
        self.assertIs(caught.exception, original)
        self.assertEqual(state["toggles"], [True, False])
        self.assertFalse(original.details["cycleIntervals"][0]["guestDispatches"]["complete"])

    def test_count_read_error_cannot_replace_latched_hook_fault(self):
        session, state = self.fixture()
        read = session.emu.dispatch_counts
        def fail_read():
            if state["sequence"] > 100:
                raise ValueError("counter unavailable")
            return read()
        def cycle(*args):
            state["sequence"] += 1
            session.party_getter_hooks.error = "original hook fault"
        session.cycle = cycle
        session.emu.dispatch_counts = fail_read
        with self.assertRaisesRegex(DevtoolsFailure, "original hook fault") as caught:
            session.step(1, [], diagnostic_details=False)
        self.assertEqual(caught.exception.details["cycleIntervals"][0]["guestDispatchError"], "counter unavailable")

    def test_raw_replay_rejects_missing_partial_and_reordered_counts(self):
        from tools.overworld.devtools_raw_chunk import validate_raw_chunk
        session, _ = self.fixture()
        prior = dict(frame=session.completed_frames, nativeCycle=session.rt.EXECUTED_FRAME_COUNT)
        result = session.step(2, [], diagnostic_details=False)
        validate_raw_chunk(result, prior)
        for fault in ("missing", "partial", "sequence", "probe-missing", "probe-invalid"):
            bad = deepcopy(result)
            row = bad["cycleIntervals"][1]
            if fault == "missing": del row["guestDispatches"]
            elif fault == "partial": row["guestDispatches"]["complete"] = False
            elif fault == "sequence": row["guestDispatches"]["frameSequence"] -= 1
            elif fault == "probe-missing": del row["hostWorkProbe"]["after"]
            else: row["hostWorkProbe"]["after"]["iterations"] += 1
            with self.assertRaises(ValueError): validate_raw_chunk(bad, prior)
