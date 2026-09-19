"""Proof reuse must save work without accepting changed or missing evidence."""
from copy import deepcopy
from contextlib import redirect_stdout
from types import SimpleNamespace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import control
from .proof_reuse import AcceptanceCache, RecorderIndex, acceptance_key, ACCEPTANCE_CACHE
from . import test_devtools_test_proof as fixtures
from .validation import ValidationFailure


class ScopedAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SharedProofTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.scope = {"schema": "overworld-scoped-proof-inputs-v1",
                      "capture": {"sha256": "capture"}, "checker": {"sha256": "checker"}}
        self.f.record["fixtureProof"]["proofInputs"] = deepcopy(self.scope)
        ACCEPTANCE_CACHE.values.clear()

    def finish(self):
        with patch("tools.overworld.proof_inputs.proof_inputs", return_value=self.scope):
            return control.finalize_shared_test(self.f.test, self.f.record, self.f.root)

    def test_same_inputs_replay_once_and_result_is_not_mutable_cache_state(self):
        with patch.object(control, "_replay_shared_test", wraps=control._replay_shared_test) as replay:
            first = self.finish()
            self.assertTrue(first["acceptedProof"], first)
            count = replay.call_count
            self.assertGreaterEqual(count, 3)  # positive plus exact subject faults
            first["proofAcceptance"]["claims"].clear()
            second = self.finish()
            self.assertEqual(replay.call_count, count)
            self.assertEqual(second["proofAcceptance"]["claims"], ["live-actor-identity"])

    def test_checker_only_change_replays_all_controls_without_old_evaluation_equality(self):
        self.assertTrue(self.finish()["acceptedProof"])
        self.scope["checker"]["sha256"] = "new-checker"
        self.f.record["evaluation"]["oldCheckerField"] = 1
        with patch.object(control, "_replay_shared_test", wraps=control._replay_shared_test) as replay:
            result = self.finish()
            self.assertTrue(result["acceptedProof"], result)
            self.assertEqual(result["proofAcceptance"]["replayMode"], "checker-update")
            self.assertGreaterEqual(replay.call_count, 3)

    def test_checker_change_can_recheck_a_replay_only_acceptance_failure(self):
        self.f.record.update(
            state="failed",
            passed=False,
            acceptedProof=False,
            proofAcceptance={
                "eligible": True,
                "reason": "independent shared observation replay did not prove the declared result",
            },
        )
        self.scope["checker"]["sha256"] = "new-checker"
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        self.assertEqual(result["proofAcceptance"]["replayMode"], "checker-update")

    def test_capture_change_cannot_reuse_or_replay_into_acceptance(self):
        self.assertTrue(self.finish()["acceptedProof"])
        self.scope["capture"]["sha256"] = "new-reader"
        with patch.object(control, "_replay_shared_test") as replay:
            result = self.finish()
            self.assertFalse(result["acceptedProof"])
            self.assertIn("fresh memory data", result["proofAcceptance"]["reason"])
            replay.assert_not_called()

    def test_cached_artifact_and_rom_corruption_are_rejected(self):
        for which in ("data", "rom"):
            with self.subTest(which=which):
                self.assertTrue(self.finish()["acceptedProof"])
                path = self.f.observations if which == "data" else self.f.root / "test.nds"
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                self.assertFalse(self.finish()["acceptedProof"])
                path.write_bytes(original)

    def test_same_checker_still_rejects_changed_evaluation_and_failed_job(self):
        self.assertTrue(self.finish()["acceptedProof"])
        original = deepcopy(self.f.record)
        self.f.record["evaluation"]["observedFrames"] += 1
        self.assertFalse(self.finish()["acceptedProof"])
        self.f.record = original
        self.f.record["state"] = "failed"
        self.assertFalse(self.finish()["acceptedProof"])

    def test_deep_native_data_is_not_a_dependency_cycle(self):
        value = {"pose": 1}
        for _ in range(30):
            value = {"native": value}
        self.f.record["extraNativeData"] = value
        self.assertTrue(self.finish()["acceptedProof"])

    def test_current_linked_recipe_inputs_are_bound_in_normal_cache_key(self):
        parent = self.f.root / "build/overworld-devtools/test-reader"
        parent.mkdir()
        manifest = parent / "manifest.json"
        manifest.write_text(json.dumps({"test": self.f.test["id"]}))
        from .runs import file_record
        self.f.record["recorderControlArtifact"] = file_record(manifest, self.f.root)
        old = acceptance_key(self.f.root, self.f.test, self.f.record, self.scope,
                             inputs_for=lambda *_: {"checker": "one"})
        new = acceptance_key(self.f.root, self.f.test, self.f.record, self.scope,
                             inputs_for=lambda *_: {"checker": "two"})
        self.assertNotEqual(old, new)

    def test_source_drift_discards_entire_pending_cache(self):
        changed = deepcopy(self.scope)
        changed["checker"]["sha256"] = "changed-during-acceptance"
        with patch("tools.overworld.proof_inputs.proof_inputs", side_effect=[self.scope, changed]):
            result = control.finalize_shared_test(self.f.test, self.f.record, self.f.root)
        self.assertFalse(result["acceptedProof"], result)
        self.assertEqual(len(ACCEPTANCE_CACHE.values), 0)

    def test_loaded_code_change_requires_fresh_process_even_on_cache_hit(self):
        self.assertTrue(self.finish()["acceptedProof"])
        with patch.object(control, "_controller_code_revision", return_value="edited-source"):
            result = self.finish()
        self.assertFalse(result["acceptedProof"])
        self.assertIn("fresh process", result["proofAcceptance"]["reason"])

    def test_recheck_is_compact_and_never_rewrites_original_manifest(self):
        manifest = self.f.observations.parent / "manifest.json"
        manifest.write_text(json.dumps({**self.f.record, "test": self.f.test["id"]}))
        before = manifest.read_bytes()
        output = io.StringIO()
        with patch.object(control, "REPO", self.f.root), redirect_stdout(output), \
                patch("tools.overworld.proof_inputs.proof_inputs", return_value=self.scope):
            code = control._scenario_recheck(SimpleNamespace(run_id="test-proof", json=True))
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0, result)
        self.assertTrue(result["acceptedProof"])
        self.assertFalse(result["gameStarted"])
        self.assertFalse(result["manifestChanged"])
        self.assertEqual(manifest.read_bytes(), before)
        self.assertNotIn("controls", result)


