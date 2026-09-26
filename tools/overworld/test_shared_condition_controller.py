from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld import test_devtools_condition_proof as native_fixtures
from tools.overworld import test_devtools_test_proof as fixtures
from tools.overworld.devtools_test_contract import validate_test


class SharedConditionControllerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SharedProofTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        real = Path(__file__).resolve().parents[2]
        self.test = validate_test(json.loads((
            real / "tests/overworld/test-recipes/profile.condition.packaged-rom-evaluator.json"
        ).read_text()))
        source = self.fixture.root / "tests/overworld/test-recipes/profile.condition.packaged-rom-evaluator.json"
        source.write_text(json.dumps(self.test))
        registry = json.loads((real / "tools/overworld/runtime_proof_registry.json").read_text())
        self.registration = registry["sharedTests"][self.test["id"]]
        self.registration["recipeSha256"] = fixtures.sha(source)
        (self.fixture.root / "tools/overworld/runtime_proof_registry.json").write_text(
            json.dumps(registry))
        _test, self.rows, self.oracle = native_fixtures.fixture()
        self.rows[0]["initialSnapshot"].update(
            prepared=False, fieldAvailable=True, actors=[])
        row = self.rows[1]
        row["action"] = "evaluate-fixed-condition-cases"
        row["snapshot"].update(prepared=True, fieldAvailable=True, actors=[])
        row["receipt"]["snapshot"] = deepcopy(row["snapshot"])
        row["receipt"]["events"] = []
        self.record = deepcopy(self.fixture.record)
        self.record.update(
            test=self.test["id"],
            testSourceSha256=fixtures.sha(source),
            sessionCleanup={"sessionId": "session-proof", "closed": True,
                            "errors": []},
        )
        self.record["fixtureProof"].update(
            registration=self.registration,
            testSourceSha256=fixtures.sha(source),
        )
        self.refresh()

    def refresh(self):
        self.fixture.rows = self.rows
        self.fixture.write_rows()
        self.record["observationsArtifact"] = self.fixture.artifact()
        self.record["evaluation"] = control._replay_shared_test(
            self.test, self.rows, repo=self.fixture.root)

    def finish(self):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch.object(control, "_condition_probe_oracle",
                             return_value=self.oracle):
            return control.finalize_shared_test(
                self.test, self.record, self.fixture.root)

    def test_subjectless_service_accepts_exact_cases_and_controls(self):
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        proof = result["proofAcceptance"]
        self.assertEqual(proof["subjects"], {})
        self.assertEqual(proof["claims"], ["profile-resolution"])
        self.assertEqual(len(proof["measurements"]), 10)
        self.assertEqual(len(proof["controls"]), 11)
        self.assertEqual(proof["observedFrameUnit"],
                         "native-condition-service-cycles")

    def test_missing_cleanup_and_changed_semantics_cannot_pass(self):
        self.record["sessionCleanup"]["closed"] = False
        self.assertFalse(self.finish()["acceptedProof"])
        self.record["sessionCleanup"]["closed"] = True
        self.rows[1]["receipt"]["value"]["receipts"][0]["resultHex"] = (
            "00" * 540)
        self.refresh()
        self.assertTrue(self.record["evaluation"]["passed"])
        result = self.finish()
        self.assertFalse(result["acceptedProof"])


if __name__ == "__main__":
    unittest.main()
