"""Keep the public structural schema usable for current scenario files.

The project validator still owns cross-field and runtime proof checks.
"""
import copy
import json
from pathlib import Path
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None


@unittest.skipIf(Draft202012Validator is None, "jsonschema is not installed")
class ScenarioJsonSchemaTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[2]
        schema = json.loads((self.repo / "tools/overworld/schemas/scenario-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema)

    def test_current_scenario_catalog(self):
        files = sorted((self.repo / "tests/overworld/scenarios").glob("*.json"))
        self.assertTrue(files)
        for filename in files:
            with self.subTest(filename=filename.name):
                self.validator.validate(json.loads(filename.read_text()))

    def test_invalid_recipe_and_unknown_field_are_rejected(self):
        source = json.loads((self.repo / "tests/overworld/scenarios/mount.detach-restores-control.json").read_text())
        for field, value in (("kind", "unknown"), ("setupAudit", "unknown"), ("limits", []), ("extra", True)):
            case = copy.deepcopy(source)
            case["verification"][field] = value
            with self.subTest(field=field):
                self.assertTrue(list(self.validator.iter_errors(case)))


if __name__ == "__main__":
    unittest.main()
