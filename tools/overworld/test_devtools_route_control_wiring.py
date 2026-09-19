"""Actual shared boundaries for route controls; no emulator proof."""
from types import SimpleNamespace
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsFailure, DevtoolsSession
from tools.overworld import test_devtools_runtime as runtime_tests


class RouteControlWiringTests(unittest.TestCase):
    def test_pin_arming_receives_only_the_validated_native_admission(self):
        from tools.overworld.devtools_observer import NativeObservation, NativeObservationError
        before = {"x": 1, "y": 2, "pos_x": 98304, "pos_z": 163840}
        after = {**before, "y": 1, "x_prev": 1, "y_prev": 2}
        calls = []
        native = NativeObservation.__new__(NativeObservation)
        native.player_steps_admitted = 4
        native.session = SimpleNamespace(emu=object(),
            rt=SimpleNamespace(player_ptr=lambda emu: 0x02030000,
                field_map_id=lambda emu: 33, object_state=lambda *args: after),
            route_control=SimpleNamespace(player_step_admitted=lambda receipt: calls.append(deepcopy(receipt))))
        value = {"objectPointer": 0x02030000, "direction": 0, "mapId": 33, "objectBefore": before}
        receipt = native._player_step_after(value, {})
        self.assertEqual(calls, [receipt])
        self.assertEqual(receipt["stepIndex"], 5)
        self.assertEqual(receipt["origin"], [1, 2])
        self.assertEqual(receipt["target"], [1, 1])
        after["pos_x"] += 1
        with self.assertRaises(NativeObservationError): native._player_step_after(value, {})
        self.assertEqual(len(calls), 1)

    def test_recipe_rejects_wrong_role_or_fault_pair_before_boot(self):
        from tools.overworld.devtools_test_contract import validate_test, TestEvaluator
        from tools.overworld.devtools_test_inputs import measurement_inputs
        root = Path(__file__).resolve().parents[2]
        recipe = json.loads((root / "tests/overworld/test-recipes/observation.live-route-control.json").read_text())
        valid = validate_test(recipe)
        evaluator = TestEvaluator(valid)
        evaluator.install_measurements(measurement_inputs(valid, root))
        self.assertTrue(evaluator.uses_raw_records)
        for fault in ("role", "duplicate", "order"):
            with self.subTest(fault=fault):
                value = deepcopy(recipe)
                if fault == "role": value["subjects"][0]["role"] = "MOUNTED"
                else:
                    controls = [a for a in value["actions"] if a["op"] == "observer-control"]
                    if fault == "duplicate": controls[1]["args"]["fault"] = "cpu-hitch"
                    else:
                        controls[0]["args"]["fault"] = "player-start-stall"
                        controls[1]["args"]["fault"] = "cpu-hitch"
                with self.assertRaises(ValueError): validate_test(value)

    def test_cpu_work_is_inside_timed_cycle_and_pin_precedes_snapshot(self):
        session, _, boundary, reads, _, _ = runtime_tests.CompletedFieldAvailabilityTests.fixture(self)
        order = []
        session.route_control = SimpleNamespace(
            before_cycle=lambda: order.append("work"),
            completed_boundary=lambda: reads.append("pin"),
            result=lambda: {"state": "player-pinning"})
        def clock():
            order.append("clock")
            return len(order) * 100
        def cycle(*args):
            order.append("cycle")
            session.rt.EXECUTED_FRAME_COUNT += 1
            boundary()
        session.cycle = cycle
        # This fixture checks call order, not CPU duration. Keep callback and
        # thread clocks synthetic too; real costs cannot fit its 300 ns cycle.
        session.callback_costs.clock = lambda: 0
        with patch("tools.overworld.devtools_runtime.time.process_time_ns", clock), \
                patch("tools.overworld.devtools_runtime.time.thread_time_ns", lambda: 0):
            receipt = session.step(1, [], diagnostic_details=False)
        self.assertEqual(order, ["clock", "work", "cycle", "clock"])
        self.assertLess(reads.index("pin"), reads.index("field"))
        self.assertEqual(receipt["cycleIntervals"][0]["cpuNs"], 300)
        self.assertEqual(receipt["samples"][0]["routeControl"], {"state": "player-pinning"})

    def test_closed_pinned_session_cannot_execute_another_native_cycle(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.runtime_health_failure = None
        session.emu = object()
        session.route_control_nonresumable = True
        session.route_control = SimpleNamespace(closed=True, failure=None)
        calls = []
        session.rt = SimpleNamespace(h=SimpleNamespace(cycle=lambda *args: calls.append(args)))
        with self.assertRaises(DevtoolsFailure) as caught:
            session.cycle(1)
        self.assertEqual(caught.exception.code, "route-control-nonresumable")
        self.assertEqual(calls, [])

    def test_failure_inside_cycle_blocks_the_next_cycle_even_before_close(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.runtime_health_failure = None
        session.emu = object()
        session.route_control = SimpleNamespace(closed=False, failure=None)
        calls = []
        def cycle(*args):
            calls.append(args)
            session.route_control.failure = {"message": "lost player owner"}
        session.rt = SimpleNamespace(h=SimpleNamespace(cycle=cycle))
        session._check_runtime_health = session._retain_prepared_events = lambda: None
        with self.assertRaises(DevtoolsFailure):
            session.cycle(2)
        self.assertEqual(len(calls), 1)

    def test_control_close_releases_input_without_advancing_or_restoring(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        session.completed_frames = 17
        session.snapshot = lambda **kwargs: {"frame": 17}
        calls = []
        session.rt = SimpleNamespace(h=SimpleNamespace(set_key_mask=lambda emu, mask: calls.append(("release", mask))))
        session.route_control = SimpleNamespace(close=lambda: calls.append(("close",)),
            result=lambda: {"closed": True, "requiresCoreClose": True})
        receipt = session.route_control_close()
        self.assertEqual(calls, [("release", 0), ("close",)])
        self.assertEqual(receipt["advancedFrames"], 0)
        self.assertEqual(receipt["frame"], 17)
        self.assertTrue(receipt["routeControl"]["requiresCoreClose"])


if __name__ == "__main__":
    unittest.main()
