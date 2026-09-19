"""Acceptance rows require complete replay and clean native-control disposal."""
from copy import deepcopy
import unittest

from tools.overworld.chain_retry_proof import KIND, RULES, measurements
from tools.overworld.test_devtools_chain_retry_measurement import fixture, replay


class ChainRetryProofTests(unittest.TestCase):
    def setUp(self):
        _, result = replay(fixture())
        self.replay = {"measurements": {KIND: result}}
        self.record = {"sessionId": "owned", "sessionCleanup": {"sessionId": "owned", "closed": True, "errors": []},
            "chainRetryCleanup": {"closed": True, "advancedFrames": 0, "chainRetryControl": {
                "closed": True, "failure": None, "pendingWrites": 0, "guestMemoryWrites": 0, "injected": True,
                "acceptedProof": False, "subject": deepcopy(result["retryProof"]["arm"]["chainRetryControl"]["subject"]),
                "injection": deepcopy(result["retryProof"]["injection"])}}}

    def test_full_replay_supplies_exact_rows(self):
        rows = measurements(self.replay, self.record)
        self.assertEqual([r["name"] for r in rows], [r[1] for r in RULES])
        self.assertTrue(all(r["passed"] and r["value"] == 1 for r in rows))

    def test_incomplete_check_or_cleanup_cannot_pass(self):
        for key in self.replay["measurements"][KIND]["proofChecks"]:
            value = deepcopy(self.replay); value["measurements"][KIND]["proofChecks"][key] = False
            with self.subTest(check=key), self.assertRaises(ValueError):
                measurements(value, self.record)
        for field, value in (("closed", False), ("failure", "parent still in flight"),
                             ("pendingWrites", 1), ("guestMemoryWrites", 1), ("injected", False),
                             ("subject", None), ("subject", {"species": 155}),
                             ("injection", None), ("injection", {"attemptId": 999}), ("acceptedProof", True)):
            record = deepcopy(self.record); record["chainRetryCleanup"]["chainRetryControl"][field] = value
            with self.subTest(cleanup=field), self.assertRaises(ValueError):
                measurements(self.replay, record)


if __name__ == "__main__":
    unittest.main()
