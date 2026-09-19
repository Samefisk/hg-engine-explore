"""Controller acceptance with synthetic package/bridge data; no gameplay proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld import test_devtools_test_proof as fixtures
from tools.overworld.test_devtools_actor_inspect_measurement import fixture
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test


class SharedActorInspectControllerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SharedProofTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        root = Path(__file__).resolve().parents[2]
        self.test = validate_test(json.loads((root / "tests/overworld/test-recipes/actor.inspect-current-and-stale.json").read_text()))
        path = self.f.root / "tests/overworld/test-recipes/actor.inspect-current-and-stale.json"
        path.write_text(json.dumps(self.test))
        registry = json.loads((root / "tools/overworld/runtime_proof_registry.json").read_text())
        self.registration = registry["sharedTests"][self.test["id"]]
        self.registration["recipeSha256"] = fixtures.sha(path)
        (self.f.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps(registry))
        _, self.rows, self.oracle = fixture()
        evaluator = TestEvaluator(self.test)
        self.rows[1]["receipt"] = evaluator.bind("mankey", self.rows[1]["snapshot"])
        self.rows[-1]["receipt"]["snapshot"] = deepcopy(self.rows[-1]["snapshot"])
        self.record = deepcopy(self.f.record)
        self.record.update(test=self.test["id"], testSourceSha256=fixtures.sha(path),
            sessionCleanup=dict(sessionId="session-proof", closed=True, errors=[]))
        self.record["fixtureProof"].update(registration=self.registration, testSourceSha256=fixtures.sha(path))
        self.refresh()

    def refresh(self):
        self.f.rows = self.rows; self.f.write_rows()
        self.record["observationsArtifact"] = self.f.artifact()
        self.record["evaluation"] = control._replay_shared_test(self.test, self.rows, repo=self.f.root)

    def finish(self):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
             patch.object(control, "_actor_inspect_probe_oracle", return_value=self.oracle):
            return control.finalize_shared_test(self.test, self.record, self.f.root)

    def test_exact_registered_native_lookup_accepts_only_controlled_action(self):
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        proof = result["proofAcceptance"]
        self.assertEqual(proof["claims"], ["controlled-action"])
        self.assertEqual(proof["requirements"], ["shared.actor-inspect-handle-v1"])
        self.assertEqual((proof["observedFrames"], proof["observedFrameUnit"]), (1, "native-inspect-cycles"))
        self.assertEqual(len(proof["measurements"]), 6)
        self.assertEqual(len(proof["controls"]), 12)
        self.assertTrue(all(v["rejected"] for v in proof["controls"].values()))

    def test_source_fixture_session_and_cleanup_each_fail_closed(self):
        original = deepcopy(self.record)
        for fault in ("source", "preflight", "rom", "session", "cleanup"):
            self.record = deepcopy(original)
            if fault == "source": self.record["fixtureProof"]["source"] = {"hash": "stale"}
            elif fault == "preflight": self.record["fixtureProof"]["passed"] = False
            elif fault == "rom": self.record["identity"]["rom"]["sha256"] = "0" * 64
            elif fault == "session": self.record["sessionId"] = "session-other"
            else: self.record["sessionCleanup"]["closed"] = False
            with self.subTest(fault=fault): self.assertFalse(self.finish()["acceptedProof"])

    def test_manual_or_unregistered_evidence_never_accepts(self):
        self.record["execution"] = "manual"
        self.assertFalse(self.finish()["acceptedProof"])
        self.record["execution"] = "shared-devtools"
        path = self.f.root / "tools/overworld/runtime_proof_registry.json"
        registry = json.loads(path.read_text()); registry["sharedTests"].pop(self.test["id"])
        path.write_text(json.dumps(registry))
        self.assertFalse(self.finish()["acceptedProof"])

    def test_changed_packaged_entry_cannot_pass_readiness_only(self):
        self.rows[-1]["receipt"]["value"]["receipts"][0]["serviceIdentity"]["entrySha256"] = "ff" * 32
        self.refresh()
        self.assertTrue(self.record["evaluation"]["passed"])
        self.assertFalse(self.finish()["acceptedProof"])

    def test_wrong_exported_measurement_cannot_pass_controller(self):
        from tools.overworld import devtools_actor_inspect_proof as proof
        real = proof.actor_inspect_measurements
        def changed(*args, **kwargs):
            result = real(*args, **kwargs)
            result["measurements"][0]["value"] = True
            return result
        with patch.object(proof, "actor_inspect_measurements", side_effect=changed):
            self.assertFalse(self.finish()["acceptedProof"])


if __name__ == "__main__": unittest.main()
