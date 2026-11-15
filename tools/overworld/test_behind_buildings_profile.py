"""Behind Buildings survives editing and resolution without traversal grants.

These checks execute the actual editor functions and portable C resolver.
They do not establish the native map placement or frame pacing claims.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.test_workshop_authoring import REPO, REQUEST, VIEWER, native_resolver


class BehindBuildingsProfileTests(unittest.TestCase):
    def test_saved_catalog_and_generated_c_preserve_spawn_only_constraint(self):
        catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        changed = copy.deepcopy(catalog)
        root = next(profile for profile in changed["profiles"]
                    if profile["id"] == changed["rootProfile"])
        # Land remains enabled. The extra bit is a restriction on that Land,
        # not a new destination that would admit ordinary Land by union.
        root["fields"]["spawnDestinationMask"]["value"] = 0x801
        root["fields"]["spawnDestinationOverrideMask"]["value"] = 0xBFF
        with tempfile.TemporaryDirectory(prefix="behind-buildings-profile-") as directory:
            temp = Path(directory)
            catalog_file = temp / "catalog.json"
            source_file = temp / "data.c"
            header_file = temp / "data.h"
            source_file.write_text(VIEWER.BEHAVIOR_DATA_SOURCE.read_text())
            header_file.write_text(VIEWER.BEHAVIOR_DATA_HEADER.read_text())
            with patch.multiple(VIEWER, BEHAVIOR_CATALOG_SOURCE=catalog_file,
                                BEHAVIOR_DATA_SOURCE=source_file,
                                BEHAVIOR_DATA_HEADER=header_file):
                VIEWER.write_behavior_catalog(changed)
                saved = json.loads(catalog_file.read_text())
                self.assertEqual(saved, changed)
                self.assertEqual(VIEWER.render_behavior_catalog(saved, source_file.read_text()),
                                 source_file.read_text())
            before = native_resolver.build(REPO, force=True, output=temp / "before")
            after = native_resolver.build(REPO, force=True, catalog=catalog_file,
                                          output=temp / "after")
            baseline = native_resolver.resolve(None, REQUEST, root=REPO, executable=before)
            resolved = native_resolver.resolve(None, REQUEST, root=REPO, executable=after)
            self.assertEqual(resolved["status"], 0)
            expected = bytearray.fromhex(baseline["profileHex"])
            actual = bytes.fromhex(resolved["profileHex"])
            for lane in range(2):
                offset = lane * 80 + 52
                expected[offset:offset + 4] = bytes.fromhex("0108ff0b")
            # All other bytes include both movement masks and every movement
            # field. A placement edit must not alter any of them.
            self.assertEqual(actual, expected)
            self.assertEqual(resolved["primitivesHex"], baseline["primitivesHex"])
            # Existing legacy Grass and Pool replacements must clear the
            # inherited constraint. Otherwise a later ordinary placement
            # profile would remain trapped behind a previous building rule.
            for species, values in ((19, (8, 0xBFF)), (165, (15, 0))):
                later = native_resolver.resolve(None, {**REQUEST, "species": species,
                    "level": 16}, root=REPO, executable=after)
                raw = bytes.fromhex(later["profileHex"])
                for lane in range(2):
                    start = lane * 80 + 52
                    self.assertEqual((int.from_bytes(raw[start:start + 2], "little"),
                        int.from_bytes(raw[start + 2:start + 4], "little")), values)

    def test_spawn_policy_rejects_water_surface_and_traversal_rejects_constraint(self):
        for field, value in (("spawnDestinationMask", 0x400),
                             ("spawnDestinationOverrideMask", 0xC00),
                             ("chillAllowedTerrainMask", 0x800),
                             ("chillAllowedTerrainOverrideMask", 0x800)):
            with self.subTest(field=field):
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER._validate_catalog_override_field(
                        field, {"operator": "replace", "value": value}, "fixture")

    def test_actual_editor_keeps_spawn_and_traversal_catalogs_separate(self):
        source = (REPO / "tools/overworld-viewer-v2/static/profiles.js").read_text()
        names = ("allowedTerrainCatalog", "terrainPolicyCatalog", "terrainPolicyAllMask",
                 "terrainPolicyMaskNumber", "terrainPolicyState", "nextTerrainPolicyState",
                 "allowedTerrainIcon", "setTerrainPolicyState", "renderTerrainPolicy")
        bodies = []
        for name in names:
            start = source.index(f"  function {name}(")
            end = source.index("\n  function ", start + 1)
            bodies.append(source[start:end])
        _, _, macros = VIEWER.behavior_authoring_context()
        data = {
            "allowedTerrains": [{"key": key, "label": label, "raw": raw, "bit": macros[raw]}
                                for key, label, raw in VIEWER.ALLOWED_TERRAIN_OPTIONS],
            "spawnDestinations": [{"key": key, "label": label, "raw": raw, "bit": macros[raw]}
                                  for key, label, raw in VIEWER.SPAWN_DESTINATION_OPTIONS],
        }
        with tempfile.TemporaryDirectory(prefix="behind-buildings-editor-") as directory:
            temp = Path(directory)
            module = temp / "profiles.mjs"
            module.write_text(source + """
