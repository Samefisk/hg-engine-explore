"""Find Playmate and Playful use the shared C evaluator and exact OOI binding."""
from pathlib import Path
import copy
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from tools.overworld.test_behavior_condition_adapter import HOST_TYPES

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_behavior_condition_runtime.h"
#include "overworld_target_bindings.h"
#include "overworld_application_bank.h"
#include "overworld_behavior_resolver.h"
extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;
static OverworldWildBehaviorDataBlob blob;
static OverworldBehaviorConditionPreparedActor prepared;
static OverworldBehaviorConditionEntryState states[32];
static OverworldBehaviorConditionWorldView world;
static OverworldBehaviorConditionCandidate candidates[2];
static OverworldBehaviorConditionScratch scratch;
static OverworldBehaviorConditionResult result;
static OverworldTargetBindingsState bindings;
static u8 findLocal,playLocal;
static u16 findActorIndex,playActorIndex,playPlayerIndex;
static OverworldActorHandle Handle(u16 slot,u16 generation){return (OverworldActorHandle){slot,generation,3,4,5,0};}
static u16 Index(u16 id){u16 i;for(i=0;i<blob.header.conditionEntryCount;i++)if(blob.conditionEntries[i].conditionId==id)return i;assert(0);return 0;}
static void Reset(void){
 blob=gOverworldWildBehaviorDataBlob;memset(&prepared,0,sizeof(prepared));memset(states,0,sizeof(states));memset(&world,0,sizeof(world));memset(candidates,0,sizeof(candidates));memset(&scratch,0,sizeof(scratch));
 world.subject=Handle(0,1);world.frame=100;world.subjectX=10;world.subjectY=10;world.subjectFacing=3;world.subjectVisionRange=4;world.subjectVisionOptions=15;world.subjectRoleMask=1;
 world.playerX=11;world.playerY=10;world.playerValid=1;world.actorCount=2;
 world.actors[0]=(OverworldBehaviorConditionActorObservation){.actor=world.subject,.x=10,.y=10,.valid=1};
 world.actors[1]=(OverworldBehaviorConditionActorObservation){.actor=Handle(1,2),.x=13,.y=10,.valid=1};
 candidates[0].context=(OverworldWildBehaviorContext){.species=35,.level=5,.terrain=1};candidates[0].roleMask=1;
 candidates[1].context=(OverworldWildBehaviorContext){.species=36,.level=5,.terrain=1};candidates[1].roleMask=1;
 assert(OverworldTargetBindings_Init(&bindings,&world.subject)==0);world.bindings=&bindings;
 prepared.states=states;prepared.stateCapacity=32;
 assert(OverworldBehaviorCondition_PrepareActor(&blob,sizeof(blob),&candidates[0].context,&world.subject,&prepared)==0);
 findActorIndex=Index(34198);playActorIndex=Index(12203);playPlayerIndex=Index(19219);
 OverworldApplicationBank bank;assert(OverworldApplicationBank_Select(&blob,35,&bank));
 findLocal=OverworldApplicationBank_Local(&bank,blob.conditionGlobalApplications[findActorIndex]);playLocal=OverworldApplicationBank_Local(&bank,blob.conditionGlobalApplications[playActorIndex]);
 assert(findLocal<playLocal && playLocal<32);
}
static void Run(void){unsigned status=OverworldBehaviorCondition_EvaluatePrepared(&blob,sizeof(blob),&prepared,&world,candidates,2,0,&scratch,&result);if(status)fprintf(stderr,"frame %u status %u\n",world.frame,status);assert(!status);}
static int Active(u8 local){return !!(result.activeApplicationMask&(1u<<local));}
static void Resolved(u8 expectedPause){
 BehaviorResolveRequest q={0};BehaviorResolveResult out;
 q.context=candidates[0].context;q.behaviorClass=OW_WILD_BEHAVIOR_CLASS_DEFAULT;q.requestVersion=BEHAVIOR_RESOLVE_REQUEST_VERSION;
 q.activeConditionalMask=result.activeApplicationMask;q.winningConditionId=result.winningConditionId;
 q.targetSourceApplication=result.resolvedTargetSourceApplication;q.resolvedTargetConditionId=result.resolvedTargetConditionId;
 q.resolvedTarget.kind=result.resolvedTarget.kind;q.resolvedTarget.actorSlot=result.resolvedTarget.actor.slot;q.resolvedTarget.actorGeneration=result.resolvedTarget.actor.generation;q.resolvedTarget.fieldEpoch=result.resolvedTarget.actor.fieldEpoch;q.resolvedTarget.mapGeneration=result.resolvedTarget.actor.mapGeneration;q.resolvedTarget.encounterGeneration=result.resolvedTarget.actor.encounterGeneration;
 assert(BehaviorResolver_Resolve(&blob,sizeof(blob),&q,&out,NULL)==0);
 assert(out.profile.owner.chainPauseAction==expectedPause);
 if(expectedPause){assert(out.profile.owner.alertTime==0 && out.profile.owner.alertEmote==255);assert((out.profile.owner.chainRepositionJumpCount>>4 &3)==1);assert((out.profile.owner.avoidPreviousTile>>1)==50);}
}
static void StageMatrix(void){
 Reset();Run();assert(Active(findLocal)&&!Active(playLocal));
 world.frame++;Run();assert(!(scratch.entryFlags[0]&OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED));
 /* The first captured Actor wins identity/provenance even though the last Player row also admitted. */
 assert(bindings.bindings[0].sourceConditionId==34198);
 assert(result.winningConditionIds[findLocal]==34198 && result.targets[findLocal].kind==2);
 assert(!memcmp(&result.targets[findLocal].actor,&world.actors[1].actor,sizeof(OverworldActorHandle)));Resolved(0);
 world.frame++;world.actors[1].x=11;Run();assert(Active(findLocal)&&Active(playLocal));
 assert(result.winningConditionIds[playLocal]==12203 && result.targets[playLocal].kind==2);
 assert(!memcmp(&result.targets[playLocal].actor,&bindings.bindings[0].target.actor,sizeof(OverworldActorHandle)));Resolved(1);
 world.frame++;world.actors[1].x=11;world.actors[1].y=11;Run();assert(Active(playLocal));
 world.frame++;world.actors[1].x=10;world.actors[1].y=10;Run();assert(Active(playLocal));
 world.frame++;world.actors[1].x=12;Run();assert(Active(findLocal)&&!Active(playLocal));
 world.actors[1].x=11;world.actors[1].y=10;world.frame++;Run();assert(Active(playLocal));
 /* A stored parent state is insufficient: it must contribute in this same pass. */
 prepared.catalogEntryIndexes[0]=playActorIndex;prepared.catalogEntryIndexes[1]=playPlayerIndex;prepared.count=2;memset(states,0,sizeof(states));Run();assert(!Active(findLocal)&&!Active(playLocal));
 Reset();world.actors[1].x=11;Run();assert(Active(playLocal));
 world.actors[1].actor.generation++;world.frame++;assert(OverworldBehaviorCondition_EvaluatePrepared(&blob,sizeof(blob),&prepared,&world,candidates,2,0,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);assert(!Active(findLocal)&&!Active(playLocal));
 /* Current player adjacency cannot replace an Actor identity after loss. */
 assert(bindings.bindings[0].target.kind==2);
 Reset();world.actors[1].x=11;Run();assert(Active(playLocal));
 world.frame=520;Run();assert(!Active(findLocal)&&!Active(playLocal));
 world.frame=530;world.actors[1].valid=0;Run();assert(Active(findLocal)&&Active(playLocal));
 assert(bindings.bindings[0].target.kind==1 && bindings.bindings[0].sourceConditionId==58853);
 assert(result.winningConditionIds[playLocal]==19219 && result.targets[playLocal].kind==1);
 /* New options reject forward/self dependency and invalid reserved bytes. */
 Reset();blob.conditionOptions[playActorIndex].requiredApplication=blob.conditionGlobalApplications[playActorIndex]+1;
 assert(OverworldBehaviorCondition_EvaluatePrepared(&blob,sizeof(blob),&prepared,&world,candidates,2,0,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
 Reset();blob.conditionOptions[playActorIndex].reservedDependency=1;
 assert(OverworldBehaviorCondition_EvaluatePrepared(&blob,sizeof(blob),&prepared,&world,candidates,2,0,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
}
int main(int argc,char **argv){StageMatrix();if(argc==2){FILE *file=fopen(argv[1],"wb");assert(file);assert(fwrite(&gOverworldWildBehaviorDataBlob,sizeof(blob),1,file)==1);assert(!fclose(file));}puts("same-pass dependency; far/adjacent/same/diagonal; stale identity; Actor-first/Player-last capture; no entry emote; 420/430 expiry and recapture PASS");}
'''

class PlaymateStageTests(unittest.TestCase):
    def test_shared_c_stage_identity_timing_and_profile(self):
        with tempfile.TemporaryDirectory(prefix='playmate-stages-') as scratch:
            folder=Path(scratch);driver=folder/'playmate.c';binary=folder/'playmate';driver.write_text(HARNESS)
            (folder/'types.h').write_text(HOST_TYPES)
            command=[*shlex.split(os.environ.get('HOST_CC','cc')),'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unknown-pragmas',
                '-DOVERWORLD_ACTOR_SYSTEM_HOST','-DOVERWORLD_BEHAVIOR_HOST','-include',str(folder/'types.h'),
                '-I',str(folder),'-I',str(ROOT/'include'),str(driver),
                *[str(ROOT/'lib/overworld'/f'{name}.c') for name in ('overworld_behavior_conditions','overworld_vision',
                    'overworld_behavior_condition_runtime','overworld_target_bindings','overworld_pickup_route','overworld_behavior_resolver')],
                str(ROOT/'data/OverworldWildBehaviorData.c'),'-o',str(binary)]
            compile_result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(compile_result.returncode,0,compile_result.stdout+compile_result.stderr)
            proof=ROOT/'build/tickets/tkt62';proof.mkdir(parents=True,exist_ok=True)
            blob=proof/'current-blob95.bin'
            run=subprocess.run([str(binary),str(blob)],capture_output=True,text=True)
            (proof/'shared-c.log').write_text(run.stdout+run.stderr)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            from scripts import validate_overworld_wild_blobs as validator
            from tools.overworld.devtools_application_bank import decode_application_bank
            validator.validate_owbd(blob,ROOT/'include/overworld_wild_behavior_data.h')
            decode_application_bank(blob.read_bytes(),ROOT)

    def test_dependency_authoring_rejects_bad_order_and_keeps_local_settings(self):
        from scripts import overworld_behavior_profile_viewer as viewer
        catalog=json.loads((ROOT/'data/overworld_behavior_profiles.json').read_text())
        viewer.validate_behavior_catalog(catalog)
        playful=next(p for p in catalog['profiles'] if p['id']=='playful')
        approach=next(p for p in catalog['profiles'] if p['id']=='find-playmate')
        self.assertEqual(approach['fields']['chainPauseAction']['value'],'OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE')
        self.assertNotIn('hopTime',approach['fields'])
        self.assertEqual(playful['fields']['alertTime']['value'],0)
        for required in ['playful','seek-safety','missing','default']:
            bad=copy.deepcopy(catalog);next(p for p in bad['profiles'] if p['id']=='playful')['conditions'][0]['requiresAppliedProfile']=required
            with self.assertRaises(viewer.ParseError):viewer.validate_behavior_catalog(bad)

if __name__=='__main__':unittest.main()
