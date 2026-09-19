"""Host controls for the data-only shared devtools test language."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test


def recipe():
    return {"schemaVersion": 1, "id": "test.actor", "title": "Actor witness", "mode": "normal",
            "fixture": {"rom": "test.nds", "save": "test.sav"},
            "expectationSource": "documentation/overworld-system/verification.md",
            "requirements": [], "budgets": {"maxSeconds": 30, "maxFrames": 20,
                "noProgressFrames": 10, "minObservedFrames": 2},
            "subjects": [{"id": "subject", "species": 165, "role": "WILD", "acquire": "existing"}],
            "setup": [], "actions": [{"id": "sample", "op": "step", "args": {"frames": 2, "keys": []},
                "budget": {"maxSeconds": 10, "maxFrames": 2, "noProgressFrames": 2}}],
            "assertions": [{"kind": "actor-field", "subject": "subject", "path": "motionPhase",
                "operator": "eq", "value": "IDLE"}]}


def snapshot(frame=1):
    actor = {"handle": {"value": 65536, "slot": 0, "generation": 1, "fieldEpoch": 1,
                       "mapGeneration": 1, "encounterGeneration": 1},
             "subjectIdentity": 123, "species": 165, "role": "WILD", "active": True,
             "presentationAttached": True, "identityVerified": True,
             "authorityGeneration": 1, "engineAnchorGeneration": 1, "presentationGeneration": 1,
             "motionPhase": "IDLE", "commitSequence": 0}
    return {"frame": frame, "context": {"fieldEpoch": 1, "mapGeneration": 1},
            "actors": [actor], "player": {"x": 1, "y": 2}, "prepared": False}


def event(frame=1, name="MOTION_FINISHED", sequence=1):
    handle = snapshot()["actors"][0]["handle"]
    return {"frame": frame, "kind": "native", "data": {"traceStream": 1, "sequence": sequence,
        "actorHandle": handle["value"], "actor": {k: v for k, v in handle.items() if k != "value"},
        "event": name}}


class ContractTests(unittest.TestCase):
    def test_host_hitch_continuation_is_diagnostic_only(self):
        path = Path(__file__).resolve().parents[2] / "tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json"
        value = json.loads(path.read_text())
        value.update(requirements=[], diagnosticContinueHostHitches=True)
        diagnostic = json.loads(path.with_name("diagnostic.unmounted.host-hitch-followthrough.json").read_text())
        for key in value.keys() | diagnostic.keys():
            if key not in ("id", "title"):
                self.assertEqual(value.get(key), diagnostic.get(key), key)
        self.assertTrue(validate_test(value)["diagnosticContinueHostHitches"])
        for change in ({"mode": "normal"}, {"requirements": ["legacy.unmounted-long-travel"]},
                       {"diagnosticContinueHostHitches": 1}, {"diagnosticContinueHostHitches": False},
                       {"measurements": []}):
            with self.assertRaises(ValueError):
                validate_test({**value, **change})
        from tools.overworld.control import _finalize_shared_test_scoped
        result = _finalize_shared_test_scoped(value, {"passed": True, "acceptedProof": True,
            "fixtureProof": {"proofInputs": {"schema": "untrusted"}}})
        self.assertFalse(result["passed"])
        self.assertFalse(result["acceptedProof"])
        self.assertFalse(result["proofAcceptance"]["eligible"])

    def test_spawn_cost_experiment_cannot_claim_requirements(self):
        value = recipe()
        value.update(mode="prepared", spawnObserverCost="baseline")
        self.assertEqual(validate_test(value)["spawnObserverCost"], "baseline")
        for change in ({"mode": "normal"}, {"requirements": ["anything"]},
                       {"spawnObserverCost": "arbitrary"}):
            with self.assertRaises(ValueError):
                validate_test({**value, **change})
        from tools.overworld.control import finalize_shared_test
        for test, record in ((value, {"passed": True}),
                             (recipe(), {"passed": True, "observationSetup": {"spawnObserverCost": {}}})):
            self.assertFalse(finalize_shared_test(test, record)["acceptedProof"])

    def test_prebind_idle_count_uses_current_verified_actor(self):
        predicate = {"kind": "actor-count", "subject": "subject", "operator": "eq",
                     "value": 1, "motionPhase": "IDLE"}
        value = recipe()
        value["assertions"] = [predicate]
        evaluator = TestEvaluator(value)
        sample = snapshot()
        evaluator.latest = sample
        self.assertTrue(evaluator.check(predicate))
        sample["actors"][0]["motionPhase"] = "ADVANCING"
        self.assertFalse(evaluator.check(predicate))
        sample["actors"][0]["motionPhase"] = "IDLE"
        sample["actors"][0]["identityVerified"] = False
        with self.assertRaises(ValueError):
            evaluator.check(predicate)
        sample["actors"][0]["identityVerified"] = True
        del sample["actors"][0]["motionPhase"]
        with self.assertRaises(ValueError):
            evaluator.check(predicate)

    def test_idle_count_rejects_unknown_phase_filter(self):
        for phase in (None, True, "", "ANY", "ADVANCING"):
            value = recipe()
            value["assertions"] = [{"kind": "actor-count", "subject": "subject",
                "operator": "eq", "value": 1, "motionPhase": phase}]
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                validate_test(value)

    def test_normal_ledyba_contract_keeps_long_actor_scoped_wait(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "tests/overworld/test-recipes/chain.ledyba-witness.json"
        value = validate_test(json.loads(path.read_text()))
        scenario = json.loads((root / "tests/overworld/scenarios/chain.pause.ledyba-normal-profile.json").read_text())
        entry = json.loads((root / "tools/overworld/runtime_proof_registry.json").read_text())["sharedTests"][value["id"]]
        self.assertEqual(value["budgets"]["minObservedFrames"], 5000)
        self.assertEqual(scenario["adapter"]["minimumFrames"], 5000)
        self.assertEqual(entry["minimumObservedFrames"], 5000)
        self.assertEqual(entry["recipeSha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        wait = value["actions"][-1]
        self.assertEqual(wait["args"]["predicate"]["kind"], "measurement-complete")
        self.assertEqual(wait["budget"]["noProgressFrames"], 240)
        self.assertEqual(value["budgets"]["noProgressFrames"], 240)
        self.assertEqual(value["requirements"], ["legacy.ledyba-normal-profile"])
        self.assertEqual(scenario["capture"], "none")

    def test_ready_measurement_waits_for_bound_subject_frame_floor(self):
        value = recipe()
        value["budgets"].update(maxFrames=6000, minObservedFrames=5000)
        evaluator = TestEvaluator(value)
        evaluator.latest = snapshot()
        evaluator.measurements["ledyba-chain-v1"] = SimpleNamespace(result=lambda: {"ready": True})
        predicate = {"kind": "measurement-complete", "measurement": "ledyba-chain-v1"}
        for observed in (0, 4999):
            evaluator.frames = observed
            self.assertFalse(evaluator.check(predicate))
        evaluator.frames = 5000
        self.assertTrue(evaluator.check(predicate))
        evaluator.measurements["ledyba-chain-v1"] = SimpleNamespace(result=lambda: {"ready": False})
        self.assertFalse(evaluator.check(predicate))

    def test_literal_recipe_round_trip(self):
        value = recipe()
        self.assertEqual(validate_test(value)["id"], value["id"])

    def test_unknown_actions_private_oracles_and_unbounded_work_rejected(self):
        for edit in (
            lambda t: t["actions"][0].update(op="python"),
            lambda t: t["actions"][0].pop("budget"),
            lambda t: t["assertions"][0].update(path="movementPolicy.chainCount"),
            lambda t: t["budgets"].update(maxFrames=True),
            lambda t: t.update(unknown=True),
        ):
            value = recipe(); edit(value)
            with self.subTest(value=value), self.assertRaises(ValueError): validate_test(value)

    def test_normal_prepared_attempt_rejected(self):
        value = recipe()
        value["setup"] = [{"id": "teleport", "op": "teleport", "args": {"map": 33, "x": 1, "z": 2},
                            "budget": {"maxSeconds": 10, "maxFrames": 10, "noProgressFrames": 10}}]
        with self.assertRaises(ValueError): validate_test(value)
        value["mode"] = "prepared"
        self.assertEqual(validate_test(value)["setup"][0]["op"], "teleport")

    def test_no_empty_proof(self):
        value = recipe(); value["assertions"] = []
        with self.assertRaises(ValueError): validate_test(value)

    def test_tools_only_frame_test_needs_no_invented_actor(self):
        value = recipe(); value["subjects"] = []
        value["assertions"] = [{"kind": "frame-count", "operator": "gte", "value": 2}]
        evaluator = TestEvaluator(value)
        evaluator.observe(snapshot(1)); evaluator.observe(snapshot(2))
        result = evaluator.finish()
        self.assertTrue(result["passed"])
        self.assertEqual(result["subjects"], {})
        self.assertFalse(result["acceptedProof"])
        value["requirements"] = ["shared.actor-identity.prepared-v1"]
        with self.assertRaises(ValueError): validate_test(value)

    def test_unique_action_ids_and_known_subjects(self):
        value = recipe(); value["actions"].append(deepcopy(value["actions"][0]))
        with self.assertRaises(ValueError): validate_test(value)

    def test_setup_skip_is_typed_and_cannot_skip_observation(self):
        value = recipe()
        action = deepcopy(value["actions"][0]); action["id"] = "route"
        action["skipIf"] = {"kind": "actor-present", "subject": "subject"}
        value["setup"] = [action]
        self.assertEqual(validate_test(value)["setup"][0]["skipIf"]["kind"], "actor-present")
        invalid = deepcopy(value); invalid["actions"][0]["skipIf"] = action["skipIf"]
        with self.assertRaises(ValueError): validate_test(invalid)
        invalid = deepcopy(value); invalid["setup"][0]["op"] = "bind"
        invalid["setup"][0]["args"] = {"subject": "subject"}
        with self.assertRaises(ValueError): validate_test(invalid)

    def test_step_until_uses_the_same_typed_predicate_validation(self):
        value = recipe(); value["actions"][0]["args"]["until"] = {
            "kind": "player-field", "path": "x", "operator": "eq", "value": 3}
        self.assertEqual(validate_test(value)["actions"][0]["args"]["until"]["value"], 3)
        value["actions"][0]["args"]["until"]["path"] = "private.scriptFlags"
        with self.assertRaises(ValueError): validate_test(value)
        value = recipe(); value["assertions"][0]["subject"] = "unknown"
        with self.assertRaises(ValueError): validate_test(value)


class EvaluatorTests(unittest.TestCase):
    def evaluator(self):
        evaluator = TestEvaluator(recipe())
        evaluator.bind("subject", snapshot())
        evaluator.observe(snapshot())
        return evaluator

    def test_exact_subject_and_two_frames_required(self):
        evaluator = self.evaluator()
        self.assertFalse(evaluator.finish()["passed"])
        evaluator = self.evaluator(); evaluator.observe(snapshot(2))
        self.assertTrue(evaluator.finish()["passed"])
        self.assertFalse(evaluator.result()["acceptedProof"])

    def test_absent_wrong_role_and_stale_subject_cannot_pass(self):
        for field, value in (("species", 56), ("role", "FOLLOWER"), ("identityVerified", False),
                             ("presentationAttached", False), ("subjectIdentity", 124)):
            evaluator = self.evaluator(); current = snapshot(2); current["actors"][0][field] = value
            evaluator.observe(current)
            with self.subTest(field=field): self.assertFalse(evaluator.finish()["passed"])
        evaluator = self.evaluator(); current = snapshot(2); current["actors"] = []
        evaluator.observe(current); self.assertFalse(evaluator.finish()["passed"])

    def test_duplicate_or_missing_frames_fail_closed(self):
        for frame in (1, 3):
            evaluator = self.evaluator(); evaluator.observe(snapshot(frame))
            with self.subTest(frame=frame): self.assertFalse(evaluator.finish()["passed"])

    def test_first_failure_is_immutable_and_cannot_be_erased_by_later_good_data(self):
        evaluator = self.evaluator(); evaluator.fail("bad-motion", "bad completed motion", {"x": 1})
        prior = evaluator.result(); prior["failures"][0]["code"] = "modified"
        evaluator.observe(snapshot(2))
        self.assertEqual(evaluator.finish()["failures"][0]["code"], "bad-motion")
        self.assertFalse(evaluator.result()["passed"])

    def test_trace_gap_fails_but_normal_ring_wrap_is_not_unread_loss(self):
        evaluator = self.evaluator()
        evaluator.observe(snapshot(2), [{"frame": 2, "kind": "trace-status", "data": {
            "code": "unread-events-lost", "coverageComplete": False}}])
        self.assertFalse(evaluator.finish()["passed"])
        evaluator = self.evaluator()
        evaluator.observe(snapshot(2), [{"frame": 2, "kind": "trace-status", "data": {
            "code": "ring-overwrite", "unreadEventsLost": 0}}])
        self.assertTrue(evaluator.finish()["passed"])

    def test_event_count_bound_to_same_full_handle(self):
        evaluator = self.evaluator(); current = event(2); current["data"]["actor"]["mapGeneration"] = 2
        evaluator.observe(snapshot(2), [current])
        predicate = {"kind": "event-count", "subject": "subject", "event": "MOTION_FINISHED",
                     "operator": "gte", "value": 1}
        self.assertFalse(evaluator.check(predicate))
        evaluator = self.evaluator(); evaluator.observe(snapshot(2), [event(2)])
        self.assertTrue(evaluator.check(predicate))

    def test_pending_count_is_not_permanent_failure_but_forbidden_event_is(self):
        value = recipe(); value["assertions"].append({"kind": "event-count", "subject": "subject",
            "event": "MOTION_FINISHED", "operator": "gte", "value": 1})
        evaluator = TestEvaluator(value); evaluator.bind("subject", snapshot()); evaluator.observe(snapshot())
        self.assertEqual(evaluator.result()["failures"], [])
        evaluator.observe(snapshot(2), [event(2)])
        self.assertTrue(evaluator.finish()["passed"])
        value["assertions"][-1].update(event="MOTION_CANCELED", operator="eq", value=0, when="always")
        evaluator = TestEvaluator(value); evaluator.bind("subject", snapshot()); evaluator.observe(snapshot())
        evaluator.observe(snapshot(2), [event(2, "MOTION_CANCELED")])
        self.assertEqual(evaluator.result()["state"], "failed")

    def test_prepared_snapshot_taints_normal_run(self):
        evaluator = self.evaluator(); current = snapshot(2); current["prepared"] = True
        evaluator.observe(current); self.assertFalse(evaluator.finish()["passed"])

    def test_never_bound_subject_cannot_pass(self):
        evaluator = TestEvaluator(recipe()); evaluator.observe(snapshot()); evaluator.observe(snapshot(2))
        self.assertFalse(evaluator.finish()["passed"])

    def test_actual_public_duration_names_and_large_error_do_not_hide_failure(self):
        evaluator = self.evaluator(); current = snapshot(2)
        current["actors"][0].update(motionElapsed=3, motionDuration=8)
        current["player"].update(movement_cmd=0, movement_step=1)
        self.assertTrue(evaluator.check({"kind": "actor-field", "subject": "subject",
            "path": "motionDuration", "operator": "eq", "value": 8}, current))
        self.assertTrue(evaluator.check({"kind": "player-field", "path": "movement_cmd",
            "operator": "eq", "value": 0}, current))
        evaluator.fail("native-timeout", "original failure", {"large": "x" * 70000})
        self.assertEqual(evaluator.result()["failures"][0]["code"], "native-timeout")
        self.assertTrue(evaluator.result()["failures"][0]["details"]["omitted"])

    def test_spawn_acquisition_needs_new_handle_and_actual_attach(self):
        value = recipe(); value["subjects"][0]["acquire"] = "spawn"
        evaluator = TestEvaluator(value); initial = snapshot(); initial["actors"] = []
        evaluator.observe(initial); evaluator.observe(snapshot(2))
        with self.assertRaises(ValueError): evaluator.bind("subject", snapshot(2))
        evaluator = TestEvaluator(value); evaluator.observe(initial)
        evaluator.observe(snapshot(2), [event(2, "ACTOR_ATTACHED")])
        self.assertTrue(evaluator.bind("subject", snapshot(2))["identityVerified"])

    def test_setup_and_unbound_frames_have_no_live_observation_credit(self):
        evaluator = TestEvaluator(recipe())
        evaluator.observe(snapshot(), count_frame=False)
        evaluator.observe(snapshot(2))
        self.assertEqual(evaluator.result()["observedFrames"], 0)
        evaluator.bind("subject", snapshot(2))
        evaluator.observe(snapshot(3), count_frame=False)
        self.assertEqual(evaluator.result()["observedFrames"], 0)
        evaluator.observe(snapshot(4))
        self.assertEqual(evaluator.result()["observedFrames"], 1)

    def test_actor_count_waits_without_binding_absent_or_invalid_actor(self):
        evaluator = TestEvaluator(recipe()); current = snapshot(); current["actors"] = []
        predicate = {"kind": "actor-count", "subject": "subject", "operator": "gte", "value": 1}
        self.assertFalse(evaluator.check(predicate, current))
        self.assertTrue(evaluator.check(predicate, snapshot()))
        self.assertEqual(evaluator.subjects, {})
        current = snapshot(); current["actors"][0]["identityVerified"] = False
        with self.assertRaises(ValueError): evaluator.check(predicate, current)


if __name__ == "__main__": unittest.main()
