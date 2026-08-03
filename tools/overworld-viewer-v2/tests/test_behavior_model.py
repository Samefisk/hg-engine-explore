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

    def test_controllers_expose_exact_typed_rosters_and_policy_defaults(self):
        self.assertEqual(len(self.data["controllers"]), 3)
        first = self.data["controllers"][0]
        self.assertEqual(first["stableId"], 12289)
        self.assertEqual(first["baseNodeId"], 12545)
        self.assertEqual(len(first["nodes"]), 7)
        self.assertEqual(sum(node["base"] for node in first["nodes"]), 1)
        self.assertEqual(
            first["scalarDefaults"],
            {"alertState": 2, "alertEmote": 7, "alertTime": 10, "alertness": 3,
             "alertRange": 2, "alertChance": 100, "stamina": 20, "restTime": 10},
        )
        self.assertEqual(first["policyIds"], {
            "spawnPolicyId": 16385,
            "populationPolicyId": 16641,
            "hookSetId": 16897,
        })
        self.assertEqual(
            len({node["semanticRoleId"] for node in first["nodes"]}),
            len(first["nodes"]),
        )
        self.assertNotIn("semanticRole", self.data["stateProfiles"][0])

    def test_transition_graph_preserves_exact_v40_rows_and_child_slices(self):
        transitions = self.data["transitionGraph"]["transitions"]
        self.assertEqual(len(transitions), 26)
        first = transitions[0]
        self.assertEqual(first["stableId"], 40961)
        self.assertEqual(first["trigger"], 1)
        self.assertEqual(first["fromRoleMask"], 0x7F)
        self.assertEqual(first["dispatchPriority"], 0x2000)
        self.assertEqual(first["controllerIds"], [12289, 12290, 12291])
        self.assertEqual((len(first["guards"]), len(first["operations"]), len(first["actions"])), (1, 1, 3))
        scoped = transitions[-1]
        self.assertEqual(scoped["controllerIds"], [12291])
        self.assertEqual(scoped["candidateDefinition"]["semanticRoleId"], 0)
        self.assertTrue(all(len(controller["transitionIds"]) == 20 for controller in self.data["controllers"]))

    def test_stack_preview_catalog_preserves_exact_v40_definitions(self):
        self.assertEqual(len(self.data["owners"]), 10)
        self.assertEqual(len(self.data["overrideDefinitions"]), 19)
        self.assertEqual(len(self.data["applicability"]), 19)
        self.assertEqual(self.data["stackPreview"], {
            "capacity": 8,
            "precedence": ["channel", "priority", "definitionStableId", "ownerId", "instanceKey"],
            "channels": [
                {"value": 0, "label": "Static context"},
                {"value": 1, "label": "Controller state"},
                {"value": 2, "label": "Temporary effect"},
                {"value": 3, "label": "Scripted force"},
                {"value": 4, "label": "Possession"},
                {"value": 5, "label": "System safety"},
            ],
        })
        applicability_ids = {item["stableId"] for item in self.data["applicability"]}
        owner_ids = {item["stableId"] for item in self.data["owners"]}
        for definition in self.data["overrideDefinitions"]:
            self.assertIn(definition["applicabilityId"], applicability_ids)
            self.assertEqual(definition["applicability"]["stableId"], definition["applicabilityId"])
            if definition["hasRequiredOwnerId"]:
                self.assertIn(definition["requiredOwnerId"], owner_ids)
            for key in (
                "kind", "channel", "priority", "selectorKind", "mapLifetime",
                "battleLifetime", "timerClock", "timerSource", "hiddenTimerPolicy",
                "recoveryPolicy", "allowMultipleOwners", "allowMultipleInstancesPerOwner",
            ):
                self.assertIn(key, definition)

    def test_controller_node_slices_reject_bounds_overlap_and_wrong_owner(self):
        module = load_viewer()
        byte_values = module.re.findall(
            r"\b0x([0-9A-Fa-f]{2})\b",
            module.V40_BEHAVIOR_DATA_SOURCE.read_text(),
        )
        blob = bytes(int(value, 16) for value in byte_values)
        controllers = module._v40_records(blob, "controllers", "<7H10B")
        nodes, slices = module._v40_controller_node_slices(blob, controllers)
        self.assertEqual([node[0] for node in slices[12289]], [node[0] for node in nodes[:7]])

        out_of_bounds = [tuple(record) for record in controllers]
        out_of_bounds[0] = (*out_of_bounds[0][:2], len(nodes), 1, *out_of_bounds[0][4:])
        with self.assertRaises(module.ParseError):
            module._v40_controller_node_slices(blob, out_of_bounds)

        wrong_owner = bytearray(blob)
        node_offset, _, _ = module._v40_section(blob, "controllerNodes")
        module.struct.pack_into("<H", wrong_owner, node_offset + 2, 12290)
        with self.assertRaises(module.ParseError):
            module._v40_controller_node_slices(bytes(wrong_owner), controllers)

        overlap = [tuple(record) for record in controllers]
        overlap[1] = (*overlap[1][:2], 0, overlap[1][3], *overlap[1][4:])
        with self.assertRaises(module.ParseError):
            module._v40_controller_node_slices(blob, overlap)


if __name__ == "__main__":
    unittest.main()
