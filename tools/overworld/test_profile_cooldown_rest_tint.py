"""Strict local authoring and v86 tail layout; no game or ROM build."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cooldown_tint_viewer", ROOT / "scripts/overworld_behavior_profile_viewer.py")
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class CooldownRestTintAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(viewer.BEHAVIOR_CATALOG_SOURCE.read_text())
        self.source = viewer.BEHAVIOR_DATA_SOURCE.read_text()
        self.profile = next(p for p in self.catalog["profiles"] if p["kind"] == "conditional")

    def test_absent_and_explicit_false_are_off_without_catalog_changes(self):
        saved = deepcopy(self.catalog)
        self.assertEqual(viewer._catalog_rest_enabled_applications(self.catalog), 0)
        self.profile["showRestTintDuringCooldown"] = False
        viewer.validate_behavior_catalog(self.catalog)
        self.assertEqual(viewer.render_behavior_catalog(self.catalog, self.source), self.source)
        self.assertEqual(json.loads(viewer.BEHAVIOR_CATALOG_SOURCE.read_text()), saved)

    def test_only_real_booleans_are_allowed(self):
        for value in (0, 1, "true", "false", None, [], {}):
            with self.subTest(value=value):
                self.profile["showRestTintDuringCooldown"] = value
                with self.assertRaisesRegex(viewer.ParseError, "must be a boolean"):
                    viewer.validate_behavior_catalog(self.catalog)
        for value in (False, True):
            self.profile["showRestTintDuringCooldown"] = value
            viewer.validate_behavior_catalog(self.catalog)

    def test_normal_profile_cannot_own_the_setting_even_when_false(self):
        normal = next(p for p in self.catalog["profiles"] if p["kind"] == "normal")
        for value in (False, True):
            normal["showRestTintDuringCooldown"] = value
            with self.assertRaises(viewer.ParseError):
                viewer.validate_behavior_catalog(self.catalog)

    def test_mask_uses_only_existing_physical_application_indices(self):
        original = deepcopy(self.catalog)
        profiles = {p["id"]: p for p in self.catalog["profiles"]}
        expected = 0
        for index, application in enumerate(self.catalog["applications"]):
            profile = profiles[application["profile"]]
            if profile["kind"] == "conditional":
                profile["showRestTintDuringCooldown"] = True
                expected |= 1 << index
                self.assertEqual(viewer._catalog_rest_enabled_applications(self.catalog), expected)
        viewer.validate_behavior_catalog(self.catalog)
        rendered = viewer.render_behavior_catalog(self.catalog, self.source)
        self.assertIn(f"/* restEnabledApplications */\n    0x{expected:08X}u", rendered)
        self.assertEqual(self.catalog["applications"], original["applications"])
        self.assertEqual(len(self.catalog["applications"]), 32)
        self.assertEqual(re.sub(r"0x[0-9A-F]{8}u(?=\n};)", "0x00000000u", rendered), self.source)

    def test_save_load_and_legacy_normalization_preserve_local_value(self):
        for enabled in (False, True):
            self.profile["showRestTintDuringCooldown"] = enabled
            loaded = json.loads(json.dumps(self.catalog))
            viewer.validate_behavior_catalog(loaded)
            projected = viewer._runtime_source_behavior_catalog(loaded)
            child = next(p for p in projected["profiles"] if p["id"] == self.profile["id"])
            self.assertIs(child["showRestTintDuringCooldown"], enabled)
            self.assertNotIn("showRestTintDuringCooldown", child["fields"])
            viewer.validate_behavior_catalog(projected)
            self.assertEqual(viewer.render_behavior_catalog(loaded, self.source),
                             viewer.render_behavior_catalog(projected, self.source))

    def test_schema_keeps_setting_out_of_inherited_lane_fields(self):
        from tools.overworld.behavior_schema import load_schema, editor_metadata, validator_metadata
        schema = load_schema()
        self.assertEqual(schema["blobVersion"], 86)
        self.assertEqual(schema["compactSize"], 80)
        self.assertEqual(len(schema["fields"]), 84)
        setting = schema["profileSettings"][0]
        self.assertEqual(setting["key"], "showRestTintDuringCooldown")
        self.assertIs(setting["default"], False)
        self.assertIs(setting["inherited"], False)
        self.assertNotIn(setting["key"], [f["key"] for f in schema["fields"]])
        for metadata in (editor_metadata(schema), validator_metadata(schema)):
            self.assertEqual(metadata["profileSettings"], [setting])
        for version in (4, 5):
            authored = json.loads((ROOT / f"tools/overworld/schemas/behavior-authoring-v{version}.schema.json").read_text())
            self.assertEqual(authored["$defs"]["conditionalProfile"]["properties"][setting["key"]],
                             dict(type="boolean", default=False))
            self.assertNotIn(setting["key"], authored["$defs"]["normalProfile"]["properties"])

    def test_workshop_toggle_is_local_strict_and_round_trips(self):
        with tempfile.TemporaryDirectory(prefix="cooldown-tint-ui-") as directory:
            temp = Path(directory)
            shutil.copyfile(ROOT / "tools/overworld-viewer-v2/static/profiles.js", temp / "profiles.mjs")
            (temp / "catalog.json").write_text(json.dumps(self.catalog))
            (temp / "check.mjs").write_text("""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { setConditionalProfileRestTint, setConditionalProfileKind, canonicalCatalogStructuralErrors } from './profiles.mjs';
