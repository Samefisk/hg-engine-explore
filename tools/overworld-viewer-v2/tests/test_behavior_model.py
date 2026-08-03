import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VIEWER = ROOT / "scripts" / "overworld_behavior_profile_viewer.py"
FIELD_METADATA = ROOT / "scripts" / "overworld_wild_behavior_v40_field_metadata.py"


def load_viewer():
    spec = importlib.util.spec_from_file_location("_v40_editor_test_viewer", VIEWER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_field_metadata():
    spec = importlib.util.spec_from_file_location("_v40_editor_test_fields", FIELD_METADATA)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BehaviorModelEditorDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_viewer().build_v40_state_profile_editor_data()

    def test_catalog_profiles_are_complete_stable_entities(self):
        self.assertEqual(self.data["modelVersion"], 40)
        self.assertEqual(len(self.data["stateProfileFields"]), 28)
        self.assertEqual(len(self.data["stateProfiles"]), 58)
        stable_ids = [profile["stableId"] for profile in self.data["stateProfiles"]]
        self.assertEqual(len(stable_ids), len(set(stable_ids)))
        for profile in self.data["stateProfiles"]:
            self.assertEqual(set(profile["values"]), {
                field["key"] for field in self.data["stateProfileFields"]
            })

    def test_profiles_do_not_own_semantic_roles(self):
        profile = self.data["stateProfiles"][0]
        self.assertNotIn("semanticRole", profile)
        self.assertIn("bodyProvenance", profile)
        self.assertIsInstance(profile["descriptiveTags"], list)
        self.assertNotIn("runtimeRole", profile)

    def test_locomotion_domain_matches_authoritative_v40_metadata(self):
        metadata = load_field_metadata()
        locomotion = next(
            field for field in self.data["stateProfileFields"]
            if field["key"] == "locomotion"
        )
        self.assertEqual(
            {option["value"] for option in locomotion["options"]},
            set(metadata.SCALAR_DOMAINS[4][1]),
        )

    def test_node_backlinks_reference_stable_ids(self):
        linked = [profile for profile in self.data["stateProfiles"] if profile["backlinks"]]
        self.assertTrue(linked)
        for profile in linked:
            for backlink in profile["backlinks"]:
                self.assertGreater(backlink["controllerId"], 0)
                self.assertGreater(backlink["nodeId"], 0)
                self.assertIn("semanticRole", backlink)


if __name__ == "__main__":
    unittest.main()
