"""Shared reset command is bounded prepared setup, not a movement claim."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld import test_devtools as fixtures
from tools.overworld.test_devtools_test_contract import recipe, snapshot
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test


def subject():
    return dict(handle=dict(value=65536, slot=0, generation=1, fieldEpoch=1,
                            mapGeneration=1, encounterGeneration=1),
                species=155, subjectIdentity=42, role="WILD",
                authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1)


class WalkResetCommandTests(unittest.TestCase):
    def test_checked_recipe_resolves_live_bound_subject_only_during_setup(self):
        test = recipe()
        test["mode"] = "prepared"
        action = dict(id="reset", op="walk-policy.reset", args=dict(subject="subject"),
                      budget=dict(maxSeconds=10, maxFrames=2, noProgressFrames=2))
        test["setup"] = [action]
        self.assertEqual(validate_test(test)["setup"], [action])
        evaluator = TestEvaluator(test)
        current = snapshot()
        with self.assertRaises(ValueError):
            evaluator.walk_reset_args("subject", current)
        evaluator.bind("subject", current)
        self.assertEqual(evaluator.walk_reset_args("subject", current)["subject"]["handle"],
                         current["actors"][0]["handle"])
        stale = deepcopy(current)
        stale["actors"][0]["authorityGeneration"] += 1
        with self.assertRaises(ValueError):
            evaluator.walk_reset_args("subject", stale)
        for bad in ({**test, "mode": "normal"}, {**test, "setup": [], "actions": [action]}):
            with self.assertRaises(ValueError):
                validate_test(bad)

    def test_requires_full_generation_safe_subject(self):
        args = {"subject": subject()}
        self.assertEqual(validate_command("walk-policy.reset", args), args)
        for key in subject():
            bad = deepcopy(args)
            del bad["subject"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_command("walk-policy.reset", bad)
        for bad in ({}, {"subject": {}}, {**args, "address": 0x02000000},
                    {"subject": {**subject(), "authorityGeneration": True}},
                    {"subject": {**subject(), "role": "FOLLOWER"}}):
            with self.subTest(args=bad), self.assertRaises(ValueError):
                validate_command("walk-policy.reset", bad)

    def test_recipe_is_prepared_only(self):
        recipe = dict(schemaVersion=1, mode="prepared",
                      actions=[dict(op="walk-policy.reset", args=dict(subject=subject()))])
        self.assertEqual(validate_recipe(recipe), recipe)
        with self.assertRaises(ValueError):
            validate_recipe({**recipe, "mode": "normal"})

    def test_shared_command_retains_receipt_and_marks_prepared(self):
        fixture = fixtures.ServiceTests()
        fixture.setUp()
        try:
            fixture.start()
            original = fixture.service.worker.call
            def call(op, args=None):
                snapshot = original(op, args)
                return dict(snapshot=snapshot, acceptedProof=False,
                            value={"reset": True}, setupBoundary={"eventsDrained": True})
            fixture.service.worker.call = call
            receipt = fixture.service.tests._command("walk-policy.reset", {"subject": subject()})
            self.assertFalse(receipt["acceptedProof"])
            self.assertEqual(receipt["value"], {"reset": True})
            self.assertEqual(fixture.service.session["mode"], "prepared")
            self.assertEqual(fixture.service.session["setupMutations"][-1]["op"], "walk-policy.reset")
        finally:
            fixture.tearDown()
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
