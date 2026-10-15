from pathlib import Path
import subprocess
import os
import shlex

from tools.overworld.test_throw_failure_composition import HOST_TYPES
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "include/overworld_behavior_condition_adapter.h"
SOURCE = ROOT / "lib/overworld/overworld_behavior_condition_adapter.c"
WILD_SOURCE = (
    ROOT
    / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)
SERVICE_SOURCE = (
    ROOT
    / "src/overworld_follower_selector_overlay/overworld_behavior_condition_service.c"
)
WALK_SOURCE = ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c"
def function(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start)
    return source[start:end]


def _actual_function(source, name, declaration="static "):
    start = source.rfind(declaration, 0, source.index(name + "("))
    assert start >= 0, name
    brace = source.index("{", source.index(name + "("))
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def target_publication_fixture(source):
    names = ["OverworldBehaviorConditionAdapter_PopulateSubject",
             "OverworldBehaviorConditionAdapter_ResolveTarget"]
    if "OverworldBehaviorConditionAdapter_ReadPriorTarget(" in source:
        names.append("OverworldBehaviorConditionAdapter_ReadPriorTarget")
    names.append("OverworldBehaviorConditionAdapter_EvaluateActor")
    publication = (ROOT / "lib/overworld/overworld_condition_publication_native.c").read_text()
    return "\n".join([TARGET_PUBLICATION_PRELUDE,
                       _actual_function((ROOT / "lib/overworld/overworld_player_damage_condition.c").read_text(),
                                        "OverworldBehaviorConditionAdapter_ConsumePlayerDamage", "static void "),
                       TARGET_PUBLICATION_QUERY_PRELUDE,
                       _actual_function((ROOT / "lib/overworld/overworld_player_damage_condition.c").read_text(),
                                        "OverworldBehaviorCondition_BuildRequest", "BOOL "),
                       "#define PUBLICATION_SECTION(name)",
                       _actual_function(publication, "OverworldConditionPublication_ChangedMask", "u32 "),
                       *[_actual_function(source, name) for name in names[:-1]],
                       TARGET_PUBLICATION_NATIVE_SDK,
                       '#include "' + str(ROOT / "lib/overworld/overworld_condition_moving_notice_native.c") + '"',
                       TARGET_PUBLICATION_NATIVE_WRAPPER,
                       _actual_function(source,names[-1]), TARGET_PUBLICATION_DRIVER])

TARGET_PUBLICATION_PRELUDE = '\n#include <assert.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "host-adapter.h"\ntypedef struct LocalMapObject { int xCurr,yCurr,curFacing; u32 flags; s32 posVec[3]; } LocalMapObject;\ntypedef struct FIELD_PLAYER_AVATAR { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;\nstruct FieldSystem { int current; FIELD_PLAYER_AVATAR *playerAvatar; };\nstruct OverworldWildSpawn { LocalMapObject *object; u16 species,encounterGeneration; u32 personality; u8 active; };\nstruct OverworldWildSpawnState { OverworldWildSpawn spawns[10];u8 movementBehaviorClasses[10];FieldSystem *movementFieldSystem; };\n#define OW_WILD_SPAWN_TERRAIN_LAND 1\nextern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;\nstatic unsigned resolves,clears;\nstatic BOOL subjectCurrent=TRUE;\nstatic u32 observation;\nstatic unsigned expectedObserveMode,resetObserveMode;\nstatic BehaviorResolveStatus CountResolve(const void *b,u32 z,const BehaviorResolveRequest *q,BehaviorResolveResult *r,BehaviorResolutionTrace *t) {resolves++;BehaviorResolveStatus status=BehaviorResolver_Resolve(b,z,q,r,t);if(status)fprintf(stderr,"resolve status%u mask%x winning%u source%u condition%u kind%u\\n",status,q->activeConditionalMask,q->winningConditionId,q->targetSourceApplication,q->resolvedTargetConditionId,q->resolvedTarget.kind);return status;}\nstatic const struct { BehaviorResolveStatus (*resolve)(const void*,u32,const BehaviorResolveRequest*,BehaviorResolveResult*,BehaviorResolutionTrace*); } resolver={CountResolve};\n#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY (&resolver)\nstatic const OverworldBehaviorConditionServiceEntry service={OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,10,sizeof(service),0,OverworldBehaviorCondition_EvaluatePrepared,0,0};\nstatic const OverworldBehaviorConditionServiceEntry *OverworldBehaviorConditionAdapter_GetService(void) { return &service; }\nstatic BOOL OverworldBehaviorConditionAdapter_BuildFrame(OverworldWildSpawnState *s,FieldSystem *f,OverworldWildBehaviorConditionRuntime *r,OverworldBehaviorConditionBuildContextFunc b,OverworldBehaviorConditionIsCurrentSpawnFunc c) {(void)s;(void)f;(void)b;(void)c;r->frame.actorSlotMask=subjectCurrent?1:0;return TRUE;}\nstatic void OverworldBehaviorConditionAdapter_ClearResolution(OverworldWildBehaviorConditionRuntime *r,u8 s){r->activeApplicationMasks[s]=0;r->timedWinningApplicationMasks[s]=0;r->targetValidMask&=~(1u<<s);r->frame.valid=FALSE;clears++;}\nstatic void OverworldBehaviorConditionAdapter_ClearActor(OverworldWildBehaviorConditionRuntime *r,u8 s){OverworldBehaviorConditionAdapter_ClearResolution(r,s);}\nstatic u8 OverworldBehaviorConditionAdapter_HandleEquals(const OverworldActorHandle *a,const OverworldActorHandle *b){return a->slot==b->slot&&a->generation==b->generation&&a->fieldEpoch==b->fieldEpoch&&a->mapGeneration==b->mapGeneration&&a->encounterGeneration==b->encounterGeneration;}\nvoid OverworldBehaviorConditionTrace_Record(const OverworldActorHandle *s,const OverworldBehaviorConditionResult *r,const OverworldBehaviorConditionEntryState *e,u16 b){(void)s;(void)r;(void)e;(void)b;}\nstatic void Context(OverworldWildBehaviorContext *c,const OverworldWildSpawn *s,u16 species,u8 level,u8 terrain,u8 shiny){(void)species;(void)level;(void)terrain;(void)shiny;memset(c,0,sizeof(*c));c->species=s->species;c->level=5;c->terrain=1;}\nstatic BOOL Current(FieldSystem *f,const OverworldWildSpawn *s){(void)f;(void)s;return subjectCurrent;}\nstatic u16 Terrain(FieldSystem *f,int x,int y){(void)f;(void)x;(void)y;return 1;}\nstatic void Visibility(FieldSystem *f,OverworldBehaviorConditionWorldView *w){(void)f;(void)w;}\nstatic u32 Observe(OverworldWildSpawnState*s,int slot,const OverworldWildBehaviorProfile*p,const OverworldWildBehaviorDataBlob*b,OverworldWildBehaviorConditionRuntime*r){(void)s;(void)slot;(void)p;(void)b;assert(r->frame.world.reservedBinding==expectedObserveMode);if(resetObserveMode)((OverworldWildBehaviorConditionRuntime *)r)->frame.world.reservedBinding=0;return observation;}\n'

TARGET_PUBLICATION_PRELUDE += '\n#include "overworld_condition_moving_notice_native.h"\ntypedef u16 OverworldBehaviorConditionVisionWord __attribute__((may_alias));\n'
TARGET_PUBLICATION_PRELUDE += r"""
#include "overworld_motion_model.h"
#include "overworld_pickup_route_wild.h"
/* Native structures are read-only SDK seams in this joined host fixture.
 * Use the real pointer-free Motion plan/state and Actor snapshot fields. */
typedef struct OverworldActorRuntimeSlot {
 OverworldActorStateSnapshot snapshot;
 OverworldMotionState motion;
} OverworldActorRuntimeSlot;
typedef struct OverworldActorSystemState {
 u32 magic;
 u16 version,size;
 u32 frame;
 u16 fieldEpoch,mapGeneration;
 OverworldActorRuntimeSlot slots[10];
} OverworldActorSystemState;
static const OverworldPickupRouteNativeSeams *hostRouteSeams;
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *world){(void)world;return hostRouteSeams;}
"""



TARGET_PUBLICATION_QUERY_PRELUDE = r"""
#include "overworld_query_code_addon_service.h"
#include "overworld_application_bank.h"
BOOL OverworldBehaviorCondition_BuildRequest(OverworldWildBehaviorConditionRuntime *, int, const OverworldWildBehaviorDataBlob *);
static OverworldBehaviorConditionStatus HostNative(OverworldConditionNativeCall *);
/* Query acquisition and the native HP/source read are SDK seams. The real
 * consume leaf and shared reducer execute below with that current event. */
void OverworldPlayerDamageCondition_Read(OverworldWildBehaviorConditionRuntime *r,
    OverworldWildSpawnState *s, FieldSystem *f, u8 slot,
    const OverworldWildBehaviorDataBlob *b)
{
 (void)s;(void)f;
 if(b){
  for(unsigned n=0;n<r->actors[slot].count;n++)
   OverworldBehaviorConditionAdapter_ConsumePlayerDamage(r,slot,
    &b->conditionEntries[r->actors[slot].catalogEntryIndexes[n]],r->scratch.entryFlags[n]);
  return;
 }
 for(unsigned n=0;n<r->frame.world.actorCount;n++){
  OverworldBehaviorConditionActorObservation *a=&r->frame.world.actors[n];
  a->facingAndOcclusion&=~OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE;
  if((r->playerDamage.pendingMask&(1u<<slot))
    &&r->playerDamage.recipientGenerations[slot]==r->actors[slot].subject.generation
    &&a->valid&&OverworldBehaviorConditionAdapter_HandleEquals(&a->actor,&r->playerDamage.source))
   a->facingAndOcclusion|=OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE;
 }
}
static const OverworldQueryCodeAddonEntry queryAddon = {
    .playerDamageRead=OverworldPlayerDamageCondition_Read,
    .conditionNative=HostNative,
};
static const OverworldQueryCodeAddonEntry *AcquireQuery(const OverworldQueryCodeAddonOwner *owner)
{
    assert(owner->fieldIdentity && owner->fieldEpoch==3 && owner->mapGeneration==3);
    return &queryAddon;
}
static const OverworldQueryCodeAddonServiceEntry queryService = {.acquire=AcquireQuery};
#undef OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR ((uintptr_t)&queryService)
"""

