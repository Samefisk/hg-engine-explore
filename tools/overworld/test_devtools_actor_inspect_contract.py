"""Recipe and bound-subject dispatch controls for the native Inspect test."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import ACTOR_INSPECT, TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_test_contract import snapshot
from tools.overworld.validation import validate_scenario


def recipe():
    budget = dict(maxSeconds=30, maxFrames=120, noProgressFrames=120)
    return dict(schemaVersion=1, id="actor.inspect-current-and-stale", title="Native Inspect lookup",
        mode="prepared", fixture=dict(rom="test.nds", save="test.sav"),
        expectationSource="documentation/overworld-system/roadmap.md",
        requirements=["shared.actor-inspect-handle-v1"],
        budgets={**budget, "minObservedFrames": 1},
        subjects=[dict(id="mankey", species=56, role="FOLLOWER", acquire="existing")],
        setup=[dict(id="bind-mankey", op="bind", args=dict(subject="mankey"), budget=budget)],
        actions=[dict(id="probe", op="actor-inspect.probe", args=dict(subject="mankey"), budget=budget)],
        assertions=[dict(kind="measurement-complete", measurement=ACTOR_INSPECT, when="final")],
        measurements=[dict(kind=ACTOR_INSPECT, subject="mankey")])


class ActorInspectContractTests(unittest.TestCase):
    def test_controlled_lookup_exception_cannot_grant_broad_actor_proof(self):
        path = Path(__file__).resolve().parents[2] / "tests/overworld/scenarios/actor.inspect-current-and-stale.json"
        scenario = json.loads(path.read_text())
        validate_scenario(scenario, path)
        for fault in ("renamed", "subjectless", "wrong-role", "wrong-species", "motion", "presentation", "s4"):
            changed = deepcopy(scenario)
            if fault == "renamed": changed["id"] = changed["adapter"]["test"] = "other.lookup"
            if fault == "subjectless": changed["subjects"] = []
            if fault == "wrong-role": changed["subjects"][0]["role"] = "MOUNTED"
            if fault == "wrong-species": changed["subjects"][0]["species"] = 155
            if fault == "motion": changed["subjects"][0]["motionActor"] = True
            if fault == "presentation": changed["subjects"][0]["requirePresentation"] = False
            if fault == "s4": changed["proofLevel"] = "S4"
            with self.subTest(fault=fault), self.assertRaises(ValueError): validate_scenario(changed, path)

    def stream_fixture(self):
        from tools.overworld.test_devtools_actor_inspect_measurement import fixture
        authored, rows, _ = fixture()
        test = recipe()
        test["setup"][0]["id"] = authored["setup"][0]["id"]
        test["actions"][0]["id"] = authored["actions"][0]["id"]
        rows[1]["receipt"] = select_current_actor(rows[1]["snapshot"], rows[1]["receipt"])
        return test, rows

    def test_full_raw_evaluator_counts_only_inspect_cycles(self):
        test, rows = self.stream_fixture()
        evaluator = TestEvaluator(test)
        evaluator.install_measurements(measurement_inputs(test, None))
        for row in rows:
            self.assertNotEqual(evaluator.observe_record(row)["state"], "failed")
        result = evaluator.finish()
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["observedFrames"], 1)
        self.assertEqual(result["measurements"][ACTOR_INSPECT]["observedFrameUnit"], "native-inspect-cycles")
        self.assertEqual(result["measurements"][ACTOR_INSPECT]["completedGameFrames"], 0)

    def test_raw_bind_cannot_substitute_a_different_boundary(self):
        test, rows = self.stream_fixture()
        rows[1]["snapshot"]["actors"][0]["subjectIdentity"] += 1
        evaluator = TestEvaluator(test)
        evaluator.install_measurements(measurement_inputs(test, None))
        evaluator.observe_record(rows[0])
        self.assertEqual(evaluator.observe_record(rows[1])["state"], "failed")

    def test_exact_prepared_recipe_and_no_profile_input_reads(self):
        test = validate_test(recipe())
        self.assertEqual(measurement_inputs(test, None), {ACTOR_INSPECT: {"contractVersion": 1}})
        self.assertEqual(test["actions"][0]["args"], {"subject": "mankey"})

    def test_rejects_substituted_subject_raw_handle_and_unrelated_setup(self):
        for fault in ("normal", "role", "species", "spawn", "handle", "extra", "missing-bind", "no-meter"):
            test = recipe()
            if fault == "normal": test["mode"] = "normal"
            if fault == "role": test["subjects"][0]["role"] = "WILD"
            if fault == "species": test["subjects"][0]["species"] = 155
            if fault == "spawn": test["subjects"][0]["acquire"] = "spawn"
            if fault == "handle": test["actions"][0]["args"] = {"handle": 65543}
            if fault == "extra":
                action = deepcopy(test["actions"][0]); action["id"] = "extra"
                test["actions"].append(action)
            if fault == "missing-bind": test["setup"] = []
            if fault == "no-meter": test["measurements"] = []
            with self.subTest(fault=fault), self.assertRaises(ValueError): validate_test(test)

    def test_dispatch_uses_already_bound_handle_not_species_search(self):
        evaluator = TestEvaluator(recipe())
        current = snapshot()
        current["actors"][0].update(species=56, role="FOLLOWER")
        evaluator.latest = deepcopy(current)
        evaluator.measurements[ACTOR_INSPECT] = object()
        with self.assertRaises(ValueError): evaluator.actor_inspect_args("mankey", current)
        bound = evaluator.bind("mankey", current)
        self.assertEqual(evaluator.actor_inspect_args("mankey", current), {"handle": bound["handle"]["value"]})
        for fault in ("replacement", "stale-context", "absent", "unverified", "new-boundary"):
            changed = deepcopy(current)
            if fault == "replacement": changed["actors"][0]["handle"]["generation"] += 1
            if fault == "stale-context": changed["context"]["fieldEpoch"] += 1
            if fault == "absent": changed["actors"] = []
            if fault == "unverified": changed["actors"][0]["identityVerified"] = False
            if fault == "new-boundary": changed["frame"] += 1
            evaluator.latest = deepcopy(changed) if fault != "new-boundary" else deepcopy(current)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                evaluator.actor_inspect_args("mankey", changed)


if __name__ == "__main__": unittest.main()