const catalog = JSON.parse(readFileSync(new URL('./catalog.json', import.meta.url)));
const profile = catalog.profiles.find(p => p.id === 'startled');
const app = catalog.applications.find(a => a.profile === profile.id);
for (const enabled of [true, false]) {
  const changed = setConditionalProfileRestTint(catalog, app.id, enabled);
  assert.equal(changed.profiles.find(p => p.id === profile.id).showRestTintDuringCooldown, enabled);
  assert.equal(Object.hasOwn(profile, 'showRestTintDuringCooldown'), false);
  assert.deepEqual(changed.applications, catalog.applications);
  const normal = setConditionalProfileKind(changed, app.id, 'normal');
  assert.equal(Object.hasOwn(normal.profiles.find(p => p.id === profile.id), 'showRestTintDuringCooldown'), false);
  assert.throws(() => setConditionalProfileRestTint(normal, app.id, false), /Only conditional/);
}
for (const bad of [0, 1, 'true', null]) {
  assert.throws(() => setConditionalProfileRestTint(catalog, app.id, bad), /boolean/);
  const changed = JSON.parse(JSON.stringify(catalog));
  changed.profiles.find(p => p.id === profile.id).showRestTintDuringCooldown = bad;
  assert.ok(canonicalCatalogStructuralErrors(changed).some(e => e.includes('boolean cooldown rest tint')));
}
""")
            result = subprocess.run(["node", str(temp / "check.mjs")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        js = (ROOT / "tools/overworld-viewer-v2/static/profiles.js").read_text()
        self.assertIn('data-profile-cooldown-rest-tint', js)
        self.assertIn('setConditionalProfileRestTint(next, application.id, event.target.checked)', js)

    def test_native_tail_is_four_bytes_and_all_old_offsets_are_identical(self):
        header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        old = header.replace('    u32 restEnabledApplications;\n', '')
        old = re.sub(r'typedef char OverworldWildBehaviorRestTintMustFollowPaddedSurfaceCatalog\[.*?\];\n', '', old, flags=re.S)
        members = ('header', 'classProfiles', 'classRules', 'speciesClassRules', 'overrideProfiles',
                   'overrideMembers', 'conditionEntries', 'surfaceModels', 'surfaceInstances', 'surfaceTemplates')
        with tempfile.TemporaryDirectory(prefix="cooldown-tint-layout-") as directory:
            temp = Path(directory)
            rows = []
            for name, text in (('old', old), ('new', header)):
                (temp / 'layout.h').write_text(text)
                code = '#include "layout.h"\n#include "overworld_behavior_conditions.h"\nint main(void) {\n'
                code += 'printf("%zu %zu %zu %zu %zu", sizeof(OverworldWildBehaviorDataBlob), sizeof(OverworldWildBehaviorDataBlobHeader), sizeof(OverworldWildBehaviorProfileData), sizeof(OverworldBehaviorConditionDefinition), sizeof(OverworldBehaviorConditionEntryState));\n'
                code += ''.join(f'printf(" %zu", __builtin_offsetof(OverworldWildBehaviorDataBlob, {m}));\n' for m in members)
                code += 'return 0; }\n'
                (temp / 'layout.c').write_text(code)
                result = subprocess.run(['cc', '-std=c99', '-w', '-DOVERWORLD_BEHAVIOR_HOST', '-DOVERWORLD_ACTOR_SYSTEM_HOST', '-I', str(ROOT / 'include'),
                                         str(temp / 'layout.c'), '-o', str(temp / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                rows.append(list(map(int, subprocess.check_output([str(temp / name)], text=True).split())))
            self.assertEqual(rows[1][0], rows[0][0] + 4)
            self.assertEqual(rows[1][1:], rows[0][1:])
            self.assertEqual(rows[1][1:5], [84, 80, 20, 16])

    def test_v86_blob_tail_rejects_wrong_size_or_nonconditional_mask(self):
        from tools.overworld.test_wild_blob_conditions import WildBlobConditionTests
        WildBlobConditionTests.setUp(self)
        self.source.write_text(self.source.read_text().replace('DATA_VERSION 85', 'DATA_VERSION 86'))
        self.blob.extend(bytes(4))
        struct.pack_into('<H', self.blob, 4, 86)
        struct.pack_into('<I', self.blob, 8, len(self.blob))
        def validate(blob):
            self.target.write_bytes(blob)
            from scripts.validate_overworld_wild_blobs import validate_owbd
            validate_owbd(self.target, self.source)
        for mask in (0, 1):
            struct.pack_into('<I', self.blob, len(self.blob)-4, mask)
            validate(self.blob)
        struct.pack_into('<I', self.blob, len(self.blob)-4, 2)
        with self.assertRaisesRegex(ValueError, 'nonconditional application'):
            validate(self.blob)
        shortened = self.blob[:-4]
        struct.pack_into('<I', shortened, 8, len(shortened))
        with self.assertRaisesRegex(ValueError, 'tail size'):
            validate(shortened)


if __name__ == '__main__':
    unittest.main()
