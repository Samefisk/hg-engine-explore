"""Host checks for the generic return checkbox and its packed profile seam."""

from pathlib import Path
import copy
import json
import struct
import subprocess
import tempfile
import unittest

from tools.overworld.test_behavior_catalog_v5 import load_viewer
from tools.overworld.test_behavior_resolver_conditions import run_resolver_harness
from tools.overworld import test_wild_blob_acceleration as acceleration_fixture
from scripts import validate_overworld_wild_blobs as validator

ROOT = Path(__file__).resolve().parents[2]
VIEWER = load_viewer()


class ReturnAfterMoveProfileTests(unittest.TestCase):
    def test_authoring_defaults_and_packed_roundtrip(self):
        for value in (0, 1, "0", "1", "OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"):
            VIEWER._validate_catalog_override_field("returnAfterMove", {"operator": "replace", "value": value}, "test")
        for value in (-1, 2, 255, True, False, 1.0, "2"):
            with self.assertRaises(VIEWER.ParseError):
                VIEWER._validate_catalog_override_field("returnAfterMove", {"operator": "replace", "value": value}, "test")
        for operator in ("relative", "divide", "atLeast", "atMost"):
            with self.assertRaises(VIEWER.ParseError):
                VIEWER._validate_catalog_override_field("returnAfterMove", {"operator": operator, "value": 1}, "test")
        catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        old = copy.deepcopy(catalog)
        root = next(p for p in old["profiles"] if p["id"] == old["rootProfile"])
        root["fields"].pop("returnAfterMove")
        saved = copy.deepcopy(old)
        normalized = VIEWER._normalize_behavior_catalog_v5(old)
        lowered_root = next(p for p in normalized["profiles"] if p["id"] == old["rootProfile"])
        self.assertEqual(lowered_root["fields"]["returnAfterMove"], {"operator": "replace", "value": 0})
        self.assertEqual(old, saved)
        raws = {field: "0" for field in VIEWER.PROFILE_FIELDS}
        for continuing in (0, 1):
            for returning in (0, 1):
                raws.update(continueWhenArrived=str(continuing), returnAfterMove=str(returning))
                literal = VIEWER.format_profile_initializer(raws, "")
                parsed = VIEWER.parse_profile(VIEWER.parse_initializer(literal), {})
                self.assertEqual(VIEWER.numeric(parsed["continueWhenArrived"]), continuing)
                self.assertEqual(VIEWER.numeric(parsed["returnAfterMove"]), returning)
                self.assertIn(f"OW_WILD_BEHAVIOR_CONTROLLER_CARGO_OPTIONS({continuing}, {returning}, 0, 0)", literal)

    def test_actual_resolver_keeps_both_flags_and_neighbor_bytes_separate(self):
        source = (ROOT / "lib/overworld/overworld_behavior_resolver.c").read_text() + r"""
void ReturnTestApply(OverworldWildBehaviorProfileData *p, const OverworldWildBehaviorOverrideProfile *o) { BehaviorResolver_ApplyOverride(p, o); }
"""
        harness = r"""
#include <assert.h>
#include <stddef.h>
#include <string.h>
#include "overworld_behavior_resolver.h"
extern void ReturnTestApply(OverworldWildBehaviorProfileData *, const OverworldWildBehaviorOverrideProfile *);
int main(void) {
    assert(sizeof(OverworldWildBehaviorProfileData) == 80);
    assert(sizeof(OverworldWildBehaviorProfile) == 160);
    assert(sizeof(BehaviorResolveRequest) == 44);
    assert(sizeof(BehaviorResolveResult) == 216);
    assert(offsetof(OverworldWildBehaviorProfileData, continueWhenArrived) == 42);
    for (unsigned a = 0; a < 2; a++) for (unsigned b = 0; b < 2; b++) {
        unsigned packed = OW_WILD_BEHAVIOR_CONTROLLER_OPTIONS(a, b);
        assert(OW_WILD_BEHAVIOR_CONTINUES_WHEN_ARRIVED(packed) == a);
        assert(OW_WILD_BEHAVIOR_RETURNS_AFTER_MOVE(packed) == b);
    }
    for (unsigned base = 0; base < 256; base++) for (unsigned incoming = 0; incoming < 256; incoming++) for (unsigned mask = 0; mask < 4; mask++) {
        OverworldWildBehaviorProfileData p, expected;
        OverworldWildBehaviorOverrideProfile o, saved;
        memset(&p, 0x5a, sizeof(p)); memset(&o, 0, sizeof(o));
        p.continueWhenArrived = base; o.profile.continueWhenArrived = incoming;
        o.mask2 = ((mask & 1) ? OW_WILD_BEHAVIOR_OVERRIDE2_CONTINUE_WHEN_ARRIVED : 0)
            | ((mask & 2) ? OW_WILD_BEHAVIOR_OVERRIDE2_RETURN_AFTER_MOVE : 0);
        expected = p; saved = o;
        unsigned bits = ((mask & 1) ? 1 : 0) | ((mask & 2) ? 2 : 0);
        expected.continueWhenArrived = (base & ~bits) | (incoming & bits);
        ReturnTestApply(&p, &o);
        assert(!memcmp(&p, &expected, sizeof(p)));
        assert(!memcmp(&o, &saved, sizeof(o)));
    }
    return 0;
}
"""
        compiled, result = run_resolver_harness(harness, source)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_blob_rejects_reserved_bits_and_numeric_operators(self):
        fixture = acceleration_fixture.WildBlobAccelerationTests("test_linear_ramp_accepts_full_frame_range")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.source.write_text(fixture.source.read_text().replace("DATA_VERSION 85", "DATA_VERSION 89"))
        blob = fixture.blob + bytes(16)  # Rest mask and empty condition-options row.
        struct.pack_into("<H", blob, 4, 89)
        struct.pack_into("<I", blob, 8, len(blob))
        bit = 1 << 25
        struct.pack_into("<I", blob, fixture.override_base + 24, bit)
        offsets = (fixture.class_base + 42, fixture.value_base + 42,
                   fixture.override_base + validator.OWBD_OVERRIDE_PROFILE_COMPOUND_BOUND_OFFSET + 42)
        for value in range(4):
            changed = blob.copy()
            for offset in offsets:
                changed[offset] = value
            fixture.validate(changed)
        for offset in offsets:
            for value in (4, 128, 255):
                changed = blob.copy()
                changed[offset] = value
                with self.assertRaisesRegex(ValueError, "undefined controller-option bits"):
                    fixture.validate(changed)
        for offset in (116, 128, 140):  # Relative, minimum, maximum mask2.
            changed = blob.copy()
            struct.pack_into("<I", changed, fixture.override_base + offset, bit)
            with self.assertRaisesRegex(ValueError, "non-numeric"):
                fixture.validate(changed)
        changed = blob.copy()
        struct.pack_into("<H", changed, 4, 88)
        fixture.source.write_text(fixture.source.read_text().replace("DATA_VERSION 89", "DATA_VERSION 88"))
        with self.assertRaisesRegex(ValueError, "mask2"):
            fixture.validate(changed)

    def test_workshop_checkbox_and_inherited_value(self):
        source = (ROOT / "tools/overworld-viewer-v2/static/profiles.js").read_text()
        bodies = []
        for name in ("fieldNumericValue", "renderReturnAfterMoveControl"):
            start = source.index(f"  function {name}(")
            end = source.index("\n  function ", start + 1)
            bodies.append(source[start:end])
        with tempfile.TemporaryDirectory(prefix="return-profile-ui-") as folder:
            module = Path(folder) / "profiles.mjs"
            module.write_text(source + """
export function returnCheckboxFixture(raw, inheritedValues = []) {
  const data = { editOptions: { returnAfterMove: [{raw:'0',value:0}, {raw:'1',value:1}] } };
  const fieldRaw = () => raw;
  const originalFieldRaw = () => raw;
  const isOverrideProfile = () => true;
  const effectiveFieldCandidates = () => inheritedValues;
  const profileKey = () => 'override:1';
  const valueRaw = value => value.raw;
  const escapeHtml = value => value;
""" + "\n".join(bodies) + """
  return renderReturnAfterMoveControl({});
}
""")
            test = Path(folder) / "test.mjs"
            test.write_text("import assert from 'node:assert/strict';\n"
                + "import { returnCheckboxFixture, canonicalCatalogStructuralErrors } from "
                + json.dumps(module.as_uri()) + ";\n" + r"""
assert.match(returnCheckboxFixture('1'), /type="checkbox"[^>]*checked/);
assert.doesNotMatch(returnCheckboxFixture('0'), /type="checkbox"[^>]*checked/);
assert.match(returnCheckboxFixture('', ['1']), /checked.*Inherited/s);
assert.match(returnCheckboxFixture('', ['0','1']), /data-return-mixed.*Mixed/s);
assert.match(returnCheckboxFixture('1'), /data-action="inherit-return-after-move"/);
for (const value of [true, 2, -1, '2']) {
  const catalog = {catalogVersion:5, rootProfile:'root', pools:[], profiles:[{id:'root',name:'Root',parent:null,kind:'normal',fields:{returnAfterMove:{operator:'replace',value}}}],applications:[],selectors:[],runtimeBindings:{}};
  assert.ok(canonicalCatalogStructuralErrors(catalog,{fields:[{key:'returnAfterMove'}]}).some(e=>e.includes('must be 0 or 1')));
}
""")
            result = subprocess.run(["node", str(test)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