class ReuseStorageTests(unittest.TestCase):
    def test_cache_is_bounded_and_never_stores_failed_acceptance(self):
        cache = AcceptanceCache(2)
        for key in range(3):
            cache.put(key, {"passed": True, "acceptedProof": True})
        self.assertIsNone(cache.get(0))
        cache.put(4, {"passed": True, "acceptedProof": False})
        self.assertIsNone(cache.get(4))
        self.assertEqual(len(cache.values), 2)

    def test_index_matches_requirement_past_64_unrelated_runs_and_refreshes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for i in range(70):
                folder = root / f"test-{i:03}"
                folder.mkdir()
                (folder / "manifest.json").write_text(json.dumps({"passed": True, "acceptedProof": True,
                    "proofAcceptance": {"requirements": ["wanted" if i == 0 else "other"]}}))
            index = RecorderIndex()
            wanted = root / "test-000/manifest.json"
            self.assertEqual(index.candidates(root, "wanted", lambda: None), [wanted])
            with patch.object(Path, "read_text", side_effect=AssertionError("unchanged file parsed again")):
                self.assertEqual(index.candidates(root, "wanted", lambda: None), [wanted])
            wanted.write_text("{}")
            self.assertEqual(index.candidates(root, "wanted", lambda: None), [])


if __name__ == "__main__":
    unittest.main()
