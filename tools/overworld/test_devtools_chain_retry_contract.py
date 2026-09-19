"""Typed retry setup cannot restore the retired forced-count/RNG workflow."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import validate_test

ROOT = Path(__file__).resolve().parents[2]


class ChainRetryContractTests(unittest.TestCase):
    def recipe(self):
        return json.loads((ROOT / "tests/overworld/test-recipes/chain.ledyba-retry.json").read_text())

    def test_natural_acquisition_then_one_control_is_valid(self):
        value = validate_test(self.recipe())
        self.assertEqual(value["mode"], "prepared")
        self.assertEqual(sum(a["op"] == "chain-retry" for a in value["actions"]), 1)
        self.assertTrue(all(a["op"] in ("assert", "step", "wait") for a in value["setup"]))

    def test_rejects_wrong_mode_subject_or_extra_control(self):
        original = self.recipe()
        variants = []
        value = deepcopy(original); value["mode"] = "normal"; variants.append(value)
        value = deepcopy(original); value["subjects"][0]["species"] = 155; variants.append(value)
        value = deepcopy(original); value["actions"].append(deepcopy(value["actions"][2])); variants.append(value)
        value = deepcopy(original); value["actions"][2]["args"]["address"] = 0x02000000; variants.append(value)
        value = deepcopy(original); value["measurements"] = []; variants.append(value)
        value = deepcopy(original); value["setup"].append(deepcopy(value["actions"][0])); variants.append(value)
        for index, value in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_test(value)

    def test_original_fixture_contract_remains_verbatim(self):
        old = json.loads((ROOT / "documentation/overworld-system/archive/chain-retry-legacy-measurements.json").read_text())
        digest = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, "4f11a37a8fc638e288bb4c0b7a6aee530d870ef4f0e41eb4dfebc8d7d19696e1")


if __name__ == "__main__":
    unittest.main()
