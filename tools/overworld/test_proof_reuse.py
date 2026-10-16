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

    def test_saved_native_pose_tuple_keeps_values_and_rejects_a_changed_pose(self):
        replay_shared = control._replay_shared_test
        def replay_with_pose(*args, **kwargs):
            result = replay_shared(*args, **kwargs)
            result["nativePose"] = (1, 2, 3)
            return result
        self.f.record["evaluation"]["nativePose"] = [1, 2, 3]
        with patch.object(control, "_replay_shared_test", side_effect=replay_with_pose):
            self.assertTrue(self.finish()["acceptedProof"])
            self.f.record["evaluation"]["nativePose"][1] = 99
            self.assertFalse(self.finish()["acceptedProof"])

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


class IsolatedCaptureDependencyTests(unittest.TestCase):
    SOAK = "tools/overworld/devtools_wild_throw_soak_measurement.py"
    NOTICE = "tools/overworld/devtools_throw_notice_walk_commit_measurement.py"
    ZERO = "tools/overworld/devtools_unmounted_zero_stutter_measurement.py"
    HEADROOM = "tools/overworld/devtools_population_headroom_measurement.py"
    READER = "tools/overworld/devtools_pokemon_combat_observer.py"
    KIND = "wild-throw-ground-lock-soak-v1"
    NOTICE_KIND = "throw-notice-walk-commit-v1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = (self.SOAK, self.NOTICE, self.ZERO, self.HEADROOM, self.READER)
        for name in self.paths:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# before\n")
        self.record = {"identity": {"toolInputs": [
            {"path": name, "sha256": control.file_record(self.root / name, self.root)["sha256"]}
            for name in self.paths]}}
        self.recorded = {"capture": {"roots": {
            "game": "same-game", "reader": "same-reader", "actions": "same-actions",
            "tools": "before", "tests": "same-tests"}}}
        self.current = deepcopy(self.recorded)
        self.current["capture"]["roots"]["tools"] = "after"
        (self.root / self.SOAK).write_text("# after\n")

    def change_notice_only(self):
        (self.root / self.SOAK).write_text("# before\n")
        (self.root / self.NOTICE).write_text("# after\n")

    def reuse(self, kinds=("wild-throw-moving-candidate-v1",)):
        test = {"measurements": [{"kind": kind} for kind in kinds]}
        with patch("tools.overworld.devtools_contract.source_paths", return_value=self.paths):
            return control._capture_update_is_unselected(
                test, self.record, self.recorded, self.current, self.root)

    def test_only_unselected_soak_meter_change_can_reuse(self):
        self.assertTrue(self.reuse())

    def test_selected_and_mixed_soak_capture_stay_strict(self):
        self.assertFalse(self.reuse((self.KIND,)))
        self.assertFalse(self.reuse(("wild-throw-moving-candidate-v1", self.KIND)))

    def test_notice_meter_reuses_only_unselected_capture(self):
        self.change_notice_only()
        self.assertTrue(self.reuse())
        self.assertFalse(self.reuse((self.NOTICE_KIND,)))
        self.assertFalse(self.reuse(("wild-throw-moving-candidate-v1", self.NOTICE_KIND)))

    def test_zero_stutter_change_is_isolated_to_its_selected_meter(self):
        (self.root / self.SOAK).write_text("# before\n")
        (self.root / self.ZERO).write_text("# after\n")
        self.assertTrue(self.reuse(("natural-refill-retry-v1",)))
        self.assertFalse(self.reuse(("unmounted-zero-stutter-v1",)))
        self.assertFalse(self.reuse(("natural-refill-retry-v1", "unmounted-zero-stutter-v1")))
        (self.root / self.READER).write_text("# changed reader\n")
        self.assertFalse(self.reuse(("natural-refill-retry-v1",)))

    def test_population_headroom_change_is_isolated_to_its_selected_meter(self):
        (self.root / self.SOAK).write_text("# before\n")
        (self.root / self.HEADROOM).write_text("# after\n")
        self.assertTrue(self.reuse(("natural-refill-retry-v1",)))
        self.assertTrue(self.reuse(("unmounted-zero-stutter-v1",)))
        self.assertFalse(self.reuse(("population-headroom-v1",)))
        self.assertFalse(self.reuse(("natural-refill-retry-v1", "population-headroom-v1")))
        (self.root / self.READER).write_text("# changed reader\n")
        self.assertFalse(self.reuse(("natural-refill-retry-v1",)))

    def test_notice_meter_keeps_other_inputs_strict(self):
        self.change_notice_only()
        (self.root / self.READER).write_text("# changed shared reader\n")
        self.assertFalse(self.reuse())
        (self.root / self.READER).write_text("# before\n")
        for name in ("game", "reader", "actions"):
            with self.subTest(root=name):
                old = self.current["capture"]["roots"][name]
                self.current["capture"]["roots"][name] = "changed"
                self.assertFalse(self.reuse())
                self.current["capture"]["roots"][name] = old
        self.record["identity"]["toolInputs"].pop()
        self.assertFalse(self.reuse())

    def test_reader_change_stays_strict_even_with_unselected_soak(self):
        (self.root / self.READER).write_text("# changed shared reader\n")
        self.assertFalse(self.reuse())

    def test_game_reader_and_action_roots_stay_strict(self):
        for name in ("game", "reader", "actions"):
            with self.subTest(root=name):
                old = self.current["capture"]["roots"][name]
                self.current["capture"]["roots"][name] = "changed"
                self.assertFalse(self.reuse())
                self.current["capture"]["roots"][name] = old
        self.current["capture"]["roots"]["extra"] = "changed"
        self.assertFalse(self.reuse())

    def test_missing_and_malformed_source_inventory_stay_strict(self):
        retained = self.record["identity"]["toolInputs"]
        self.record["identity"]["toolInputs"] = retained[:-1]
        self.assertFalse(self.reuse())
        self.record["identity"]["toolInputs"] = deepcopy(retained)
        self.record["identity"]["toolInputs"][0]["extra"] = True
        self.assertFalse(self.reuse())


