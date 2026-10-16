"""Application switches keep authoring data but omit native activation rows."""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts import overworld_behavior_profile_viewer as viewer


REPO = Path(__file__).resolve().parents[2]
JS = REPO / "tools/overworld-viewer-v2/static/profiles.js"


class ProfileApplicationEnabledTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(viewer.BEHAVIOR_CATALOG_SOURCE.read_text())

    def test_missing_and_true_are_the_same_runtime_and_schema_is_optional(self):
        implicit = copy.deepcopy(self.catalog)
        for application in implicit["applications"]:
            if application.get("enabled", True):
                application.pop("enabled", None)
        explicit = copy.deepcopy(implicit)
        for application in explicit["applications"]:
            if application.get("enabled", True):
                application["enabled"] = True
        self.assertEqual(viewer._runtime_source_behavior_catalog(implicit),
                         viewer._runtime_source_behavior_catalog(explicit))
        schema = json.loads(viewer.BEHAVIOR_AUTHORING_SCHEMA_V5.read_text())
        for name in ("targetedApplication", "linkedApplication"):
            self.assertEqual(schema["$defs"][name]["properties"]["enabled"],
                             {"type": "boolean", "default": True})
            self.assertNotIn("enabled", schema["$defs"][name]["required"])

    def test_disabled_conditional_keeps_id_fields_order_and_omits_native_rows(self):
        application = next(a for a in self.catalog["applications"]
                           if a["id"] == "apply-basic-attack")
        application["enabled"] = False
        before = copy.deepcopy(self.catalog)
        profile = next(p for p in self.catalog["profiles"] if p["id"] == application["profile"])
        disabled_condition_ids = {viewer._stable_condition_id(profile["id"], c["id"])
                                  for c in profile["conditions"]}
        runtime = viewer._runtime_source_behavior_catalog(self.catalog)
        viewer.validate_behavior_catalog(runtime)
        self.assertEqual(self.catalog, before)
        self.assertNotIn(application["id"], {a["id"] for a in runtime["applications"]})
        self.assertTrue(disabled_condition_ids.isdisjoint(
            {entry["conditionId"] for entry in viewer._catalog_condition_layout(runtime)[1]}))
        projected = viewer.project_behavior_catalog_runtime(self.catalog)
        self.assertEqual(len(projected["overrideProfiles"]), len(runtime["applications"]))
        self.assertFalse(any(p["name"] == profile["name"] for p in projected["overrideProfiles"]))
        self.assertEqual(viewer.render_behavior_catalog(self.catalog, viewer.BEHAVIOR_DATA_SOURCE.read_text()),
                         viewer.render_behavior_catalog(runtime, viewer.BEHAVIOR_DATA_SOURCE.read_text()))

    def test_disabled_normal_pool_owner_does_not_leave_a_missing_subject_reference(self):
        application = next(a for a in self.catalog["applications"]
                           if a["id"] == "apply-floaty-bounce")
        pool = {"id": "enabled-test-pool", "name": "Enabled test pool", **application["target"]}
        self.catalog["pools"].append(pool)
        application["target"] = {"pool": pool["id"]}
        application["enabled"] = False
        skittish = next(p for p in self.catalog["profiles"] if p["id"] == "skittish")
        skittish["conditions"][0]["subjects"] = {"pool": pool["id"]}
        runtime = viewer._runtime_source_behavior_catalog(self.catalog)
        subjects = next(p for p in runtime["profiles"] if p["id"] == "skittish")["conditions"][0]["subjects"]
        self.assertEqual(subjects, {key: value for key, value in pool.items() if key not in {"id", "name"}})
        self.assertNotIn("application", subjects)
        viewer.project_behavior_catalog_runtime(self.catalog)

    def test_runtime_and_tired_references_cannot_be_disabled(self):
        required = {self.catalog["runtimeBindings"][key] for key in (
            "followerApplication", "mountedApplication", "defaultTiredApplication", "forcedAsleepApplication")}
        required.update(p["fields"]["tiredProfile"]["value"] for p in self.catalog["profiles"]
                        if "tiredProfile" in p["fields"])
        for application_id in required:
            with self.subTest(application=application_id):
                changed = copy.deepcopy(self.catalog)
                next(a for a in changed["applications"] if a["id"] == application_id)["enabled"] = False
                with self.assertRaisesRegex(viewer.ParseError, "runtime-bound or Tired-referenced"):
                    viewer.validate_behavior_catalog(changed)

    def test_switch_is_boolean_and_disabled_rows_still_validate(self):
        for value in (0, 1, None, "false", [], {}):
            changed = copy.deepcopy(self.catalog)
            next(a for a in changed["applications"] if a["id"] == "apply-basic-attack")["enabled"] = value
            with self.subTest(value=value), self.assertRaisesRegex(viewer.ParseError, "enabled must be a boolean"):
                viewer.validate_behavior_catalog(changed)
        changed = copy.deepcopy(self.catalog)
        next(a for a in changed["applications"] if a["id"] == "apply-basic-attack")["enabled"] = False
        next(p for p in changed["profiles"] if p["id"] == "basic-attack")["fields"]["chillSpeed"] = {
            "operator": "unknown", "value": 4}
        with self.assertRaisesRegex(viewer.ParseError, "operator"):
            viewer.validate_behavior_catalog(changed)

    def test_disabled_application_frees_one_mask_bit_without_raising_the_limit(self):
        tail = viewer._catalog_tired_only_application_ids(self.catalog)
        active = sum(a.get("enabled", True) for a in self.catalog["applications"]) - len(tail)
        profile = {"id": "enabled-cap-test", "name": "Enabled cap test", "parent": self.catalog["rootProfile"],
                   "kind": "normal", "classification": "modifier", "fields": {}}
        self.catalog["profiles"].append(profile)
        for index in range(33 - active):
            self.catalog["applications"].append({
                "id": f"apply-enabled-cap-test-{index}", "profile": profile["id"],
                "target": {"pool": "baby-pokemon"}, "enabled": index < 32 - active})
        viewer.validate_behavior_catalog(self.catalog)
        runtime = viewer._runtime_source_behavior_catalog(self.catalog)
        self.assertEqual(len(runtime["applications"]) - len(tail), 32)
        self.catalog["applications"][-1]["enabled"] = True
        with self.assertRaisesRegex(viewer.ParseError, "at most 32"):
            viewer.validate_behavior_catalog(self.catalog)

    def test_ui_switch_preserves_draft_projection_and_protects_references(self):
        with tempfile.TemporaryDirectory(prefix="profile-enabled-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            module.write_text(JS.read_text() + "\nexport { projectCanonicalProfileDeck };\n")
            script = temp / "check.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ setProfileApplicationEnabled, canonicalCatalogStructuralErrors,
  projectCanonicalProfileDeck }} from {json.dumps(module.as_uri())};
