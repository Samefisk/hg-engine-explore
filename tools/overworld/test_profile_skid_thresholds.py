"""Production-C skid picker, packed composition, authoring roundtrip and Vision3."""
from pathlib import Path
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from tools.overworld.test_behavior_catalog_v5 import load_viewer
from tools.overworld.test_behavior_resolver_conditions import run_resolver_harness
from scripts.verify_overworld_mount import function_body
ROOT=Path(__file__).resolve().parents[2]
VIEWER=load_viewer()

class ProfileSkidThresholdsTests(unittest.TestCase):
    def test_catalog_bounds_and_packed_roundtrip(self):
        catalog=json.loads((ROOT/"data/overworld_behavior_profiles.json").read_text())
        VIEWER.validate_behavior_catalog(catalog)
        root=next(p for p in catalog["profiles"] if p["id"]==catalog["rootProfile"])
        for field in ("turnSkidOneTime","turnSkidTwoTime","stopSkidTime"):
            # The root thresholds are user settings, not fixed defaults.
            self.assertEqual(root["fields"][field]["operator"],"replace")
            self.assertIn(int(root["fields"][field]["value"]),range(128))
            for value in (0,1,32,127):
                VIEWER._validate_catalog_override_field(field,{"operator":"replace","value":value},"test")
            for value in (-1,128):
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER._validate_catalog_override_field(field,{"operator":"replace","value":value},"test")
            for op in ("relative","divide","atLeast","atMost"):
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER._validate_catalog_override_field(field,{"operator":op,"value":2},"test")
        raws={field:"0" for field in VIEWER.PROFILE_FIELDS}
        for enabled in (0,1):
            for threshold in (0,1,32,127):
                raws.update(turnSkidOneTime="127",turnSkidTwoTime=str(threshold),stopSkidTime=str(threshold),hopAllowVerticalObstacles=str(enabled),chainRepositionDust=str(enabled))
                literal=VIEWER.format_profile_initializer(raws,"")
                storage=VIEWER.parse_initializer(literal)
                parsed=VIEWER.parse_profile(storage,{})
                for field in ("turnSkidOneTime","turnSkidTwoTime","stopSkidTime","hopAllowVerticalObstacles","chainRepositionDust"):
                    self.assertEqual(VIEWER.numeric(parsed[field]),int(raws[field]))
                self.assertIn(f"OW_WILD_BEHAVIOR_SKID_OPTIONS({enabled}, {threshold})",literal)

    def test_cardinal_lines_lowering(self):
        for cone,code in (("forward-90",1),("forward-line",2),("cardinal-lines",3)):
            for adjacent in (False,True):
                when={"kind":"notice-player","vision":{"mode":"custom","range":32,"cone":cone,"adjacentAwareness":adjacent},"chancePercent":100}
                lowered=VIEWER._normalize_v5_condition_when(when,"test")
                self.assertEqual(lowered["visionOptions"],code | (4 if adjacent else 0))
                self.assertEqual(lowered["rangeLength"],32)
                self.assertEqual(lowered["rangeKind"],"OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM")

    def test_workshop_skid_groups_and_cardinal_lines(self):
        with tempfile.TemporaryDirectory(prefix="profile-skid-ui-") as folder:
            module=Path(folder)/"profiles.mjs"
            module.write_text((ROOT/"tools/overworld-viewer-v2/static/profiles.js").read_text()
                + "\nexport {setConditionVisionSelection};\n")
            script=Path(folder)/"test.mjs"
            script.write_text("import assert from 'node:assert/strict';\n"
                + "import {movementEditorGroups,setConditionVisionSelection,canonicalCatalogStructuralErrors} from "
                + json.dumps(module.as_uri()) + ";\n" + r"""
const fields=['tilesBeforeTurnSkid','turnSkidOneTime','turnSkidTwoTime','stopSkid','stopSkidTime'];
for(const scope of ['chill','tired']) {
 const groups=movementEditorGroups(fields.map(field=>({field})),scope);
 const skid=groups.flatMap(section=>section.groups).find(group=>group.label==='Turn and stop skids');
 assert.deepEqual(skid.nodes.map(node=>node.field),fields);
}
for(const cone of ['forward-90','forward-line','cardinal-lines']) {
 const condition={when:{kind:'notice-player',vision:{mode:'custom',range:32,cone,adjacentAwareness:false}}};
 setConditionVisionSelection(condition,'custom',5);
 assert.equal(condition.when.vision.cone,cone);
 assert.equal(condition.when.vision.adjacentAwareness,false);
}
""")
            result=subprocess.run(["node",str(script)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_actual_resolver_keeps_each_packed_slice_independent(self):
        source=(ROOT/"lib/overworld/overworld_behavior_resolver.c").read_text()+r"""
void SkidTestApply(OverworldWildBehaviorProfileData *p,const OverworldWildBehaviorOverrideProfile *o) {BehaviorResolver_ApplyOverride(p,o);}
"""
        harness=r"""
#include <assert.h>
#include <stddef.h>
#include <string.h>
#include "overworld_behavior_resolver.h"
extern void SkidTestApply(OverworldWildBehaviorProfileData *,const OverworldWildBehaviorOverrideProfile *);
int main(void) {
    assert(sizeof(OverworldWildBehaviorProfileData)==80);
    assert(sizeof(OverworldWildBehaviorProfile)==160);
    assert(offsetof(OverworldWildBehaviorProfileData,hopAllowVerticalObstacles)==56);
    assert(offsetof(OverworldWildBehaviorProfileData,chainRepositionDust)==62);
    for(unsigned base=0;base<256;base++) for(unsigned incoming=0;incoming<256;incoming++) for(unsigned mask=0;mask<32;mask++) {
        OverworldWildBehaviorProfileData p,expected;
        OverworldWildBehaviorOverrideProfile o,saved;
        memset(&p,0x5A,sizeof(p));memset(&o,0,sizeof(o));
        p.hopAllowVerticalObstacles=p.chainRepositionDust=base;p.range=7;
        o.profile.hopAllowVerticalObstacles=o.profile.chainRepositionDust=incoming;o.profile.range=13;
        o.mask=(mask&1)?OW_WILD_BEHAVIOR_OVERRIDE_TURN_SKID_ONE_TIME:0;
        o.mask2=((mask&2)?OW_WILD_BEHAVIOR_OVERRIDE2_TURN_SKID_TWO_TIME:0)|((mask&4)?OW_WILD_BEHAVIOR_OVERRIDE2_STOP_SKID_TIME:0);
        o.mask3=((mask&8)?OW_WILD_BEHAVIOR_OVERRIDE3_HOP_ALLOW_VERTICAL_OBSTACLES:0)|((mask&16)?OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_DUST:0);
        expected=p;saved=o;
        if(mask&1)expected.range=13;
        if(mask&2)expected.hopAllowVerticalObstacles=(expected.hopAllowVerticalObstacles&1)|(incoming&254);
        if(mask&4)expected.chainRepositionDust=(expected.chainRepositionDust&1)|(incoming&254);
        if(mask&8)expected.hopAllowVerticalObstacles=(expected.hopAllowVerticalObstacles&254)|(incoming&1);
        if(mask&16)expected.chainRepositionDust=(expected.chainRepositionDust&254)|(incoming&1);
        SkidTestApply(&p,&o);
        assert(!memcmp(&p,&expected,sizeof(p)));assert(!memcmp(&o,&saved,sizeof(o)));
    }
    return 0;
}
"""
        compiled,result=run_resolver_harness(harness,source)
        self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_threshold_extremes_and_shared_knockback_byte(self):
        source=(ROOT/"lib/overworld/overworld_behavior_resolver.c").read_text()+r"""
void SkidTestApply(OverworldWildBehaviorProfileData *p,const OverworldWildBehaviorOverrideProfile *o) {BehaviorResolver_ApplyOverride(p,o);}
"""
        harness=r"""
#include <assert.h>
#include <string.h>
#include "overworld_behavior_resolver.h"
#include "overworld_walk_timing_policy.h"
extern void SkidTestApply(OverworldWildBehaviorProfileData *,const OverworldWildBehaviorOverrideProfile *);
int main(void) {
    const u8 limits[]={0,1,4,127};
    for(unsigned time=0;time<256;time++) for(unsigned one=0;one<128;one++)
    for(unsigned i=0;i<4;i++) for(unsigned j=0;j<4;j++) {
        unsigned two=limits[i],stop=limits[j];
        unsigned turn=time && time<=two ? (time==1?4:2) : time && time<=one;
        unsigned stopping=time && time<=stop ? (time==1?4:time<=4?2:1) : 0;
        assert(OverworldWalkTimingPolicy_ProfileSkidTiles(time,one,two,stop,0)==turn);
        assert(OverworldWalkTimingPolicy_ProfileSkidTiles(time,one,two,stop,1)==stopping);
    }
    for(unsigned base=0;base<256;base++) for(unsigned incoming=0;incoming<256;incoming++)
    for(unsigned mask=0;mask<8;mask++) {
        OverworldWildBehaviorProfileData p,expected;
        OverworldWildBehaviorOverrideProfile o,saved;
        memset(&p,0x5A,sizeof(p));memset(&o,0,sizeof(o));
        p.knockbackOptions=base;o.profile.knockbackOptions=incoming;
        o.mask2=((mask&1)?OW_WILD_BEHAVIOR_OVERRIDE2_KNOCKBACK_TYPE:0)
            |((mask&2)?OW_WILD_BEHAVIOR_OVERRIDE2_KNOCKBACK_DISTANCE:0)
            |((mask&4)?OW_WILD_BEHAVIOR_OVERRIDE2_DAMAGE_RECIPIENTS:0);
        expected=p;saved=o;
        unsigned bits=((mask&1)?3:0)|((mask&2)?28:0)|((mask&4)?224:0);
        expected.knockbackOptions=(base&~bits)|(incoming&bits);
        SkidTestApply(&p,&o);
        assert(!memcmp(&p,&expected,sizeof(p)));assert(!memcmp(&o,&saved,sizeof(o)));
    }
    return 0;
}
"""
        compiled,result=run_resolver_harness(harness,source)
        self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_wild_frame_work_merged_throw_guard(self):
        source=(ROOT/"src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        body=function_body(source,"OverworldWildSpawns_GetFrameMovementWork(")
        prelude=r"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16;typedef uint32_t u32;typedef int BOOL;
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT 16
#define OW_WILD_SPAWNER_FRAME_WORK_GLOBAL 0x80000000u
struct Runtime {u16 movementHelpSpawnParentSlotPlusOne,movementHelpSpawnRemaining;struct{u16 targetMask,carrierMask;}throwState;};
typedef struct{u16 movementInProgressMask;struct Runtime *movementRuntimeState;}OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) ((state)->movementRuntimeState)
static BOOL queued;static unsigned inspected;
static BOOL OverworldWildSpawns_HasQueuedBattle(OverworldWildSpawnState *state){(void)state;return queued;}
static u32 OverworldWildSpawns_GetFrameMovementWorkForSlot(OverworldWildSpawnState *state,int slot){(void)state;(void)slot;inspected++;return 0;}
"""
        main=r"""
int main(void){
 struct Runtime r={0};OverworldWildSpawnState s={3,&r};
 const u16 values[]={0,1,255,256,65535};
 assert(OverworldWildSpawns_GetFrameMovementWork(0)==0);
 s.movementRuntimeState=0;
 assert(OverworldWildSpawns_GetFrameMovementWork(&s)==0x00030003);s.movementRuntimeState=&r;
 for(unsigned raw=0;raw<65536;raw++) for(unsigned j=0;j<5;j++) {
  r.throwState.targetMask=raw;r.throwState.carrierMask=values[j];
  inspected=0;
  assert(OverworldWildSpawns_GetFrameMovementWork(&s)==(0x00030003u|((raw||values[j])?0x80000000u:0)));
  assert(inspected==10);
 }
 r.throwState.targetMask=r.throwState.carrierMask=0;
 for(unsigned parent=0;parent<2;parent++) for(unsigned left=0;left<2;left++) {
  r.movementHelpSpawnParentSlotPlusOne=parent;r.movementHelpSpawnRemaining=left;
  assert(OverworldWildSpawns_GetFrameMovementWork(&s)==(0x00030003u|((parent&&left)?0x80000000u:0)));
 }
 r.movementHelpSpawnParentSlotPlusOne=r.movementHelpSpawnRemaining=0;queued=1;
 assert(OverworldWildSpawns_GetFrameMovementWork(&s)==0x80030003u);
 return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="skid-frame-guard-") as folder:
            binary=Path(folder)/"guard"
            compiled=subprocess.run(["cc","-std=c11","-O0","-x","c","-","-o",str(binary)],
                input=prelude+"static u32 OverworldWildSpawns_GetFrameMovementWork(OverworldWildSpawnState *state){"+body+"}\n"+main,
                text=True,capture_output=True)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run([str(binary)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