TARGET_PUBLICATION_DRIVER = '\nstatic OverworldWildBehaviorConditionRuntime r;\nstatic OverworldWildBehaviorDataBlob *blob;\nstatic OverworldBehaviorConditionEntryState states[4];\nstatic OverworldWildSpawnState wild;\nstatic FieldSystem field;\nstatic LocalMapObject object={.xCurr=10,.yCurr=10};\nstatic unsigned playerIndex,actorIndex;\nstatic OverworldActorHandle H(unsigned slot,unsigned generation){return (OverworldActorHandle){slot,generation,3,3,1,0};}\nstatic unsigned LocalApplication(const OverworldWildBehaviorDataBlob *b,u16 species,u16 global){OverworldApplicationBank bank;assert(OverworldApplicationBank_Select(b,species,&bank));int local=OverworldApplicationBank_Local(&bank,global);assert(local>=0);return (unsigned)local;}\nstatic void Reset(void){\n memset(&r,0,sizeof(r));memset(states,0,sizeof(states));memset(&wild,0,sizeof(wild));\n memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));\n playerIndex=actorIndex=999;\n for(unsigned i=0;i<blob->header.conditionEntryCount;i++){\n  if(blob->conditionEntries[i].conditionId==20034)playerIndex=i;\n  if(blob->conditionEntries[i].conditionId==43840)actorIndex=i;\n }\n assert(playerIndex<32&&actorIndex<32);\n assert(blob->conditionGlobalApplications[playerIndex]==blob->conditionGlobalApplications[actorIndex]);\n r.actors[0].subject=H(0,2);r.actors[0].subjectSpecies=173;r.actors[0].valid=1;r.actors[0].count=2;\n r.actors[0].states=states;r.actors[0].stateCapacity=4;\n r.actors[0].catalogEntryIndexes[0]=playerIndex;r.actors[0].catalogEntryIndexes[1]=actorIndex;\n r.currentVisions[0].range=3;r.currentVisions[0].options=5;\n wild.spawns[0].object=&object;wild.spawns[0].species=173;\n r.frame.world.frame=100;r.frame.world.playerValid=1;r.frame.world.playerX=10;r.frame.world.playerY=8;\n r.frame.world.actorCount=3;\n for(unsigned i=0;i<2;i++){\n  r.frame.world.actors[i].actor=H(i+1,i+5);r.frame.world.actors[i].x=11+i;r.frame.world.actors[i].y=10;r.frame.world.actors[i].valid=1;\n  r.frame.candidates[i].context.species=74;r.frame.candidates[i].roleMask=1;\n }\n r.frame.world.actors[2].actor=H(0,2);r.frame.world.actors[2].x=10;r.frame.world.actors[2].y=10;r.frame.world.actors[2].valid=1;r.frame.candidates[2].context.species=173;r.frame.candidates[2].roleMask=1;\n resolves=clears=observation=0;subjectCurrent=TRUE;\n}\nstatic OverworldBehaviorConditionStatus Eval(void){\n OverworldBehaviorConditionAdapterOutcome o;\n return OverworldBehaviorConditionAdapter_EvaluateActor(&r,&wild,&field,blob,sizeof(*blob),0,2,NULL,Observe,-1,Context,Current,Terrain,Visibility,&o);\n}\nstatic void Step(void){r.frame.world.frame++;unsigned status=Eval();if(status)fprintf(stderr,"step frame%u obs%x status%u resolve%u count%u mask%x\\n",r.frame.world.frame,observation,status,resolves,r.actors[0].count,r.result.activeApplicationMask);assert(status==0);}\nint main(void){\n blob=malloc(sizeof(*blob));assert(blob);Reset();\n assert(Eval()==0);assert(resolves==1);assert(r.resolution.resolvedTarget.kind==1);\n unsigned original=r.resolution.fingerprint;\n observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP|(1u<<19);\n Step();assert(r.result.resolvedTarget.kind==2&&r.result.resolvedTarget.actor.slot==1);\n assert(resolves==2);assert(r.resolution.resolvedTarget.kind==2&&r.resolution.resolvedTarget.actorSlot==1);\n assert(r.resolution.resolvedTargetConditionId==43840&&r.resolution.targetSourceApplication==LocalApplication(blob,173,blob->conditionGlobalApplications[actorIndex]));\n assert(r.resolution.fingerprint!=original);\n original=r.resolution.fingerprint;\n r.frame.world.actors[0].x=13;Step();assert(resolves==2);assert(r.targetX[0]==13);assert(r.resolution.fingerprint==original);\n /* Interleaved scratch from another subject cannot decide this actor\'s reuse. */\n memset(&r.request,0x99,sizeof(r.request));memset(&r.resolution,0x77,sizeof(r.resolution));\n Step();assert(resolves==2&&r.targetX[0]==13);\n /* Leaving the claim restores the still-active Player winner in the same app. */\n observation=0;Step();assert(resolves==3&&r.resolution.resolvedTarget.kind==1&&r.resolution.resolvedTargetConditionId==20034);\n /* A timed Actor contribution can recapture a different still-current Actor. */\n Reset();blob->conditionEntries[playerIndex].chancePercent=0;\n blob->conditionEntries[actorIndex].kind=OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED;\n blob->conditionEntries[actorIndex].terrainMask=blob->conditionEntries[actorIndex].terrainOverrideMask=0;\n blob->conditionEntries[actorIndex].rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS;\n blob->conditionEntries[actorIndex].rangeLength=32;\n blob->conditionEntries[actorIndex].activationMode=OVERWORLD_BEHAVIOR_CONDITION_TIMED;\n blob->conditionEntries[actorIndex].durationFrames=20;blob->conditionEntries[actorIndex].cooldownFrames=0;\n observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP|((1u<<1|1u<<2)<<18);\n assert(Eval()==0&&resolves==1&&r.resolution.resolvedTarget.actorSlot==1);\n r.frame.world.actors[0].x=14;r.frame.world.actors[1].x=11;\n Step();assert(resolves==2&&r.resolution.resolvedTarget.actorSlot==2);\n Step();assert(resolves==2);\n /* An absent full captured target keeps the existing fail-closed status. */\n r.frame.world.actors[1].actor.generation++;r.frame.world.frame++;\n assert(Eval()==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);assert(clears==1&&r.targetValidMask==0&&resolves==2);\n /* A lost subject cannot reach the evaluator or resolver. */\n Reset();subjectCurrent=FALSE;assert(Eval()==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&resolves==0&&clears==1);\n /* Last active targetless row overwrites the targeted row in the same app. */\n Reset();blob->conditionEntries[actorIndex].targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;\n assert(Eval()==0&&resolves==1&&r.resolution.resolvedTarget.kind==1);\n observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP;\n Step();assert(resolves==2&&r.resolution.resolvedTarget.kind==0&&r.resolution.winningConditionId==43840);\n Step();assert(resolves==2);\n observation=0;Step();assert(resolves==3&&r.resolution.resolvedTarget.kind==1);\n /* Overall current provenance changes even when both winners have no target. */\n Reset();blob->conditionEntries[playerIndex].targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;\n blob->conditionEntries[actorIndex].targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;\n assert(Eval()==0&&resolves==1&&r.resolution.winningConditionId==20034&&r.resolution.resolvedTarget.kind==0);\n observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP;\n Step();assert(resolves==2&&r.resolution.winningConditionId==43840&&r.resolution.resolvedTarget.kind==0);\n Step();assert(resolves==2);\n /* bindOnly retains its binding state but never replaces the behavior target. */\n Reset();blob->conditionOptions[actorIndex].bindOnly=1;blob->conditionOptions[actorIndex].captureBinding=1;r.bindings[0].subject=H(0,2);\n assert(Eval()==0&&resolves==1);observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP|(1u<<19);\n Step();assert(resolves==1&&r.resolution.resolvedTarget.kind==1&&r.result.resolvedTargetConditionId==20034);\n Step();assert(resolves==1);\n puts("same-app Player/Actor/full identity/provenance publication; position-only reuse; stale/lost/targetless/bindOnly guards GREEN");free(blob);return 0;\n}\n'


WARM_CARGO_DRIVER = r"""
static OverworldWildBehaviorConditionRuntime r;
static OverworldWildBehaviorDataBlob *blob;
static OverworldBehaviorConditionEntryState states[4];
static OverworldWildSpawnState wild;
static FieldSystem field;
static LocalMapObject object={.xCurr=10,.yCurr=10};
static unsigned triggerIndex,cargoIndex,otherIndex,cargoApplication;
static OverworldActorHandle H(unsigned slot,unsigned generation){return (OverworldActorHandle){slot,generation,3,3,1,0};}
static void Reset(void){
 memset(&r,0,sizeof(r));memset(states,0,sizeof(states));memset(&wild,0,sizeof(wild));
 memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
 triggerIndex=cargoIndex=otherIndex=999;
 for(unsigned i=0;i<blob->header.conditionEntryCount;i++){
  if(blob->conditionEntries[i].conditionId==24737)triggerIndex=i;
  if(blob->conditionEntries[i].conditionId==57932)cargoIndex=i;
  if(blob->conditionEntries[i].conditionId==20034)otherIndex=i;
 }
 assert(triggerIndex<blob->header.conditionEntryCount&&cargoIndex<blob->header.conditionEntryCount&&otherIndex<blob->header.conditionEntryCount);
 /* Warm admission is tested with an explicitly bind-only initiating row;
  * current product sight admission is proved by the registered game case. */
 blob->conditionOptions[triggerIndex].bindOnly=1;
 OverworldApplicationBank cargoBank;assert(OverworldApplicationBank_Select(blob,74,&cargoBank));
 int cargoLocal=OverworldApplicationBank_Local(&cargoBank,blob->conditionGlobalApplications[cargoIndex]);assert(cargoLocal>=0);cargoApplication=(unsigned)cargoLocal;
 blob->conditionGlobalApplications[otherIndex]=cargoBank.globalIds[0];assert(blob->conditionGlobalApplications[otherIndex]!=blob->conditionGlobalApplications[cargoIndex]);
 r.actors[0].subject=H(0,2);r.actors[0].subjectSpecies=74;r.actors[0].valid=1;r.actors[0].count=2;
 r.actors[0].states=states;r.actors[0].stateCapacity=4;
 r.actors[0].catalogEntryIndexes[0]=triggerIndex;r.actors[0].catalogEntryIndexes[1]=cargoIndex;r.actors[0].catalogEntryIndexes[2]=otherIndex;
 r.currentVisions[0].range=5;r.currentVisions[0].options=5;
 wild.spawns[0].object=&object;wild.spawns[0].species=74;
 r.frame.world.frame=100;r.frame.world.playerValid=1;r.frame.world.playerX=10;r.frame.world.playerY=8;
 r.frame.world.actorCount=3;
 for(unsigned i=0;i<2;i++){
  r.frame.world.actors[i].actor=H(i+1,i+5);r.frame.world.actors[i].x=11+i;r.frame.world.actors[i].y=10;r.frame.world.actors[i].valid=1;
  r.frame.candidates[i].context.species=173;r.frame.candidates[i].roleMask=1;
 }
 r.frame.world.actors[2].actor=H(0,2);r.frame.world.actors[2].x=10;r.frame.world.actors[2].y=10;r.frame.world.actors[2].valid=1;r.frame.candidates[2].context.species=74;r.frame.candidates[2].roleMask=1;
 assert(OverworldTargetBindings_Init(&r.bindings[0],&r.actors[0].subject)==0);
 resolves=clears=observation=0;subjectCurrent=TRUE;
}
static OverworldBehaviorConditionStatus Eval(int operation,OverworldBehaviorConditionAdapterOutcome *out){
 expectedObserveMode=operation==OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO:0;
 /* Frame refresh in the callback may clear the marker. The actual adapter
  * must restore private warm evaluation before the prepared reducer runs. */
 resetObserveMode=expectedObserveMode;
 return OverworldBehaviorConditionAdapter_EvaluateActor(&r,&wild,&field,blob,sizeof(*blob),0,2,NULL,Observe,operation,Context,Current,Terrain,Visibility,out);
}
static OverworldBehaviorConditionAdapterOutcome out;
static void Start(void){
 assert(Eval(-1,&out)==0);
 assert(r.bindings[0].bindings[0].flags&OVERWORLD_TARGET_BINDING_BOUND);
 assert(r.bindings[0].bindings[0].target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
 assert(!(r.bindings[0].bindings[1].flags&OVERWORLD_TARGET_BINDING_BOUND));
 assert(resolves==0);assert(BehaviorResolver_Resolve(blob,sizeof(*blob),&r.request,&r.resolution,NULL)==0);r.frame.world.frame++;
 observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID|(1u<<(8+1));
}
static void Warm(void){static unsigned warmCalls;unsigned status=Eval(OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO,&out);warmCalls++;if(status)fprintf(stderr,"warm call%u frame%u status%u mode%u\n",warmCalls,r.frame.world.frame,status,r.frame.world.reservedBinding);assert(status==0);assert(out.flags==0);assert(r.frame.world.reservedBinding==0);}
int main(void){
 blob=malloc(sizeof(*blob));assert(blob);
 Reset();Start();
 OverworldBehaviorConditionEntryState before[4];memcpy(before,states,sizeof(states));
 BehaviorResolveResult oldResolution=r.resolution;
 u32 oldMask=r.activeApplicationMasks[0],oldTimed=r.timedWinningApplicationMasks[0];
 Warm();
 assert(resolves==0&&clears==0&&r.activeApplicationMasks[0]==oldMask&&r.timedWinningApplicationMasks[0]==oldTimed);
 assert(memcmp(before,states,sizeof(states))==0&&memcmp(&oldResolution,&r.resolution,sizeof(oldResolution))==0);
 assert(r.bindings[0].bindings[1].flags&OVERWORLD_TARGET_BINDING_BOUND);
 assert(r.bindings[0].bindings[1].target.kind==2&&r.bindings[0].bindings[1].target.actor.slot==1);
 OverworldTargetBinding bound=r.bindings[0].bindings[1];
 /* Another reachable candidate cannot retarget the captured full identity. */
 r.frame.world.frame++;observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID|(1u<<(8+2));Warm();
 assert(memcmp(&bound,&r.bindings[0].bindings[1],sizeof(bound))==0&&memcmp(before,states,sizeof(states))==0);
 /* Existing current Cargo retention supplies its own eligibility on idle. */
 observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID|(1u<<(8+1));r.frame.world.frame++;
 assert(Eval(-1,&out)==0&&resolves==1);
 assert(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
 assert(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED);
 assert(r.result.targets[cargoApplication].kind==2&&r.result.targets[cargoApplication].actor.slot==1);assert(r.result.winningConditionId==57932);assert(r.resolution.primitives.chillTarget==OW_WILD_BEHAVIOR_TARGET_CARGO);
 r.frame.world.frame++;assert(Eval(-1,&out)==0&&resolves==1&&out.flags==0);
 /* Chance is the real prepared evaluator rule; failed warm and idle do not capture. */
 Reset();Start();blob->conditionEntries[cargoIndex].chancePercent=0;Warm();
 assert(!(r.bindings[0].bindings[1].flags&1));r.frame.world.frame++;assert(Eval(-1,&out)==0&&resolves==0&&!(r.bindings[0].bindings[1].flags&1));
 /* Pending query never admits a Cargo. */
 Reset();Start();observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID;Warm();assert(!(r.bindings[0].bindings[1].flags&1));
 /* Held/recovering facts and wrong role cannot capture through the shared row. */
 for(unsigned fact=2;fact<=8;fact+=6){Reset();Start();observation|=fact;Warm();assert(!(r.bindings[0].bindings[1].flags&1));}
 Reset();Start();r.frame.candidates[2].roleMask=4;Warm();assert(!(r.bindings[0].bindings[1].flags&1));
 /* Lost/stale current Trigger and subject preserve strict identity guards. */
 Reset();Start();r.frame.world.playerValid=0;memcpy(before,states,sizeof(states));Warm();assert(!(r.bindings[0].bindings[1].flags&1)&&memcmp(before,states,sizeof(states))==0);
 Reset();Start();r.bindings[0].subject.generation++;Warm();assert(!(r.bindings[0].bindings[1].flags&1));
 Reset();Start();subjectCurrent=FALSE;assert(Eval(OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO,&out)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&resolves==0&&clears==1);
 /* Absent or non-current Cargo cannot pass selection/full-handle validation. */
 Reset();Start();r.frame.world.actors[0].valid=0;Warm();assert(!(r.bindings[0].bindings[1].flags&1));

 /* Repeated chance37 uses the same real per-frame Truth gate as normal
  * evaluation; Cargo capture does not refresh or retarget after admission. */
 Reset();Start();blob->conditionEntries[cargoIndex].chancePercent=37;
 OverworldBehaviorConditionPreparedActor reference=r.actors[0];
 OverworldBehaviorConditionEntryState referenceStates[4];memcpy(referenceStates,states,sizeof(states));reference.states=referenceStates;
 OverworldTargetBindingsState referenceBindings=r.bindings[0];
 OverworldBehaviorConditionWorldView referenceWorld=r.frame.world;referenceWorld.bindings=&referenceBindings;
 OverworldBehaviorConditionScratch referenceScratch={0};OverworldBehaviorConditionResult referenceResult;
 unsigned admitted=0;
 for(unsigned n=0;n<180;n++){
  r.frame.world.frame++;referenceWorld.frame=r.frame.world.frame;
  referenceWorld.reserved[0]=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID;
  referenceWorld.reserved[1]=1u<<1;referenceWorld.reserved[2]=referenceWorld.reservedBinding=0;
  assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),&reference,&referenceWorld,r.frame.candidates,referenceWorld.actorCount,referenceWorld.frame,&referenceScratch,&referenceResult)==0);
  memcpy(before,states,sizeof(states));Warm();
  assert(memcmp(before,states,sizeof(states))==0);
  assert(memcmp(&referenceBindings,&r.bindings[0],sizeof(referenceBindings))==0);
  assert((referenceResult.activeApplicationMask&(1u<<cargoApplication))==(r.result.activeApplicationMask&(1u<<cargoApplication)));
  admitted|=(r.bindings[0].bindings[1].flags&1);
 }
 assert(admitted&&resolves==0);
 /* A valid timed notice capture is outside warm ActorFacts admission.
  * Its saved cooldown stays unchanged; idle starts its timer exactly once. */
 Reset();Start();blob->conditionEntries[cargoIndex].kind=OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED;
 blob->conditionEntries[cargoIndex].rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS;blob->conditionEntries[cargoIndex].rangeLength=8;
 blob->conditionEntries[cargoIndex].activationMode=OVERWORLD_BEHAVIOR_CONDITION_TIMED;
 blob->conditionEntries[cargoIndex].durationFrames=10;blob->conditionEntries[cargoIndex].cooldownFrames=12;
 states[1].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;states[1].cooldownUntil=r.frame.world.frame+5;
 memcpy(before,states,sizeof(states));
 for(unsigned n=0;n<5;n++){Warm();assert(!(r.bindings[0].bindings[1].flags&1));assert(memcmp(before,states,sizeof(states))==0);r.frame.world.frame++;}
 Warm();assert(!(r.bindings[0].bindings[1].flags&1));assert(memcmp(before,states,sizeof(states))==0);
 assert(Eval(-1,&out)==0&&resolves==1&&(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 assert(states[1].activeUntil==r.frame.world.frame+10&&states[1].cooldownUntil==r.frame.world.frame+12);
 r.frame.world.frame++;assert(Eval(-1,&out)==0&&resolves==1&&!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 /* Unrelated timed rows cannot advance while the existing Walk owns motion. */
 Reset();Start();r.actors[0].count=3;
 states[2].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE|OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
 states[2].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;states[2].activeUntil=r.frame.world.frame+2;states[2].cooldownUntil=r.frame.world.frame+20;
 memcpy(before,states,sizeof(states));
 for(unsigned n=0;n<5;n++){Warm();assert(memcmp(before,states,sizeof(states))==0&&resolves==0);r.frame.world.frame++;}
 /* A stale captured Cargo stays captured for the legal idle loss path;
  * another current candidate is never substituted during warm reads. */
 Reset();Start();Warm();bound=r.bindings[0].bindings[1];r.frame.world.actors[0].actor.generation++;
 observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID|(1u<<(8+2));Warm();assert(memcmp(&bound,&r.bindings[0].bindings[1],sizeof(bound))==0);
 /* A malformed later row remains atomic, including warm capture. */
 Reset();Start();r.actors[0].count=3;blob->conditionOptions[otherIndex].captureBinding=3;memcpy(before,states,sizeof(states));
 assert(Eval(OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO,&out)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
 assert(r.frame.world.reservedBinding==0&&!(r.bindings[0].bindings[1].flags&1)&&memcmp(before,states,sizeof(states))==0&&clears==0);
 puts("actual shared warm Cargo capture; prepared/public/motion unchanged; idle once-only activation/alert; chance/current/role/held/recovering/atomic guards GREEN");free(blob);return 0;
}
"""


