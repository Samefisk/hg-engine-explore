"""The fixed probe uses shared setup ownership, not a raw-call interface."""
import unittest
from tools.overworld import test_devtools as fixtures
from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe


class ResolverCommandTests(unittest.TestCase):
    def test_checked_job_keeps_full_probe_receipt(self):
        f = fixtures.ServiceTests(); f.setUp()
        try:
            f.start()
            original = f.service.worker.call
            def call(op, args=None):
                snapshot = original(op, args)
                return {"snapshot": snapshot, "value": {"receipts": ["retained"]},
                        "setupBoundary": {"eventsDrained": True}} if op == "resolver.probe" else snapshot
            f.service.worker.call = call
            receipt = f.service.tests._command("resolver.probe", {})
            self.assertEqual(receipt["value"], {"receipts": ["retained"]})
            self.assertIn("snapshot", receipt)
        finally:
            f.tearDown(); f.doCleanups()

    def test_no_user_addresses_and_no_normal_recipe_credit(self):
        self.assertEqual(validate_command("resolver.probe", {}), {})
        with self.assertRaises(ValueError): validate_command("resolver.probe", {"address": 1})
        recipe = {"schemaVersion":1,"mode":"prepared","actions":[{"op":"resolver.probe","args":{}}]}
        self.assertEqual(validate_recipe(recipe), recipe)
        with self.assertRaises(ValueError): validate_recipe({**recipe,"mode":"normal"})

    def test_shared_service_marks_prepared_and_remembers_probe(self):
        f = fixtures.ServiceTests(); f.setUp()
        try:
            f.start()
            result = f.command("resolver.probe")
            self.assertTrue(result["ok"], result)
            self.assertEqual(f.service.session["mode"], "prepared")
            self.assertEqual(f.service.actions[-1], {"op":"resolver.probe","args":{}})
            self.assertIn(("resolver.probe", {}), f.service.worker.calls)
            self.assertEqual(f.service.session["setupMutations"][-1]["op"], "resolver.probe")
        finally:
            f.tearDown(); f.doCleanups()


if __name__ == "__main__": unittest.main()
