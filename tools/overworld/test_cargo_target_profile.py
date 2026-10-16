"""Fixed-size profile controls for Wild Cargo pursuit target selection."""

import copy
import json
from pathlib import Path
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
FIELDS = {"cargoTargetCheckInterval": (1, 15, 12), "cargoTargetSwitchAdvantage": (0, 3, 1)}


class CargoTargetProfileTests(unittest.TestCase):
    def test_bounds_defaults_and_packed_roundtrip(self):
        for field, (low, high, _) in FIELDS.items():
            for value in (low, high, str(low), str(high)):
                VIEWER._validate_catalog_override_field(field, {"operator": "replace", "value": value}, "test")
            for value in (low - 1, high + 1, True, False, 1.0):
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER._validate_catalog_override_field(field, {"operator": "replace", "value": value}, "test")
            for operator in ("relative", "divide", "atLeast", "atMost"):
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER._validate_catalog_override_field(field, {"operator": operator, "value": 1}, "test")
        catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        old = copy.deepcopy(catalog)
        root = next(p for p in old["profiles"] if p["id"] == old["rootProfile"])
        for field in FIELDS:
            root["fields"].pop(field)
        saved = copy.deepcopy(old)
        normalized = VIEWER._normalize_behavior_catalog_v5(old)
        root = next(p for p in normalized["profiles"] if p["id"] == old["rootProfile"])
        for field, (_, _, default) in FIELDS.items():
            self.assertEqual(root["fields"][field], {"operator": "replace", "value": default})
        self.assertEqual(old, saved)
        for continuing in (0, 1):
            for returning in (0, 1):
                for interval in (1, 12, 15):
                    for advantage in (0, 1, 3):
                        raws = {field: "0" for field in VIEWER.PROFILE_FIELDS}
                        raws.update(continueWhenArrived=str(continuing), returnAfterMove=str(returning),
                                    cargoTargetCheckInterval=str(interval), cargoTargetSwitchAdvantage=str(advantage))
                        parsed = VIEWER.parse_profile(VIEWER.parse_initializer(VIEWER.format_profile_initializer(raws, "")), {})
                        for field in ("continueWhenArrived", "returnAfterMove", *FIELDS):
                            self.assertEqual(VIEWER.numeric(parsed[field]), int(raws[field]))

    def test_actual_resolver_merges_each_slice_without_neighbor_changes(self):
        source = (ROOT / "lib/overworld/overworld_behavior_resolver.c").read_text() + r"""
void CargoTestApply(OverworldWildBehaviorProfileData *p, const OverworldWildBehaviorOverrideProfile *o) { BehaviorResolver_ApplyOverride(p, o); }
"""
        harness = r"""
#include <assert.h>
#include <stddef.h>
#include <string.h>
#include "overworld_behavior_resolver.h"
extern void CargoTestApply(OverworldWildBehaviorProfileData *, const OverworldWildBehaviorOverrideProfile *);
int main(void) {
    assert(sizeof(OverworldWildBehaviorProfileData) == 80);
    assert(sizeof(OverworldWildBehaviorProfile) == 160);
    assert(sizeof(OverworldWildBehaviorOverrideProfile) == 228);
    assert(offsetof(OverworldWildBehaviorProfileData, continueWhenArrived) == 42);
    for (unsigned a=0; a<2; a++) for (unsigned b=0; b<2; b++)
      for (unsigned c=1; c<16; c++) for (unsigned d=0; d<4; d++) {
        unsigned p=OW_WILD_BEHAVIOR_CONTROLLER_CARGO_OPTIONS(a,b,c,d);
        assert(OW_WILD_BEHAVIOR_CONTINUES_WHEN_ARRIVED(p)==a);
        assert(OW_WILD_BEHAVIOR_RETURNS_AFTER_MOVE(p)==b);
        assert(OW_WILD_BEHAVIOR_CARGO_TARGET_CHECK_INTERVAL(p)==c);
        assert(OW_WILD_BEHAVIOR_CARGO_TARGET_SWITCH_ADVANTAGE(p)==d);
      }
    for (unsigned base=0; base<256; base++) for (unsigned incoming=0; incoming<256; incoming++)
      for (unsigned mask=0; mask<16; mask++) {
        OverworldWildBehaviorProfileData p, expected;
        OverworldWildBehaviorOverrideProfile o, saved;
        memset(&p,0x5a,sizeof(p)); memset(&o,0,sizeof(o));
        p.continueWhenArrived=base; o.profile.continueWhenArrived=incoming;
        o.mask2=((mask&1)?OW_WILD_BEHAVIOR_OVERRIDE2_CONTINUE_WHEN_ARRIVED:0)
          | ((mask&2)?OW_WILD_BEHAVIOR_OVERRIDE2_RETURN_AFTER_MOVE:0)
          | ((mask&4)?OW_WILD_BEHAVIOR_OVERRIDE2_CARGO_TARGET_CHECK_INTERVAL:0)
          | ((mask&8)?OW_WILD_BEHAVIOR_OVERRIDE2_CARGO_TARGET_SWITCH_ADVANTAGE:0);
        expected=p; saved=o;
        unsigned bits=((mask&1)?1:0)|((mask&2)?2:0)|((mask&4)?60:0)|((mask&8)?192:0);
        expected.continueWhenArrived=(base&~bits)|(incoming&bits);
        CargoTestApply(&p,&o);
        assert(!memcmp(&p,&expected,sizeof(p)));
        assert(!memcmp(&o,&saved,sizeof(o)));
      }
    return 0;
}
"""
        compiled, result = run_resolver_harness(harness, source)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_blob_controls_and_old_version_remain_strict(self):
        fixture = acceleration_fixture.WildBlobAccelerationTests("test_linear_ramp_accepts_full_frame_range")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.source.write_text(fixture.source.read_text().replace("DATA_VERSION 85", "DATA_VERSION 90"))
        blob = fixture.blob + bytes(16)
        struct.pack_into("<H", blob, 4, 90)
        struct.pack_into("<I", blob, 8, len(blob))
        bits = (1 << 26) | (1 << 27)
        struct.pack_into("<I", blob, fixture.override_base + 24, bits)
        for interval in (1, 12, 15):
            for advantage in (0, 1, 3):
                changed = blob.copy()
                for offset in (fixture.class_base + 42, fixture.value_base + 42):
                    changed[offset] = (interval << 2) | (advantage << 6) | 3
                fixture.validate(changed)
        for offset in (fixture.class_base + 42, fixture.value_base + 42):
            changed = blob.copy()
            changed[fixture.class_base + 42] = 12 << 2
            changed[fixture.value_base + 42] = 12 << 2
            changed[offset] = 0
            with self.assertRaisesRegex(ValueError, "Cargo target check interval"):
                fixture.validate(changed)
        changed = blob.copy()
        changed[fixture.class_base + 42] = 12 << 2
        changed[fixture.value_base + 42] = 12 << 2
        struct.pack_into("<I", changed, fixture.override_base + 140, bits)
        with self.assertRaisesRegex(ValueError, "non-numeric|non-supported|divide|bound"):
            fixture.validate(changed)
        fixture.source.write_text(fixture.source.read_text().replace("DATA_VERSION 90", "DATA_VERSION 89"))
        struct.pack_into("<H", changed, 4, 89)
        with self.assertRaisesRegex(ValueError, "undefined controller-option bits"):
            fixture.validate(changed)

    def test_workshop_controls_are_visible_and_bounds_checked(self):
        source = (ROOT / "tools/overworld-viewer-v2/static/profiles.js").read_text()
        bodies = []
        for name in ("explicitInactiveNode", "behaviorBranch"):
            start = source.index(f"  function {name}(")
            end = source.index("\n  function ", start + 1)
            bodies.append(source[start:end])
        with tempfile.TemporaryDirectory(prefix="cargo-profile-ui-") as folder:
            module = Path(folder) / "profiles.mjs"
            module.write_text(source + """
export function cargoControlsFixture(target) {
  const profile = {fields:{chillState:'OW_WILD_BEHAVIOR_KIND_CHASE',chillTarget:target,cargoTargetCheckInterval:'12',cargoTargetSwitchAdvantage:'1'}};
  const fieldRaw = (p,f) => p.fields[f] || '';
  const fieldDraftMap = () => null;
  const isOverrideProfile = () => true;
  const effectiveFieldCandidates = (p,f) => [p.fields[f]];
""" + "\n".join(bodies) + """
  return behaviorBranch(profile,'chill-behavior').nodes;
}
""")
            test = Path(folder) / "test.mjs"
            test.write_text("import assert from 'node:assert/strict';\n"
                + "import {cargoControlsFixture,canonicalCatalogStructuralErrors} from " + json.dumps(module.as_uri()) + ";\n" + r"""
for (const target of ['OW_WILD_BEHAVIOR_TARGET_CARGO','OW_WILD_BEHAVIOR_TARGET_PLAYER']) {
  const nodes=cargoControlsFixture(target);
  for (const field of ['cargoTargetCheckInterval','cargoTargetSwitchAdvantage']) {
    const node=nodes.find(n=>n.field===field);
    assert.ok(node); assert.equal(Boolean(node.inactive),target!=='OW_WILD_BEHAVIOR_TARGET_CARGO');
    assert.match(node.note,/Wild/);
  }
}
for (const [field,values] of [['cargoTargetCheckInterval',[0,16,true,1.5]],['cargoTargetSwitchAdvantage',[-1,4,false,1.5]]]) {
  for (const value of values) {
    const catalog={catalogVersion:5,rootProfile:'root',pools:[],profiles:[{id:'root',name:'Root',parent:null,kind:'normal',fields:{[field]:{operator:'replace',value}}}],applications:[],selectors:[],runtimeBindings:{}};
    assert.ok(canonicalCatalogStructuralErrors(catalog,{fields:[{key:field}]}).some(e=>e.includes(field+' must be')));
  }
}
""")
            result = subprocess.run(["node", str(test)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