TARGET_PUBLICATION_NATIVE_SDK = r"""
static const OverworldBehaviorConditionWorldView *hostWorld;
static unsigned terrainTraces;
static u8 blockedPlayer;
static u16 blockedActorMask;
void OverworldConditionSubject_Populate(OverworldWildBehaviorConditionRuntime *r,FieldSystem *f,
 const OverworldBehaviorConditionPreparedActor *p,const LocalMapObject *o,u8 s,u8 v,OverworldBehaviorConditionTerrainFunc t)
 {OverworldBehaviorConditionAdapter_PopulateSubject(r,f,p,o,s,v,t);}
int OverworldConditionVisibility_PlayerX(FIELD_PLAYER_AVATAR *a){(void)a;return hostWorld->playerX;}
int OverworldConditionVisibility_PlayerY(FIELD_PLAYER_AVATAR *a){(void)a;return hostWorld->playerY;}
BOOL OverworldConditionVisibility_TraceBlocked(FieldSystem *f,const OverworldBehaviorConditionWorldView *w,s16 x,s16 y){
 (void)f;terrainTraces++;
 if(x==w->playerX&&y==w->playerY)return blockedPlayer;
 for(unsigned n=0;n<w->actorCount;n++)if(w->actors[n].x==x&&w->actors[n].y==y)
  return (blockedActorMask&(1u<<w->actors[n].actor.slot))!=0;
 return FALSE;
}
"""

TARGET_PUBLICATION_NATIVE_WRAPPER = r"""
static OverworldBehaviorConditionStatus HostNative(OverworldConditionNativeCall *call){
 static FIELD_PLAYER_AVATAR avatar;
 static LocalMapObject player;
 hostWorld=&call->runtime->frame.world;
 player.curFacing=hostWorld->playerFacingAndOcclusion&3;
 avatar.mapObject=&player;
 call->field->playerAvatar=hostWorld->playerValid?&avatar:NULL;
 return OverworldConditionNative_Run(call);
}
"""

MOVING_NOTICE_DRIVER = r"""
static OverworldWildBehaviorConditionRuntime r;
static OverworldWildBehaviorDataBlob *blob;
static OverworldBehaviorConditionEntryState states[4];
static OverworldWildSpawnState wild;
static FieldSystem field;
static LocalMapObject object={.xCurr=10,.yCurr=10};
static unsigned playerIndex,actorIndex,otherIndex;
static OverworldActorHandle H(unsigned slot,unsigned generation){return (OverworldActorHandle){slot,generation,3,3,1,0};}
static void Reset(void){
 memset(&r,0,sizeof(r));memset(states,0,sizeof(states));memset(&wild,0,sizeof(wild));
 memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
 playerIndex=actorIndex=otherIndex=999;
 for(unsigned i=0;i<blob->header.conditionEntryCount;i++){
  if(blob->conditionEntries[i].conditionId==20305)playerIndex=i;
  if(blob->conditionEntries[i].conditionId==49626)actorIndex=i;
 }
 assert(playerIndex<blob->header.conditionEntryCount&&actorIndex<blob->header.conditionEntryCount);
 otherIndex=actorIndex;
 /* Keep the distinct actor row, but bind its subject selector to this Onix fixture. */
 blob->conditionEntries[actorIndex].subjectMatch=blob->conditionEntries[playerIndex].subjectMatch;
 blob->conditionEntries[actorIndex].subjectMode=blob->conditionEntries[playerIndex].subjectMode;
 blob->conditionEntries[actorIndex].subjectMemberStart=blob->conditionEntries[playerIndex].subjectMemberStart;
 blob->conditionEntries[actorIndex].subjectMemberCount=blob->conditionEntries[playerIndex].subjectMemberCount;
 r.actors[0].subject=H(0,2);r.actors[0].subjectSpecies=95;r.actors[0].valid=1;r.actors[0].count=1;
 r.actors[0].states=states;r.actors[0].stateCapacity=4;
 r.actors[0].catalogEntryIndexes[0]=playerIndex;
 wild.spawns[0].object=&object;wild.spawns[0].species=95;
 r.frame.world.frame=100;r.frame.world.playerValid=1;r.frame.world.playerX=12;r.frame.world.playerY=11;
 r.frame.world.actorCount=3;
 for(unsigned i=0;i<2;i++){
  r.frame.world.actors[i].actor=H(i+1,i+5);r.frame.world.actors[i].x=11+i;r.frame.world.actors[i].y=10;r.frame.world.actors[i].valid=1;
  r.frame.candidates[i].context.species=74;r.frame.candidates[i].roleMask=1;
 }
 r.frame.world.actors[2].actor=H(0,2);r.frame.world.actors[2].x=10;r.frame.world.actors[2].y=10;r.frame.world.actors[2].valid=1;
 r.frame.candidates[2].context.species=95;r.frame.candidates[2].roleMask=1;
 assert(OverworldTargetBindings_Init(&r.bindings[0],&r.actors[0].subject)==0);
 resolves=clears=observation=terrainTraces=blockedPlayer=blockedActorMask=0;subjectCurrent=TRUE;
}
static OverworldBehaviorConditionAdapterOutcome out;
static unsigned Eval(int operation){
 expectedObserveMode=operation==OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY:0;
 resetObserveMode=expectedObserveMode;
 unsigned status=OverworldBehaviorConditionAdapter_EvaluateActor(&r,&wild,&field,blob,sizeof(*blob),0,2,NULL,Observe,operation,Context,Current,Terrain,Visibility,&out);
 assert(r.frame.world.reservedBinding==0);
 return status;
}
static void Sample(void){unsigned z=Eval(OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE);if(z)fprintf(stderr,"moving status %u kind %u mode %u flags %x\n",z,blob->conditionEntries[r.actors[0].catalogEntryIndexes[0]].kind,blob->conditionEntries[r.actors[0].catalogEntryIndexes[0]].activationMode,states[0].flags);assert(z==0);}
int main(void){
 blob=malloc(sizeof(*blob));assert(blob);Reset();
 OverworldConditionNativeCall packet={.runtime=&r,.state=&wild,.field=&field,.blob=blob,
  .blobSize=sizeof(*blob),.version=OVERWORLD_CONDITION_NATIVE_CALL_VERSION,.size=sizeof(packet)};
 packet.version=0;assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
 packet.version=OVERWORLD_CONDITION_NATIVE_CALL_VERSION;packet.size--;
 assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
 packet.size=sizeof(packet);packet.operation=2;
 assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
 packet.operation=0;packet.reserved=1;
 assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
 packet.reserved=0;packet.slot=10;
 assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
 packet.slot=0;r.actors[0].count=5;
 assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
 r.actors[0].count=1;r.actors[0].states=NULL;
 assert(OverworldConditionNative_Run(&packet)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
 Reset();
 /* Every condition applies during motion. The first sighting publishes
  * ACTIVE and profile metadata while presentation waits for legal intent. */
 Sample();assert(terrainTraces==0&&states[0].flags==OVERWORLD_BEHAVIOR_CONDITION_STATE_UNTIL_CRASH&&resolves==0);
 r.frame.world.frame++;r.frame.world.playerY=10;Sample();
 assert(terrainTraces==1&&(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 assert((states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)&&resolves==1);
 assert((out.flags&(OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED|OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED))==5);
 assert(states[0].targetKind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER&&states[0].activeUntil==0&&states[0].cooldownUntil==0);
 unsigned mask=r.activeApplicationMasks[0];assert(mask&&r.targetValidMask==1&&r.targetX[0]==12&&r.targetY[0]==10);
 r.frame.world.frame++;r.frame.world.playerX=15;r.frame.world.playerY=11;Sample();
 assert(terrainTraces==1&&(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 assert(resolves==1&&clears==0&&r.activeApplicationMasks[0]==mask&&r.targetValidMask==1&&r.targetX[0]==15&&r.targetY[0]==11);
 assert(!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 /* Legal intent consumes the exact pending target's presentation without
  * another sight roll, timer restart, or resolver publication. */
 r.frame.world.frame++;assert(Eval(-1)==0&&resolves==1&&(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 assert(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED);
 assert(!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED));
 assert((states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)&&!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 assert(out.targetDx==5&&out.targetDy==1&&r.resolution.resolvedTargetConditionId==20305);
 r.frame.world.frame++;assert(Eval(-1)==0&&resolves==1&&!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 /* Cooldown does not trace needlessly; rearm still reads real visibility. */
 Reset();r.frame.world.playerY=10;states[0].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;states[0].cooldownUntil=110;
 Sample();assert(terrainTraces==0&&!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 states[0].flags|=OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM;r.frame.world.frame=111;Sample();assert(terrainTraces==1);
 /* A full Timed episode can start and end during one accepted move. Its
  * end marker persists across false frames and reaches intent exactly once. */
 Reset();r.actors[0].catalogEntryIndexes[0]=otherIndex;
 OverworldWildBehaviorConditionEntry *timed=&blob->conditionEntries[otherIndex];
 blob->conditionOptions[otherIndex].subjectRoleMask=blob->conditionOptions[playerIndex].subjectRoleMask;
 timed->kind=OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED;timed->targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER;
 timed->activationMode=OVERWORLD_BEHAVIOR_CONDITION_TIMED;timed->durationFrames=3;timed->cooldownFrames=100;
 timed->rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_CARDINAL_LINE;timed->rangeLength=32;timed->targetSelection=0;
 r.frame.world.playerY=10;Sample();assert((states[0].flags&1)&&states[0].activeUntil==103&&states[0].cooldownUntil==200);
 r.frame.world.frame=104;r.frame.world.playerY=11;Sample();assert(!(states[0].flags&1)&&(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING));
 r.frame.world.frame++;Sample();assert(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING);
 assert(Eval(-1)==0&&(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED));
 assert(!(states[0].flags&(OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING|OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING)));
 assert(Eval(-1)==0&&!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED));
 /* WhileTrue entries end on the observed frame; delayed presentation cannot
  * revive an expired condition at the later intent boundary. */
 Reset();r.actors[0].catalogEntryIndexes[0]=otherIndex;
 OverworldWildBehaviorConditionEntry *row=&blob->conditionEntries[otherIndex];
 blob->conditionOptions[otherIndex].subjectRoleMask=blob->conditionOptions[playerIndex].subjectRoleMask;
 row->kind=OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED;row->targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER;
 row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;row->durationFrames=row->cooldownFrames=0;
 row->rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_CARDINAL_LINE;row->rangeLength=32;
 r.frame.world.playerY=10;Sample();assert((states[0].flags&33)==33&&r.activeApplicationMasks[0]);
 r.frame.world.frame++;r.frame.world.playerY=11;Sample();assert(!(states[0].flags&33)&&!r.activeApplicationMasks[0]&&!r.targetValidMask);
 assert(Eval(-1)==0&&!(out.flags&(OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED|OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED)));
 /* Terrain and interaction facts run through that same moving reducer. */
 Reset();row=&blob->conditionEntries[playerIndex];
 row->kind=OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED;row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
 row->targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;row->durationFrames=row->cooldownFrames=0;
 row->terrainMask=row->terrainOverrideMask=1;row->minMovementSpeed=2;row->maxMovementSpeed=3;
 Sample();assert((states[0].flags&1)&&r.activeApplicationMasks[0]&&terrainTraces==0);
 row->minMovementSpeed=3;Sample();assert(!(states[0].flags&1)&&!r.activeApplicationMasks[0]);
 Reset();row=&blob->conditionEntries[playerIndex];row->kind=OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS;
 row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;row->targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;
 row->durationFrames=row->cooldownFrames=0;row->terrainMask=OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD;row->terrainOverrideMask=0;
 observation=OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD;Sample();assert((states[0].flags&1)&&r.activeApplicationMasks[0]);
 observation=0;Sample();assert(!(states[0].flags&1)&&!r.activeApplicationMasks[0]);
 /* Inverse visibility needs a native trace even when clear geometric sight
  * says false. An occluded target becomes true; clearing it ends WhileTrue. */
 Reset();row=&blob->conditionEntries[playerIndex];row->kind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT;
 row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;row->durationFrames=row->cooldownFrames=0;
 row->rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;row->rangeLength=32;row->minMovementSpeed=9;
 r.frame.world.playerY=10;r.frame.world.playerFacingAndOcclusion=2;blockedPlayer=1;
 Sample();assert((states[0].flags&1)&&terrainTraces==1);
 blockedPlayer=0;Sample();assert(!(states[0].flags&1)&&terrainTraces==2);
 Reset();r.actors[0].catalogEntryIndexes[0]=actorIndex;row=&blob->conditionEntries[actorIndex];
 row->kind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT;row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
 row->durationFrames=row->cooldownFrames=0;row->rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;
 row->rangeLength=32;row->minMovementSpeed=9;r.frame.candidates[2].roleMask=2;
 for(unsigned n=0;n<2;n++)r.frame.world.actors[n].facingAndOcclusion=2;
 blockedActorMask=1u<<1;Sample();assert((states[0].flags&1)&&states[0].targetSlot==1&&terrainTraces==2);
 blockedActorMask=0;Sample();assert(!(states[0].flags&1)&&terrainTraces==4);
 /* An accepted Player hit captures its exact source during motion and the
  * existing consume leaf clears only that recipient after successful bind. */
 Reset();row=&blob->conditionEntries[playerIndex];row->kind=OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED;
 row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;row->targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR;
 row->durationFrames=row->cooldownFrames=row->terrainMask=row->terrainOverrideMask=0;
 row->rangeKind=row->rangeLength=row->minMovementSpeed=row->maxMovementSpeed=0;row->targetRoleMask=1;
 blob->conditionOptions[playerIndex]=(OverworldWildBehaviorConditionOptions){.subjectRoleMask=1,.captureBinding=1};
 r.playerDamage.source=H(1,5);r.playerDamage.pendingMask=1;r.playerDamage.recipientGenerations[0]=2;
 Sample();assert((states[0].flags&33)==33&&states[0].targetSlot==1&&!r.playerDamage.pendingMask);
 assert(r.bindings[0].bindings[0].flags==1&&r.bindings[0].bindings[0].target.actor.generation==5);
 Sample();assert(!(states[0].flags&33)&&!r.playerDamage.pendingMask);
 /* The trace mask must not replace routed Cargo eligibility. */
 Reset();r.actors[0].catalogEntryIndexes[0]=actorIndex;r.frame.candidates[2].roleMask=2;
 row=&blob->conditionEntries[actorIndex];row->activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
 row->durationFrames=row->cooldownFrames=0;row->rangeKind=OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;
 row->rangeLength=32;row->minMovementSpeed=OVERWORLD_VISION_CONE_CARDINAL_LINES;r.frame.world.actors[1].y=11;
 blob->conditionOptions[actorIndex]=(OverworldWildBehaviorConditionOptions){.subjectRoleMask=2,.captureBinding=2,.mustBeReachableForPickup=1,.pickupDistance=1,.pickupHeight=64};
 observation=(1u<<1|1u<<2)<<8;Sample();assert((states[0].flags&1)&&states[0].targetSlot==1&&terrainTraces==1);
 assert((r.frame.world.reserved[1]|((u16)r.frame.world.reserved[2]<<8))==(1u<<1|1u<<2));
 assert(r.bindings[0].bindings[1].flags==1&&r.bindings[0].bindings[1].target.actor.slot==1);
 /* Chance and native occlusion can veto capture. */
 Reset();r.frame.world.playerY=10;blob->conditionEntries[playerIndex].chancePercent=0;Sample();assert(!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 Reset();r.frame.world.playerY=10;blockedPlayer=4;Sample();assert(terrainTraces==1&&!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 /* Player loss retires pending; Crash notification does the same without
  * erasing the normal cooldown/rearm state. */
 Reset();r.frame.world.playerY=10;Sample();r.frame.world.playerValid=0;
 assert(Eval(OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&clears==0);
 assert(!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 Reset();r.frame.world.playerY=10;Sample();states[0].cooldownUntil=150;
 OverworldBehaviorCondition_NotifyWorldEffect(&r.actors[0],&r.actors[0].subject,OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
 assert(!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING)&&states[0].cooldownUntil==150);
 /* Follower Ram captures the full Wild identity, not the nearest new actor
  * on a later frame. Recycled target and wrong role cannot admit a notice. */
 Reset();r.actors[0].catalogEntryIndexes[0]=actorIndex;r.frame.candidates[2].roleMask=2;Sample();
 assert(states[0].targetKind==2&&states[0].targetSlot==1&&states[0].targetGeneration==5&&terrainTraces==2);
 r.frame.world.actors[0].x=14;r.frame.world.actors[0].y=11;r.frame.world.frame++;Sample();
 assert(states[0].targetSlot==1&&states[0].targetGeneration==5&&terrainTraces==2);
 r.frame.world.actors[0].actor.generation++;
 assert(Eval(OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&clears==0);
 assert(!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 Reset();r.frame.candidates[2].roleMask=2;r.frame.world.playerY=10;Sample();assert(terrainTraces==0&&!(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
 /* A malformed later row remains atomic before even a pending capture. */
 Reset();r.frame.world.playerY=10;r.actors[0].count=2;r.actors[0].catalogEntryIndexes[1]=otherIndex;blob->conditionOptions[otherIndex].captureBinding=3;
 OverworldBehaviorConditionEntryState before[4];memcpy(before,states,sizeof(states));
 assert(Eval(OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
 assert(memcmp(before,states,sizeof(states))==0&&resolves==0&&clears==0&&terrainTraces==0);
 puts("actual moving notice: brief capture, deferred once-only publication, current full target, geometry/cooldown/occlusion/stale/role/atomic guards GREEN");free(blob);return 0;
}
"""



