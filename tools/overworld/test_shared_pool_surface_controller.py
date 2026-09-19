"""Real controller replay of synthetic surface receipts; no game acceptance."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from tools.overworld import control, test_devtools_test_proof as pool_tests
from tools.overworld.test_devtools_spawn_surface_integration import surface_stream


KIND = "pool-spawn-surface-v1"
REQUIREMENTS = ["shared.ledyba-pool-site-v1", "shared.ledyba-pool-surface-v1"]
CLAIMS = ["live-actor-identity", "profile-resolution", "natural-input", "logical-commit",
          "control-release", "terrain-selection"]


def extendable_surface_stream():
    stream = surface_stream()
    # surface_stream inserts one extra native receipt into saved rows. Keep
    # its generator clock aligned when the pool fixture appends idle frames.
    stream.sequence += 1
    stream.actor["engineIdentity"]["id_lookup"] = {"eligible_count": 1, "pointer_matches": True}
    return stream


class SharedPoolSurfaceControllerTests(unittest.TestCase):
    write_rows = pool_tests.SharedPoolProofTests.write_rows
    artifact = pool_tests.SharedPoolProofTests.artifact
    current = pool_tests.SharedPoolProofTests.current
    replay = pool_tests.SharedPoolProofTests.replay

    def setUp(self):
        # Reuse the own-site controller fixture and native surface receipt
        # factory. Only sealed host input loading is substituted, not replay.
        with patch("tools.overworld.test_devtools_spawn_measurement.landing_stream",
                   side_effect=extendable_surface_stream):
            pool_tests.SharedPoolProofTests.setUp(self)
        self.inputs = {KIND: self.inputs["pool-spawn-v1"]}
        self.test.update(requirements=list(REQUIREMENTS),
            measurements=[{"kind": KIND, "subject": "subject"}],
            assertions=[{"kind": "measurement-complete", "measurement": KIND}])
        self.registration.update(evaluator=KIND, requirements=list(REQUIREMENTS), claims=list(CLAIMS))
        self.save_registration()
        self.record["evaluation"] = self.replay()
        self.assertTrue(self.record["evaluation"]["passed"], self.record["evaluation"])

    def save_registration(self):
        source = self.root / "tests/overworld/test-recipes/test.actor.json"
        source.write_text(json.dumps(self.test))
        digest = pool_tests.sha(source)
        self.registration["recipeSha256"] = digest
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
            "sharedTests": {self.test["id"]: self.registration}}))
        self.record["testSourceSha256"] = digest
        self.record["fixtureProof"].update(registration=deepcopy(self.registration), testSourceSha256=digest)

    def test_surface_registration_retains_exact_own_site_contract(self):
        registration, _ = control._shared_test_registration(self.test, self.root)
        self.assertEqual(registration["requirements"], REQUIREMENTS)
        self.assertEqual(registration["claims"], CLAIMS)
        self.assertEqual(registration["proofLevel"], "S3")
        original_test, original_registration = deepcopy(self.test), deepcopy(self.registration)
        for requirements in ([REQUIREMENTS[1]], [REQUIREMENTS[0]], list(reversed(REQUIREMENTS))):
            with self.subTest(requirements=requirements):
                self.test = deepcopy(original_test)
                self.registration = deepcopy(original_registration)
                self.test["requirements"] = self.registration["requirements"] = requirements
                self.save_registration()
                with self.assertRaises(control.ValidationFailure):
                    control._shared_test_registration(self.test, self.root)
        self.test, self.registration = original_test, original_registration
        self.registration["claims"].remove("logical-commit")
        self.save_registration()
        with self.assertRaises(control.ValidationFailure):
            control._shared_test_registration(self.test, self.root)

    def test_real_measurements_add_surface_without_losing_placement(self):
        result = self.replay()
        measured = control._shared_pool_measurements(result, KIND)
        self.assertEqual([m["claim"] for m in measured], CLAIMS + ["terrain-selection"])
        self.assertEqual([m["name"] for m in measured][-2:],
                         ["pool-spawn-loaded-surface-permitted", "pool-spawn-native-terminal-height"])
        self.assertTrue(result["measurements"][KIND]["placement"]["passed"])
        self.assertFalse(result["acceptedProof"])

    def test_measurements_reject_missing_flags_and_wrong_surface_identity(self):
        valid = self.replay()
        for field in ("loadedTerrainVerified", "authoredSurfaceExcluded", "terminalHeightVerified",
                      "nativeLandingY", "terminalFrame", "scope", "target", "passed"):
            with self.subTest(missing=field):
                changed = deepcopy(valid)
                changed["measurements"][KIND]["surface"].pop(field)
                with self.assertRaisesRegex(control.ValidationFailure, "native loaded surface"):
                    control._shared_pool_measurements(changed, KIND)
        for field in ("loadedTerrainVerified", "authoredSurfaceExcluded", "terminalHeightVerified"):
            for value in (False, 1, "true"):
                with self.subTest(field=field, value=value):
                    changed = deepcopy(valid)
                    changed["measurements"][KIND]["surface"][field] = value
                    with self.assertRaises(control.ValidationFailure):
                        control._shared_pool_measurements(changed, KIND)
        for field, value in (("handle", {}), ("species", 56), ("role", "MOUNTED"),
                             ("subjectIdentity", 999)):
            with self.subTest(identity=field):
                changed = deepcopy(valid)
                changed["measurements"][KIND]["surface"]["subject"][field] = value
                with self.assertRaisesRegex(control.ValidationFailure, "native loaded surface"):
                    control._shared_pool_measurements(changed, KIND)

    def test_four_meaning_controls_reach_surface_rejection_on_real_replay(self):
        expected = ("pool-surface-missing-query", "pool-surface-missing-refresh",
                    "pool-surface-missing-terrain", "pool-surface-missing-height")
        self.assertEqual(control._POOL_SURFACE_CONTROLS, expected)
        before = deepcopy(self.rows)
        for fault in expected:
            with self.subTest(fault=fault):
                result = self.replay(fault)
                self.assertFalse(result["passed"], result)
                self.assertTrue(result["failures"])
                meter = result["measurements"][KIND]
                self.assertTrue(meter["spawnPassed"], meter)
                self.assertTrue(meter["placement"]["passed"], meter)
                self.assertIn("invalid-spawn-surface", [e["code"] for e in meter["surfaceErrors"]])
                self.assertNotIn("missing-spawn-height-event", [e["code"] for e in meter["surfaceErrors"]])
                self.assertEqual(self.rows, before)
        self.assertTrue(self.replay()["passed"])

    def test_stronger_replay_still_rejects_old_site_and_subject_controls(self):
        before = deepcopy(self.rows)
        for fault in ("absent-subject", "stale-subject", "pool-missing-finalization", "pool-replaced-site",
                      *("pool-missing-meaning:" + name for name in control._LEDYBA_REQUIRED_MEANINGS)):
            with self.subTest(fault=fault):
                result = self.replay(fault)
                self.assertFalse(result["passed"])
                self.assertTrue(result["failures"])
                meter = result["measurements"][KIND]
                if fault in ("pool-missing-finalization", "pool-replaced-site"):
                    expected = "invalid-pool-receipt" if fault.endswith("finalization") else "pool-destination-replaced"
                    self.assertIn(expected, [error["code"] for error in meter["failures"]])
                elif fault.startswith("pool-missing-meaning:"):
                    meaning = fault.split(":", 1)[1]
                    reason = "missing-motion-start-event" if meaning == "MOTION_STARTED" else "missing-or-duplicate-terminal-event"
                    self.assertTrue(any(error.get("reason") == reason and
                        (meaning == "MOTION_STARTED" or error.get("event") == meaning)
                        for error in meter["measurementErrors"]), meter)
                self.assertEqual(self.rows, before)

    def test_surface_acceptance_rejects_absent_height_recorder_calibration(self):
        # Existing chain calibration says nothing about the new height reader.
        # Keep real positive replay and all controller meaning controls active.
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs), \
                patch.object(control, "_shared_recorder_control", return_value={"revalidated": True}):
            result = control.finalize_shared_test(self.test, self.record, self.root)
        self.assertFalse(result["acceptedProof"], result)


if __name__ == "__main__":
    unittest.main()