class PinnedWildMovingFixtureReuseTests(unittest.TestCase):
    PAIRS = {
        "tools/overworld/devtools_test_contract.py": (
            "690cc0343f541505693180fe82e4f68ade32c4a86c2380c00717abd8abbe298a",
            "da0afb046de7c94f89d01b8ca584eef8bd86196a3ced4f7a13f5d7b267914141",
        ),
        "tools/overworld/devtools_wild_throw_moving_candidate_measurement.py": (
            "be4665931e7d84452cc2b7c32d43dfb3d7f32aedc6464d228c77ca31e32795da",
            "3bab464f394df3a5b05189e632b4ae37286aaba2c64e1bb8d76531c714415474",
        ),
    }
    SOAK = "tools/overworld/devtools_wild_throw_soak_measurement.py"
    READER = "tools/overworld/devtools_pokemon_combat_observer.py"
    MOVING = "wild-throw-moving-candidate-v1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = (*self.PAIRS, self.SOAK, self.READER)
        self.before = {path: pair[0] for path, pair in self.PAIRS.items()}
        self.before.update({self.SOAK: "a" * 64, self.READER: "b" * 64})
        self.after = {path: pair[1] for path, pair in self.PAIRS.items()}
        self.after.update({self.SOAK: self.before[self.SOAK], self.READER: self.before[self.READER]})
        self.record = {"identity": {"toolInputs": [
            {"path": path, "sha256": self.before[path]} for path in self.paths]}}
        self.recorded = {"capture": {"roots": {
            "game": "same-game", "reader": "same-reader", "actions": "same-actions",
            "tools": "before", "tests": "same-tests"}}}
        self.current = deepcopy(self.recorded)
        self.current["capture"]["roots"]["tools"] = "after"

    def reuse(self, kinds=("follower-throw-player-damage-v1",)):
        test = {"measurements": [{"kind": kind} for kind in kinds]}
        def current_file(path, _repo):
            return {"sha256": self.after[path.relative_to(self.root).as_posix()]}
        with patch("tools.overworld.devtools_contract.source_paths", return_value=self.paths), \
                patch.object(control, "file_record", side_effect=current_file):
            return control._capture_update_is_unselected(
                test, self.record, self.recorded, self.current, self.root)

    def test_exact_paired_change_reuses_only_unselected_capture(self):
        self.assertTrue(self.reuse())
        self.after[self.SOAK] = "c" * 64
        self.assertTrue(self.reuse())  # Existing isolated soak change can coexist.

    def test_selected_and_mixed_moving_capture_cannot_reuse(self):
        self.assertFalse(self.reuse((self.MOVING,)))
        self.assertFalse(self.reuse(("follower-throw-player-damage-v1", self.MOVING)))

    def test_partial_pair_and_wrong_hashes_cannot_reuse(self):
        for path, (old, new) in self.PAIRS.items():
            with self.subTest(path=path, fault="partial"):
                self.after[path] = old
                self.assertFalse(self.reuse())
                self.after[path] = new
            with self.subTest(path=path, fault="wrong-current"):
                self.after[path] = "0" * 64
                self.assertFalse(self.reuse())
                self.after[path] = new
            with self.subTest(path=path, fault="wrong-saved"):
                saved = next(item for item in self.record["identity"]["toolInputs"]
                             if item["path"] == path)
                saved["sha256"] = "0" * 64
                self.assertFalse(self.reuse())
                saved["sha256"] = old

    def test_other_source_root_or_inventory_change_cannot_reuse(self):
        self.after[self.READER] = "c" * 64
        self.assertFalse(self.reuse())
        self.after[self.READER] = self.before[self.READER]
        for root in ("game", "reader", "actions"):
            with self.subTest(root=root):
                self.current["capture"]["roots"][root] = "changed"
                self.assertFalse(self.reuse())
                self.current["capture"]["roots"][root] = self.recorded["capture"]["roots"][root]
        self.record["identity"]["toolInputs"].pop()
        self.assertFalse(self.reuse())


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
