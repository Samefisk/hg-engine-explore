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





class SharedPoolFlyControllerTests(unittest.TestCase):
    """Current catalog + Fly144 on real replay; synthetic rows are not acceptance."""
    replay = pool_tests.SharedPoolProofTests.replay
    write_rows = pool_tests.SharedProofTests.write_rows
    artifact = pool_tests.SharedProofTests.artifact
    current = pool_tests.SharedProofTests.current

    def setUp(self):
        from tools.overworld.test_devtools_spawn_measurement import fly_stream, fly_authored, SCHEMA, SOURCE
        from tools.overworld.test_devtools_spawn_surface_integration import PoolFlySurfaceIntegrationTests
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_test_contract import validate_test
        pool_tests.SharedProofTests.setUp(self)
        self.inputs = {KIND: {'schema': SCHEMA, 'sourceSha256': SOURCE, 'authoredProfiles': fly_authored()}}
        self.test.update(mode='normal', requirements=list(REQUIREMENTS),
            measurements=[{'kind': KIND, 'subject': 'subject'}],
            assertions=[{'kind': 'measurement-complete', 'measurement': KIND}])
        self.test['subjects'][0]['acquire'] = 'spawn'
        self.test['budgets'].update(maxFrames=200, minObservedFrames=16)
        self.test = validate_test(self.test)
        self.registration.update(evaluator=KIND, proofLevel='S3', mode='normal',
            requirements=list(REQUIREMENTS), minimumObservedFrames=16, claims=list(CLAIMS),
            recorderControlRequirement='legacy.live-observer-controls')
        source = self.root / 'tests/overworld/test-recipes/test.actor.json'
        source.write_text(json.dumps(self.test)); self.registration['recipeSha256'] = pool_tests.sha(source)
        (self.root / 'tools/overworld/runtime_proof_registry.json').write_text(json.dumps({
            'sharedTests': {self.test['id']: self.registration}}))
        stream = fly_stream()
        PoolFlySurfaceIntegrationTests.collect_fly(stream)
        items = stream.items
        for sample, _ in items:
            for actor in sample['actors']: actor['engineIdentity']['manager_index'] = 0
        attachment = deepcopy(next(e for e in items[1][1] if e['kind'] == 'native'))
        attachment['data']['event'] = 'ACTOR_ATTACHED'
        for _, events in items:
            for event in events:
                if event['kind'] == 'native': event['data']['sequence'] += 1
        items[1][1].insert(0, attachment)
        binding = select_current_actor(items[1][0], items[1][0]['actors'][0])
        self.rows = [{'phase': 'setup', 'initialSnapshot': items[0][0]},
            {'phase': 'setup', 'samples': [items[1][0]], 'snapshot': items[1][0],
             'events': items[1][1], 'completedGameFrames': 1},
            {'phase': 'setup', 'command': 'bind', 'action': 'bind-subject', 'snapshot': items[1][0], 'receipt': binding},
            {'phase': 'observe', 'samples': [s for s, _ in items[2:]], 'snapshot': items[-1][0],
             'events': [e for _, events in items[2:] for e in events], 'completedGameFrames': len(items) - 2}]
        self.write_rows()

    def test_current_fly_real_replay_and_four_actual_surface_meanings(self):
        before = deepcopy(self.rows)
        positive = self.replay()
        self.assertTrue(positive['passed'], positive)
        self.assertEqual(positive['measurements'][KIND]['placement']['startupKind'], 9)
        for fault in control._POOL_SURFACE_CONTROLS:
            with self.subTest(fault=fault):
                result = self.replay(fault)
                self.assertFalse(result['passed'], result)
                self.assertTrue(result['failures'])
                meter = result['measurements'][KIND]
                if fault == 'pool-surface-missing-refresh':
                    self.assertTrue(any(e['code'] == 'invalid-pool-receipt' and
                        'finalized Fly In startup' in e['message'] for e in meter['failures']), meter)
                elif fault == 'pool-surface-missing-height':
                    self.assertTrue(any(e['code'] == 'invalid-observation' and e['message'] == "'pos_y'"
                        for e in meter['failures']), meter)
                else:
                    self.assertIn('invalid-spawn-surface', [e['code'] for e in meter['surfaceErrors']], meter)
                self.assertEqual(self.rows, before)

    def test_current_fly_replay_keeps_identity_site_source_and_terminal_controls(self):
        self.assertTrue(self.replay()['passed'])
        for fault in ('absent-subject', 'stale-subject', 'pool-missing-finalization', 'pool-replaced-site',
                      *('pool-missing-meaning:' + name for name in control._LEDYBA_REQUIRED_MEANINGS)):
            with self.subTest(fault=fault):
                result = self.replay(fault)
                self.assertFalse(result['passed'], result)
                self.assertTrue(result['failures'])

    def test_current_fly_acceptance_still_requires_both_recorder_controls(self):
        self.record.update(test=self.test['id'], evaluation=self.replay(), observationsArtifact=self.artifact(),
            testSourceSha256=self.registration['recipeSha256'])
        self.record['fixtureProof'].update(registration=deepcopy(self.registration),
            testSourceSha256=self.registration['recipeSha256'])
        with patch.object(control, 'source_record', return_value={'hash': 'source'}), \
                patch('tools.overworld.devtools_test_inputs.measurement_inputs', return_value=self.inputs), \
                patch.object(control, '_shared_recorder_control', return_value={'revalidated': True}) as common, \
                patch.object(control, '_shared_surface_recorder_control', return_value={'revalidated': True}) as surface:
            result = control.finalize_shared_test(self.test, self.record, self.root)
        self.assertTrue(result['acceptedProof'], result)  # host-only mocked calibration
        common.assert_called_once(); surface.assert_called_once()
        with patch.object(control, 'source_record', return_value={'hash': 'source'}), \
                patch('tools.overworld.devtools_test_inputs.measurement_inputs', return_value=self.inputs), \
                patch.object(control, '_shared_recorder_control', return_value={'revalidated': True}), \
                patch.object(control, '_shared_surface_recorder_control', side_effect=control.ValidationFailure('missing current native calibration')):
            result = control.finalize_shared_test(self.test, self.record, self.root)
        self.assertFalse(result['acceptedProof'], result)
        self.assertEqual(result['proofAcceptance']['reason'], 'missing current native calibration')


if __name__ == "__main__":
    unittest.main()
