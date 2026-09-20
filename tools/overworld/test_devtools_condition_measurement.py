from copy import deepcopy
import unittest

from tools.overworld.devtools_condition_measurement import ConditionMeasurement
from tools.overworld.test_devtools_condition_proof import fixture


class ConditionMeasurementTests(unittest.TestCase):
    def test_exact_two_rows_and_detached_result(self):
        test, rows, _oracle = fixture()
        meter = ConditionMeasurement(test)
        meter.observe_record(rows[0])
        result = meter.observe_record(rows[1])
        self.assertTrue(result["ready"])
        self.assertTrue(result["passed"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["observedFrameUnit"],
                         "native-condition-service-cycles")
        original = deepcopy(rows[1])
        result["receipt"].clear()
        self.assertEqual(rows[1], original)
        self.assertTrue(meter.finish()["passed"])

    def test_missing_duplicate_and_bad_native_rows_fail(self):
        test, rows, _oracle = fixture()
        meter = ConditionMeasurement(test)
        meter.observe_record(rows[0])
        self.assertEqual(meter.finish()["failures"][0]["code"],
                         "condition-probe-missing")
        for name in ("status", "free", "clock", "buffer", "fatal"):
            test, rows, _oracle = fixture()
            changed = deepcopy(rows)
            value = changed[1]["receipt"]["value"]
            if name == "status":
                value["receipts"][4]["status"] = 0
            elif name == "free":
                value["allocation"]["released"] = False
            elif name == "clock":
                value["receipts"][0]["returnClock"]["nativeCycle"] = 1000
            elif name == "buffer":
                value["receipts"][0]["resultHex"] = "00"
            else:
                changed[1]["receipt"]["fatal"] = True
            meter = ConditionMeasurement(test)
            meter.observe_record(changed[0])
            result = meter.observe_record(changed[1])
            with self.subTest(name=name):
                self.assertFalse(result["passed"])
                self.assertEqual(result["failures"][0]["code"],
                                 "condition-probe-invalid")


if __name__ == "__main__":
    unittest.main()
