from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_acceleration_acceptance import (
    KIND, REQUIREMENT, FAULTS, contract, measurements, AccelerationNegative, validate_negative_result)
from tools.overworld.test_devtools_acceleration_contract import integration_fixture, replay, SCHEMA, SOURCE
from tools.overworld.devtools_test_contract import TestEvaluator


class AccelerationAcceptanceTests(unittest.TestCase):
    def test_original_contract_and_four_native_rows(self):
        registry = json.loads((Path(__file__).parent / "runtime_proof_registry.json").read_text())
        self.assertEqual(contract(), registry["measurementContracts"][REQUIREMENT])
        test, rows = integration_fixture()
        result = replay(test, rows).finish()
        cleanup = dict(sessionId="host-fixture", sessionCleanup=dict(sessionId="host-fixture", closed=True, errors=[]))
        checked = measurements(result, cleanup)
        self.assertEqual(len(checked), 4)
        self.assertEqual(checked[-1]["value"], 14)
        self.assertTrue(all(row["passed"] for row in checked))

    def test_cleanup_rows_and_missing_lifecycle_reject(self):
        test, rows = integration_fixture()
        good = replay(test, rows).finish()
        for fault in ("cleanup", "row", "motion", "policy", "trace", "reset", "replay"):
            result = deepcopy(good)
            record = dict(sessionId="s", sessionCleanup=dict(sessionId="s", closed=True, errors=[]))
            state = result["measurements"][KIND]["roles"]["WILD"]
            if fault == "cleanup": record["sessionCleanup"]["errors"] = ["close failed"]
            elif fault == "row": result["measurements"][KIND]["measurements"][0]["value"] = [6, 7]
            elif fault == "motion": state["motions"].pop()
            elif fault == "policy": state["policies"].pop()
            elif fault == "trace": state["traces"].pop()
            elif fault == "reset": state["reset"]["scratchRestored"] = False
            else: result["passed"] = False
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                measurements(result, record)

    def test_each_copied_fault_hits_real_evaluator_for_its_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                test, rows = integration_fixture()
                original = deepcopy(rows)
                evaluator = TestEvaluator(test)
                evaluator.install_measurements({KIND: dict(schema=SCHEMA, sourceSha256=SOURCE)})
                control = AccelerationNegative(fault)
                for row in rows:
                    changed = control.mutate(row, evaluator.subjects)
                    if evaluator.observe_record(changed)["state"] == "failed":
                        break
                result = evaluator.finish()
                self.assertTrue(control.applied)
                self.assertFalse(result["passed"], result)
                validate_negative_result(result, fault)
                self.assertEqual(rows, original)
                with self.assertRaises(ValueError):
                    validate_negative_result(dict(passed=False, failures=[dict(code="unrelated-budget")]), fault)


if __name__ == "__main__":
    unittest.main()
