"""Typed corner test boundaries; no emulator or gameplay acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import validate_test, TestEvaluator, CORNER
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_test_contract import snapshot

ROOT = Path(__file__).resolve().parents[2]


def recipe():
    return json.loads((ROOT / "tests/overworld/test-recipes/walk.diagonal.corner-block.json").read_text())


class CornerContractTests(unittest.TestCase):
    def test_exact_recipe_and_input_contract(self):
        value = validate_test(recipe())
        self.assertEqual(measurement_inputs(value, ROOT), {CORNER: {"contractVersion": 1}})
        self.assertEqual(value["actions"][2]["args"]["keys"], [])

    def test_wrong_phase_subject_mode_and_input_are_rejected(self):
        for fault in ("mode", "species", "keys", "release", "probe", "arm", "measurement", "bound"):
            with self.subTest(fault=fault):
                value = recipe()
                if fault == "mode": value["mode"] = "normal"
                elif fault == "species": value["subjects"][0]["species"] = 19
                elif fault == "keys": value["actions"][1]["args"]["keys"] = ["DOWN"]
                elif fault == "release": value["actions"][2]["args"]["keys"] = ["UP"]
                elif fault == "probe": value["setup"][-1]["args"]["address"] = 0x02000000
                elif fault == "arm": value["actions"][0]["args"]["subject"] = "missing"
                elif fault == "measurement": value["measurements"] = []
                else: value["budgets"]["maxFrames"] = 601
                with self.assertRaises(ValueError): validate_test(value)

    def test_full_current_subject_is_resolved_before_command(self):
        evaluator = TestEvaluator(recipe())
        current = snapshot()
        current["actors"][0]["species"] = 155
        current["actors"][0]["role"] = "MOUNTED"
        evaluator.measurements[CORNER] = object()
        with self.assertRaises(ValueError): evaluator.corner_args("cyndaquil", current)
        evaluator.bind("cyndaquil", current)
        args = evaluator.corner_args("cyndaquil", current)
        self.assertEqual(args["maxFrames"], 600)
        self.assertEqual(args["subject"]["handle"], current["actors"][0]["handle"])
        self.assertNotIn("maxFrames", evaluator.corner_args("cyndaquil", current, probe=True))
        stale = deepcopy(current)
        stale["actors"][0]["authorityGeneration"] += 1
        with self.assertRaises(ValueError): evaluator.corner_args("cyndaquil", stale)


if __name__ == "__main__":
    unittest.main()
