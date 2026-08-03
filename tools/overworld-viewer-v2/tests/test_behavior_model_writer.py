import copy
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WRITER_PATH = ROOT / "tools/overworld-viewer-v2/behavior_model_writer.py"
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"
MODEL_REL = Path("data/OverworldWildBehaviorModelV40.json")
INC_REL = Path("data/OverworldWildBehaviorDataV40.generated.inc")
HEADER_REL = Path("include/overworld_wild_behavior_data.h")
MANAGED = (MODEL_REL, INC_REL, HEADER_REL)


def load_writer():
    spec = importlib.util.spec_from_file_location("_behavior_model_writer_test", WRITER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_viewer():
    spec = importlib.util.spec_from_file_location("_behavior_model_writer_viewer_test", VIEWER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile_payload(profile, *, draft_id=None, name=None):
    result = {
        "name": name or profile["name"],
        "descriptiveTags": list(profile["descriptiveTags"]),
        "values": copy.deepcopy(profile["body"]["values"]),
    }
    if draft_id:
        result["draftId"] = draft_id
        result["templateProvenance"] = {
            "kind": profile["body"]["provenanceKind"],
            "provenanceId": profile["provenanceId"],
        }
    else:
        result["stableId"] = profile["stableId"]
    return result


def node_payload(node, *, draft_id=None, profile_ref=None):
    result = {
        "profileRef": profile_ref if profile_ref is not None else node["profileId"],
        "semanticRoleId": node["semanticRoleId"],
        "customRoleId": node["customRoleId"] or None,
        "base": bool(node["base"]),
        "optional": bool(node["optional"]),
        "hidden": bool(node["hidden"]),
    }
    result["draftId" if draft_id else "stableId"] = draft_id or node["stableId"]
    return result


def controller_payload(controller, *, draft_id=None, nodes=None, name=None):
    result = {
        "name": name or controller["name"],
        "nodes": nodes if nodes is not None else [node_payload(node) for node in controller["nodes"]],
        "scalarDefaults": {key: controller[key] for key in (
            "alertState", "alertEmote", "alertTime", "alertness",
            "alertRange", "alertChance", "stamina", "restTime",
        )},
        "policyIds": {key: controller[key] for key in (
            "spawnPolicyId", "populationPolicyId", "hookSetId",
        )},
    }
    result["draftId" if draft_id else "stableId"] = draft_id or controller["stableId"]
    return result


def applicability_payload(applicability, identity=None, **updates):
    excluded = {"stableId", "registryKey"}
    result = {key: copy.deepcopy(value) for key, value in applicability.items() if key not in excluded}
    chosen = applicability["stableId"] if identity is None else identity
    result["draftId" if isinstance(chosen, str) else "stableId"] = chosen
    result.update(updates)
    return result


def definition_payload(definition, identity, applicability, applicability_identity=None, **updates):
    excluded = {"stableId", "registryKey", "nameId"}
    result = {key: copy.deepcopy(value) for key, value in definition.items() if key not in excluded}
    result["draftId" if isinstance(identity, str) else "stableId"] = identity
    result["applicability"] = applicability_payload(applicability, applicability_identity)
    if applicability_identity is not None:
        result["applicabilityId"] = applicability_identity
    result.update(updates)
    return result


def transition_payload(transition, definition, applicability, identity, definition_identity,
                       *, applicability_identity=None, operation=None):
    controller_ids = ([definition["controllerId"]] if definition["controllerId"] else [12289, 12290, 12291])
    result = {
        "name": f"Transition {identity}",
        "controllerIds": controller_ids,
        "candidateDefinitionId": definition_identity,
        "candidateDefinition": definition_payload(
            definition, definition_identity, applicability, applicability_identity
        ),
        "ownerId": transition["ownerId"],
        "trigger": transition["trigger"],
        "fromRoleMask": transition["fromRoleMask"],
        "dispatchPriority": transition["dispatchPriority"],
        "order": transition["order"],
        "guards": [], "operations": [operation] if operation else [],
        "actions": [], "recoveryActions": [],
    }
    result["draftId" if isinstance(identity, str) else "stableId"] = identity
    return result


def saved_transition_payload(model, transition, *, name):
    definition = next(item for item in model["overrideDefinitions"]
                      if item["stableId"] == transition["definitionId"])
    applicability = next(item for item in model["applicability"]
                         if item["stableId"] == definition["applicabilityId"])
    result = transition_payload(
        transition, definition, applicability, transition["stableId"], definition["stableId"]
    )
    result["name"] = name
    result["guards"] = [{
        "stableId": child["stableId"], "kind": child["kind"],
        "negate": bool(child["negate"]), "payload": child["payload"],
        "referenceId": child["referenceId"] or None,
    } for child in transition["guards"]]
    result["operations"] = [{
        "stableId": child["stableId"], "definitionId": child["definitionId"] or None,
        "ownerId": child["ownerId"] or None,
        "replacementDefinitionId": child["replacementDefinitionId"] or None,
        "policyId": child["policyId"] or None, "instanceKey": child["instanceKey"] or None,
        "kind": child["kind"], "busyPolicy": child["busyPolicy"],
        "required": bool(child["required"]),
    } for child in transition["operations"]]
    result["actions"] = [{
        "stableId": child["stableId"], "phase": child["phase"], "kind": child["kind"],
        "referenceId": child["referenceId"] or None, "payload": child["payload"],
    } for child in transition["actions"]]
    result["recoveryActions"] = [{
        "stableId": child["stableId"], "ownerId": child["ownerId"],
        "kind": child["kind"], "required": bool(child["required"]),
    } for child in transition["recoveryActions"]]
    return result


class BehaviorModelWriterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.writer = load_writer()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        for relative in MANAGED:
            target = self.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def tearDown(self):
        self.temp.cleanup()

    def bytes(self):
        return {relative: (self.workspace / relative).read_bytes() for relative in MANAGED}

    def model(self):
        return json.loads((self.workspace / MODEL_REL).read_text())

    def test_noop_is_byte_identical(self):
        before = self.bytes()
        self.assertEqual(self.writer.apply_behavior_model_changes(
            self.workspace, {"modelVersion": 40}
        ), {})
        self.assertEqual(self.bytes(), before)

    def test_multi_entity_create_allocates_parent_then_owned_descendants(self):
        model = self.model()
        profile_draft = profile_payload(
            model["stateProfiles"][0], draft_id="draft:profile", name="Editor profile"
        )
        node = node_payload(
            model["controllers"][0]["nodes"][0],
            draft_id="draft:node", profile_ref="draft:profile",
        )
        controller_draft = controller_payload(
            model["controllers"][0], draft_id="draft:controller",
            nodes=[node], name="Editor controller",
        )
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "modelVersion": 40,
            "stateProfiles": {"create": [profile_draft]},
            "controllers": {"create": [controller_draft]},
        })
        self.assertEqual(mapping["draft:node"], mapping["draft:controller"] + 1)
        self.assertEqual(mapping["draft:controller"], mapping["draft:profile"] + 2)
        saved = self.model()
        profile = next(item for item in saved["stateProfiles"] if item["stableId"] == mapping["draft:profile"])
        controller = next(item for item in saved["controllers"] if item["stableId"] == mapping["draft:controller"])
        self.assertEqual(profile["name"], "Editor profile")
        self.assertEqual(profile["bodyId"], mapping["draft:profile"] + 1)
        self.assertEqual(controller["nodes"][0]["profileId"], mapping["draft:profile"])
        self.assertEqual(controller["nodes"][0]["stableId"], mapping["draft:node"])

    def test_reorder_and_metadata_update_preserve_existing_ids(self):
        model = self.model()
        controller = model["controllers"][0]
        original_ids = [node["stableId"] for node in controller["nodes"]]
        update = controller_payload(
            controller, nodes=[node_payload(node) for node in reversed(controller["nodes"])],
            name="Reordered controller",
        )
        profile = profile_payload(
            model["stateProfiles"][0], name="Renamed state"
        )
        profile["descriptiveTags"] = ["bird", "calm"]
        transition = model["transitions"][0]
        transition_update = saved_transition_payload(model, transition, name="Named transition")
        self.writer.apply_behavior_model_changes(self.workspace, {
            "controllers": {"update": [update]},
            "stateProfiles": {"update": [profile]},
            "transitions": {"update": [transition_update]},
        })
        saved = self.model()
        actual = next(item for item in saved["controllers"] if item["stableId"] == controller["stableId"])
        self.assertEqual([node["stableId"] for node in actual["nodes"]], list(reversed(original_ids)))
        self.assertEqual(actual["name"], "Reordered controller")
        actual_profile = next(item for item in saved["stateProfiles"] if item["stableId"] == profile["stableId"])
        self.assertEqual((actual_profile["name"], actual_profile["descriptiveTags"]),
                         ("Renamed state", ["bird", "calm"]))
        actual_transition = next(item for item in saved["transitions"]
                                 if item["stableId"] == transition["stableId"])
        self.assertEqual(actual_transition["name"], "Named transition")
        blob = self.writer.v40.read_inc(self.workspace / INC_REL)
        decoded = self.writer.v40.decode_blob(blob, stable_id_history=saved["stableIdHistory"])
        self.assertEqual(
            self.writer.v40.merge_authored_metadata(decoded, saved), saved
        )
        viewer = load_viewer()
        viewer.V40_BEHAVIOR_DATA_SOURCE = self.workspace / INC_REL
        viewer.V40_BEHAVIOR_MODEL_SOURCE = self.workspace / MODEL_REL
        editor = viewer.build_v40_state_profile_editor_data()
        self.assertEqual(next(item for item in editor["stateProfiles"]
                              if item["stableId"] == profile["stableId"])["name"], "Renamed state")
        self.assertEqual(next(item for item in editor["stateProfiles"]
                              if item["stableId"] == profile["stableId"])["descriptiveTags"],
                         ["bird", "calm"])
        self.assertEqual(next(item for item in editor["controllers"]
                              if item["stableId"] == controller["stableId"])["name"],
                         "Reordered controller")
        self.assertEqual(next(item for item in editor["transitionGraph"]["transitions"]
                              if item["stableId"] == transition["stableId"])["name"],
                         "Named transition")

    def test_transition_reorder_survives_wire_and_reader_reload(self):
        model = self.model()
        first, second = model["transitions"][:2]
        first_update = saved_transition_payload(
            model, first, name=first.get("name", first["registryKey"])
        )
        second_update = saved_transition_payload(
            model, second, name=second.get("name", second["registryKey"])
        )
        first_update["order"], second_update["order"] = second["order"], first["order"]
        stable_ids = {item["stableId"] for item in model["transitions"]}
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"update": [first_update, second_update]},
        })
        saved = self.model()
        self.assertEqual({item["stableId"] for item in saved["transitions"]}, stable_ids)
        self.assertEqual([item["stableId"] for item in saved["transitions"][:2]],
                         [second["stableId"], first["stableId"]])
        self.assertEqual([item["order"] for item in saved["transitions"]],
                         list(range(len(saved["transitions"]))))
        blob = self.writer.v40.read_inc(self.workspace / INC_REL)
        decoded = self.writer.v40.decode_blob(blob, stable_id_history=saved["stableIdHistory"])
        self.assertEqual([item["stableId"] for item in decoded["transitions"][:2]],
                         [second["stableId"], first["stableId"]])
        viewer = load_viewer()
        viewer.V40_BEHAVIOR_DATA_SOURCE = self.workspace / INC_REL
        viewer.V40_BEHAVIOR_MODEL_SOURCE = self.workspace / MODEL_REL
        reloaded = viewer.build_v40_state_profile_editor_data()
        self.assertEqual(
            [item["stableId"] for item in reloaded["transitionGraph"]["transitions"][:2]],
            [second["stableId"], first["stableId"]],
        )

    def test_active_and_tired_duplicates_preserve_template_provenance(self):
        model = self.model()
        sources = [next(item for item in model["stateProfiles"]
                        if item["body"]["provenanceKind"] == kind) for kind in (2, 3)]
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [
                profile_payload(sources[0], draft_id="draft:active"),
                profile_payload(sources[1], draft_id="draft:tired"),
            ]},
        })
        saved = self.model()
        by_id = {item["stableId"]: item for item in saved["stateProfiles"]}
        for draft, source in (("draft:active", sources[0]), ("draft:tired", sources[1])):
            copy_record = by_id[mapping[draft]]
            self.assertEqual(copy_record["body"]["provenanceKind"], source["body"]["provenanceKind"])
            self.assertEqual(copy_record["provenanceId"], source["provenanceId"])

    def test_local_clone_remaps_owned_applicability_and_controller_refs(self):
        model = self.model()
        source_controller = model["controllers"][0]
        node = node_payload(source_controller["nodes"][0], draft_id="draft:local-node")
        controller = controller_payload(
            source_controller, draft_id="draft:local-controller", nodes=[node]
        )
        source_transition = model["transitions"][0]
        definition = copy.deepcopy(next(item for item in model["overrideDefinitions"]
                                        if item["stableId"] == source_transition["definitionId"]))
        rule = copy.deepcopy(next(item for item in model["applicability"]
                                  if item["stableId"] == definition["applicabilityId"]))
        definition.update({"controllerId": "draft:local-controller", "nodeId": "draft:local-node"})
        rule["controllerId"] = "draft:local-controller"
        transition = transition_payload(
            source_transition, definition, rule, "draft:local-transition", "draft:local-definition",
            applicability_identity="draft:local-applicability",
        )
        transition["controllerIds"] = ["draft:local-controller"]
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "controllers": {"create": [controller]},
            "transitions": {"create": [transition]},
        })
        saved = self.model()
        saved_definition = next(item for item in saved["overrideDefinitions"]
                                if item["stableId"] == mapping["draft:local-definition"])
        saved_rule = next(item for item in saved["applicability"]
                          if item["stableId"] == mapping["draft:local-applicability"])
        self.assertEqual(saved_definition["controllerId"], mapping["draft:local-controller"])
        self.assertEqual(saved_definition["nodeId"], mapping["draft:local-node"])
        self.assertEqual(saved_definition["applicabilityId"], saved_rule["stableId"])
        self.assertEqual(saved_rule["controllerId"], mapping["draft:local-controller"])

    def test_shared_definition_and_applicability_retire_after_last_backlink(self):
        model = self.model()
        source_transition = model["transitions"][0]
        definition = copy.deepcopy(next(item for item in model["overrideDefinitions"]
                                        if item["stableId"] == source_transition["definitionId"]))
        rule = copy.deepcopy(next(item for item in model["applicability"]
                                  if item["stableId"] == definition["applicabilityId"]))
        definition.update({"controllerId": 0, "nodeId": 0, "recoveryTransitionId": 0})
        left = transition_payload(
            source_transition, definition, rule, "draft:shared-left", "draft:shared-definition",
            applicability_identity="draft:shared-applicability",
        )
        right = transition_payload(
            source_transition, definition, rule, "draft:shared-right", "draft:shared-definition",
            applicability_identity="draft:shared-applicability",
        )
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [left, right]},
        })
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"remove": [mapping["draft:shared-left"]]},
        })
        middle = self.model()
        self.assertIn(mapping["draft:shared-definition"],
                      {item["stableId"] for item in middle["overrideDefinitions"]})
        self.assertIn(mapping["draft:shared-applicability"],
                      {item["stableId"] for item in middle["applicability"]})
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"remove": [mapping["draft:shared-right"]]},
        })
        final = self.model()
        self.assertNotIn(mapping["draft:shared-definition"],
                         {item["stableId"] for item in final["overrideDefinitions"]})
        self.assertNotIn(mapping["draft:shared-applicability"],
                         {item["stableId"] for item in final["applicability"]})
        tombstones = {event["registryKey"] for event in final["stableIdHistory"]["extensions"]
                      if event["kind"] == "retire"}
        self.assertIn(f"editor:override-definition:{mapping['draft:shared-definition']}", tombstones)
        self.assertIn(f"editor:applicability:{mapping['draft:shared-applicability']}", tombstones)

    def test_rebind_retires_replaced_owned_definition_and_applicability(self):
        model = self.model()
        source = model["transitions"][0]
        definition = copy.deepcopy(next(item for item in model["overrideDefinitions"]
                                        if item["stableId"] == source["definitionId"]))
        rule = copy.deepcopy(next(item for item in model["applicability"]
                                  if item["stableId"] == definition["applicabilityId"]))
        definition.update({"controllerId": 0, "nodeId": 0, "recoveryTransitionId": 0})
        created = transition_payload(
            source, definition, rule, "draft:rebind-transition", "draft:old-definition",
            applicability_identity="draft:old-applicability",
        )
        first = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [created]},
        })
        saved = self.model()
        transition = next(item for item in saved["transitions"]
                          if item["stableId"] == first["draft:rebind-transition"])
        rebound = transition_payload(
            transition, definition, rule, transition["stableId"], "draft:new-definition",
            applicability_identity="draft:new-applicability",
        )
        second = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"update": [rebound]},
        })
        final = self.model()
        definition_ids = {item["stableId"] for item in final["overrideDefinitions"]}
        applicability_ids = {item["stableId"] for item in final["applicability"]}
        self.assertNotIn(first["draft:old-definition"], definition_ids)
        self.assertNotIn(first["draft:old-applicability"], applicability_ids)
        self.assertIn(second["draft:new-definition"], definition_ids)
        self.assertIn(second["draft:new-applicability"], applicability_ids)

    def test_delete_tombstones_owned_body_and_never_reuses_ids(self):
        source = self.model()["stateProfiles"][0]
        first = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [profile_payload(source, draft_id="draft:first")]},
        })["draft:first"]
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"remove": [first]},
        })
        deleted = self.model()
        allocations = deleted["stableIdHistory"]["extensions"]
        retired = [event["registryKey"] for event in allocations if event["kind"] == "retire"]
        self.assertIn(f"editor:state-profile:{first}", retired)
        self.assertIn(f"editor:state-body:{first + 1}", retired)
        second = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [profile_payload(source, draft_id="draft:second")]},
        })["draft:second"]
        self.assertGreater(second, first + 1)

    def test_deep_cycles_and_definition_references_are_remapped(self):
        model = self.model()
        transition = model["transitions"][0]
        definition = copy.deepcopy(next(
            item for item in model["overrideDefinitions"]
            if item["stableId"] == transition["definitionId"]
        ))
        applicability = copy.deepcopy(next(
            item for item in model["applicability"]
            if item["stableId"] == definition["applicabilityId"]
        ))
        definition["controllerId"] = 0
        definition["nodeId"] = 0
        left_op = {
            "draftId": "draft:left-op", "definitionId": "draft:left-def",
            "ownerId": transition["ownerId"], "replacementDefinitionId": "draft:right-def",
            "policyId": 0, "instanceKey": "draft:right-def", "kind": 1,
            "busyPolicy": 1, "required": False,
        }
        right_op = {
            "draftId": "draft:right-op", "definitionId": "draft:right-def",
            "ownerId": transition["ownerId"], "replacementDefinitionId": "draft:left-def",
            "policyId": 0, "instanceKey": "draft:left-def", "kind": 1,
            "busyPolicy": 1, "required": False,
        }
        left = transition_payload(
            transition, definition, applicability, "draft:left", "draft:left-def",
            operation=left_op
        )
        right = transition_payload(
            transition, definition, applicability, "draft:right", "draft:right-def",
            operation=right_op
        )
        left["candidateDefinition"]["recoveryTransitionId"] = "draft:right"
        right["candidateDefinition"]["recoveryTransitionId"] = "draft:left"
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [left, right]},
        })
        saved = self.model()
        left_saved = next(item for item in saved["transitions"] if item["stableId"] == mapping["draft:left"])
        right_saved = next(item for item in saved["transitions"] if item["stableId"] == mapping["draft:right"])
        definitions = {item["stableId"]: item for item in saved["overrideDefinitions"]}
        self.assertEqual(definitions[left_saved["definitionId"]]["recoveryTransitionId"], right_saved["stableId"])
        self.assertEqual(definitions[right_saved["definitionId"]]["recoveryTransitionId"], left_saved["stableId"])
        self.assertEqual(left_saved["operations"][0]["replacementDefinitionId"], right_saved["definitionId"])
        self.assertEqual(right_saved["operations"][0]["instanceKey"], left_saved["definitionId"])

    def test_hard_cap_and_invalid_payload_leave_all_files_unchanged(self):
        source = self.model()["stateProfiles"][0]
        creates = [profile_payload(source, draft_id=f"draft:overflow-{index}") for index in range(30)]
        before = self.bytes()
        with self.assertRaises(self.writer.v40.ModelError):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "stateProfiles": {"create": creates},
            })
        self.assertEqual(self.bytes(), before)
        with self.assertRaises(self.writer.BehaviorModelWriteError):
            self.writer.apply_behavior_model_changes(self.workspace, {"profiles": []})
        self.assertEqual(self.bytes(), before)
        mixed = profile_payload(source, draft_id="draft:mixed")
        mixed["registryKey"] = "legacy:caller-owned"
        with self.assertRaises(self.writer.BehaviorModelWriteError):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "stateProfiles": {"create": [mixed]},
            })
        self.assertEqual(self.bytes(), before)

    def test_failure_before_or_during_replace_rolls_back_every_file(self):
        source = self.model()["stateProfiles"][0]
        update = profile_payload(source, name="Atomic rename")
        update["values"]["movementRange"] = (update["values"]["movementRange"] + 1) & 0xFF
        payload = {"stateProfiles": {"update": [update]}}
        before = self.bytes()

        def fail_before(index, _path):
            if index == 0:
                raise RuntimeError("before replace")

        with self.assertRaisesRegex(RuntimeError, "before replace"):
            self.writer.apply_behavior_model_changes(
                self.workspace, payload, _before_replace=fail_before
            )
        self.assertEqual(self.bytes(), before)

        def fail_during(index, _path):
            if index == 1:
                raise RuntimeError("during replace")

        with self.assertRaisesRegex(RuntimeError, "during replace"):
            self.writer.apply_behavior_model_changes(
                self.workspace, payload, _before_replace=fail_during
            )
        self.assertEqual(self.bytes(), before)

        attempts = 0
        def replace_then_raise(source, destination):
            nonlocal attempts
            os.replace(source, destination)
            attempts += 1
            if attempts == 1:
                raise RuntimeError("after replace")

        with self.assertRaisesRegex(RuntimeError, "after replace"):
            self.writer.apply_behavior_model_changes(
                self.workspace, payload, _replace_func=replace_then_raise
            )
        self.assertEqual(self.bytes(), before)


if __name__ == "__main__":
    unittest.main()