TARGET_ACCESS_DRIVER = r"""
static OverworldWildBehaviorConditionRuntime r;
static OverworldWildBehaviorDataBlob *blob;
static OverworldBehaviorConditionEntryState entryState;
static OverworldWildSpawnState wild;
static FieldSystem field;
static LocalMapObject object={.xCurr=10,.yCurr=10,.curFacing=3};
static unsigned noticeIndex;
static OverworldActorHandle H(unsigned slot,unsigned generation){return (OverworldActorHandle){slot,generation,3,3,1,0};}
static void Reset(void){
 memset(&r,0,sizeof(r));memset(&entryState,0,sizeof(entryState));memset(&wild,0,sizeof(wild));
 memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
 noticeIndex=999;
 for(unsigned i=0;i<blob->header.conditionEntryCount;i++)
  if(blob->conditionEntries[i].conditionId==12365)noticeIndex=i;
 assert(noticeIndex<blob->header.conditionEntryCount);
 assert(blob->conditionOptions[noticeIndex].captureBinding==1);
 r.actors[0].subject=H(0,2);r.actors[0].subjectSpecies=56;r.actors[0].valid=1;r.actors[0].count=1;
 r.actors[0].states=&entryState;r.actors[0].stateCapacity=1;
 r.actors[0].catalogEntryIndexes[0]=noticeIndex;
 r.currentVisions[0].range=5;r.currentVisions[0].options=5;
 wild.spawns[0].object=&object;wild.spawns[0].species=56;
 r.frame.world.frame=100;r.frame.world.actorCount=2;
 r.frame.world.actors[0]=(OverworldBehaviorConditionActorObservation){.actor=H(1,5),.x=11,.y=10,.valid=1};
 r.frame.candidates[0].context.species=16;r.frame.candidates[0].roleMask=1;
 r.frame.world.actors[1]=(OverworldBehaviorConditionActorObservation){.actor=H(0,2),.x=10,.y=10,.valid=1};
 r.frame.candidates[1].context.species=56;r.frame.candidates[1].roleMask=2;
 assert(OverworldTargetBindings_Init(&r.bindings[0],&r.actors[0].subject)==0);
 resolves=clears=observation=0;subjectCurrent=TRUE;
}
static unsigned Eval(int operation){
 OverworldBehaviorConditionAdapterOutcome outcome;
 expectedObserveMode=operation==OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_GEOMETRY:0;
 return OverworldBehaviorConditionAdapter_EvaluateActor(&r,&wild,&field,blob,sizeof(*blob),0,2,NULL,Observe,operation,Context,Current,Terrain,Visibility,&outcome);
}
int main(void){
 blob=malloc(sizeof(*blob));assert(blob);
 /* This subject-specific native fact must veto target admission before
  * the unchanged geometric Vision and real authored Throw notice capture. */
 for(unsigned moving=0;moving<2;moving++){
  Reset();r.frame.candidates[0].reserved[0]=1u;
  assert(Eval(moving?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT:-1)==0);
  if(entryState.flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)
   fprintf(stderr,"T44 inaccessible target admitted by real notice12365; moving=%u flags=%u\n",moving,entryState.flags);
  assert(!(entryState.flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
  assert(!(r.bindings[0].bindings[0].flags&OVERWORLD_TARGET_BINDING_BOUND));
  assert(r.result.resolvedTarget.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE);
  /* Zero retains portable supplied eligibility and accessible targets. */
  r.frame.candidates[0].reserved[0]=0;r.frame.world.frame++;
  assert(Eval(moving?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT:-1)==0);
  assert(entryState.flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE);
  assert(r.bindings[0].bindings[0].flags&OVERWORLD_TARGET_BINDING_BOUND);
  assert(r.bindings[0].bindings[0].target.actor.generation==5);
  /* A retained same-generation target loses the condition when its access
  * fact changes. No stale-state permission can bypass the shared mask. */
  r.frame.candidates[0].reserved[0]=1u;r.frame.world.frame++;
  assert(Eval(moving?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT:-1)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);
  assert(!(entryState.flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
 }
 puts("T44 real authored notice12365 access fact: inaccessible excluded, accessible admitted, retained target invalidated; idle/moving GREEN");
 free(blob);return 0;
}
"""


