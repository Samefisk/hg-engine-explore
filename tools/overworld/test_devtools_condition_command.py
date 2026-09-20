import unittest

from tools.overworld import test_devtools as fixtures
from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe


class ConditionCommandTests(unittest.TestCase):
    def test_checked_job_keeps_full_probe_receipt(self):
        fixture = fixtures.ServiceTests()
        fixture.setUp()
        try:
            fixture.start()
            original = fixture.service.worker.call

            def call(operation, args=None):
                snapshot = original(operation, args)
                if operation != "condition.probe":
                    return snapshot
                return {"snapshot": snapshot,
                        "value": {"receipts": ["retained"]},
                        "setupBoundary": {"eventsDrained": True}}

            fixture.service.worker.call = call
            receipt = fixture.service.tests._command("condition.probe", {})
            self.assertEqual(receipt["value"], {"receipts": ["retained"]})
            self.assertIn("snapshot", receipt)
        finally:
            fixture.tearDown()
            fixture.doCleanups()

    def test_no_user_addresses_and_no_normal_recipe_credit(self):
        self.assertEqual(validate_command("condition.probe", {}), {})
        with self.assertRaises(ValueError):
            validate_command("condition.probe", {"address": 1})
        recipe = {"schemaVersion": 1, "mode": "prepared",
                  "actions": [{"op": "condition.probe", "args": {}}]}
        self.assertEqual(validate_recipe(recipe), recipe)
        with self.assertRaises(ValueError):
            validate_recipe({**recipe, "mode": "normal"})

    def test_shared_service_marks_prepared_and_remembers_probe(self):
        fixture = fixtures.ServiceTests()
        fixture.setUp()
        try:
            fixture.start()
            result = fixture.command("condition.probe")
            self.assertTrue(result["ok"], result)
            self.assertEqual(fixture.service.session["mode"], "prepared")
            self.assertEqual(fixture.service.actions[-1],
                             {"op": "condition.probe", "args": {}})
            self.assertIn(("condition.probe", {}), fixture.service.worker.calls)
            self.assertEqual(fixture.service.session["setupMutations"][-1]["op"],
                             "condition.probe")
        finally:
            fixture.tearDown()
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
