"""Checked runner wiring and fixed-route controls; no gameplay claims."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs

ROOT = Path(__file__).resolve().parents[2]
NAMES = ("walk.cardinal.frames-1-32", "observation.walk-matrix-state-control")


def recipe(name):
    return json.loads((ROOT / "tests/overworld/test-recipes" / (name + ".json")).read_text())


class MatrixRecipeTests(unittest.TestCase):
    def test_both_recipes_install_their_real_meter(self):
        for name, count in zip(NAMES, (65, 2)):
            test = validate_test(recipe(name))
            evaluator = TestEvaluator(test)
            evaluator.install_measurements(measurement_inputs(test, ROOT))
            meter = next(iter(evaluator.measurements.values()))
            self.assertEqual(meter.case_limit, count)

    def test_route_cannot_shrink_reorder_or_change_the_witness(self):
        for name in NAMES:
            for fault in ("omit", "keys", "time", "configure", "gate", "mode"):
                test = recipe(name)
                if fault == "omit": test["actions"].pop(2)
                elif fault == "keys": test["actions"][1]["args"]["keys"] = ["UP"]
                elif fault == "time": test["setup"][4]["args"]["travelTime"] = 2
                elif fault == "configure": test["actions"][3]["args"]["travelTime"] = 3
                elif fault == "gate": test["actions"][1]["args"].pop("until")
                else: test["mode"] = "normal"
                with self.subTest(name=name, fault=fault), self.assertRaises(ValueError):
                    validate_test(test)

    def test_matrix_commands_remain_prepared_and_terminal_control_is_separate(self):
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import validate_recipe
        self.assertEqual(validate_command("walk-matrix.calibrate", {}), {})
        with self.assertRaises(ValueError):
            validate_recipe(dict(schemaVersion=1, mode="normal", actions=[dict(op="walk-matrix.calibrate", args={})]))
        test = recipe(NAMES[0])
        test["actions"].insert(-1, dict(id="illegal-control", op="walk-matrix.calibrate", args={},
                budget=dict(maxSeconds=5, maxFrames=1, noProgressFrames=1)))
        with self.assertRaises(ValueError): validate_test(test)


if __name__ == "__main__": unittest.main()