NATIVE_TARGET_ACCESS_DRIVER = r"""
static OverworldWildBehaviorConditionRuntime r;
static OverworldWildSpawnState wild;
static FieldSystem field;
static LocalMapObject objects[2];
static OverworldActorSystemState systemState;
static OverworldPickupRouteWildWorld world;
static OverworldWildBehaviorDataBlob *blob;
#ifndef EXPECT_SUPPORT_REUSE
#define EXPECT_SUPPORT_REUSE 1
#endif
#define IDENTICAL_SUPPORT_READS (EXPECT_SUPPORT_REUSE ? 2u : 3u)
static unsigned targetSurface,missingTerrain,missingSupport,terrainReads,supportReads;
static unsigned relativeTargetSupport,targetNeedsFlag29;
static s32 originSupport=65536;
static s32 targetSupport=65536;
static unsigned noticeIndex,cargoAccessIndex;
static OverworldBehaviorConditionEntryState accessEntryState;
static OverworldActorHandle H(unsigned slot,unsigned generation){return (OverworldActorHandle){slot,generation,3,3,1,0};}
static const OverworldActorSystemState *ActorState(void){return &systemState;}
static BOOL CurrentObject(FieldSystem *f,LocalMapObject *o){return f==&field&&(o==&objects[0]||o==&objects[1]);}
static OverworldPickupRouteEdgeResult TerrainRead(void *raw,s16 x,s16 y,u16 wanted,OverworldPickupRouteNativeTile *tile){
 assert(raw!=NULL&&wanted==0xFFFF);terrainReads++;(void)y;
 if(missingTerrain&&x==objects[1].xCurr)return OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED;
 *tile=(OverworldPickupRouteNativeTile){OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND,OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND,0,0,0};
 if(x==objects[1].xCurr&&targetSurface){
  tile->surfaceId=targetSurface==2?OW_WILD_SURFACE_ID_NATIVE_CANOPY:
      (targetSurface==3?OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND:7);
  if(targetSurface==2)tile->terrainMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY;
  else if(targetSurface==3)tile->terrainMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
  /* Underlying Land and synthetic Interest never override this surface. */
  if(targetSurface==1)tile->terrainMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST|OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST;
  tile->flags=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST;
 }
 return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL;
}
static OverworldPickupRouteEdgeResult SupportRead(void *raw,const OverworldPickupRoutePosition *origin,s16 x,s16 y,const OverworldPickupRouteNativeTile *tile,s32 *height){
 OverworldPickupRouteWildWorld *w=raw;
 assert(w->routeRead==1&&tile!=NULL);supportReads++;(void)y;
 if(missingSupport&&x==objects[1].xCurr)return OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED;
 /* This is the native relative-height flag: the subject's actual support
  * seed matters, while an absolute catalog hit uses the loaded height. */
 if(x==objects[1].xCurr&&targetNeedsFlag29&&!(w->heightObject->flags&(1u<<29)))
  return OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED;
 if(tile->surfaceId!=OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND&&tile->surfaceId!=OW_WILD_SURFACE_ID_NATIVE_CANOPY)
  *height=targetSupport;
 else if(w->heightObject->flags&(1u<<23))*height=origin->baseY;
 else if(x==objects[1].xCurr)*height=relativeTargetSupport?origin->baseY+32768:targetSupport;
 else *height=originSupport;
 return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL;
}
static const OverworldPickupRouteNativeSeams accessSeams={.terrain=TerrainRead,.support=SupportRead};
static const OverworldPickupRouteWildOps ops={.version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION,.size=sizeof(ops),.currentObject=CurrentObject,.actorState=ActorState};
static void Reset(void){
 memset(&r,0,sizeof(r));memset(&wild,0,sizeof(wild));memset(objects,0,sizeof(objects));memset(&systemState,0,sizeof(systemState));
 world=(OverworldPickupRouteWildWorld){.version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION,.size=sizeof(world),.field=&field,.state=&wild,.subjectObject=&objects[0],.heightObject=&objects[0],.ops=&ops,.slot=0};
 hostRouteSeams=&accessSeams;
 wild.movementFieldSystem=&field;r.frame.world.frame=100;r.frame.world.actorCount=1;r.frame.world.subject=H(0,2);r.frame.world.subjectRoleMask=2;
 memset(&accessEntryState,0,sizeof(accessEntryState));
 r.actors[0].count=r.actors[0].stateCapacity=1;r.actors[0].states=&accessEntryState;r.actors[0].catalogEntryIndexes[0]=noticeIndex;
 r.frame.world.actors[0]=(OverworldBehaviorConditionActorObservation){.actor=H(1,5),.x=11,.y=10,.valid=1};
 systemState.magic=OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC;systemState.version=OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;systemState.size=sizeof(systemState);systemState.frame=100;systemState.fieldEpoch=systemState.mapGeneration=3;
 for(unsigned i=0;i<2;i++){
  OverworldActorHandle h=H(i,i?5:2);r.actors[i].subject=h;r.actors[i].valid=1;
  wild.spawns[i].object=&objects[i];wild.spawns[i].active=1;wild.spawns[i].encounterGeneration=1;wild.spawns[i].personality=20+i;
  objects[i].xCurr=10+i;objects[i].yCurr=10;objects[i].flags=1;objects[i].posVec[1]=65536;
  systemState.slots[i].snapshot.handle=h;systemState.slots[i].snapshot.active=1;systemState.slots[i].snapshot.subjectIdentity=20+i;
 }
 targetSurface=missingTerrain=missingSupport=terrainReads=supportReads=relativeTargetSupport=targetNeedsFlag29=0;targetSupport=originSupport=65536;
}
static unsigned Access(u16 allowed){
 OverworldConditionNativeCall call={.runtime=&r,.state=&wild,.field=&field,.blob=blob,.blobSize=sizeof(*blob),.allowedTerrainMask=allowed,
  .version=OVERWORLD_CONDITION_NATIVE_CALL_VERSION,.size=sizeof(call),.slot=0,.operation=OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS,.targetAccessWorld=&world};
 unsigned status=OverworldConditionNative_Run(&call);
 assert(terrainReads<=2&&supportReads<=3);
 return status;
}
static BOOL Allowed(void){return !(r.frame.candidates[0].reserved[0]&OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE);}
static void WarmAccessRow(unsigned index){
 Reset();r.actors[0].catalogEntryIndexes[0]=index;
 r.frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;
}
static void WarmAccessControls(void){
 OverworldWildBehaviorConditionEntry cargoEntry=blob->conditionEntries[cargoAccessIndex];
 OverworldWildBehaviorConditionOptions cargoOptions=blob->conditionOptions[cargoAccessIndex];
 WarmAccessRow(noticeIndex);
 assert(Access(1)==0&&!Allowed()&&terrainReads==0&&supportReads==0);
 /* Each part of the reducer's Cargo-only row filter is required. */
 for(unsigned fault=0;fault<3;fault++){
  blob->conditionEntries[cargoAccessIndex]=cargoEntry;
  blob->conditionOptions[cargoAccessIndex]=cargoOptions;
  if(fault==0)blob->conditionEntries[cargoAccessIndex].kind=OW_WILD_BEHAVIOR_CONDITION_POKEMON_NOTICED;
  else if(fault==1)blob->conditionOptions[cargoAccessIndex].captureBinding=OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST+1;
  else blob->conditionOptions[cargoAccessIndex].mustBeReachableForPickup=0;
  WarmAccessRow(cargoAccessIndex);
  assert(Access(1)==0&&!Allowed()&&terrainReads==0&&supportReads==0);
 }
 blob->conditionEntries[cargoAccessIndex]=cargoEntry;
 blob->conditionOptions[cargoAccessIndex]=cargoOptions;
 WarmAccessRow(cargoAccessIndex);
 assert(Access(1)==0&&Allowed()&&terrainReads==2&&supportReads==IDENTICAL_SUPPORT_READS);
 /* Warm filtering cannot skip the later row-index or common input guards. */
 for(unsigned index=0;index<2;index++){
  WarmAccessRow(index?cargoAccessIndex:noticeIndex);
  r.actors[0].count=r.actors[0].stateCapacity=2;
  r.actors[0].catalogEntryIndexes[1]=blob->header.conditionEntryCount;
  assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION&&!Allowed());
  assert(terrainReads==0&&supportReads==0);
 }
 WarmAccessRow(noticeIndex);world.state=NULL;
 assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT&&!Allowed());
 WarmAccessRow(noticeIndex);r.actors[0].states=NULL;
 assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION&&!Allowed());
 WarmAccessRow(cargoAccessIndex);systemState.frame++;
 assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&!Allowed());
 WarmAccessRow(cargoAccessIndex);systemState.slots[1].snapshot.handle.generation++;
 assert(Access(1)==0&&!Allowed());
 /* Ordinary Actor Notice still performs the exact same physical reads. */
 Reset();assert(Access(1)==0&&Allowed()&&terrainReads==2&&supportReads==IDENTICAL_SUPPORT_READS);
 puts("T67 native Warm Cargo: non-Cargo0 reads; reachable Cargo and normal Notice2 terrain/exact identical support; malformed and stale controls GREEN");
}

static void IntermediateWalk(void){
 OverworldActorRuntimeSlot *actor=&systemState.slots[1];
 objects[1].xCurr=r.frame.world.actors[0].x=12;objects[1].posVec[1]=400000;
 actor->motion.phase=OVERWORLD_MOTION_PHASE_MOVING;actor->snapshot.reservationId=9;
 actor->motion.plan=(OverworldMotionPlan){.version=OVERWORLD_MOTION_MODEL_VERSION,
  .kind=OVERWORLD_MOTION_KIND_WALK,.fieldEpoch=3,.reservationId=9,
  .startX=11,.startY=10,.targetX=13,.targetY=10,.startBaseY=65536,.targetBaseY=131072};
 relativeTargetSupport=1;
}
static void SupportKeyControls(void){
 /* The original three calls become two only for the identical native key. */
 Reset();assert(Access(1)==0&&Allowed()&&terrainReads==2&&supportReads==IDENTICAL_SUPPORT_READS);
 /* Other flags cannot change the native height query; flags23/29 can. */
 Reset();objects[1].flags|=1u<<7;assert(Access(1)==0&&Allowed()&&supportReads==IDENTICAL_SUPPORT_READS);
 Reset();objects[0].flags|=1u<<23;
 assert(Access(1)==0&&Allowed()&&supportReads==3);
 Reset();objects[1].flags|=1u<<29;targetNeedsFlag29=1;
 assert(Access(1)==0&&!Allowed()&&supportReads==3);
 Reset();objects[0].flags|=1u<<29;objects[1].flags|=1u<<29;targetNeedsFlag29=1;
 assert(Access(1)==0&&Allowed()&&supportReads==IDENTICAL_SUPPORT_READS);
 /* Input A can produce support B at an intermediate Walk tile. Subject A
  * reuses that exact query; subject B must query again and obtain C. */
 Reset();IntermediateWalk();OverworldMotionState saved=systemState.slots[1].motion;
 assert(Access(1)==0&&Allowed()&&supportReads==IDENTICAL_SUPPORT_READS);
 assert(memcmp(&saved,&systemState.slots[1].motion,sizeof(saved))==0);
 Reset();IntermediateWalk();objects[0].posVec[1]=originSupport=98304;
 assert(Access(1)==0&&!Allowed()&&supportReads==3);
 /* Same input A but relative-height flag23 makes subject output A, not B. */
 Reset();IntermediateWalk();objects[0].flags|=1u<<23;
 assert(Access(1)==0&&!Allowed()&&supportReads==3);
 /* Surface permission remains required even when the physical key matches. */
 for(unsigned surface=1;surface<=3;surface++){
  u16 permission=surface==1?OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST:
      (surface==2?OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY:OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER);
  Reset();targetSurface=surface;assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST)==0&&!Allowed()&&supportReads==2);
  Reset();targetSurface=surface;assert(Access(permission)==0&&Allowed()&&supportReads==IDENTICAL_SUPPORT_READS);
 }
 /* Failed/deferred support, invalid tile and a stale full target never reuse. */
 Reset();missingSupport=1;assert(Access(1)==0&&!Allowed()&&supportReads==2);
 Reset();systemState.slots[1].snapshot.handle.generation++;assert(Access(1)==0&&!Allowed()&&supportReads==1);
 /* A new invocation still reads both current poses/terrain/support. */
 Reset();assert(Access(1)==0&&Allowed());terrainReads=supportReads=0;
 objects[1].posVec[1]=targetSupport=98304;
 assert(Access(1)==0&&Allowed()&&terrainReads==2&&supportReads==3);
 puts("immediate support key: identical3->2; original input anchor, flags23/29, Walk/Hop, surface, deferred and current identity controls GREEN");
}

static void SettledPose(unsigned index){
 OverworldActorRuntimeSlot *actor=&systemState.slots[index];
 actor->motion.phase=OVERWORLD_MOTION_PHASE_SETTLING;
 actor->motion.elapsed=4;actor->motion.commitPublished=1;actor->motion.settleRemaining=5;
 actor->motion.plan=(OverworldMotionPlan){.version=OVERWORLD_MOTION_MODEL_VERSION,.kind=OVERWORLD_MOTION_KIND_HOP,
  .fieldEpoch=3,.reservationId=9,.duration=4,.startX=objects[index].xCurr-1,.startY=10,
  .targetX=objects[index].xCurr,.targetY=10,.startBaseY=32768,.targetBaseY=65536};
 actor->snapshot.reservationId=0;
 actor->snapshot.motionPhase=OVERWORLD_MOTION_PHASE_SETTLING;
 actor->snapshot.motionKind=OVERWORLD_MOTION_KIND_HOP;
 actor->snapshot.motionElapsed=4;actor->snapshot.motionDuration=4;
 actor->snapshot.commitSequence=actor->motion.commitSequence=1;
 /* The support anchor is the committed target, not a Hop's render lift. */
 objects[index].posVec[1]=400000;
}
int main(void){
 blob=malloc(sizeof(*blob));assert(blob);memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
 cargoAccessIndex=blob->header.conditionEntryCount;
 for(unsigned i=0;i<blob->header.conditionEntryCount;i++){
  if(blob->conditionEntries[i].conditionId==12365)noticeIndex=i;
  if(blob->conditionEntries[i].kind==OW_WILD_BEHAVIOR_CONDITION_ACTOR_FACTS
      &&blob->conditionOptions[i].captureBinding==OVERWORLD_TARGET_BINDING_CARGO+1
      &&blob->conditionOptions[i].mustBeReachableForPickup
      &&OverworldBehaviorCondition_RoleApplies(blob->conditionOptions[i].subjectRoleMask,2))cargoAccessIndex=i;
 }
 assert(blob->conditionEntries[noticeIndex].conditionId==12365);
 assert(cargoAccessIndex<blob->header.conditionEntryCount);
 WarmAccessControls();
 SupportKeyControls();
 Reset();assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND)==0&&Allowed());
 for(unsigned privatePolicy=1;privatePolicy<=2;privatePolicy++){
  Reset();world.landingPolicy=privatePolicy;
  assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
  assert(terrainReads==0&&supportReads==0&&!Allowed());
 }
 Reset();assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST)==0&&Allowed());
 for(unsigned mask=0;mask<2;mask++){
  Reset();targetSurface=1;targetSupport=objects[1].posVec[1]=230912;
  assert(Access(mask?OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST:OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND)==0&&!Allowed());
 }
 Reset();targetSurface=1;targetSupport=objects[1].posVec[1]=230912;
 assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST)==0&&Allowed());
 Reset();targetSurface=1;targetSupport=230912;
 assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST)==0&&!Allowed());
 Reset();missingTerrain=1;assert(Access(1)==0&&!Allowed());
 Reset();missingSupport=1;assert(Access(1)==0&&!Allowed());
 /* Equal XY is no proof of equal elevation or subject-accessible support. */
 Reset();objects[1].xCurr=10;r.frame.world.actors[0].x=10;
 objects[0].flags|=1u<<23;objects[1].flags|=1u<<23;objects[1].posVec[1]=131072;
 assert(Access(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST)==0&&!Allowed());
 /* A current accepted Hop uses physical endpoint support, never its raised
  * render pose; current logical crossing selects the new endpoint support. */
 for(unsigned committed=0;committed<2;committed++){
  Reset();OverworldActorRuntimeSlot *actor=&systemState.slots[1];
  actor->motion.phase=OVERWORLD_MOTION_PHASE_MOVING;actor->snapshot.reservationId=9;
  actor->motion.plan=(OverworldMotionPlan){.version=OVERWORLD_MOTION_MODEL_VERSION,.kind=OVERWORLD_MOTION_KIND_HOP,.fieldEpoch=3,.reservationId=9,.startX=11,.startY=10,.targetX=12,.targetY=10,.startBaseY=65536,.targetBaseY=98304};
  objects[1].posVec[1]=400000;
  if(committed){objects[1].xCurr=r.frame.world.actors[0].x=12;targetSupport=98304;actor->motion.commitPublished=1;}
  OverworldMotionState saved=actor->motion;
  assert(Access(1)==0&&Allowed()&&supportReads==(committed?3u:IDENTICAL_SUPPORT_READS));assert(memcmp(&saved,&actor->motion,sizeof(saved))==0);
 }
 /* A landed ordinary move retains its native plan during pause, but the
  * public reservation has already been released. Both reacting subject and
  * candidate use the real committed target support; neither plan is changed. */
 for(unsigned index=0;index<2;index++){
  Reset();SettledPose(index);OverworldMotionState saved=systemState.slots[index].motion;
  assert(Access(1)==0&&Allowed());
  assert(memcmp(&saved,&systemState.slots[index].motion,sizeof(saved))==0);
  for(unsigned fault=0;fault<6;fault++){
   Reset();SettledPose(index);OverworldActorRuntimeSlot *actor=&systemState.slots[index];
   if(fault==0)actor->motion.plan.fieldEpoch++;
   else if(fault==1)actor->motion.commitPublished=0;
   else if(fault==2)actor->motion.plan.targetX++;
   else if(fault==3)actor->snapshot.reservationId=8;
   else if(fault==4)actor->motion.phase=OVERWORLD_MOTION_PHASE_MOVING;
   else actor->motion.plan.reservationId=0;
   assert(Access(1)==0&&!Allowed());
  }
 }
 Reset();systemState.slots[1].snapshot.handle.generation++;assert(Access(1)==0&&!Allowed());
 Reset();r.actors[1].subject.generation++;assert(Access(1)==0&&!Allowed());
 Reset();wild.spawns[1].encounterGeneration++;assert(Access(1)==0&&!Allowed());
 Reset();wild.spawns[1].personality++;assert(Access(1)==0&&!Allowed());
 Reset();objects[1].xCurr++;assert(Access(1)==0&&!Allowed());
 Reset();r.frame.world.actors[0].actor.reserved=1;assert(Access(1)==0&&!Allowed());
 Reset();objects[1].flags=0;assert(Access(1)==0&&!Allowed());
 Reset();systemState.frame++;assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&!Allowed());
 Reset();world.state=NULL;assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT&&!Allowed());
 Reset();hostRouteSeams=NULL;assert(Access(1)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT&&!Allowed());
 /* Shared Player-only role and disabled inactive rows do no native target
  * reads. Active rows still revalidate access even after authored chance0. */
 Reset();r.frame.world.subjectRoleMask=1;assert(Access(1)==0&&!Allowed()&&terrainReads==0&&supportReads==0);
 Reset();blob->conditionEntries[noticeIndex].chancePercent=0;assert(Access(1)==0&&!Allowed()&&terrainReads==0&&supportReads==0);
 Reset();accessEntryState.flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;assert(Access(1)==0&&Allowed());
 blob->conditionEntries[noticeIndex].chancePercent=100;
 puts("T44 production heap access: physical surface/support precedence, Interest-ground, same-XY elevation, loaded support, current full identities, accepted Hop and committed SETTLING support/no-plan-write GREEN");
 free(blob);return 0;
}
"""


