"""Prepared boundary watermarks must reach both shared sequence consumers."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld import test_devtools_cadence_measurement as cadence_fixtures

Route = cadence_fixtures.Route


class PreparedSequenceTests(unittest.TestCase):
    def fixture(self):
        root = Path(__file__).resolve().parents[2]
        test = json.loads((root / "tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json").read_text())
        meter, commands = cadence_fixtures.PreparedCadenceSetupTests().fixture()
        evaluator = TestEvaluator(test)
        evaluator.measurements = {"unmounted-cadence-v1": meter}
        evaluator.measurements_installed = True
        evaluator._raw_frame = meter.latest["frame"]
        evaluator.observe(deepcopy(meter.latest), count_frame=False)
        evaluator._raw_frame = None
        commands[0]["receipt"]["setupBoundary"]["traceSequences"] = {"1": 8}
        commands[1]["receipt"]["setupBoundary"]["traceSequences"] = {"1": 75}
        return evaluator, commands

    def test_next_native_event_follows_validated_excluded_setup(self):
        evaluator, commands = self.fixture()
        for command in commands:
            self.assertEqual(evaluator.observe_record(command)["failures"], [])
        self.assertEqual(evaluator.last_sequence, {1: 75})
        self.assertEqual(sum(evaluator.events.values()), 0)
        event = Route().trace("MOTION_STARTED", 1, 8)
        event["data"]["sequence"] = 76
        evaluator._events([event], event["frame"])
        self.assertEqual(evaluator.last_sequence, {1: 76})

    def test_duplicate_or_skipped_first_route_sequence_still_fails(self):
        for sequence in (75, 77):
            with self.subTest(sequence=sequence):
                evaluator, commands = self.fixture()
                for command in commands: evaluator.observe_record(command)
                event = Route().trace("MOTION_STARTED", 1, 8)
                event["data"]["sequence"] = sequence
                with self.assertRaisesRegex(ValueError, "missing, duplicated, or reordered"):
                    evaluator._events([event], event["frame"])

    def test_invalid_prepared_receipt_cannot_advance_watermark(self):
        for fault in ("missing-events", "wrong-events", "undrained", "wrong-clock", "rollback"):
            with self.subTest(fault=fault):
                evaluator, commands = self.fixture()
                evaluator.observe_record(commands[0])
                receipt = commands[1]["receipt"]
                if fault == "missing-events": del receipt["events"]
                elif fault == "wrong-events": receipt["events"] = {}
                elif fault == "undrained": receipt["setupBoundary"]["eventsDrained"] = False
                elif fault == "wrong-clock": receipt["setupBoundary"]["frame"] += 1
                else: receipt["setupBoundary"]["traceSequences"] = {"1": 7}
                self.assertTrue(evaluator.observe_record(commands[1])["failures"])
                self.assertEqual(evaluator.last_sequence, {1: 8})

    def test_ordinary_event_cannot_supply_a_new_baseline(self):
        evaluator, _ = self.fixture()
        event = Route().trace("MOTION_STARTED", 1, 8)
        event["data"]["sequence"] = 76
        with self.assertRaisesRegex(ValueError, "missing, duplicated, or reordered"):
            evaluator._events([event], event["frame"])


if __name__ == "__main__":
    unittest.main()