const catalog = {json.dumps(self.catalog)};
const before = JSON.stringify(catalog);
const off = setProfileApplicationEnabled(catalog, 'apply-basic-attack', false);
assert.equal(JSON.stringify(catalog), before);
assert.deepEqual(off.profiles, catalog.profiles);
assert.deepEqual(off.applications.map(a => a.id), catalog.applications.map(a => a.id));
const deck = projectCanonicalProfileDeck({{}}, off);
const basic = deck.classes.find(p => p.catalogApplicationId === 'apply-basic-attack');
assert.equal(basic.catalogEnabled, false);
assert.equal(basic.catalogKind, 'conditional');
assert.deepEqual(basic.catalogConditions, catalog.profiles.find(p => p.id === 'basic-attack').conditions);
const on = setProfileApplicationEnabled(off, 'apply-basic-attack', true);
assert.equal(on.applications.find(a => a.id === 'apply-basic-attack').enabled, true);
for (const key of ['followerApplication', 'mountedApplication', 'defaultTiredApplication', 'forcedAsleepApplication']) {{
  const id = catalog.runtimeBindings[key];
  assert.throws(() => setProfileApplicationEnabled(catalog, id, false), /cannot be disabled/);
  const bad = JSON.parse(JSON.stringify(catalog));
  bad.applications.find(a => a.id === id).enabled = false;
  assert(canonicalCatalogStructuralErrors(bad).some(e => /cannot be disabled/.test(e)));
}}
for (const p of catalog.profiles.filter(p => p.fields.tiredProfile)) {{
  assert.throws(() => setProfileApplicationEnabled(catalog, p.fields.tiredProfile.value, false), /cannot be disabled/);
}}
for (const value of [0, 1, null, 'false']) {{
  assert.throws(() => setProfileApplicationEnabled(catalog, 'apply-basic-attack', value), /boolean/);
  const bad = JSON.parse(JSON.stringify(catalog));
  bad.applications.find(a => a.id === 'apply-basic-attack').enabled = value;
  assert(canonicalCatalogStructuralErrors(bad).some(e => /Enabled must be a boolean/.test(e)));
}}
""")
            result = subprocess.run(["node", str(script)], cwd=REPO, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        source = JS.read_text()
        self.assertIn('data-profile-application-enabled aria-label="Application Enabled"', source)
        self.assertIn('setProfileApplicationEnabled(next, application.id, event.target.checked)', source)

    def test_disabled_basic_declaration_validates_but_cannot_install_a_game_meter(self):
        from tools.overworld import devtools_basic_attack_measurement as basic
        from tools.overworld.devtools_profile_feature_measurement import application_index
        from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
        disabled = copy.deepcopy(self.catalog)
        next(a for a in disabled["applications"] if a["id"] == "apply-basic-attack")["enabled"] = False
        with mock.patch.object(Path, "read_text", return_value=json.dumps(disabled)):
            self.assertIsNone(application_index("apply-basic-attack", allow_disabled=True))
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                application_index("apply-basic-attack")
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                application_index("apply-missing-application", allow_disabled=True)
        recipe = json.loads((REPO / "tests/overworld/test-recipes/profile.basic-attack.json").read_text())
        test = validate_test(recipe)
        basic.validate_recipe(test)
        evaluator = TestEvaluator(test)
        source = dict(contractVersion=1, romSha256="a" * 64,
                      overlaySha256="b" * 64, profileSha256="c" * 64)
        with mock.patch.object(basic, "APPLICATION", None), mock.patch.object(basic, "ATTACK_MASK", 0):
            with self.assertRaisesRegex(ValueError, "application is disabled"):
                basic.BasicAttackMeasurement(source, test)
            with self.assertRaisesRegex(ValueError, "application is disabled"):
                evaluator.install_measurements({basic.KIND: source})


if __name__ == "__main__":
    unittest.main()