NATIVE_TARGET_ACCESS_SELF_CONTROLS = r"""
static void SelfCandidateControls(void){
 for(unsigned warm=0;warm<2;warm++){
  Reset();if(warm){r.actors[0].catalogEntryIndexes[0]=cargoAccessIndex;r.frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;}
  /* Execute actual BuildFrame: its compact list contains the subject and target. */
  r.frame.valid=FALSE;
  assert(OverworldBehaviorConditionAdapter_BuildFrame(&wild,&field,&r,Context,Current));
  assert(r.frame.world.actorCount==2);
  assert(Native_HandleEquals(&r.frame.world.actors[0].actor,&r.frame.world.subject));
  assert(r.frame.world.actors[1].actor.slot==1);
  r.frame.world.subjectRoleMask=2;
  /* Keep target-first fixture index for existing Allowed() helper. */
  OverworldBehaviorConditionActorObservation tmp=r.frame.world.actors[0];
  r.frame.world.actors[0]=r.frame.world.actors[1];r.frame.world.actors[1]=tmp;
  assert(Access(1)==0&&Allowed());
  assert(terrainReads==2&&supportReads==IDENTICAL_SUPPORT_READS);
  assert(r.frame.candidates[1].reserved[0]&OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE);
  /* Full handle comparison cannot confuse slot reuse or another map/encounter. */
  for(unsigned member=0;member<5;member++){
   OverworldActorHandle changed=H(0,2);
   if(member==0)changed.slot=2;
   else if(member==1)changed.generation++;
   else if(member==2)changed.fieldEpoch++;
   else if(member==3)changed.mapGeneration++;
   else changed.encounterGeneration++;
   assert(!Native_HandleEquals(&r.frame.world.subject,&changed));
   Reset();if(warm){r.actors[0].catalogEntryIndexes[0]=cargoAccessIndex;r.frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;}
   r.frame.world.actors[0].actor=changed;
   assert(Access(1)==0&&!Allowed());
   assert(terrainReads==1&&supportReads==1);
  }
  /* Target-access mutates only access flags. Self damage/context remains readable. */
  Reset();if(warm){r.actors[0].catalogEntryIndexes[0]=cargoAccessIndex;r.frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;}r.actors[0].subjectDamagePending=1;
  r.frame.world.playerFacingAndOcclusion|=OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED;
  OverworldBehaviorConditionActorObservation before=r.frame.world.actors[0];
  assert(Access(1)==0&&Allowed());
  assert(r.actors[0].subjectDamagePending==1);
  assert(r.frame.world.playerFacingAndOcclusion&OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED);
  assert(memcmp(&before,&r.frame.world.actors[0],sizeof(before))==0);
  /* Different actor at the exact subject tile remains a real physical target. */
  Reset();if(warm){r.actors[0].catalogEntryIndexes[0]=cargoAccessIndex;r.frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;}objects[1].xCurr=10;r.frame.world.actors[0].x=10;
  assert(Access(1)==0&&Allowed()&&terrainReads==2&&supportReads==IDENTICAL_SUPPORT_READS);
 }
 puts("exact full-handle self excluded; normal and Cargo two terrain/exact identical support; different actor same XY remains current GREEN");
}
"""

class BehaviorConditionAdapterTests(unittest.TestCase):
    def test_forced_request_maps_current_subject_local_role(self):
        helper = _actual_function(
            (ROOT / "lib/overworld/overworld_player_damage_condition.c").read_text(),
            "OverworldBehaviorCondition_BuildRequest", "BOOL ",
        )
        wild = _actual_function(WILD_SOURCE.read_text(),
            "OverworldWildSpawns_ResolveBehaviorProfileForContext", "static const ")
        driver = r"""
#include <assert.h>
#include <string.h>
#include "host-adapter.h"
#include "overworld_application_bank.h"
static OverworldWildBehaviorDataBlob blob;
static u32 resolvedMask, resolvedConditional;
static unsigned resolves;
static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void){return &blob;}
static void OverworldWildSpawns_InitBehaviorResolveRequest(BehaviorResolveRequest *r){memset(r,0,sizeof(*r));}
static void OverworldWildSpawns_GetFallbackBehaviorResolution(BehaviorResolveResult *r,u8 c){(void)c;memset(r,0,sizeof(*r));}
static BehaviorResolveStatus Resolve(const void *b,u32 z,const BehaviorResolveRequest *r,BehaviorResolveResult *o,BehaviorResolutionTrace *t){
 (void)b;(void)z;(void)t;resolvedMask=r->forcedOverrideMask;resolvedConditional=r->activeConditionalMask;resolves++;o->fingerprint=1;return BEHAVIOR_RESOLVE_OK;}
static const struct {BehaviorResolveStatus (*resolve)(const void *,u32,const BehaviorResolveRequest *,BehaviorResolveResult *,BehaviorResolutionTrace *);} resolver={Resolve};
#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY (&resolver)
/* @HELPER@ */
/* @WILD@ */
int main(void) {
 static OverworldWildBehaviorConditionRuntime runtime;
 BehaviorResolveResult output;
 const unsigned row=OWBD_APPLICATION_BANK_DIRECTORY_COUNT-1;
 blob.header.overrideProfileCount=400;
 blob.applicationBankDirectory[row].first=0;
 blob.applicationBankDirectory[row].count=3;
 blob.applicationBankIndexes[0]=15;blob.applicationBankIndexes[1]=31;blob.applicationBankIndexes[2]=300;
 runtime.context.species=155;
 runtime.result.activeApplicationMask=4;runtime.result.winningConditionId=21;
 runtime.result.resolvedTargetSourceApplication=2;runtime.result.resolvedTargetConditionId=22;
 runtime.result.resolvedTarget.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
 const int globals[]={15,31,300,-1};const u32 masks[]={1,2,4,0};
 for(unsigned i=0;i<4;i++){
  assert(OverworldBehaviorCondition_BuildRequest(&runtime,globals[i],&blob));
  assert(runtime.request.forcedOverrideMask==masks[i]);
  assert(runtime.request.activeConditionalMask==4&&runtime.request.winningConditionId==21);
  assert(runtime.request.resolvedTargetConditionId==22&&runtime.request.targetSourceApplication==2);
  assert(runtime.request.resolvedTarget.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
  resolves=0;OverworldWildSpawns_ResolveBehaviorProfileForContext(&runtime.context,globals[i],&runtime.request,&output);
  assert(resolves==1&&resolvedMask==masks[i]&&resolvedConditional==4&&output.fingerprint==1);
 }
 /* A role absent from this species, the u16 NONE sentinel, and wider values
  * cannot reach Resolve with an unforced or unrelated local application. */
 const int missing[]={0,32,255,65535,65536};
 for(unsigned i=0;i<5;i++){
  BehaviorResolveRequest before=runtime.request;
  assert(!OverworldBehaviorCondition_BuildRequest(&runtime,missing[i],&blob));
  assert(memcmp(&before,&runtime.request,sizeof(before))==0);
  resolves=0;OverworldWildSpawns_ResolveBehaviorProfileForContext(&runtime.context,missing[i],&runtime.request,&output);
  assert(resolves==0&&output.fingerprint==0);
 }
 assert(!OverworldBehaviorCondition_BuildRequest(&runtime,15,NULL));
 blob.applicationBankDirectory[row].count=33;
 assert(!OverworldBehaviorCondition_BuildRequest(&runtime,15,&blob));
 resolves=0;OverworldWildSpawns_ResolveBehaviorProfileForContext(&runtime.context,15,NULL,&output);assert(!resolves&&!output.fingerprint);
 blob.applicationBankDirectory[row].count=3;blob.applicationBankIndexes[1]=15;
 assert(!OverworldBehaviorCondition_BuildRequest(&runtime,15,&blob));
 blob.applicationBankIndexes[1]=31;blob.applicationBankIndexes[2]=400;
 assert(!OverworldBehaviorCondition_BuildRequest(&runtime,15,&blob));
 /* Local bit31 is legal when the current authenticated bank has32 entries. */
 blob.applicationBankDirectory[row].count=32;for(unsigned i=0;i<32;i++)blob.applicationBankIndexes[i]=i;
 assert(OverworldBehaviorCondition_BuildRequest(&runtime,31,&blob));assert(runtime.request.forcedOverrideMask==0x80000000u);
 return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="condition-force-boundary-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES)
            unit, binary = output / "force.c", output / "force"
            unit.write_text(driver.replace("/* @HELPER@ */", helper).replace("/* @WILD@ */", wild))
            compiled = subprocess.run([
                *shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=undefined", "-fno-sanitize-recover=all",
                "-Wno-unknown-attributes",
                "-DOVERWORLD_BEHAVIOR_HOST", "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST",
                "-include", str(output / "host-types.h"),
                "-I", str(output), "-I", str(ROOT / "include"),
                str(unit), "-o", str(binary),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_warm_cargo_capture_defers_publication_until_idle(self):
        # Join the actual adapter, prepared reducer, binding reducer and
        # resolver. Only current frame/SDK reads are existing native seams.
        with tempfile.TemporaryDirectory(prefix="condition-warm-cargo-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "overworld_behavior_condition_runtime.h").write_text(
                (HEADER.parent / "overworld_behavior_condition_runtime.h").read_text())
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            fixture = target_publication_fixture(SOURCE.read_text())
            assert fixture.endswith(TARGET_PUBLICATION_DRIVER)
            unit, binary = output / "warm.c", output / "warm"
            unit.write_text(fixture[:-len(TARGET_PUBLICATION_DRIVER)] + WARM_CARGO_DRIVER)
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                str(output / "host-types.h"), "-I", str(output),
                "-I", str(ROOT / "include"), "-iquote",
                str(ROOT / "lib/overworld"), str(unit),
                *[str(SOURCE.parent / (name + ".c")
                      if name == "overworld_behavior_condition_runtime"
                      else ROOT / ("lib/overworld/" + name + ".c"))
                  for name in ("overworld_behavior_conditions", "overworld_vision",
                    "overworld_behavior_condition_runtime", "overworld_target_bindings",
                    "overworld_pickup_route", "overworld_behavior_resolver")],
                str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_all_conditions_apply_during_motion_and_defer_presentation(self):
        # Use the same joined production core, reducer, binding and resolver
        # fixture as Warm Cargo. The visibility seam counts selected traces.
        with tempfile.TemporaryDirectory(prefix="condition-moving-notice-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            fixture = target_publication_fixture(SOURCE.read_text())
            assert fixture.endswith(TARGET_PUBLICATION_DRIVER)
            fixture = fixture[:-len(TARGET_PUBLICATION_DRIVER)]
            unit, binary = output / "notice.c", output / "notice"
            unit.write_text(fixture + MOVING_NOTICE_DRIVER)
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                str(output / "host-types.h"), "-I", str(output),
                "-I", str(ROOT / "include"), "-iquote",
                str(ROOT / "lib/overworld"), str(unit),
                *[str(ROOT / ("lib/overworld/" + name + ".c"))
                  for name in ("overworld_behavior_conditions", "overworld_vision",
                    "overworld_behavior_condition_runtime", "overworld_target_bindings",
                    "overworld_pickup_route", "overworld_behavior_resolver")],
                str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_moving_evaluated_receipt_requires_full_success(self):
        # Run the actual adapter, Native Moving, prepared reducer and resolver.
        # Only native motion admission and failing SDK return boundaries vary.
        source = SOURCE.read_text()
        receipt = (
            "    if (forcedOverrideProfileIndex == OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE)\n"
            "        outcome->flags |= OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED;\n"
        )
        self.assertEqual(source.count(receipt), 1)
        native = ROOT / "lib/overworld/overworld_condition_moving_notice_native.c"
        native_source = native.read_text()
        admission = "    (void)runtime; (void)state; (void)slot;\n    return TRUE;"
        self.assertEqual(native_source.count(admission), 1)
        native_source = native_source.replace(admission,
            "    (void)runtime; (void)state; (void)slot;\n    return hostMovingAllowed;")
        driver = MOVING_NOTICE_DRIVER.split("int main(void){", 1)[0]
        driver = driver.replace(
            "expectedObserveMode=operation==OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY:0;",
            "expectedObserveMode=operation==OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY:"
            "operation==OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO?OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO:0;")
        driver += r"""