export function placementFixture(data) {
  const profile = { draftId: 'fixture', fields: {
    spawnDestinationMask: '1', spawnDestinationOverrideMask: '1023',
    chillAllowedTerrainMask: '1', chillAllowedTerrainOverrideMask: '2047' } };
  const fieldRaw = (owner, key) => owner.fields[key];
  const originalFieldRaw = () => '';
  const setField = (owner, key, value) => { owner.fields[key] = value; };
  const isOverrideProfile = () => true;
  const profileKey = () => 'fixture';
  const escapeHtml = value => String(value);
""" + "\n".join(bodies) + """
  return { profile, terrainPolicyCatalog, terrainPolicyMaskNumber,
    setTerrainPolicyState, renderTerrainPolicy };
}
export { canonicalAuthoredFromEditorRaw };
""")
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ placementFixture, canonicalAuthoredFromEditorRaw }} from {json.dumps(module.as_uri())};
const data = {json.dumps(data)};
for (const input of [data, {{}}]) {{
  const ui = placementFixture(input);
  const allowed = ui.terrainPolicyCatalog('allowed');
  const spawn = ui.terrainPolicyCatalog('spawn');
  assert.ok(!allowed.some(item => item.key === 'behind-buildings'));
  assert.ok(allowed.some(item => item.key === 'water-surface'));
  assert.ok(spawn.some(item => item.key === 'behind-buildings' && item.bit === 2048));
  assert.ok(!spawn.some(item => item.key === 'water-surface'));
  assert.equal(ui.terrainPolicyMaskNumber('OW_WILD_SPAWN_DESTINATION_MASK_ALL', 'spawn'), 3071);
  assert.equal(ui.terrainPolicyMaskNumber('2048', 'allowed'), 0);
  const before = {{ ...ui.profile.fields }};
  ui.setTerrainPolicyState(ui.profile, 'spawn', 2048, 'on');
  assert.equal(ui.profile.fields.spawnDestinationMask, '2049');
  assert.equal(ui.profile.fields.spawnDestinationOverrideMask, '3071');
  assert.equal(ui.profile.fields.chillAllowedTerrainMask, before.chillAllowedTerrainMask);
  assert.equal(ui.profile.fields.chillAllowedTerrainOverrideMask, before.chillAllowedTerrainOverrideMask);
  assert.deepEqual(canonicalAuthoredFromEditorRaw(ui.profile.fields.spawnDestinationMask,
    'spawnDestinationMask', {{}}, {{}}), {{ operator: 'replace', value: '2049' }});
  const markup = ui.renderTerrainPolicy(ui.profile, {{}}, {{}}, 'spawn');
  assert.match(markup, /data-terrain-label="Behind Buildings" data-terrain-bit="2048" data-terrain-state="on"/);
  assert.ok(!ui.renderTerrainPolicy(ui.profile, {{}}, {{}}, 'allowed').includes('Behind Buildings'));
  ui.setTerrainPolicyState(ui.profile, 'spawn', 2048, 'off');
  assert.equal(ui.profile.fields.spawnDestinationMask, '1');
  assert.equal(ui.profile.fields.spawnDestinationOverrideMask, '3071');
  ui.setTerrainPolicyState(ui.profile, 'spawn', 2048, 'inherit');
  assert.equal(ui.profile.fields.spawnDestinationMask, '1');
  assert.equal(ui.profile.fields.spawnDestinationOverrideMask, '1023');
}}
""")
            result = subprocess.run(["node", script], cwd=REPO, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
