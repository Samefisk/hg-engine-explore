"""Current progress must be cheap, truthful, and retain failed repetitions."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.overworld import control
from tools.overworld.progress import record_resolution, resolution_for, summarize
from tools.overworld.runs import RUN_SCHEMA, digest_value, file_record, run_id_for
from tools.overworld.validation import ValidationFailure


def receipt(scenario, passed, steps=None):
    document = {"schema": RUN_SCHEMA, "proofLevel": "S3", "costTier": 3,
                "identity": {"kind": "scenario", "target": "case", "source": {"content": "one"},
                             "scenarioRevision": digest_value(scenario)},
                "result": {"passed": passed, "steps": steps or [{"passed": passed, "elapsedSeconds": 3.0,
                    "failureStage": "fixture-preflight"}]}}
    document["runId"], document["resultSha256"] = run_id_for(
        document["identity"], document["result"], "S3", 3)
    return document


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.scenario = {"status": "active", "proofLevel": "S3"}

    def test_good_run_cannot_hide_failed_repetition(self):
        directory = self.root / "build/overworld-runs"
        directory.mkdir(parents=True)
        for name, passed in (("first", False), ("second", True)):
            (directory / f"{name}.json").write_text(json.dumps(receipt(self.scenario, passed)))
        result = summarize(self.root, {"case": self.scenario}, {"content": "one"})
        self.assertEqual(result["counts"]["failed"], 1)
        self.assertEqual(result["scenarios"][0]["elapsedSeconds"], 6)
        self.assertEqual(result["acceptance"], "not-evaluated")

    def test_planned_and_untested_are_distinct(self):
        result = summarize(self.root, {"case": self.scenario,
            "missing": {"status": "planned", "proofLevel": "S4"}}, {})
        self.assertEqual(result["counts"]["untested"], 1)
        self.assertEqual(result["counts"]["planned"], 1)

    def test_progress_does_not_execute_checks_or_probe_emulator(self):
        with (mock.patch.object(control, "REPO", self.root),
              mock.patch.object(control, "load_scenarios", return_value={"case": self.scenario}),
              mock.patch.object(control, "source_record", return_value={}),
              mock.patch.object(control, "_json"),
              mock.patch.object(control, "_roadmap_runtime_fixture") as fixture,
              mock.patch.object(control, "_roadmap_static_results") as checks,
              mock.patch.object(control, "emulator_record") as emulator):
            self.assertEqual(control.main(["progress", "--json"]), 0)
            fixture.assert_not_called()
            checks.assert_not_called()
            emulator.assert_not_called()

    def test_changed_source_makes_recorded_pass_stale(self):
        directory = self.root / "build/overworld-runs"
        directory.mkdir(parents=True)
        (directory / "one.json").write_text(json.dumps(receipt(self.scenario, True)))
        result = summarize(self.root, {"case": self.scenario}, {"content": "two"})
        self.assertEqual(result["counts"]["stale"], 1)

    def review(self, failed, replacement):
        evidence = self.root / "review.txt"
        evidence.write_text("Captured host error, no gameplay failure measured.")
        return record_resolution(self.root, failed, replacement, "host", "Host process failed before collection.",
                                 "codex", evidence)

    def test_resolution_needs_current_passing_replacement_and_review_evidence(self):
        failed = receipt(self.scenario, False)
        replacement = receipt(self.scenario, True)
        review = self.review(failed, replacement)
        self.assertIsNone(resolution_for(self.root, failed, set()))
        self.assertEqual(resolution_for(self.root, failed, {replacement["runId"]}), review)
        (self.root / "review.txt").write_text("changed")
        self.assertIsNone(resolution_for(self.root, failed, {replacement["runId"]}))

    def test_observed_failed_behavior_cannot_be_dismissed_as_host_failure(self):
        failed = receipt(self.scenario, False, [{"passed": False, "proofClaims": {"frame-pacing": False}}])
        with self.assertRaisesRegex(ValidationFailure, "gameplay failures"):
            self.review(failed, receipt(self.scenario, True))

    def test_wrong_candidate_cannot_resolve_failure(self):
        replacement = receipt(self.scenario, True)
        replacement["identity"]["source"] = {"content": "two"}
        with self.assertRaisesRegex(ValidationFailure, "same exact"):
            self.review(receipt(self.scenario, False), replacement)

    def test_runtime_timeout_without_claims_cannot_be_waived(self):
        for stage in (None, "runtime"):
            failed = receipt(self.scenario, False, [{"passed": False,
                "failureStage": stage, "resultError": "timeout"}])
            with self.assertRaisesRegex(ValidationFailure, "gameplay failures"):
                self.review(failed, receipt(self.scenario, True))

    def test_invalid_receipt_shape_does_not_abort_progress(self):
        directory = self.root / "build/overworld-runs"
        directory.mkdir(parents=True)
        for index, value in enumerate(([], None, "bad")):
            document = receipt(self.scenario, True)
            document["identity"] = value
            document["runId"], document["resultSha256"] = run_id_for(value, document["result"], "S3", 3)
            (directory / f"{index}.json").write_text(json.dumps(document))
        result = summarize(self.root, {"case": self.scenario}, {})
        self.assertEqual(len(result["invalidReceipts"]), 3)

    def test_interrupted_review_write_preserves_existing_records(self):
        from tools.overworld.progress import DISPOSITIONS
        path = self.root / DISPOSITIONS
        path.parent.mkdir(parents=True)
        original = '{"schemaVersion": 1, "records": []}'
        path.write_text(original)
        with mock.patch("tools.overworld.progress.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.review(receipt(self.scenario, False), receipt(self.scenario, True))
        self.assertEqual(path.read_text(), original)

    def test_bad_disposition_ledger_is_a_reported_gap(self):
        from tools.overworld.progress import DISPOSITIONS
        path = self.root / DISPOSITIONS
        path.parent.mkdir(parents=True)
        path.write_text('{"schemaVersion": 1, "records": [null]}')
        result = summarize(self.root, {"case": self.scenario}, {})
        self.assertTrue(result["failureLedgerErrors"])

    def test_invalid_nested_file_record_does_not_crash_progress(self):
        directory = self.root / "build/overworld-runs"
        directory.mkdir(parents=True)
        document = receipt(self.scenario, True)
        document["identity"]["rom"] = {"path": [], "sha256": "bad"}
        document["runId"], document["resultSha256"] = run_id_for(
            document["identity"], document["result"], "S3", 3)
        (directory / "bad.json").write_text(json.dumps(document))
        result = summarize(self.root, {"case": self.scenario}, {})
        self.assertEqual(len(result["invalidReceipts"]), 1)

    def test_invalid_nested_review_record_is_a_reported_gap(self):
        from tools.overworld.progress import DISPOSITIONS
        self.review(receipt(self.scenario, False), receipt(self.scenario, True))
        path = self.root / DISPOSITIONS
        document = json.loads(path.read_text())
        document["records"][0]["replacementRunId"] = []
        path.write_text(json.dumps(document))
        result = summarize(self.root, {"case": self.scenario}, {})
        self.assertTrue(result["failureLedgerErrors"])

    def test_old_schema_is_history_not_a_new_invalid_attempt(self):
        directory = self.root / "build/overworld-runs"
        directory.mkdir(parents=True)
        document = receipt(self.scenario, True)
        document["schema"] = "overworld-system-run-v3"
        (directory / "old.json").write_text(json.dumps(document))
        result = summarize(self.root, {"case": self.scenario}, {})
        self.assertEqual(result["invalidReceipts"], [])
        self.assertEqual(len(result["historicalReceipts"]), 1)


class SharedProgressTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = {"content": "shared-source"}
        self.scenarios = {"shared.case": {"status": "active", "proofLevel": "S3",
            "adapter": {"kind": "devtools-test", "test": "shared.case", "claims": ["live-actor-identity"]}}}
        recipe = self.root / "tests/overworld/test-recipes/shared.case.json"
        recipe.parent.mkdir(parents=True)
        recipe.write_text(json.dumps({"fixture": {"rom": "test.nds", "save": "test.sav"}}))
        self.registration = {"recipeSha256": file_record(recipe, self.root)["sha256"],
            "claims": ["live-actor-identity"], "requirements": ["shared.identity"], "proofLevel": "S3"}
        registry = self.root / "tools/overworld/runtime_proof_registry.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps({"sharedTests": {"shared.case": self.registration}}))
        self.identity = {"sessionId": "session-one"}
        for key, label in (("rom", "test.nds"), ("save", "test.sav"), ("debugDescriptor", "build/overworld-system.debug.json")):
            path = self.root / label; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("host fixture")
            self.identity[key] = file_record(path, self.root)

    def write_run(self, name="one", *, passed=True, accepted=True, state=None):
        directory = self.root / "build/overworld-devtools" / ("test-" + name)
        directory.mkdir(parents=True)
        observations = directory / "observations.jsonl"; observations.write_text("host observation fixture\n")
        document = {"runId": directory.name, "test": "shared.case", "execution": "shared-devtools",
            "state": state or ("completed" if passed else "failed"), "passed": passed, "acceptedProof": accepted,
            "sessionId": "session-one", "identity": self.identity, "elapsedSeconds": 4,
            "testSourceSha256": self.registration["recipeSha256"],
            "fixtureProof": {"passed": True, "source": self.source, "registration": self.registration},
            "proofAcceptance": {"source": self.source, "eligible": accepted,
                "claims": self.registration["claims"], "requirements": self.registration["requirements"], "proofLevel": "S3"},
            "observationsArtifact": file_record(observations, self.root),
            "evaluation": {"observedFrames": 16, "failures": [] if passed else [{"code": "subject-missing"}]}}
        path = directory / "manifest.json"; path.write_text(json.dumps(document))
        return path, document

    def summary(self): return summarize(self.root, self.scenarios, self.source)

    def test_shared_accepted_record_is_visible_without_reacceptance_or_subprocess(self):
        self.write_run()
        with mock.patch("subprocess.run", side_effect=AssertionError("progress must not run checks")):
            result = self.summary()
        self.assertEqual(result["scenarios"][0]["state"], "recorded-pass")
        self.assertTrue(result["scenarios"][0]["runs"][0]["acceptedProofRecorded"])
        self.assertEqual(result["acceptance"], "not-evaluated")

    def test_failed_and_canceled_repetitions_survive_a_later_pass(self):
        self.write_run("failure", passed=False, accepted=False)
        self.write_run("canceled", passed=False, accepted=False, state="canceled")
        self.write_run("pass")
        row = self.summary()["scenarios"][0]
        self.assertEqual(row["state"], "failed"); self.assertEqual(len(row["runs"]), 3)
        self.assertEqual(row["elapsedSeconds"], 12)

    def test_changed_source_recipe_or_artifact_is_stale_but_new_history_is_not(self):
        path, _ = self.write_run()
        self.assertEqual(self.summary()["scenarios"][0]["state"], "recorded-pass")
        (path.parent / "notes.txt").write_text("new output is not a proof input")
        self.assertEqual(self.summary()["scenarios"][0]["state"], "recorded-pass")
        (path.parent / "observations.jsonl").write_text("changed")
        self.assertEqual(self.summary()["scenarios"][0]["state"], "stale")
        self.assertEqual(summarize(self.root, self.scenarios, {"content": "changed"})["scenarios"][0]["state"], "stale")

    def test_diagnostic_pass_and_malformed_manifest_never_become_accepted(self):
        self.write_run(accepted=False)
        self.assertEqual(self.summary()["scenarios"][0]["state"], "recorded-diagnostic")
        path, document = self.write_run("bad"); document["identity"] = []
        path.write_text(json.dumps(document))
        self.assertEqual(len(self.summary()["invalidReceipts"]), 1)

    def test_scenario_status_and_history_share_the_same_read_only_records(self):
        self.write_run()
        with mock.patch.object(control, "REPO", self.root), \
             mock.patch.object(control, "load_scenarios", return_value=self.scenarios), \
             mock.patch.object(control, "source_record", return_value=self.source), \
             mock.patch.object(control, "_json") as output, \
             mock.patch.object(control, "_roadmap_runtime_fixture") as fixture:
            for command in ("status", "history"):
                self.assertEqual(control.main(["scenario", command, "shared.case", "--json"]), 0)
                self.assertEqual(output.call_args.args[0]["state"], "recorded-pass")
            fixture.assert_not_called()

    def test_final_gate_replays_shared_receipt_instead_of_trusting_recorded_bit(self):
        self.write_run()
        with mock.patch.object(control, "REPO", self.root), \
             mock.patch.object(control, "finalize_shared_test", return_value={"acceptedProof": False,
                 "proofAcceptance": {"reason": "bad retained subject"}}) as replay:
            result = control._roadmap_runtime_evidence(self.scenarios, {"passed": True},
                                                       current_source=self.source, current_emulator={})
        replay.assert_called_once()
        self.assertEqual(result["acceptedScenarios"], {})
        self.assertEqual(result["currentFailures"][0]["reason"], "bad retained subject")

    def test_old_unfinished_and_unknown_attempts_do_not_hide_current_pass(self):
        old_path, old = self.write_run("old", passed=False, accepted=False, state="running")
        old["attemptIdentity"] = {"schemaVersion": 1, "source": {"content": "old"},
                                  "testSourceSha256": self.registration["recipeSha256"]}
        old_path.write_text(json.dumps(old))
        unknown_path, unknown = self.write_run("unknown", passed=False, accepted=False)
        unknown.pop("fixtureProof"); unknown.pop("testSourceSha256"); unknown.pop("identity")
        unknown_path.write_text(json.dumps(unknown))
        self.write_run("pass")
        row = self.summary()["scenarios"][0]
        self.assertEqual(row["state"], "recorded-pass")
        self.assertEqual({run["runId"]: run["state"] for run in row["runs"]},
                         {"test-old": "stale", "test-unknown": "unverified", "test-pass": "recorded-pass"})
        with mock.patch.object(control, "REPO", self.root), mock.patch.object(control, "finalize_shared_test", return_value={
                "acceptedProof": True, "proofAcceptance": {"proofLevel": "S3", "requirements": ["shared.identity"],
                                                          "claims": ["live-actor-identity"]}}):
            result = control._roadmap_runtime_evidence(self.scenarios, {"passed": True},
                                                       current_source=self.source, current_emulator={})
        self.assertIn("shared.case", result["acceptedScenarios"])
        self.assertEqual(result["currentFailures"], [])

    def test_current_early_failure_does_not_need_a_created_session(self):
        path, document = self.write_run(passed=False, accepted=False)
        document.pop("identity"); document.pop("sessionId"); document["fixtureProof"] = None
        document["attemptIdentity"] = {"schemaVersion": 1, "source": self.source,
                                       "testSourceSha256": self.registration["recipeSha256"]}
        path.write_text(json.dumps(document))
        self.assertEqual(self.summary()["scenarios"][0]["state"], "failed")
        document.pop("attemptIdentity")
        document["fixtureProof"] = {"source": self.source, "registration": self.registration, "passed": False}
        path.write_text(json.dumps(document))
        self.assertEqual(self.summary()["scenarios"][0]["state"], "failed")
        self.assertEqual(summarize(self.root, self.scenarios, {"content": "new"})["scenarios"][0]["state"], "stale")

    def test_current_unfinished_attempt_is_explicit_not_assumed_alive(self):
        self.write_run(passed=False, accepted=False, state="running")
        row = self.summary()["scenarios"][0]
        self.assertEqual(row["state"], "unfinished")
        self.assertEqual(row["runs"][0]["liveOwnership"], "not-checked")
        with mock.patch.object(control, "REPO", self.root):
            result = control._roadmap_runtime_evidence(self.scenarios, {"passed": True},
                                                       current_source=self.source, current_emulator={})
        self.assertEqual(len(result["currentFailures"]), 1)

    def test_preflight_missing_file_failure_is_current_until_input_is_fixed(self):
        path, document = self.write_run(passed=False, accepted=False)
        missing = self.root / "build/overworld-system.debug.json"; missing.unlink()
        files = {key: file_record(self.root / record["path"], self.root) for key, record in self.identity.items() if key != "sessionId"}
        document.pop("identity"); document["fixtureProof"] = None
        document["attemptIdentity"] = {"schemaVersion": 1, "source": self.source,
            "testSourceSha256": self.registration["recipeSha256"], "files": files}
        path.write_text(json.dumps(document))
        self.assertEqual(self.summary()["scenarios"][0]["state"], "failed")
        missing.write_text("new current descriptor")
        self.assertEqual(self.summary()["scenarios"][0]["state"], "stale")


if __name__ == "__main__":
    unittest.main()
