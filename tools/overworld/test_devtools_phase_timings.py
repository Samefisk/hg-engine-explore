from copy import deepcopy
import unittest

from tools.overworld.devtools_phase_timings import PHASES, SCOPE, validate_phase_timings
from tools.overworld.devtools_runtime import DevtoolsFailure
from tools.overworld import test_devtools_dispatch_counts as dispatch_fixtures


def timings(sequence=100, complete=True):
    return dict(version=2, enabled=True, complete=complete, invalid=False,
                frameSequence=sequence, scope=SCOPE,
                phases={name: dict(cpuNs=100, calls=1) for name in PHASES})


class PhaseTimingsTests(unittest.TestCase):
    def fixture(self):
        base = dispatch_fixtures.DispatchCountsTests()
        self.addCleanup(base.doCleanups)
        session, counts = base.fixture()
        state = dict(enabled=False, toggles=[])
        def enable(value):
            previous = state["enabled"]
            state["enabled"] = value
            state["toggles"].append(value)
            return previous
        def read():
            return {**timings(counts["sequence"], counts["complete"]), "enabled": state["enabled"]}
        session.emu.enable_phase_timings = enable
        session.emu.phase_timings = read
        return session, state, counts

    def test_schema_and_cycle_cost_bounds(self):
        validate_phase_timings(timings(), cpu_ns=300)
        for key, value in (("version", True), ("enabled", False), ("invalid", True),
                           ("complete", False), ("frameSequence", 0), ("scope", "game CPU")):
            bad = timings(); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_phase_timings(bad)
        for entry in (dict(cpuNs=1, calls=0), dict(cpuNs=-1, calls=1),
                      dict(cpuNs=1, calls=True), dict(cpuNs=1, calls=100001)):
            bad = timings(); bad["phases"]["nonRender"] = entry
            with self.assertRaises(ValueError): validate_phase_timings(bad)
        with self.assertRaises(ValueError): validate_phase_timings(timings(), cpu_ns=299)
        validate_phase_timings(timings(complete=False), require_complete=False)

    def test_real_step_keeps_all_cycles_and_original_cpu_bracket(self):
        session, state, _ = self.fixture()
        result = session.step(3, [], diagnostic_details=False)
        self.assertEqual(state["toggles"], [True, False])
        self.assertEqual([i["nativePhases"]["frameSequence"] for i in result["cycleIntervals"]], [101, 102, 103])
        for interval in result["cycleIntervals"]:
            self.assertEqual(interval["cpuNs"], 100_000_000)
            validate_phase_timings(interval["nativePhases"], cpu_ns=interval["cpuNs"])

    def test_original_fault_survives_partial_phase_and_cleanup_error(self):
        session, state, counts = self.fixture()
        original = DevtoolsFailure("native-fault", "original")
        def cycle(*args):
            counts["sequence"] += 1
            raise original
        enable = session.emu.enable_phase_timings
        def cleanup_fails(value):
            result = enable(value)
            if not value: raise ValueError("phase cleanup")
            return result
        session.cycle = cycle
        session.emu.enable_phase_timings = cleanup_fails
        with self.assertRaises(DevtoolsFailure) as caught:
            session.step(1, [], diagnostic_details=False)
        self.assertIs(caught.exception, original)
        self.assertFalse(original.details["cycleIntervals"][0]["nativePhases"]["complete"])
        self.assertEqual(original.details["nativePhaseCleanupError"], "phase cleanup")
        self.assertEqual(state["toggles"], [True, False])

    def test_phase_read_failure_preserves_latched_hook_fault(self):
        session, _, counts = self.fixture()
        read = session.emu.phase_timings
        def fail_read():
            if counts["sequence"] > 100: raise ValueError("phase reader")
            return read()
        cycle = session.cycle
        def fail_hook(*args):
            cycle(*args)
            session.party_getter_hooks.error = "original observer fault"
        session.emu.phase_timings = fail_read
        session.cycle = fail_hook
        with self.assertRaisesRegex(DevtoolsFailure, "original observer fault") as caught:
            session.step(1, [], diagnostic_details=False)
        self.assertEqual(caught.exception.details["cycleIntervals"][0]["nativePhaseError"], "phase reader")

    def test_raw_replay_rejects_missing_invalid_reordered_and_excess_cost(self):
        from tools.overworld.devtools_raw_chunk import validate_raw_chunk
        session, _, _ = self.fixture()
        prior = dict(frame=session.completed_frames, nativeCycle=session.rt.EXECUTED_FRAME_COUNT)
        result = session.step(2, [], diagnostic_details=False)
        validate_raw_chunk(result, prior)
        for fault in ("missing", "invalid", "sequence", "cost", "names", "error"):
            bad = deepcopy(result)
            interval = bad["cycleIntervals"][1]
            phase = interval["nativePhases"]
            if fault == "missing": del interval["nativePhases"]
            elif fault == "invalid": phase["invalid"] = True
            elif fault == "sequence": phase["frameSequence"] += 1
            elif fault == "cost": phase["phases"]["nonRender"]["cpuNs"] = interval["cpuNs"] + 1
            elif fault == "names": del phase["phases"]["render2d"]
            else: interval["nativePhaseError"] = "failed"
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                validate_raw_chunk(bad, prior)