static void Setup(void){
 Reset();hostMovingAllowed=1;hostResolverFailure=hostTargetLost=0;
 out=(OverworldBehaviorConditionAdapterOutcome){.flags=255};
}
static unsigned Complete(void){return Eval(OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE);}
int main(void){
 blob=malloc(sizeof(*blob));assert(blob);
 assert(sizeof(out)==6&&offsetof(OverworldBehaviorConditionAdapterOutcome,targetDx)==2);
 assert(OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED==8);
 /* Full success is a receipt even when no condition triggers. */
 Setup();assert(Complete()==0&&resolves==0);
 assert(out.flags==OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED);
 /* A new profile must keep both publication and completion bits. */
 Setup();r.frame.world.playerY=10;assert(Complete()==0&&resolves==1&&r.targetValidMask==1);
 assert((out.flags&(OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED
  |OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED
  |OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED))==13);
 assert(states[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING);
 /* Later intent still delivers the pending notice, but is not Moving. */
 r.frame.world.frame++;assert(Eval(-1)==0);
 assert(!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED));
 assert(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED);
 Setup();assert(Eval(OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO)==0&&out.flags==0);
 /* An admitted OK skip cannot suppress fallback work. */
 Setup();hostMovingAllowed=0;assert(Complete()==0&&out.flags==0&&resolves==0);
 /* A malformed prepared row and a missing full subject fail before publication. */
 Setup();r.actors[0].count=5;assert(Complete()==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION&&out.flags==0);
 Setup();subjectCurrent=FALSE;assert(Complete()==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&out.flags==0);
 /* Resolver failure and late current-target loss cannot issue the receipt. */
 Setup();r.frame.world.playerY=10;hostResolverFailure=1;
 assert(Complete()==OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION&&resolves==1);
 assert(!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED));
 Setup();r.frame.world.playerY=10;hostTargetLost=1;
 assert(Complete()==OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET&&resolves==1&&clears==1);
 assert(!(out.flags&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED));
 puts("full Moving completion receipt: success/publication/skip/error/current-target/size controls GREEN");
 free(blob);return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="condition-moving-complete-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            copied_native = output / "native.c"
            copied_native.write_text(native_source)
            for fault in (None, "missing-receipt", "early-receipt"):
                with self.subTest(fault=fault):
                    candidate = source
                    if fault == "missing-receipt":
                        candidate = candidate.replace(receipt, "")
                    elif fault == "early-receipt":
                        candidate = candidate.replace(receipt, "").replace(
                            "    status=addon->conditionNative(&nativeCall);",
                            receipt + "    status=addon->conditionNative(&nativeCall);", 1)
                    fixture = target_publication_fixture(candidate)
                    self.assertTrue(fixture.endswith(TARGET_PUBLICATION_DRIVER))
                    fixture = fixture[:-len(TARGET_PUBLICATION_DRIVER)]
                    fixture = fixture.replace(
                        "static unsigned resolves,clears;",
                        "static unsigned resolves,clears;\n"
                        "static unsigned hostMovingAllowed=1,hostResolverFailure,hostTargetLost;")
                    fixture = fixture.replace("{resolves++;BehaviorResolveStatus status=",
                        "{resolves++;if(hostResolverFailure)return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;BehaviorResolveStatus status=")
                    fixture = fixture.replace(" if(b){\n", " if(b){\n  if(hostTargetLost)r->frame.world.playerValid=0;\n", 1)
                    fixture = fixture.replace(str(native), str(copied_native))
                    unit, binary = output / "complete.c", output / "complete"
                    unit.write_text(fixture + driver)
                    command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                        "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                        "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                        str(output / "host-types.h"), "-I", str(output),
                        "-I", str(ROOT / "include"), "-iquote", str(ROOT / "lib/overworld"), str(unit),
                        *[str(ROOT / ("lib/overworld/" + name + ".c"))
                          for name in ("overworld_behavior_conditions", "overworld_vision",
                            "overworld_behavior_condition_runtime", "overworld_target_bindings",
                            "overworld_pickup_route", "overworld_behavior_resolver")],
                        str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
                    compiled = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    completed = subprocess.run([str(binary)], capture_output=True, text=True)
                    if fault:
                        self.assertNotEqual(completed.returncode, 0)
                        self.assertIn("OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED", completed.stderr)
                    else:
                        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_inaccessible_actor_target_is_excluded_before_condition_capture(self):
        # Use the same joined production core, reducer, binding and resolver
        # fixture as Warm Cargo. The visibility seam counts selected traces.
        with tempfile.TemporaryDirectory(prefix="condition-target-access-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            fixture = target_publication_fixture(SOURCE.read_text())
            assert fixture.endswith(TARGET_PUBLICATION_DRIVER)
            fixture = fixture[:-len(TARGET_PUBLICATION_DRIVER)]
            unit, binary = output / "notice.c", output / "notice"
            unit.write_text(fixture + TARGET_ACCESS_DRIVER)
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                str(output / "host-types.h"), "-I", str(output),
                "-I", str(ROOT / "include"), "-iquote",
                str(ROOT / "lib/overworld"), str(unit),
                *[str(ROOT / ("lib/overworld/" + name + ".c"))
                  for name in ("overworld_behavior_conditions", "overworld_vision",
                    "overworld_behavior_condition_runtime", "overworld_target_bindings",
                    "overworld_pickup_route", "overworld_behavior_resolver")],
                str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_native_target_access_skips_only_current_full_handle_self(self):
        # The actual frame builder includes Self. Join it to Native_Run so
        # this check catches repeated Field terrain/support work at the caller.
        fixture = target_publication_fixture(SOURCE.read_text())
        old_frame = _actual_function(TARGET_PUBLICATION_PRELUDE,
            "OverworldBehaviorConditionAdapter_BuildFrame", "static BOOL ")
        sdk = r"""
static u8 OverworldBehaviorConditionAdapter_HandleEquals(const OverworldActorHandle*,const OverworldActorHandle*);
static OverworldActorResult HostFrameInspect(const OverworldActorQuery *q,OverworldActorSnapshot *s){assert(q->kind==OVERWORLD_ACTOR_INSPECT_SYSTEM);s->frame=100;return OVERWORLD_ACTOR_RESULT_OK;}
static const struct {OverworldActorResult (*inspect)(const OverworldActorQuery*,OverworldActorSnapshot*);} hostFrameEntry={HostFrameInspect};
#undef OVERWORLD_ACTOR_SYSTEM_ENTRY
#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&hostFrameEntry)
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
"""
        fixture = fixture.replace(old_frame, sdk + _actual_function(
            SOURCE.read_text(), "OverworldBehaviorConditionAdapter_BuildFrame", "BOOL "))
        assert fixture.endswith(TARGET_PUBLICATION_DRIVER)
        fixture = fixture[:-len(TARGET_PUBLICATION_DRIVER)]
        driver = NATIVE_TARGET_ACCESS_DRIVER.replace(
            'assert(terrainReads<=2&&supportReads<=3);',
            'assert(terrainReads<=3&&supportReads<=5);').replace('int main(void){',
            NATIVE_TARGET_ACCESS_SELF_CONTROLS + '\nint main(void){').replace(
                ' WarmAccessControls();', ' SelfCandidateControls();\n WarmAccessControls();')
        native = ROOT / "lib/overworld/overworld_condition_moving_notice_native.c"
        native_source = native.read_text()
        self_guard = "            || observation->actor.slot == frame->world.subject.slot\n"
        self.assertEqual(native_source.count(self_guard), 1)
        with tempfile.TemporaryDirectory(prefix="condition-target-self-access-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            for bad in (False, True):
                with self.subTest(missing_self_guard=bad):
                    copied = output / ("bad-native.c" if bad else "native.c")
                    copied.write_text(native_source.replace(self_guard, "") if bad else native_source)
                    unit, binary = output / "self.c", output / "self"
                    unit.write_text(fixture.replace(str(native), str(copied)) + driver)
                    command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                        "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                        "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                        str(output / "host-types.h"), "-I", str(output),
                        "-I", str(ROOT / "include"), "-iquote", str(ROOT / "lib/overworld"), str(unit),
                        *[str(ROOT / ("lib/overworld/" + name + ".c"))
                          for name in ("overworld_behavior_conditions", "overworld_vision",
                            "overworld_behavior_condition_runtime", "overworld_target_bindings",
                            "overworld_pickup_route", "overworld_behavior_resolver")],
                        str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
                    compiled = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    completed = subprocess.run([str(binary)], capture_output=True, text=True)
                    if bad:
                        self.assertNotEqual(completed.returncode, 0)
                        self.assertIn("terrainReads==2&&supportReads==IDENTICAL_SUPPORT_READS", completed.stderr)
                    else:
                        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_native_target_access_reuses_only_exact_immediate_support_key(self):
        fixture = target_publication_fixture(SOURCE.read_text())
        assert fixture.endswith(TARGET_PUBLICATION_DRIVER)
        fixture = fixture[:-len(TARGET_PUBLICATION_DRIVER)]
        native = ROOT / "lib/overworld/overworld_condition_moving_notice_native.c"
        native_source = native.read_text()
        fast_path = """        if (targetInput.baseY == origin.baseY
            && targetInput.flags == (subject->flags & OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK))
            subjectSupport = target.baseY;
        else if (seams->support(&world, &origin, target.x, target.y, &tile, &subjectSupport)
                != OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL) continue;
"""
        baseline = """        if (seams->support(&world, &origin, target.x, target.y, &tile, &subjectSupport)
                != OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL) continue;
"""
        self.assertEqual(native_source.count(fast_path), 1)
        mask = "OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK"
        variants = {
            "baseline": native_source.replace(fast_path, baseline),
            "reuse": native_source,
            "without_anchor": native_source.replace(
                "targetInput.baseY == origin.baseY\n            && ", ""),
            "without_flag23": native_source.replace(mask, "(" + mask + " & ~(1u << 23))"),
            "without_flag29": native_source.replace(mask, "(" + mask + " & ~(1u << 29))"),
            "output_instead_of_input": native_source.replace(
                "    pose->surfaceId = tile->surfaceId;",
                "    if (supportInput != NULL) supportInput->baseY = pose->baseY;\n"
                "    pose->surfaceId = tile->surfaceId;"),
        }
        with tempfile.TemporaryDirectory(prefix="condition-immediate-support-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            for name, source in variants.items():
                with self.subTest(query_key=name):
                    copied = output / (name + "-native.c")
                    copied.write_text(source)
                    unit, binary = output / "notice.c", output / "notice"
                    driver = "#define EXPECT_SUPPORT_REUSE " + ("0" if name == "baseline" else "1") + "\n"
                    unit.write_text(fixture.replace(str(native), str(copied)) + driver + NATIVE_TARGET_ACCESS_DRIVER)
                    command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                        "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                        "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                        str(output / "host-types.h"), "-I", str(output),
                        "-I", str(ROOT / "include"), "-iquote", str(ROOT / "lib/overworld"), str(unit),
                        *[str(ROOT / ("lib/overworld/" + part + ".c"))
                          for part in ("overworld_behavior_conditions", "overworld_vision",
                            "overworld_behavior_condition_runtime", "overworld_target_bindings",
                            "overworld_pickup_route", "overworld_behavior_resolver")],
                        str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
                    compiled = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    completed = subprocess.run([str(binary)], capture_output=True, text=True)
                    if name in ("baseline", "reuse"):
                        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    else:
                        self.assertNotEqual(completed.returncode, 0)
                        self.assertIn("SupportKeyControls", completed.stderr)

    def test_native_support_owner_keeps_declared_query_key(self):
        runtime = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
        helper = _actual_function(runtime.read_text(),
            "OverworldWildRuntime_ResolveBaseYAt", "static BOOL ")
        self.assertIn("objectFlags &= OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK;", helper)
        flags = (ROOT / "include/map_events_internal.h").read_text()
        for bit in (23, 29):
            self.assertIn("MAPOBJECTFLAG_UNK%d = (1 << %d)" % (bit, bit), flags)
        driver = r"""
#include <assert.h>
#include "overworld_pickup_route_wild.h"
#define MAPOBJECTFLAG_UNK23 (1u << 23)
#define MAPOBJECTFLAG_UNK29 (1u << 29)
#define OW_WILD_RUNTIME_FX32_ONE 4096
struct FieldSystem { unsigned unused; };
static FieldSystem field;
static unsigned reads,needs29,last29;
static BOOL NativeHeight(FieldSystem *f,VecFx32 *v,BOOL flag29){
 assert(f==&field&&v->x==((11*16+8)*4096)&&v->z==((10*16+8)*4096));
 reads++;last29=flag29;if(needs29&&!flag29)return FALSE;
 v->y+=32768;return TRUE;
}
#define OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT NativeHeight
/* @HELPER@ */
int main(void){
 assert(OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK==((1u<<23)|(1u<<29)));
 s32 height=-7;OverworldWildSurfaceHit hit={.height=4096,.surfaceId=7};
 for(unsigned bit=0;bit<32;bit++){
  if(bit==23||bit==29)continue;
  reads=last29=0;height=-7;
  assert(OverworldWildRuntime_ResolveBaseYAt(&field,NULL,65536,1u<<bit,11,10,&height));
  assert(height==98304&&reads==1&&!last29);
 }
 for(unsigned native=0;native<2;native++){
  hit.surfaceId=native?0xFFFE:0xFFFF;
  reads=last29=0;height=-7;needs29=0;
  assert(OverworldWildRuntime_ResolveBaseYAt(&field,&hit,65536,0,11,10,&height));
  assert(height==102400&&reads==1&&!last29);
  reads=0;height=-7;
  assert(OverworldWildRuntime_ResolveBaseYAt(&field,&hit,65536,MAPOBJECTFLAG_UNK23,11,10,&height));
  assert(height==65536&&reads==0);
 }
 needs29=1;reads=0;height=-7;
 assert(!OverworldWildRuntime_ResolveBaseYAt(&field,NULL,65536,0,11,10,&height));
 assert(height==-7&&reads==1&&!last29);
 reads=0;
 assert(OverworldWildRuntime_ResolveBaseYAt(&field,NULL,65536,MAPOBJECTFLAG_UNK29,11,10,&height));
 assert(height==98304&&reads==1&&last29);
 hit.surfaceId=7;reads=0;height=-7;
 assert(OverworldWildRuntime_ResolveBaseYAt(&field,&hit,65536,~0u,11,10,&height));
 assert(height==4096&&reads==0);
 height=-7;
 assert(!OverworldWildRuntime_ResolveBaseYAt(NULL,NULL,65536,0,11,10,&height));
 assert(height==-7&&reads==0);
 assert(!OverworldWildRuntime_ResolveBaseYAt(&field,NULL,65536,0,11,10,NULL));
 assert(reads==0);return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="condition-native-support-key-") as directory:
            output = Path(directory)
            (output / "host-types.h").write_text(HOST_TYPES)
            unit, binary = output / "support.c", output / "support"
            unit.write_text(driver.replace("/* @HELPER@ */", helper))
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-include", str(output / "host-types.h"),
                "-I", str(ROOT / "include"), str(unit), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_native_target_access_uses_physical_support_and_current_identity(self):
        # Use the same joined production core, reducer, binding and resolver
        # fixture as Warm Cargo. The visibility seam counts selected traces.
        with tempfile.TemporaryDirectory(prefix="condition-target-physical-access-") as directory:
            output = Path(directory)
            header = HEADER.read_text().split(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")[0]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            fixture = target_publication_fixture(SOURCE.read_text())
            assert fixture.endswith(TARGET_PUBLICATION_DRIVER)
            fixture = fixture[:-len(TARGET_PUBLICATION_DRIVER)]
            unit, binary = output / "notice.c", output / "notice"
            unit.write_text(fixture + NATIVE_TARGET_ACCESS_DRIVER)
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                str(output / "host-types.h"), "-I", str(output),
                "-I", str(ROOT / "include"), "-iquote",
                str(ROOT / "lib/overworld"), str(unit),
                *[str(ROOT / ("lib/overworld/" + name + ".c"))
                  for name in ("overworld_behavior_conditions", "overworld_vision",
                    "overworld_behavior_condition_runtime", "overworld_target_bindings",
                    "overworld_pickup_route", "overworld_behavior_resolver")],
                str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_same_application_target_changes_refresh_current_publication(self):
        # Join the actual adapter, prepared condition reducer, binding reducer,
        # resolver and current catalog. Only native frame/SDK reads are seams.
        with tempfile.TemporaryDirectory(prefix="condition-target-publication-") as directory:
            output = Path(directory)
            header = HEADER.read_text()
            # The pointer-bearing native entry is28B on ARM. Host pointers have
            # a different width; the existing ARM layout test owns that check.
            header = header[:header.index(
                "typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")]
            (output / "host-adapter.h").write_text(header + "\n#endif\n")
            (output / "host-types.h").write_text(HOST_TYPES +
                '\n#include <string.h>\n#ifdef __clang__\n'
                '#pragma clang diagnostic ignored "-Wunknown-pragmas"\n#endif\n')
            unit, binary = output / "target.c", output / "target"
            unit.write_text(target_publication_fixture(SOURCE.read_text()))
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-function", "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_MOTION_HOST", "-include",
                str(output / "host-types.h"), "-I", str(output),
                "-I", str(ROOT / "include"), "-iquote",
                str(ROOT / "lib/overworld"), str(unit),
                *[str(SOURCE.parent / (name + ".c")
                      if name == "overworld_behavior_condition_runtime"
                      else ROOT / ("lib/overworld/" + name + ".c")) for name in (
                    "overworld_behavior_conditions", "overworld_vision",
                    "overworld_behavior_condition_runtime", "overworld_target_bindings",
                    "overworld_pickup_route", "overworld_behavior_resolver")],
                str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_adapter_v12_outcome_exposes_independent_timed_endings(self):
        harness = r"""
#include "overworld_behavior_condition_adapter.h"
#include "overworld_condition_moving_notice_native.h"
#include "overworld_query_code_addon.h"

typedef char VersionMustBe12[
    OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION == 12 ? 1 : -1];
typedef char NativeCallMustBe56[sizeof(OverworldConditionNativeCall)==56?1:-1];
typedef char AddonVersionMustBe9[OVERWORLD_QUERY_CODE_ADDON_VERSION==9?1:-1];
typedef char NativeCallbackMustBe152[
    offsetof(OverworldQueryCodeAddonEntry,conditionNative)==152?1:-1];
typedef char EntryMustBe28[
    sizeof(OverworldBehaviorConditionAdapterEntry) == 28 ? 1 : -1];
typedef char OutcomeMustBe6[
    sizeof(OverworldBehaviorConditionAdapterOutcome) == 6 ? 1 : -1];
typedef char TargetDxOffsetMustBe2[
    offsetof(OverworldBehaviorConditionAdapterOutcome,
        targetDx) == 2 ? 1 : -1];
typedef char TimedWinnerMaskMustBeU32[
    sizeof(((OverworldWildBehaviorConditionRuntime *)0)
        ->timedWinningApplicationMasks[0]) == sizeof(u32) ? 1 : -1];
"""
        with tempfile.TemporaryDirectory(
            prefix="behavior-condition-adapter-"
        ) as directory:
            source = Path(directory) / "adapter_layout.c"
            source.write_text(harness)
            command = [
                "arm-none-eabi-gcc",
                "-std=c11",
                "-mthumb",
                "-mcpu=arm946e-s",
                "-Wall",
                "-Wextra",
                "-fsyntax-only",
                "-I",
                str(ROOT / "include"),
                str(source),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )

    def test_timed_winner_endings_are_tracked_per_application(self):
        source = SOURCE.read_text()
        evaluation = function(
            source,
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        self.assertNotIn("timedConditionActive", source)
        collect = _actual_function((ROOT / "lib/overworld/overworld_condition_moving_notice_native.c").read_text(), "OverworldBehaviorConditionAdapter_CollectWinningEntries")
        self.assertIn("addon->conditionNative(&nativeCall)", evaluation)
        self.assertIn("1u << localApplication", collect)
        self.assertIn("OverworldApplicationBank_Local", collect)
        self.assertIn(
            "runtime->timedWinningApplicationMasks[slot]", evaluation
        )
        self.assertIn("& ~timedWinningApplicationMask", evaluation)
        self.assertIn("endedTimedApplicationMask", evaluation)
        self.assertNotIn("outcome->endedTimedApplicationMask", evaluation)

    def test_retrigger_only_requests_presentation_when_resolution_changes(self):
        source = SOURCE.read_text()
        evaluation = function(
            source,
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        self.assertIn("runtime->result.triggeredApplicationMask", evaluation)
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
            evaluation,
        )

    def test_trace_is_subject_bound_and_contains_available_state(self):
        source = SOURCE.read_text()
        evaluation = function(
            source,
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        trace = function(
            WALK_SOURCE.read_text(),
            "OverworldBehaviorConditionTrace_Record(",
            "OverworldWalk_ProposeStep(",
        )
        self.assertIn("&prepared->subject", evaluation)
        self.assertNotIn("traceActor", evaluation)
        self.assertNotIn("&result->resolvedTarget.actor,", trace)
        collect = _actual_function((ROOT / "lib/overworld/overworld_condition_moving_notice_native.c").read_text(), "OverworldBehaviorConditionAdapter_CollectWinningEntries")
        self.assertIn("addon->conditionNative(&nativeCall)", evaluation)
        for required in (
            "OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED",
            "OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE",
            "entry->activationMode",
            "OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD(",
        ):
            self.assertIn(required, collect + evaluation)
        for required in (
            "entryState->activeUntil",
            "entryState->cooldownUntil",
            "resolvedTarget.actor.slot",
        ):
            self.assertIn(required, trace)

    def test_follower_slot_uses_authoritative_mounted_role(self):
        source = SOURCE.read_text()
        frame = function(
            source,
            "OverworldBehaviorConditionAdapter_BuildFrame(",
            "OverworldBehaviorConditionAdapter_ResolveTarget(",
        )
        self.assertIn("OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX", frame)
        self.assertIn("query.index = (u8)slot", frame)
        self.assertIn(
            "actorRole == OVERWORLD_ACTOR_ROLE_MOUNTED",
            frame,
        )
        service = SERVICE_SOURCE.read_text()
        self.assertIn("OverworldBehaviorConditionService_Get(void)", service)
        self.assertIn("OverworldFollowerSelector_IsDirectLoaded()", service)
        self.assertIn("OverworldBehaviorConditionAdapter_HandleEquals", frame)

    def test_cross_overlay_service_gate_preserves_thumb_state(self):
        source = SOURCE.read_text()
        linker = (
            ROOT / "src/overworld_actor_system_overlay/linker.ld"
        ).read_text()
        header = (
            ROOT / "include/overworld_behavior_condition_runtime.h"
        ).read_text()
        self.assertIn("OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE()", source)
        self.assertIn("OverworldBehaviorConditionServiceGetFunc", header)
        self.assertNotIn(
            "OverworldBehaviorConditionService_Get =",
            linker,
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD_ADDR | 1u",
            (ROOT / "include/overworld_behavior_condition_adapter.h").read_text(),
        )
        self.assertNotIn(
            "OverworldBehaviorConditionTrace_Record =",
            linker,
        )

    def test_service_owns_exact_per_actor_state_allocation(self):
        adapter = SOURCE.read_text()
        runtime = (
            ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"
        ).read_text()
        prepare = function(
            adapter,
            "OverworldBehaviorConditionAdapter_PrepareActor(",
            "OverworldBehaviorConditionAdapter_HandleEquals(",
        )
        self.assertNotIn("OverworldBehaviorConditionAdapter_Allocate", adapter)
        self.assertEqual(prepare.count("service->prepareActor("), 1)
        self.assertIn("sys_AllocMemory(\n            HEAPID_WORLD,", runtime)
        self.assertIn("prepared->count * sizeof(*prepared->states)", runtime)
        self.assertIn("OverworldBehaviorConditionAdapter_Free", adapter)

    def test_unchanged_application_mask_reuses_the_actor_profile(self):
        adapter = function(
            SOURCE.read_text(),
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        wild = function(
            WILD_SOURCE.read_text(),
            "OverworldWildSpawns_EvaluateConditionsForSlot(",
            "static BOOL OverworldWildSpawns_BehaviorSlotCacheMatches(",
        )
        self.assertIn("OverworldConditionPublication_ChangedMask(runtime, slot)", adapter)
        publication = _actual_function(
            (ROOT / "lib/overworld/overworld_condition_publication_native.c").read_text(),
            "OverworldConditionPublication_ChangedMask", "u32 ",
        )
        self.assertIn("runtime->result.activeApplicationMask ^ runtime->activeApplicationMasks[slot]", publication)
        self.assertIn("OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED", publication)
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
            adapter,
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
            wild,
        )
        self.assertIn(
            "outcome.flags\n"
            "            & (OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED\n"
            "                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED\n"
            "                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED\n"
            "                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED\n"
            "                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED))",
            wild,
        )

    def test_wild_runtime_owns_nested_condition_state_cleanup(self):
        source = WILD_SOURCE.read_text()
        clear_record = function(
            source,
            "OverworldWildSpawns_ClearConditionActorRecord(",
            "static void OverworldWildSpawns_ClearConditionSlot(",
        )
        cleanup = function(
            source,
            "OverworldWildSpawns_ClearConditionActorRecord(",
            "static BOOL OverworldWildSpawns_PrepareConditionsForSlot(",
        )
        self.assertIn("sys_FreeMemoryEz(prepared->states)", clear_record)
        self.assertIn("prepared->states = NULL", clear_record)
        self.assertIn("prepared->valid = FALSE", clear_record)
        self.assertIn(
            "conditions->activeApplicationMasks[slot] = 0", clear_record
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS", cleanup
        )
        self.assertNotIn("GetConditionAdapter", cleanup)


if __name__ == "__main__":
    unittest.main()
