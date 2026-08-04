import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VIEWER = ROOT / "scripts" / "overworld_behavior_profile_viewer.py"
FIELD_METADATA = ROOT / "scripts" / "overworld_wild_behavior_v40_field_metadata.py"
CODEC = ROOT / "scripts" / "overworld_wild_behavior_model_v40.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def load_codec():
    spec = importlib.util.spec_from_file_location("_v40_editor_test_codec", CODEC)
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
        bodies = {}
        for profile in self.data["stateProfiles"]:
            self.assertEqual(set(profile["values"]), {
                field["key"] for field in self.data["stateProfileFields"]
            })
            self.assertTrue(profile["bodyRegistryKey"])
            signature = (
                profile["bodyRegistryKey"], profile["bodyProvenance"]["kind"],
                tuple(profile["values"][field["key"]]
                      for field in self.data["stateProfileFields"]),
            )
            self.assertEqual(bodies.setdefault(profile["bodyId"], signature), signature)
        self.assertLess(len(bodies), len(self.data["stateProfiles"]))

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

    def test_applicability_only_controller_scope_drives_endpoint_rosters(self):
        codec = load_codec()
        model = codec.load_model()
        transition = model["transitions"][0]
        definition = next(
            item for item in model["overrideDefinitions"]
            if item["stableId"] == transition["definitionId"]
        )
        self.assertEqual(definition["controllerId"], 0)
        rule = next(
            item for item in model["applicability"]
            if item["stableId"] == definition["applicabilityId"]
        )
        controller_id = model["controllers"][0]["stableId"]
        rule.update({"kind": rule["kind"] | 2, "controllerId": controller_id})
        blob = codec.encode_model(model)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_path = root / "model.json"
            data_path = root / "data.inc"
            model_path.write_text(json.dumps(model))
            data_path.write_text(codec.render_inc(blob))
            viewer = load_viewer()
            viewer.V40_BEHAVIOR_MODEL_SOURCE = model_path
            viewer.V40_BEHAVIOR_DATA_SOURCE = data_path
            scoped = viewer.build_v40_state_profile_editor_data()

        endpoint_transition = next(
            item for item in scoped["transitionGraph"]["transitions"]
            if item["stableId"] == transition["stableId"]
        )
        self.assertEqual(endpoint_transition["controllerIds"], [controller_id])
        owners = [
            controller["stableId"] for controller in scoped["controllers"]
            if transition["stableId"] in controller["transitionIds"]
        ]
        self.assertEqual(owners, [controller_id])

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

    def test_stack_preview_resolves_species_priority_from_endpoint_payload(self):
        self.assertEqual(len(self.data["assignmentActions"]), 3)
        self.assertEqual(len(self.data["genericAssignments"]), 2)
        self.assertEqual(len(self.data["speciesAssignments"]), 113)
        selected = next(item for item in self.data["speciesAssignments"]
                        if item["controllerIndex"] == 1)
        module_url = (ROOT / "tools" / "overworld-viewer-v2" / "static"
                      / "stack-preview.js").as_uri()
        script = f"""
import fs from "node:fs";
const {{ resolveStackPreviewContext }} = await import({json.dumps(module_url)});
const model = JSON.parse(fs.readFileSync(0, "utf8"));
const resolved = resolveStackPreviewContext(model, {{
  species: {selected['species']}, groupMask: 1, behaviorClass: 0,
}});
process.stdout.write(JSON.stringify(resolved));
"""
        process = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=ROOT,
            input=json.dumps(self.data),
            text=True,
            capture_output=True,
            check=True,
        )
        resolved = json.loads(process.stdout)
        action = self.data["assignmentActions"][selected["controllerIndex"]]
        controller_id = int.from_bytes(bytes(action["payload"][:2]), "little")
        self.assertEqual(resolved["controllerRef"], controller_id)
        self.assertEqual(resolved["dispatch"], {
            "kind": "species",
            "assignmentId": selected["stableId"],
            "priority": selected["dispatchPriority"],
        })

    def test_stack_preview_replays_real_tired_recovery_contract(self):
        module_url = (ROOT / "tools" / "overworld-viewer-v2" / "static"
                      / "stack-preview.js").as_uri()
        script = f"""
import fs from "node:fs";
const {{ runStackEventSequence }} = await import({json.dumps(module_url)});
const model = JSON.parse(fs.readFileSync(0, "utf8"));
const sequence = runStackEventSequence({{
  model,
  context: {{ controllerRef: model.controllers[0].stableId, systemRoute: 2 }},
  steps: [
    {{ kind: "event", trigger: 2 }},
    {{ kind: "tick", clock: 1, ticks: 4 }},
  ],
}});
const tired = sequence.history?.[1]?.snapshot?.layers?.find(
  (layer) => layer.definitionId === 0x7004 && layer.ownerId === 0x8105
);
const recovery = sequence.history?.[2]?.report?.recoveries?.[0];
process.stdout.write(JSON.stringify({{
  ok: sequence.ok,
  tired: tired ? {{ definitionId: tired.definitionId, ownerId: tired.ownerId }} : null,
  recovery,
  remainingLayers: sequence.result?.layers?.length,
}}));
"""
        process = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=ROOT,
            input=json.dumps(self.data),
            text=True,
            capture_output=True,
            check=True,
        )
        replay = json.loads(process.stdout)
        self.assertTrue(replay["ok"])
        self.assertEqual(replay["tired"], {
            "definitionId": 0x7004,
            "ownerId": 0x8105,
        })
        recovery = replay["recovery"]
        self.assertEqual(recovery["transitionId"], 0xA003)
        self.assertEqual(recovery["operations"][0], {
            "operationId": 0xC003,
            "kind": 3,
            "status": "removed",
            "definitionId": 0x7004,
            "ownerId": 0x8105,
            "instanceKey": 0,
        })
        self.assertEqual(
            [item["ownerId"] for item in recovery["operations"][1:]],
            [0x8102, 0x8103, 0x8104],
        )
        self.assertTrue(all(item["kind"] == 5
                            for item in recovery["operations"][1:]))
        self.assertEqual(replay["remainingLayers"], 0)

    def test_validation_metadata_matches_v40_wire_contract(self):
        schema = self.data["validationSchema"]
        self.assertEqual(schema["stateFieldCount"], 28)
        self.assertEqual(schema["stackCapacity"], 8)
        self.assertEqual(schema["unsigned"], {
            "byte": 0xFF, "short": 0xFFFF, "word": 0xFFFFFFFF,
        })
        self.assertEqual(schema["childCountMaximums"], {
            "guards": 0xFFFF, "operations": 0xFFFF,
            "actions": 0xFFFF, "recoveryActions": 0xFF,
        })
        self.assertEqual(schema["domains"]["actionKind"], tuple(range(1, 9)))
        self.assertEqual(
            {(item["name"], item["stride"]) for item in schema["wireSections"]},
            set(load_viewer().V40_SECTION_SPECS),
        )
        self.assertEqual(schema["crossReferences"]["transition.definition"],
                         "overrideDefinitions")

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
