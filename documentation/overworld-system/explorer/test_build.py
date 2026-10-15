"""Reject the copied profile facts that caused the source map to drift."""

import importlib.util
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("explorer_build", HERE / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ProfileFactChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = (HERE / "map.md").read_text()
        cls.nodes = builder.parse_map(cls.markdown)["nodes"]
        cls.schema = json.loads(
            (builder.ROOT / "tools/overworld/schemas/behavior-authoring-v5.schema.json").read_text()
        )
        cls.catalog = json.loads((builder.ROOT / "data/overworld_behavior_profiles.json").read_text())

    def validate_with_sources(self, schema, catalog):
        with tempfile.TemporaryDirectory(prefix="explorer-profile-sources-") as raw_root:
            root = Path(raw_root)
            for relative, data in [
                ("tools/overworld/schemas/behavior-authoring-v5.schema.json", schema),
                ("data/overworld_behavior_profiles.json", catalog),
            ]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(data))
            with patch.object(builder, "ROOT", root):
                builder.validate_profile_facts(self.nodes)

    def test_current_sources_and_map_agree(self):
        builder.parse_map(self.markdown)

    def test_copied_old_order_is_rejected(self):
        stale = self.markdown.replace(
            "Summary: Routine → Placement → Follower → Capability → Attitude → Style → Follower/Mount → Modifier.",
            "Summary: Routine → Placement → Capability → Attitude → Modifier → System → Utility.",
        )
        self.assertNotEqual(stale, self.markdown)
        with self.assertRaisesRegex(ValueError, "profile order differs from the V5 schema"):
            builder.parse_map(stale)

    def test_copied_waddle_class_is_rejected(self):
        stale = self.markdown.replace(
            "Waddle uses the Style classification.",
            "Waddle uses the Modifier classification.",
        )
        self.assertNotEqual(stale, self.markdown)
        with self.assertRaisesRegex(ValueError, "Waddle classification differs from the catalog"):
            builder.parse_map(stale)

    def test_invalid_schema_shape_is_rejected(self):
        malformed = [[], {}, {"$defs": []}, {"$defs": {"profileClassification": []}}]
        for values in ([], "style", [None], [[]], ["style", "style"]):
            malformed.append({"$defs": {"profileClassification": {"enum": values}}})
        for schema in malformed:
            with self.subTest(schema=schema):
                with self.assertRaisesRegex(ValueError, "invalid V5 schema"):
                    self.validate_with_sources(schema, self.catalog)

    def test_invalid_catalog_shape_is_rejected(self):
        for catalog in ([], {}, {"profiles": {}}, {"profiles": [None]}, {"profiles": [{}]}):
            with self.subTest(catalog=catalog):
                with self.assertRaisesRegex(ValueError, "invalid profile catalog"):
                    self.validate_with_sources(self.schema, catalog)
        catalog = copy.deepcopy(self.catalog)
        next(profile for profile in catalog["profiles"] if profile["id"] == "waddle")["classification"] = []
        with self.assertRaisesRegex(ValueError, "no classified Waddle profile"):
            self.validate_with_sources(self.schema, catalog)

    def test_ambiguous_waddle_is_rejected(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["profiles"].append({"id": "waddle", "classification": "modifier"})
        with self.assertRaisesRegex(ValueError, "exactly one Waddle profile; found 2"):
            self.validate_with_sources(self.schema, catalog)
        catalog["profiles"] = [profile for profile in catalog["profiles"] if profile["id"] != "waddle"]
        with self.assertRaisesRegex(ValueError, "exactly one Waddle profile; found 0"):
            self.validate_with_sources(self.schema, catalog)

    def test_source_links_preserve_fragments(self):
        self.assertEqual(builder.source_path("CONTEXT.md#behavior"), "CONTEXT.md#behavior")
        template = (HERE / "template.html").read_text()
        helpers = template[template.index("  const esc ="):template.index("  const color =")]
        script = helpers + """
const assert = require('node:assert/strict');
assert.equal(sourceUrl('CONTEXT.md#behavior'), '../../../CONTEXT.md#behavior');
assert.equal(sourceUrl('documentation/My guide.md#part-two'), '../../../documentation/My%20guide.md#part-two');
assert.equal(sourceUrl('documentation/guide.md'), '../../../documentation/guide.md');
assert.equal(sourceUrl('CONTEXT.md#two%20words'), '../../../CONTEXT.md#two%20words');
assert.ok(sourceLink('CONTEXT.md#behavior').includes('href="../../../CONTEXT.md#behavior"'));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
