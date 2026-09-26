"""The obstacle-direction control is bounded and cannot grant movement."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_obstacle_intent import NativeObstacleIntent
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.devtools_test_contract import TestEvaluator, _handle, validate_test
from tools.overworld.devtools_wild_sprint_obstacle_proof import contract
from tools.overworld.test_devtools_walk_reset_command import subject
from tools.overworld.test_devtools_wild_walk_contract import spawn_setup


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/walk.wild.sprint-obstacle-approach.json"
REGISTRY = ROOT / "tools/overworld/runtime_proof_registry.json"


def stantler():
    return {**subject(), "species": 234}


class ObstacleIntentTests(unittest.TestCase):
    def test_exact_stantler_and_short_frame_bound(self):
        args = {"subject": stantler(), "maxFrames": 100}
        self.assertEqual(validate_command("obstacle-intent.arm", args), args)
        for bad in ({}, {**args, "maxFrames": 0}, {**args, "maxFrames": 121},
                    {**args, "maxFrames": True}, {**args, "address": 0x02000000}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_command("obstacle-intent.arm", bad)
        for role, species in (("MOUNTED", 234), ("WILD", 19)):
            bad = deepcopy(args)
            bad["subject"].update(role=role, species=species)
            with self.subTest(role=role, species=species), self.assertRaises(ValueError):
                validate_command("obstacle-intent.arm", bad)
        self.assertEqual(validate_command("obstacle-intent.close", {}), {})
        with self.assertRaises(ValueError):
            validate_command("obstacle-intent.close", {"force": True})

    def test_control_is_prepared_and_exact_registered_recipe(self):
        for op, args in (("obstacle-intent.arm", {"subject": stantler(), "maxFrames": 100}),
                         ("obstacle-intent.close", {})):
            recipe = {"schemaVersion": 1, "mode": "prepared",
                      "actions": [{"op": op, "args": args}]}
            self.assertEqual(validate_recipe(recipe), recipe)
            with self.assertRaises(ValueError):
                validate_recipe({**recipe, "mode": "normal"})
        test = json.loads(RECIPE.read_text())
        self.assertEqual(validate_test(test)["id"], "walk.wild.sprint-obstacle-approach")
        registry = json.loads(REGISTRY.read_text())
        self.assertEqual(registry["measurementContracts"]
                         ["current.wild-sprint-obstacle-approach"], contract())

    def test_validated_prepared_spawn_can_bind_without_trace_event_credit(self):
        test = validate_test(json.loads(RECIPE.read_text()))
        receipt, snapshot = spawn_setup(species=234, locomotion=7)
        snapshot["fieldAvailable"] = True
        initial = deepcopy(snapshot)
        initial["actors"] = []
        initial["frame"] -= 1
        initial["nativeCycle"] -= 1
        initial["prepared"] = False
        receipt.update(preparedOnly=True, snapshot=deepcopy(snapshot),
                       setupBoundary={"eventsDrained": True,
                                      "frame": snapshot["frame"],
                                      "nativeCycle": snapshot["nativeCycle"],
                                      "endpointNativeCycle": snapshot["nativeCycle"],
                                      "traceSequences": {}})

        def evaluator_for(value):
            evaluator = TestEvaluator(test)
            evaluator.observe(initial, count_frame=False)
            row = {"phase": "setup", "action": "spawn-sprint-stantler",
                   "command": "spawn", "receipt": value, "snapshot": snapshot}
            return evaluator, evaluator.observe_prepared_command(row)

        evaluator, result = evaluator_for(deepcopy(receipt))
        self.assertFalse(result["failures"], result["failures"])
        actor = snapshot["actors"][0]
        self.assertIn(_handle(actor["handle"]), evaluator._prepared_attached)
        self.assertFalse(evaluator.events)
        self.assertEqual(evaluator.bind("stantler", snapshot)["handle"], actor["handle"])

        invalid = deepcopy(receipt)
        invalid["events"][0]["data"]["finalization"]["status"] = "missing"
        _, result = evaluator_for(invalid)
        self.assertTrue(result["failures"])

    def test_native_current_reads_full_actor_not_slim_subject(self):
        _, snapshot = spawn_setup(species=234, locomotion=7)
        actor = snapshot["actors"][0]
        actor["logical"] = {"x": 579, "y": 397}
        slim = {key: deepcopy(value) for key, value in actor.items()
                if key not in ("logical", "render", "origin", "target")}
        self.assertNotIn("logical", slim)
        session = SimpleNamespace(
            completed_frames=0, native_bridge_active=False, emu=object(),
            native_observation=SimpleNamespace(
                _chain_current=lambda slot: (slim, {}, actor["engineIdentity"], {})),
            rt=SimpleNamespace(actor_state=lambda emu, slot: actor))
        selected = {key: deepcopy(actor[key]) for key in
                    ("handle", "species", "subjectIdentity", "role",
                     "authorityGeneration", "engineAnchorGeneration",
                     "presentationGeneration", "engineIdentity")}
        current = NativeObstacleIntent(session, selected, 100).current()
        self.assertEqual(current["actor"]["logical"], {"x": 579, "y": 397})


if __name__ == "__main__":
    unittest.main()
