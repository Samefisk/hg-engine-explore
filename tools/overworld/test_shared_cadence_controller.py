"""Exact full-route controller registration; no emulator or live proof."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.overworld.cadence_diagnostics import UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS
from tools.overworld.control import (
    _shared_cadence_queue_budget,
    _shared_test_registration,
    ValidationFailure,
)

ROOT = Path(__file__).resolve().parents[2]
NAME = "world.unmounted.long-travel-cadence"
GAME_NAME = "world.unmounted.game-cadence"
GAME_KIND = "unmounted-game-cadence-v1"


def queue_rows(ticks, *, clocks=True):
    rows = []
    for index, tick in enumerate(ticks):
        sample = {
            "frame": index + 1,
            "nativeCycle": 10 + index * 2,
            "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion",
            "fieldControl": {"fieldPointer": 0x02200000, "taskPointer": 0},
            "context": {"mapId": 67, "fieldEpoch": 3},
        }
        if clocks:
            sample["guestQueueClock"] = {
                "version": 1,
                "running": True,
                "scope": "nds-scheduler-ticks-not-cpu-or-instructions",
                "arm9Timestamp": tick,
                "arm7Timestamp": tick // 2,
                "frameSequence": sample["nativeCycle"],
            }
        rows.append({"phase": "observe", "action": "route", "samples": [sample]})
    return rows


class CadenceQueueBudgetTests(unittest.TestCase):
    def test_dense_exact_clock_at_budget_passes_with_bounded_details(self):
        result = _shared_cadence_queue_budget(queue_rows(
            [0, 100, UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS]))
        self.assertTrue(result["passed"])
        self.assertEqual(result["maximumTwoQueueArm9Ticks"],
                         UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS)
        self.assertEqual(result["eligibleTwoQueueIntervals"], 1)
        self.assertEqual(result["observedTwoQueueIntervals"], 1)
        self.assertEqual(result["missingClockTriples"], 0)
        self.assertLessEqual(len(result["topTwoQueueIntervals"]), 8)
        self.assertIn("not rendered-frame", result["scope"])

    def test_exceeded_exact_clock_rejects_with_budget_maximum_and_frames(self):
        maximum = UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS + 1
        with self.assertRaisesRegex(ValidationFailure,
                rf"budget-exceeded: maximumTwoQueueArm9Ticks={maximum}, "
                rf"budgetArm9Ticks={UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS}, frames=1->3"):
            _shared_cadence_queue_budget(queue_rows([0, 100, maximum]))

    def test_missing_exact_clock_cannot_pass(self):
        with self.assertRaisesRegex(ValidationFailure,
                r"missing-clock-triples: maximumTwoQueueArm9Ticks=None"):
            _shared_cadence_queue_budget(queue_rows([0, 100, 200], clocks=False))

    def test_current_game_contract_uses_the_same_missing_and_excess_clock_guard(self):
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        current = registry["sharedTests"][GAME_NAME]
        self.assertEqual(current["guestQueueBudgetArm9Ticks"],
                         UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS)
        for ticks, reason in (
                ([0, 100, 200], "missing-clock-triples"),
                ([0, 100, UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS + 1],
                 "budget-exceeded")):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(ValidationFailure, reason):
                    _shared_cadence_queue_budget(queue_rows(ticks, clocks=reason != "missing-clock-triples"))


class CadenceRegistrationTests(unittest.TestCase):
    def test_exact_registration_and_each_scope_boundary(self):
        original = json.loads((ROOT / "tests/overworld/test-recipes" / (NAME + ".json")).read_text())
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "tests/overworld/test-recipes" / (NAME + ".json")
            table = root / "tools/overworld/runtime_proof_registry.json"
            target.parent.mkdir(parents=True)
            table.parent.mkdir(parents=True)
            for fault in (None, "role", "floor", "calibration", "claim", "expected", "setup", "mode"):
                with self.subTest(fault=fault):
                    test, saved = deepcopy(original), deepcopy(registry)
                    entry = saved["sharedTests"][NAME]
                    if fault == "role": test["subjects"][0]["role"] = "MOUNTED"
                    if fault == "floor": test["budgets"]["minObservedFrames"] = 4999
                    if fault == "calibration": entry["recorderControlRequirement"] = "legacy.live-observer-controls"
                    if fault == "claim": entry["claims"].pop()
                    if fault == "expected":
                        saved["measurementContracts"]["legacy.unmounted-long-travel"]["natural-input"][0]["minimum"] = 1
                    if fault == "setup": test["measurements"][0]["setupTransitions"] = [33]
                    if fault == "mode": test["mode"] = "normal"
                    content = json.dumps(test).encode()
                    target.write_bytes(content)
                    entry["recipeSha256"] = sha256(content).hexdigest()
                    table.write_text(json.dumps(saved))
                    if fault is None:
                        actual, _ = _shared_test_registration(test, root)
                        self.assertEqual(actual, entry)
                    else:
                        with self.assertRaises((ValueError, ValidationFailure)):
                            _shared_test_registration(test, root)

    def test_current_game_registration_has_nine_rows_and_retains_cpu_diagnostics(self):
        recipe = json.loads((ROOT / "tests/overworld/test-recipes" / (GAME_NAME + ".json")).read_text())
        registration, _ = _shared_test_registration(recipe, ROOT)
        self.assertEqual(registration["evaluator"], GAME_KIND)
        self.assertEqual(registration["guestQueueBudgetArm9Ticks"],
                         UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS)
        self.assertEqual(registration["claims"], [
            "live-actor-identity", "natural-input", "logical-commit",
            "rendered-motion", "control-release"])
        self.assertNotIn("host-cpu-pacing", registration["claims"])
        self.assertEqual(sum((len(rows) for rows in registration["measurementContract"].values()), 0), 9)
        from tools.overworld.devtools_test_contract import TestEvaluator
        from tools.overworld.devtools_test_inputs import measurement_inputs
        evaluator = TestEvaluator(recipe)
        evaluator.install_measurements(measurement_inputs(recipe, ROOT))
        meter = evaluator.measurements[GAME_KIND]
        self.assertTrue(meter.diagnostic_continue_host_hitches)
        self.assertTrue(meter.accept_host_cpu_hitches)


if __name__ == "__main__": unittest.main()
