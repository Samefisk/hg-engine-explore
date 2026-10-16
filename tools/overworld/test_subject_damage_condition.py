"""Subject-only accepted damage, prepared identity, and normal timed admission."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

from tools.overworld.test_behavior_condition_adapter import _actual_function, HOST_TYPES

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'lib/overworld/overworld_player_damage_condition.c'

PRELUDE = r'''
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "host-adapter.h"
struct FieldSystem { unsigned marker; };
struct OverworldWildSpawn { u16 species,encounterGeneration; u32 personality; };
struct OverworldWildOverlayRuntimeState { OverworldWildBehaviorConditionRuntime *conditions; };
typedef struct OverworldWildOverlayRuntimeState OverworldWildOverlayRuntimeState;
struct OverworldWildSpawnState {
 OverworldWildOverlayRuntimeState *movementRuntimeState;
 FieldSystem *movementFieldSystem;
 u16 mapGeneration;
 struct OverworldWildSpawn spawns[10];
};
typedef struct { OverworldActorStateSnapshot snapshot; } TestSlot;
typedef struct { u32 frame;u16 fieldEpoch;TestSlot slots[10]; } OverworldActorSystemState;
static OverworldActorSystemState actorState;
#define OVERWORLD_ACTOR_SYSTEM_STATE_ADDR ((uintptr_t)&actorState)
#define OW_WILD_MAX_SPAWNS 10
static BOOL Ready(void){return TRUE;}
static BOOL ReadHp(const OverworldWildSpawnState *s,u8 slot,u16 *hp,u16 *max){(void)s;(void)slot;*hp=10;*max=20;return TRUE;}
static const struct { BOOL (*readHp)(const OverworldWildSpawnState *,u8,u16 *,u16 *); } combat={ReadHp};
#define OverworldCombat_IsReady Ready
#define OVERWORLD_COMBAT_ENTRY (&combat)
static void sys_FreeMemoryEz(void *p){(void)p;}
static void OverworldBehaviorConditionAdapter_ClearResolution(OverworldWildBehaviorConditionRuntime *r,u8 s){r->activeApplicationMasks[s]=0;r->frame.valid=FALSE;}
'''

DRIVER = r'''
static OverworldWildBehaviorConditionRuntime r;
static OverworldWildOverlayRuntimeState runtime={&r};
static FieldSystem field;
static OverworldWildSpawnState wild={&runtime,&field,4,{{0}}};
static BOOL current=TRUE;
static BOOL Current(const OverworldWildSpawnState *s,u8 slot){(void)s;return current && slot<10;}
static void Reset(void){
 memset(&r,0,sizeof(r));memset(&actorState,0,sizeof(actorState));current=TRUE;
 actorState.fieldEpoch=2;
 for(unsigned n=1;n<=2;n++){
  OverworldActorStateSnapshot *a=&actorState.slots[n].snapshot;
  a->handle=(OverworldActorHandle){n,3,2,4,9,0};a->active=1;a->species=173;a->subjectIdentity=11+n;
  r.actors[n].subject=a->handle;r.actors[n].valid=1;
  wild.spawns[n]=(struct OverworldWildSpawn){173,9,11+n};
 }
 r.frame.world.subject=r.actors[1].subject;r.frame.world.playerValid=1;r.frame.world.frame=100;
}
static void Publish(u8 slot){OverworldPlayerDamageCondition_Publish(&wild,slot|OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE,Current);}
static void Read(u8 slot){OverworldPlayerDamageCondition_Read(&r,&wild,&field,slot,NULL);}
extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;
static void MovingThenSecondHit(void){
 Reset();const OverworldWildBehaviorDataBlob *blob=&gOverworldWildBehaviorDataBlob;
 OverworldBehaviorConditionPreparedActor *p=&r.actors[1];
 OverworldBehaviorConditionEntryState movementState={0};
 unsigned index=0;while(index<blob->header.conditionEntryCount && (blob->conditionEntries[index].kind!=OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED || blob->conditionOptions[index].subjectRoleMask!=2))index++;
 assert(index<blob->header.conditionEntryCount);
 p->catalogEntryIndexes[0]=index;p->count=1;p->stateCapacity=1;p->states=&movementState;p->subjectSpecies=173;
 r.frame.candidates[0].context=(OverworldWildBehaviorContext){.species=173,.level=5,.terrain=1};
 r.frame.candidates[0].roleMask=2;
 r.frame.world.actors[0].actor=p->subject;r.frame.world.actors[0].valid=1;r.frame.world.actorCount=1;
 r.frame.world.subjectRoleMask=2;
 r.frame.world.bindings=&r.bindings[1];
 Publish(1);Read(1);r.frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING;
 assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),p,&r.frame.world,r.frame.candidates,1,0,&r.scratch,&r.result)==0);
 assert((r.scratch.entryFlags[0]&OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED) && movementState.activeUntil==1060);
 OverworldPlayerDamageCondition_Read(&r,&wild,&field,1,blob);assert(!p->subjectDamagePending);
 Publish(1);Read(1);r.frame.world.frame=101;r.frame.world.reservedBinding=0;
 assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),p,&r.frame.world,r.frame.candidates,1,0,&r.scratch,&r.result)==0);
 assert(r.scratch.entryFlags[0]&OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PRESENTATION_ENTERED);
 OverworldPlayerDamageCondition_Read(&r,&wild,&field,1,blob);assert(p->subjectDamagePending==1);
 r.frame.world.frame=1070;
 assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),p,&r.frame.world,r.frame.candidates,1,0,&r.scratch,&r.result)==0);
 assert((r.scratch.entryFlags[0]&OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED) && movementState.activeUntil==2030);
 OverworldPlayerDamageCondition_Read(&r,&wild,&field,1,blob);assert(!p->subjectDamagePending);
 p->states=NULL;p->stateCapacity=0;p->subjectDamagePending=1;
 OverworldBehaviorCondition_PrepareActor(blob,sizeof(*blob),&r.frame.candidates[0].context,&p->subject,p);
 assert(!p->subjectDamagePending);
}
int main(int argc,char **argv){
 Reset();Publish(2);assert(r.actors[2].subjectDamagePending==1&&!r.actors[1].subjectDamagePending);
 Read(2);assert(r.frame.world.playerFacingAndOcclusion&OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED);
 Read(1);assert(!(r.frame.world.playerFacingAndOcclusion&OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED));
 /* Every prepared identity component remains a required current event gate. */
 for(unsigned n=0;n<6;n++){
  Reset();u16 *h=(u16*)&r.actors[1].subject;h[n]++;
  Publish(1);assert(!r.actors[1].subjectDamagePending);
 }
 Reset();current=FALSE;Publish(1);assert(!r.actors[1].subjectDamagePending);
 Reset();actorState.slots[1].snapshot.subjectIdentity++;Publish(1);assert(!r.actors[1].subjectDamagePending);
 Reset();actorState.slots[1].snapshot.species++;Publish(1);assert(!r.actors[1].subjectDamagePending);
 Reset();Publish(10);assert(!r.actors[1].subjectDamagePending);
 Reset();Publish(1);Publish(1);assert(r.actors[1].subjectDamagePending==1);
 OverworldBehaviorConditionDefinition d={.conditionId=61,.durationFrames=960,.cooldownFrames=970,
  .applicationIndex=0,.kind=OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED,
  .activationMode=OVERWORLD_BEHAVIOR_CONDITION_TIMED,.targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER,.chance=100};
 OverworldBehaviorConditionEntryInput input={0};OverworldBehaviorConditionEntryState state={0};OverworldBehaviorConditionEntryResult result;
 Read(1);assert(OverworldBehaviorCondition_EvaluateEntry(&d,&input,&r.frame.world,&state,&result)==0);
 assert(result.triggered&&result.active&&result.target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
 assert(state.activeUntil==1060&&state.cooldownUntil==1070);
 OverworldWildBehaviorConditionEntry entry={.kind=OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS};
 OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&r,1,&entry,OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED);
 assert(r.actors[1].subjectDamagePending==1);
 entry.kind=OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED;
 OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&r,1,&entry,0);assert(r.actors[1].subjectDamagePending==1);
 r.playerDamage.pendingMask=7;
 OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&r,1,&entry,OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED);
 assert(!r.actors[1].subjectDamagePending&&r.playerDamage.pendingMask==7);
 Read(1);r.frame.world.frame=101;
 assert(OverworldBehaviorCondition_EvaluateEntry(&d,&input,&r.frame.world,&state,&result)==0&&result.active&&!result.triggered);
 assert(state.activeUntil==1060&&state.cooldownUntil==1070);
 /* A later hit waits through this condition's ordinary cooldown. */
 Publish(1);Read(1);r.frame.world.frame=1060;
 assert(OverworldBehaviorCondition_EvaluateEntry(&d,&input,&r.frame.world,&state,&result)==0&&!result.active&&!result.triggered);
 assert(r.actors[1].subjectDamagePending==1);
 r.frame.world.frame=1070;
 assert(OverworldBehaviorCondition_EvaluateEntry(&d,&input,&r.frame.world,&state,&result)==0&&result.triggered&&state.activeUntil==2030);
 /* Old event cannot survive the prepared handle's normal clear. */
 OverworldConditionSubject_ClearActor(&r,1);assert(!r.actors[1].subjectDamagePending&&!r.actors[1].valid);
 MovingThenSecondHit();
 if(argc==2){FILE *f=fopen(argv[1],"wb");assert(f);assert(fwrite(&gOverworldWildBehaviorDataBlob,sizeof(gOverworldWildBehaviorDataBlob),1,f)==1);assert(fclose(f)==0);}
 puts("accepted subject event; unrelated exclusion; full handle; duplicate; cached world; consume; 960/970 timing; lifecycle clear PASS");
 return 0;
}
'''


class SubjectDamageTests(unittest.TestCase):
    def test_native_event_identity_and_timed_response(self):
        source=SOURCE.read_text()
        parts=[PRELUDE]
        for name,prefix in (
                ('OverworldBehaviorConditionAdapter_HandleEquals','static BOOL '),
                ('OverworldBehaviorConditionAdapter_PlayerDamage','static void '),
                ('OverworldBehaviorConditionAdapter_ConsumePlayerDamage','static void '),
                ('OverworldPlayerDamageCondition_Read','void '),
                ('OverworldPlayerDamageCondition_Publish','void ')):
            parts.append(_actual_function(source,name,prefix))
        parts.append(_actual_function((ROOT/'lib/overworld/overworld_condition_subject_native.c').read_text(),
                                     'OverworldConditionSubject_ClearActor','void ').replace(
            '__attribute__((noinline, section(".overworld_condition_subject_clear")))',
            '__attribute__((noinline))'))
        parts.append(DRIVER)
        with tempfile.TemporaryDirectory(prefix='subject-damage-') as directory:
            p=Path(directory);driver=p/'subject.c';binary=p/'subject';driver.write_text('\n'.join(parts))
            (p/'host-types.h').write_text(HOST_TYPES)
            header=(ROOT/'include/overworld_behavior_condition_adapter.h').read_text().split(
                'typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[')[0]
            (p/'host-adapter.h').write_text(header+'\n#endif\n')
            command=[*shlex.split(os.environ.get('HOST_CC','cc')),'-std=c11','-O2','-Wall','-Wextra','-Werror',
                '-DOVERWORLD_ACTOR_SYSTEM_HOST','-DOVERWORLD_BEHAVIOR_HOST',
                '-include',str(p/'host-types.h'),'-I',str(p),'-I',str(ROOT/'include'),str(driver),
                *[str(ROOT/'lib/overworld'/f'{name}.c') for name in ('overworld_behavior_conditions',
                    'overworld_vision','overworld_behavior_condition_runtime','overworld_target_bindings','overworld_pickup_route')],
                str(ROOT/'data/OverworldWildBehaviorData.c'),'-o',str(binary)]
            compiled=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            blob=p/'subject.bin'
            run=subprocess.run([str(binary),str(blob)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            from scripts import validate_overworld_wild_blobs as validator
            validator.validate_owbd(blob,ROOT/'include/overworld_wild_behavior_data.h')
            import struct
            original=blob.read_bytes();offset,count,stride=struct.unpack_from('<IHH',original,52)
            entry=next(offset+i*stride for i in range(count) if original[offset+i*stride+37]==6)
            for fault,at,value in (('unknown-kind',37,7),('actor-target',39,2),('vision-range',42,5),('chance',44,99),('speed',45,1)):
                with self.subTest(packaging=fault):
                    bad=bytearray(original);bad[entry+at]=value;blob.write_bytes(bad)
                    with self.assertRaises(ValueError):validator.validate_owbd(blob,ROOT/'include/overworld_wild_behavior_data.h')
            # The same joined production sequence rejects the old consume
            # shape: deferred first presentation must keep a second hit.
            guard='&& !(entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PRESENTATION_ENTERED)'
            actual='\n'.join(parts);self.assertEqual(actual.count(guard),1)
            driver.write_text(actual.replace(guard,''))
            old=p/'old-consume';compiled=subprocess.run(command[:-2]+['-o',str(old)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            rejected=subprocess.run([str(old)],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn('p->subjectDamagePending==1',rejected.stderr)

    def test_authoring_kind_keeps_subject_scope_and_normal_timers(self):
        spec=importlib.util.spec_from_file_location('subject_damage_viewer',ROOT/'scripts/overworld_behavior_profile_viewer.py')
        viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(viewer)
        catalog=json.loads((ROOT/'data/overworld_behavior_profiles.json').read_text())
        seek=next(p for p in catalog['profiles'] if p['id']=='seek-safety')
        condition=copy.deepcopy(seek['conditions'][0]);condition.update(id='test-subject-damage',when={'kind':'subject-damaged'},target={'kind':'player'})
        seek['conditions'].append(condition)
        viewer.validate_behavior_catalog(catalog)
        source=viewer.render_behavior_catalog(catalog,viewer.BEHAVIOR_DATA_SOURCE.read_text())
        header=viewer.render_behavior_catalog_header(viewer.BEHAVIOR_DATA_HEADER.read_text(),catalog,source)
        self.assertIn('OW_WILD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED',source)
        self.assertIn('#define OW_WILD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED 6',header)
        for bad in ('vision','actor target'):
            candidate=copy.deepcopy(catalog);c=next(p for p in candidate['profiles'] if p['id']=='seek-safety')['conditions'][-1]
            if bad=='vision':c['when']['vision']={'mode':'current'}
            else:c['target']={'kind':'actor','roles':['wild'],'selection':'nearest','members':[],'groupMask':'OW_WILD_BEHAVIOR_GROUP_NONE'}
            with self.subTest(bad=bad),self.assertRaises(viewer.ParseError):viewer.validate_behavior_catalog(candidate)

    def test_workshop_visible_condition_is_not_vision(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        with tempfile.TemporaryDirectory(prefix='subject-damage-ui-') as directory:
            p=Path(directory);module=p/'profiles.mjs';module.write_bytes((ROOT/'tools/overworld-viewer-v2/static/profiles.js').read_bytes())
            catalog=json.loads((ROOT/'data/overworld_behavior_profiles.json').read_text())
            script="""
