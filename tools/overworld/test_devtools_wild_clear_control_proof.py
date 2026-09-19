"""Controller checks and copied-data faults through the unchanged reducer."""
from copy import deepcopy
import unittest
from tools.overworld.devtools_wild_clear_control_proof import KIND,FAULTS,measurements,validate_negative_result,contract
from tools.overworld.test_devtools_wild_clear_control_measurement import replay


class WildClearControlProofTests(unittest.TestCase):
    def record(self):return dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[]))

    def test_four_exact_rows(self):
        result=measurements(replay(),self.record())
        self.assertEqual(len(result),4)
        self.assertEqual(sum(map(len,contract().values())),4)

    def test_startup_noop_checked_but_not_walk_credit(self):
        result=replay(startup_noop=True)
        self.assertEqual(len(measurements(result,self.record())),4)
        result["measurements"][KIND]["natural"]["idleNoopClears"][0]["data"]["before"]["active"]=1
        with self.assertRaises(ValueError):measurements(result,self.record())

    def test_all_copied_faults_fail_for_expected_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):validate_negative_result(replay(fault),fault)

    def test_raw_missing_clear_and_cleanup_fail(self):
        for fault in ("clear","cleanup","closed","clock"):
            result=replay();record=self.record();meter=result["measurements"][KIND]
            if fault=="clear":meter["natural"]["clearReceipts"]=[]
            elif fault=="cleanup":record["sessionCleanup"]["closed"]=False
            elif fault=="closed":meter["closed"]=False
            else:meter["control"]["restoredClock"]["frame"]+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):measurements(result,record)

    def test_unrelated_failure_rejected(self):
        with self.assertRaisesRegex(ValueError,"unrelated"):
            validate_negative_result(dict(passed=False,failures=["other fault"]),FAULTS[0])


if __name__=="__main__":unittest.main()
