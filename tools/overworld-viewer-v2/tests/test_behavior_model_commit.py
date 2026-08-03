#!/usr/bin/env python3
"""Global Save coverage for the V40 behavior-model commit domain."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools/overworld-viewer-v2"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import behavior_model_writer as writer  # noqa: E402
import reliability  # noqa: E402


def revision(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return f"sha256:{digest.hexdigest()}"


class FakeLegacy:
    BUILD_LOCK = threading.RLock()

    def __init__(self, route_source: Path):
        self.route_source = route_source
        self.fail_route = False
        self.invalidations = 0

    def source_capabilities(self):
        return {
            "routes": {"available": True},
            "routeOverrides": {"available": True},
            "spawnSettings": {"available": True},
            "pokemon": {"available": True},
        }

    def invalidate_data_cache(self):
        self.invalidations += 1

    def apply_encounter_changes(self, _body: bytes):
        self.route_source.write_text("changed route\n")
        if self.fail_route:
            raise ValueError("route validation failed")
        return {"saved": True}


class BehaviorModelCommitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name).resolve()
        for relative in writer.MANAGED_PATHS:
            target = self.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        self.route_source = self.workspace / "route-data.c"
        self.route_source.write_text("original route\n")
        self.sources = tuple(
            [(self.workspace / relative).resolve() for relative in writer.MANAGED_PATHS]
            + [self.route_source.resolve()]
        )
        self.legacy = FakeLegacy(self.route_source)
        self.patches = [
            mock.patch.object(reliability, "mutation_source_paths", return_value=self.sources),
            mock.patch.object(reliability, "current_revision", side_effect=lambda _legacy, _root: revision(self.sources)),
            mock.patch.object(reliability, "validate_commit_domains", return_value=None),
            mock.patch.object(reliability.pokemon_data, "asset_snapshot", return_value=SimpleNamespace(revision="asset:test")),
            mock.patch.object(reliability.pokemon_data, "invalidate_asset_snapshot", return_value=None),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp.cleanup()

    def model(self):
        return json.loads((self.workspace / writer.MODEL_PATH).read_text())

    def bodies(self):
        return {path: path.read_bytes() for path in self.sources}

    def commit(self, domains, source_revision=None):
        payload = {"sourceRevision": source_revision or revision(self.sources), **domains}
        return reliability.transactional_commit(
            self.legacy, self.workspace, json.dumps(payload).encode("utf-8")
        )

    def test_multi_entity_save_reloads_with_stable_identity_mapping(self):
        model = self.model()
        source_profile = model["stateProfiles"][0]
        source_controller = model["controllers"][0]
        profile = {
            "draftId": "draft:profile", "name": "Saved profile",
            "descriptiveTags": ["bird", "saved"],
            "values": copy.deepcopy(source_profile["body"]["values"]),
            "templateProvenance": {
                "kind": source_profile["body"]["provenanceKind"],
                "provenanceId": source_profile["provenanceId"],
            },
        }
        first_node = source_controller["nodes"][0]
        controller = {
            "draftId": "draft:controller", "name": "Saved controller",
            "nodes": [{
                "draftId": "draft:node", "profileRef": "draft:profile",
                "semanticRoleId": first_node["semanticRoleId"],
                "customRoleId": first_node["customRoleId"] or None,
                "base": True, "optional": False, "hidden": False,
            }],
            "scalarDefaults": {key: source_controller[key] for key in writer.SCALAR_KEYS},
            "policyIds": {key: source_controller[key] for key in writer.POLICY_KEYS},
        }
        result = self.commit({"behaviorModel": {
            "modelVersion": 40,
            "stateProfiles": {"create": [profile]},
            "controllers": {"create": [controller]},
        }})
        mapping = result["domains"]["behaviorModel"]["draftIdMap"]
        self.assertEqual(result["draftIdMap"], mapping)
        self.assertEqual(result["changedDomains"], ["behaviorModel"])
        self.assertTrue(result["saved"])
        reloaded = self.model()
        saved_profile = next(row for row in reloaded["stateProfiles"] if row["stableId"] == mapping["draft:profile"])
        saved_controller = next(row for row in reloaded["controllers"] if row["stableId"] == mapping["draft:controller"])
        self.assertEqual((saved_profile["name"], saved_profile["descriptiveTags"]), ("Saved profile", ["bird", "saved"]))
        self.assertEqual(saved_controller["nodes"][0]["profileId"], mapping["draft:profile"])

    def test_stale_revision_and_legacy_domains_preserve_every_file(self):
        before = self.bodies()
        with self.assertRaises(reliability.RevisionConflict):
            self.commit({"behaviorModel": {"modelVersion": 40}}, "sha256:stale")
        self.assertEqual(self.bodies(), before)
        for domains in (
            {"profiles": {}},
            {"behaviorModel": {"modelVersion": 40}, "profileOverrides": {}},
        ):
            with self.assertRaisesRegex(ValueError, "legacy profile commit domains"):
                self.commit(domains)
            self.assertEqual(self.bodies(), before)

    def test_combined_domain_failure_rolls_back_behavior_model_and_route(self):
        model = self.model()
        profile = model["stateProfiles"][0]
        update = {
            "stableId": profile["stableId"], "name": "Must roll back",
            "descriptiveTags": ["rollback"],
            "values": copy.deepcopy(profile["body"]["values"]),
        }
        before = self.bodies()
        self.legacy.fail_route = True
        with self.assertRaisesRegex(ValueError, "route validation failed"):
            self.commit({
                "behaviorModel": {"stateProfiles": {"update": [update]}},
                "encounters": {"records": []},
            })
        self.assertEqual(self.bodies(), before)

    def test_controller_duplicate_clones_scoped_applicability_through_ui_payload(self):
        import server

        editor_model = server.build_behavior_model_editor_payload()
        script = r'''import fs from "node:fs";
import {createControllerDraft, compactBehaviorModelDraft} from "./tools/overworld-viewer-v2/static/profiles.js";
const model = JSON.parse(fs.readFileSync(0, "utf8"));
const source = model.controllers.find((controller) => model.transitionGraph.transitions.some((transition) =>
  transition.candidateDefinition?.controllerId === controller.stableId
  && transition.candidateDefinition?.applicability?.controllerId === controller.stableId));
const scoped = model.transitionGraph.transitions.filter((transition) => transition.candidateDefinition?.controllerId === source.stableId);
const draft = createControllerDraft({source, profiles: model.stateProfiles, transitions: scoped,
  transitionOrderStart: model.transitionGraph.transitions.length,
  behaviorModelAuthoring: model.behaviorModelAuthoring});
process.stdout.write(JSON.stringify({sourceControllerId: source.stableId,
  controllerDraftId: draft.controller.draftId,
  definitionDraftIds: draft.transitions.map((item) => item.candidateDefinition.draftId),
  applicabilityDraftIds: draft.transitions.map((item) => item.candidateDefinition.applicability.draftId),
  transaction: compactBehaviorModelDraft({controllers: {create: [draft.controller]}, transitions: {create: draft.transitions}}, model)}));'''
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script], cwd=ROOT,
            input=json.dumps(editor_model), text=True, capture_output=True, check=True,
        )
        authored = json.loads(completed.stdout)
        blocker_index = editor_model["behaviorModelAuthoring"]["profileDeleteBlockers"]
        self.assertTrue(blocker_index)
        canonical = self.model()
        expected_blocked = {
            str(row["profileId"])
            for domain in ("importRecipes", "tiredTranslations")
            for row in canonical[domain]
        }
        self.assertEqual(set(blocker_index), expected_blocked)
        for transition in authored["transaction"]["transitions"]["create"]:
            rule = transition["candidateDefinition"]["applicability"]
            self.assertTrue({"kind", "groupMask", "profileId", "minimum", "maximum"} <= set(rule))
            self.assertTrue(str(rule["draftId"]).startswith("draft:"))
        self.assertTrue(all(
            any(transition[child_key] for transition in authored["transaction"]["transitions"]["create"])
            for child_key in writer.CHILD_FIELDS
        ))
        before = self.model()
        source_controller = next(row for row in before["controllers"] if row["stableId"] == authored["sourceControllerId"])
        source_definition_ids = {
            row["definitionId"] for row in before["transitions"]
            if next(item for item in before["overrideDefinitions"] if item["stableId"] == row["definitionId"])["controllerId"] == source_controller["stableId"]
        }
        source_definitions = {row["stableId"]: copy.deepcopy(row) for row in before["overrideDefinitions"] if row["stableId"] in source_definition_ids}
        source_applicability = {row["stableId"]: copy.deepcopy(row) for row in before["applicability"] if row["stableId"] in {item["applicabilityId"] for item in source_definitions.values()}}
        mapping = writer.apply_behavior_model_changes(self.workspace, authored["transaction"])
        saved = self.model()
        new_controller_id = mapping[authored["controllerDraftId"]]
        for definition_draft, applicability_draft in zip(authored["definitionDraftIds"], authored["applicabilityDraftIds"]):
            definition = next(row for row in saved["overrideDefinitions"] if row["stableId"] == mapping[definition_draft])
            rule = next(row for row in saved["applicability"] if row["stableId"] == mapping[applicability_draft])
            self.assertEqual((definition["controllerId"], definition["applicabilityId"]),
                             (new_controller_id, rule["stableId"]))
            self.assertEqual(rule["controllerId"], new_controller_id)
        draft_ids = []
        for transition in authored["transaction"]["transitions"]["create"]:
            draft_ids.extend([
                transition["draftId"], transition["candidateDefinition"]["draftId"],
                transition["candidateDefinition"]["applicability"]["draftId"],
            ])
            for child_key in writer.CHILD_FIELDS:
                draft_ids.extend(child["draftId"] for child in transition[child_key])
        self.assertEqual(len(draft_ids), len(set(draft_ids)))
        self.assertTrue(all(draft in mapping for draft in draft_ids))

        def resolved(value):
            if value is None:
                return 0
            return mapping.get(value, value)

        transitions_by_id = {row["stableId"]: row for row in saved["transitions"]}
        definitions_by_id = {row["stableId"]: row for row in saved["overrideDefinitions"]}
        applicability_by_id = {row["stableId"]: row for row in saved["applicability"]}
        reference_fields = {
            "controllerId", "nodeId", "requiredOwnerId", "recoveryTransitionId",
            "applicabilityId",
        }
        applicability_references = {"controllerId", "profileId"}
        child_references = {
            "guards": {"referenceId"},
            "operations": {"definitionId", "ownerId", "replacementDefinitionId", "policyId", "instanceKey"},
            "actions": {"referenceId"},
            "recoveryActions": {"ownerId"},
        }
        for submitted in authored["transaction"]["transitions"]["create"]:
            persisted = transitions_by_id[mapping[submitted["draftId"]]]
            definition = definitions_by_id[mapping[submitted["candidateDefinition"]["draftId"]]]
            rule = applicability_by_id[mapping[submitted["candidateDefinition"]["applicability"]["draftId"]]]
            self.assertEqual(persisted["definitionId"], definition["stableId"])
            for key in ("ownerId", "trigger", "fromRoleMask", "dispatchPriority", "order"):
                self.assertEqual(persisted[key], resolved(submitted[key]))
            for key in writer.DEFINITION_AUTHORED_FIELDS:
                expected = resolved(submitted["candidateDefinition"][key]) if key in reference_fields else submitted["candidateDefinition"][key]
                self.assertEqual(definition[key], expected, f"definition field {key}")
            submitted_rule = submitted["candidateDefinition"]["applicability"]
            for key in writer.APPLICABILITY_AUTHORED_FIELDS:
                expected = resolved(submitted_rule[key]) if key in applicability_references else submitted_rule[key]
                self.assertEqual(rule[key], expected, f"applicability field {key}")
            for child_key, authored_fields in writer.CHILD_FIELDS.items():
                persisted_children = {row["stableId"]: row for row in persisted[child_key]}
                for child in submitted[child_key]:
                    actual = persisted_children[mapping[child["draftId"]]]
                    for key in authored_fields - {"draftId", "stableId"}:
                        expected = resolved(child[key]) if key in child_references[child_key] else child[key]
                        self.assertEqual(actual[key], expected, f"{child_key} field {key}")
        self.assertEqual({row["stableId"]: row for row in saved["overrideDefinitions"] if row["stableId"] in source_definition_ids}, source_definitions)
        self.assertEqual({row["stableId"]: row for row in saved["applicability"] if row["stableId"] in source_applicability}, source_applicability)


if __name__ == "__main__":
    unittest.main()