import assert from 'node:assert/strict';
import {canonicalCatalogStructuralErrors as errors} from MODULE;
const catalog=CATALOG;
const p=catalog.profiles.find(p=>p.id==='seek-safety');const c=p.conditions[0];
c.when={kind:'subject-damaged'};c.target={kind:'player'};
c.activation={mode:'timed',durationFrames:960,cooldownFrames:970};
const fields=Object.keys(catalog.profiles.find(p=>p.id===catalog.rootProfile).fields);
const input={fields:fields.map(key=>({key})),numericOverrideOperatorFieldKeys:fields,boundedOverrideOperatorFieldKeys:fields};
assert.deepEqual(errors(catalog,input),[]);
c.when.vision={mode:'current'};assert.ok(errors(catalog,input).some(e=>e.includes('subject-damaged')));delete c.when.vision;
c.target={kind:'actor',roles:['wild'],selection:'nearest',groupMask:'OW_WILD_BEHAVIOR_GROUP_NONE',members:[]};
assert.ok(errors(catalog,input).some(e=>e.includes('subject-damaged')));
c.target={kind:'none'};assert.deepEqual(errors(catalog,input),[]);
""".replace('MODULE',json.dumps(module.as_uri())).replace('CATALOG',json.dumps(catalog))
            completed=subprocess.run([node,'--input-type=module','-e',script],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        text=(ROOT/'tools/overworld-viewer-v2/static/profiles.js').read_text()
        self.assertIn('value="subject-damaged"',text)
        self.assertIn('This Pokémon takes damage',text)


if __name__=='__main__':unittest.main()
