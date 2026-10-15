"""Extracted production-C guards for ordinary outward/return admission."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools.overworld.test_picked_up_actor_control import extract_function

ROOT = Path(__file__).resolve().parents[2]


def typedef(source, name):
    start = source.index("typedef struct " + name + " {")
    end = source.index("} " + name + ";", start) + len("} " + name + ";")
    return source[start:end]


PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "overworld_motion_model.h"
typedef int BOOL;
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_SPAWN_ENTRY_NONE 0
#define OW_WILD_SPAWN_ENTRY_FLY_IN 3
#define OW_WILD_SURFACE_ID_NATIVE_GROUND 65535
#define OW_WILD_RUNTIME_MOTION_REQUEST_FORCED 0x80
#define OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING 2
#define OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING 4
#define OW_WILD_RUNTIME_ORDINARY_HOP_PENDING 1
#define OW_WILD_RUNTIME_ORDINARY_WALK_PENDING 3
#define OVERWORLD_ACTOR_SYSTEM_ABI_VERSION 2
#define OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX 2
#define OVERWORLD_ACTOR_RESULT_OK 0
#define OVERWORLD_ACTOR_MOTION_CALL_VERSION 5
#define OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST 0
#define OVERWORLD_ACTOR_ROLE_WILD 1
#define OVERWORLD_ACTOR_ROLE_FOLLOWER 2
#define OVERWORLD_ACTOR_ROLE_MOUNTED 3
#define OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(value) ((u16)(value))
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(value) ((u16)((value)>>16))
typedef struct FieldSystem {int value;} FieldSystem;
typedef struct LocalMapObject {int value;} LocalMapObject;
typedef struct OverworldActorWalkPolicyCall OverworldActorWalkPolicyCall;
typedef struct OverworldWildSurfaceHit {u16 surfaceId;} OverworldWildSurfaceHit;
'''

FIXTURE = r'''
typedef struct OverworldWildSpawn {LocalMapObject *object;u8 active;u16 encounterGeneration;u32 personality;} OverworldWildSpawn;
typedef struct OverworldWildOverlayRuntimeState {
    s16 movementCustomJumpStartX[10],movementCustomJumpStartY[10];
    s16 movementCustomJumpTargetX[10],movementCustomJumpTargetY[10];
    s32 movementCustomJumpStartBaseY[10],movementCustomJumpTargetBaseY[10];
    u16 movementMotionIdentities[10];
    struct {u8 targets[10];u16 carrierMask,targetMask,recoveringMask;} throwState;
    OverworldWildReturnMove returnMoves[10];
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    void *movementRuntimeState;
    FieldSystem *movementFieldSystem;
    u16 mapGeneration;
    OverworldWildSpawn spawns[10];
    u8 movementActorControlModes[10],movementSpawnRunActive[10],movementStagedHopPending[10];
    s16 movementStagedHopTargetX[10],movementStagedHopTargetY[10];
    u8 movementSpotStates[10],movementPendingDirections[10],movementPendingDistances[10];
} OverworldWildSpawnState;
typedef struct OverworldActorStateSnapshot {
    OverworldActorHandle handle;
    u32 subjectIdentity;
    u8 active,role,inputOwnership;
} OverworldActorStateSnapshot;
typedef struct OverworldActorSnapshot {u8 hasActor;OverworldActorStateSnapshot actor;u32 frame;} OverworldActorSnapshot;
typedef struct OverworldActorMotionRequestCall {
    u16 version,size;u8 operation,actorSlot,candidateCount,selectedIndex;
    s16 startX,startY;s32 startBaseY;
    OverworldMotionIntent *intent;OverworldMotionCandidate *candidates;OverworldMotionPlan *plan;
    u8 reserved;u16 targetSurfaceId,motionIdentity;OverworldMotionDecision decision;
} OverworldActorMotionRequestCall;
static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime;
static OverworldWildBehaviorProfileData lane;
static OverworldActorSnapshot snapshot;
static OverworldMotionPlan lastPlan;
static OverworldMotionDecision nextDecision;
static int inspectResult,requestResult,inspectCalls,requestCalls,pauseCalls;
static u16 nextIdentity;
static u32 context;
static FieldSystem field;
static LocalMapObject object;
static u32 OverworldWildRuntime_GetFieldContext(void){return context;}
static u8 OverworldWildSpawns_ResolveWalkPause(const OverworldWildBehaviorProfileData *input){
    ++pauseCalls;return input->walkPause+2;
}
static int Inspect(const OverworldActorQuery *query,OverworldActorSnapshot *output){
    ++inspectCalls;assert(query->version==2&&query->size==sizeof(*query));
    assert(query->kind==OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX&&query->index==1);
    assert(query->reserved==0);*output=snapshot;return inspectResult;
}
static int Request(OverworldActorMotionRequestCall *call){
    ++requestCalls;call->motionIdentity=0;
    if(requestResult)return requestResult;
    call->decision=nextDecision;
    if(nextDecision==OVERWORLD_MOTION_DECISION_ACCEPTED){
        assert(OverworldMotion_SelectPlan(call->intent,call->startX,call->startY,
            call->startBaseY,call->candidates,call->candidateCount,&lastPlan,
            &call->selectedIndex)==OVERWORLD_MOTION_DECISION_ACCEPTED);
        lastPlan.reservationId=++nextIdentity;lastPlan.behaviorFingerprint=0x51;
        if(call->plan)*call->plan=lastPlan;
        call->motionIdentity=lastPlan.reservationId;
    }
    return 0;
}
static struct {int (*inspect)(const OverworldActorQuery*,OverworldActorSnapshot*);} actorEntry={Inspect};
static struct {int (*request)(OverworldActorMotionRequestCall*);} motionEntry={Request};
#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&actorEntry)
#define OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY (&motionEntry)
'''

DRIVER = r'''
static void Setup(void){
    memset(&state,0,sizeof(state));memset(&runtime,0,sizeof(runtime));
    memset(&lane,0,sizeof(lane));memset(&snapshot,0,sizeof(snapshot));
    state.movementRuntimeState=&runtime;state.movementFieldSystem=&field;state.mapGeneration=4;
    state.spawns[1].active=1;state.spawns[1].object=&object;
    state.spawns[1].personality=99;state.spawns[1].encounterGeneration=5;
    runtime.movementCustomJumpStartX[1]=12;runtime.movementCustomJumpStartY[1]=20;
    runtime.movementCustomJumpTargetX[1]=13;runtime.movementCustomJumpTargetY[1]=20;
    runtime.movementCustomJumpTargetBaseY[1]=1024;runtime.returnMoves[1].originSurfaceId=77;
    state.movementPendingDirections[1]=3;state.movementPendingDistances[1]=1;
    lane.continueWhenArrived=2;lane.hopPause=7;lane.walkPause=9;lane.hopTime=4;
    lane.hopElevationArcScale=9;lane.collisionDamage=20;
    snapshot.hasActor=1;snapshot.actor.active=1;snapshot.actor.role=OVERWORLD_ACTOR_ROLE_WILD;
    snapshot.actor.subjectIdentity=99;
    snapshot.actor.handle=(OverworldActorHandle){1,2,3,4,5,0};context=(4u<<16)|3;
    nextDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;requestResult=inspectResult=0;
    nextIdentity=70;inspectCalls=requestCalls=pauseCalls=0;
}
static OverworldMotionDecision Start(u8 kind,const OverworldWildBehaviorProfileData *input){
    BOOL returning=runtime.returnMoves[1].phase==OW_WILD_RETURN_PENDING;
    return OverworldWildRuntime_RequestMotion(&state,1,input,kind,
        OVERWORLD_MOTION_VISIBILITY_VISIBLE,returning?99:16,3,returning?88:4,
        returning?77:0,returning?66:2,77);
}
static void Pending(void){
    OverworldWildReturnMove *record=&runtime.returnMoves[1];
    record->phase=OW_WILD_RETURN_PENDING;
    runtime.movementCustomJumpStartX[1]=record->plan.targetX;
    runtime.movementCustomJumpStartY[1]=record->plan.targetY;
    runtime.movementCustomJumpStartBaseY[1]=record->plan.targetBaseY;
    runtime.movementCustomJumpTargetX[1]=record->plan.startX;
    runtime.movementCustomJumpTargetY[1]=record->plan.startY;
    runtime.movementCustomJumpTargetBaseY[1]=record->plan.startBaseY;
    state.movementPendingDirections[1]=2;
}
int main(void){
    OverworldWildReturnMove saved;
    /* Both legs use the actual planner; only the return earns normal chain/pause. */
    for(u8 kind=OVERWORLD_MOTION_KIND_WALK;kind<=OVERWORLD_MOTION_KIND_HOP;++kind){
        Setup();assert(Start(kind,&lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
        saved=runtime.returnMoves[1];
        assert(saved.phase==OW_WILD_RETURN_OUTWARD&&saved.plan.reservationId==71);
        assert(saved.fieldSystem==&field&&saved.originSurfaceId==77&&saved.laneState==0);
        assert(memcmp(&saved.subject,&snapshot.actor.handle,sizeof(saved.subject))==0);
        assert(memcmp(&saved.plan,&lastPlan,sizeof(saved.plan))==0);
        assert(memcmp(&saved.lane,&lane,sizeof(lane))==0);
        assert(lastPlan.pauseFrames==0&&lastPlan.commitPolicy==OVERWORLD_MOTION_COMMIT_NO_CHAIN);
        assert(lastPlan.kind==kind&&lastPlan.startX==12&&lastPlan.targetX==13);
        assert(lastPlan.startBaseY==0&&lastPlan.targetBaseY==1024&&lastPlan.duration==4);
        assert(lastPlan.arcHeightQ4==16&&lastPlan.facing==3&&lastPlan.swayWidth==2);
        assert(saved.deferredPause==(kind==OVERWORLD_MOTION_KIND_WALK?11:7));
        assert(saved.retryFrames==0&&saved.returnMotionIdentity==0);
        Pending();lane.hopPause=99;lane.walkPause=99;
        assert(Start(kind,&saved.lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING);
        assert(runtime.returnMoves[1].returnMotionIdentity==72);
        assert(memcmp(&runtime.returnMoves[1].plan,&saved.plan,sizeof(saved.plan))==0);
        assert(lastPlan.pauseFrames==saved.deferredPause&&lastPlan.commitPolicy==OVERWORLD_MOTION_COMMIT_NORMAL);
        assert(lastPlan.duration==saved.plan.duration&&lastPlan.arcHeightQ4==saved.plan.arcHeightQ4);
        assert(lastPlan.spinSpeed==saved.plan.spinSpeed&&lastPlan.swayWidth==saved.plan.swayWidth);
        assert(lastPlan.targetX==12&&lastPlan.startX==13);
        assert(pauseCalls==(kind==OVERWORLD_MOTION_KIND_WALK?1:0));
        assert(inspectCalls==2&&requestCalls==2);
    }
    /* Ordinary full-leg staged markers are allowed; intermediate/special legs are not. */
    for(int mode=0;mode<7;++mode){
        Setup();state.movementStagedHopPending[1]=mode;
        state.movementStagedHopTargetX[1]=13;state.movementStagedHopTargetY[1]=20;
        assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
        assert((runtime.returnMoves[1].phase==OW_WILD_RETURN_OUTWARD)==(mode==0||mode==1));
    }
    Setup();state.movementStagedHopPending[1]=3;state.movementStagedHopTargetX[1]=13;
    state.movementStagedHopTargetY[1]=20;
    assert(Start(OVERWORLD_MOTION_KIND_WALK,&lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_OUTWARD);
    /* Automatic spawn Fly-in selection overrides the caller's ordinary kind.
     * Forced knockback remains Hop even while the entry mode is Fly-in. */
    const u8 automaticKinds[]={OVERWORLD_MOTION_KIND_WALK,OVERWORLD_MOTION_KIND_HOP,
        OVERWORLD_MOTION_KIND_REPOSITION};
    for(unsigned index=0;index<sizeof(automaticKinds);++index){
        Setup();state.movementSpawnRunActive[1]=OW_WILD_SPAWN_ENTRY_FLY_IN;
        assert(Start(automaticKinds[index],&lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
        assert(lastPlan.kind==OVERWORLD_MOTION_KIND_FLY_IN&&lastPlan.flags==0);
        assert(lastPlan.pauseFrames==0&&lastPlan.commitPolicy==OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY);
        assert(lastPlan.pathAdvancePolicy==OVERWORLD_MOTION_PATH_ADVANCE_NONE);
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE&&inspectCalls==0);
    }
    Setup();state.movementSpawnRunActive[1]=OW_WILD_SPAWN_ENTRY_FLY_IN;
    assert(Start(OVERWORLD_MOTION_KIND_HOP|OW_WILD_RUNTIME_MOTION_REQUEST_FORCED,0)
        ==OVERWORLD_MOTION_DECISION_ACCEPTED);
    assert(lastPlan.kind==OVERWORLD_MOTION_KIND_HOP&&lastPlan.flags==OVERWORLD_MOTION_FLAG_FORCED);
    assert(lastPlan.pauseFrames==0&&lastPlan.commitPolicy==OVERWORLD_MOTION_COMMIT_NO_CHAIN);
    assert(lastPlan.pathAdvancePolicy==OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE&&inspectCalls==0);
    for(int bad=0;bad<14;++bad){
        if(bad==8)continue; /* Incoming pursuit cannot change ordinary movement. */
        Setup();u8 kind=OVERWORLD_MOTION_KIND_HOP;
        switch(bad){
        case 0:lane.continueWhenArrived=0;break;case 1:lane.continueWhenArrived=1;break;
        case 2:kind|=OW_WILD_RUNTIME_MOTION_REQUEST_FORCED;break;
        case 3:kind=OVERWORLD_MOTION_KIND_REPOSITION;break;
        case 4:state.movementSpawnRunActive[1]=1;break;
        case 5:state.movementActorControlModes[1]=OW_WILD_ACTOR_CONTROL_HELD;break;
        case 6:runtime.throwState.targets[1]=3;break;
        case 7:runtime.throwState.carrierMask=2;break;case 8:runtime.throwState.targetMask=2;break;
        case 9:runtime.throwState.recoveringMask=2;break;
        case 10:runtime.movementCustomJumpTargetX[1]=12;break;
        case 11:state.movementStagedHopPending[1]=1;state.movementStagedHopTargetX[1]=30;break;
        case 12:lane.continueWhenArrived=4;break;
        case 13:snapshot.actor.role=OVERWORLD_ACTOR_ROLE_MOUNTED;break;
        }
        assert(Start(kind,&lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE);
        assert(lastPlan.pauseFrames==((kind&OW_WILD_RUNTIME_MOTION_REQUEST_FORCED)||kind==OVERWORLD_MOTION_KIND_REPOSITION?0:7));
    }
    Setup();runtime.throwState.targetMask=2;
    assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==OVERWORLD_MOTION_DECISION_ACCEPTED);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_OUTWARD&&lastPlan.pauseFrames==0);
    /* Rejected outward starts publish no record; rejected returns retain the same pending work. */
    Setup();nextDecision=OVERWORLD_MOTION_DECISION_RESERVED;
    assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==nextDecision);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE&&runtime.movementMotionIdentities[1]==0);
    Setup();assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==0);Pending();saved=runtime.returnMoves[1];
    nextDecision=OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==nextDecision);
    assert(memcmp(&saved,&runtime.returnMoves[1],sizeof(saved))==0);
    nextDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;
    assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==0);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING&&runtime.returnMoves[1].returnMotionIdentity==72);
    /* Full identity and exact inverse endpoint/support are checked before admission. */
    for(int bad=0;bad<24;++bad){
        Setup();assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==0);Pending();
        switch(bad){
        case 0:snapshot.actor.handle.generation++;break;case 1:snapshot.actor.handle.fieldEpoch++;break;
        case 2:snapshot.actor.handle.mapGeneration++;break;case 3:snapshot.actor.handle.encounterGeneration++;break;
        case 4:snapshot.actor.handle.reserved=1;break;case 5:snapshot.actor.subjectIdentity++;break;
        case 6:snapshot.hasActor=0;break;case 7:snapshot.actor.active=0;break;
        case 8:snapshot.actor.inputOwnership=1;break;case 9:runtime.returnMoves[1].fieldSystem=0;break;
        case 10:state.mapGeneration++;break;case 11:state.movementSpotStates[1]++;break;
        case 12:runtime.movementCustomJumpStartX[1]++;break;
        case 13:runtime.movementCustomJumpTargetY[1]++;break;
        case 14:runtime.movementCustomJumpStartBaseY[1]++;break;
        case 15:runtime.movementCustomJumpTargetBaseY[1]++;break;
        case 16:runtime.returnMoves[1].originSurfaceId++;break;
        case 17:inspectResult=2;break;
        case 18:state.movementFieldSystem=0;break;case 19:snapshot.actor.handle.slot=2;break;
        case 20:snapshot.actor.handle.generation=0;break;case 21:snapshot.actor.handle.fieldEpoch=0;break;
        case 22:snapshot.actor.handle.mapGeneration=0;break;case 23:snapshot.actor.handle.encounterGeneration=0;break;
        }
        assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==OVERWORLD_MOTION_DECISION_CONTEXT_LOST);
        assert(requestCalls==1&&runtime.returnMoves[1].phase==OW_WILD_RETURN_PENDING);
    }
    Setup();snapshot.actor.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
    assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==0);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_OUTWARD);
    /* An unaccepted native proposal cannot publish an outward record. */
    Setup();requestResult=2;
    assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==OVERWORLD_MOTION_DECISION_PROFILE);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE);
    /* A forced hit may replace pending return, and never arms another return. */
    Setup();assert(Start(OVERWORLD_MOTION_KIND_HOP,&lane)==0);Pending();
    assert(Start(OVERWORLD_MOTION_KIND_HOP|OW_WILD_RUNTIME_MOTION_REQUEST_FORCED,0)==0);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE&&lastPlan.flags==OVERWORLD_MOTION_FLAG_FORCED);
    assert(lastPlan.pauseFrames==0&&lastPlan.commitPolicy==OVERWORLD_MOTION_COMMIT_NO_CHAIN);
    return 0;
}
'''


ADAPTER_PRELUDE = PRELUDE.replace(
    "typedef struct LocalMapObject {int value;} LocalMapObject;",
    "typedef struct LocalMapObject {s16 xCurr,yCurr;u32 posVec[3];} LocalMapObject;") + r'''
#define TRUE 1
#define FALSE 0
#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState*)(state)->movementRuntimeState)
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_SPOT_STATE_TIRED 3
#define OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE 1
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL 0x03FF
#define OW_WILD_SURFACE_ID_NATIVE_GROUND 65535
#define OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_SPAWNER_STAGED_WALK_PENDING 3
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG 0x80
#define OW_WILD_WALK_DIRECTION_NONE 255
#define OW_WILD_CUSTOM_MOTION_NONE 0
#define OW_WILD_CUSTOM_MOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_SPAWNER_THROW_TARGET_NONE 0
#define OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS 15
#define OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX 3
typedef struct OverworldActorPolicyProfileBinding OverworldActorPolicyProfileBinding;
typedef struct OverworldActorPolicyProfileTransaction OverworldActorPolicyProfileTransaction;
typedef struct OverworldActorPolicyView {
    struct {u8 skidRemaining;} walkMomentum;
    u16 pendingLastPathAdvance;
    u8 pendingSkid,motionPhase;
} OverworldActorPolicyView;
'''

ADAPTER_FIXTURE = r'''
typedef struct OverworldWildSpawn {LocalMapObject *object;u8 active;u16 encounterGeneration;u32 personality;} OverworldWildSpawn;
typedef struct OverworldWildOverlayRuntimeState {
    struct {u8 targets[10];u16 carrierMask,targetMask,recoveringMask;} throwState;
    struct {u16 distanceDespawnPendingMask;} spawnPresentations;
    u8 movementCustomMotionModes[10];
    u16 movementMotionIdentities[10];
    OverworldWildReturnMove returnMoves[10];
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    void *movementRuntimeState;
    FieldSystem *movementFieldSystem;
    OverworldWildSpawn spawns[10];
    u8 movementActorControlModes[10],movementSpawnRunActive[10],movementSpotStates[10];
    u8 movementPreviousTileLocked[10],movementStagedHopPending[10],movementCooldowns[10];
    u8 movementLastDirections[10],movementLastDistances[10];
    s16 movementStagedHopOriginX[10],movementStagedHopOriginY[10];
    s16 movementStagedHopTargetX[10],movementStagedHopTargetY[10];
    u16 captureTargetMask;
} OverworldWildSpawnState;
typedef struct OverworldActorStateSnapshot {
    OverworldActorHandle handle;u32 subjectIdentity;u8 active,role,inputOwnership;
} OverworldActorStateSnapshot;
typedef struct OverworldActorSnapshot {u8 hasActor;OverworldActorStateSnapshot actor;u32 frame;} OverworldActorSnapshot;
static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime;
static OverworldActorSnapshot snapshot;
static OverworldActorPolicyView policy;
static FieldSystem field,otherField;
static LocalMapObject object;
static BOOL fieldCurrent,objectCurrent,mounted,surfaceFound,policyKnown,reduceOK,terminalOK;
static u16 surfaceId;
static s32 groundHeight;
static OverworldMotionDecision landingDecision,startDecision;
static int inspectCalls,landingCalls,startCalls,bufferCalls,inputCalls,resultCalls;
static int terminalCalls,clearCalls,executeCalls,resetCalls;
static int commitCalls,chainPauseCalls,queryCalls;
static BOOL queryAvailable;
static int currentSpawnCalls,combatReadyCalls,combatPrepareCalls;
static BOOL combatReady;
static u8 combatWork;
static OverworldMotionPlan combatPlan;
static u8 terminalPhase,inputDirection,inputFlags,resultValue,commitFlags;
static int InspectHandle(const OverworldActorQuery *query,OverworldActorSnapshot *out){
    ++inspectCalls;assert(query->kind==OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE);
    assert(query->version==2&&query->size==sizeof(*query));
    /* The real HANDLE API rejects any stale complete handle. */
    if(memcmp(&query->actor,&snapshot.actor.handle,sizeof(query->actor)))return 2;
    *out=snapshot;return 0;
}
static struct {int (*inspect)(const OverworldActorQuery*,OverworldActorSnapshot*);} actorEntry={InspectHandle};
#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&actorEntry)
static BOOL OverworldWildSpawns_IsPresentationFieldContextCurrent(OverworldWildSpawnState *s,FieldSystem *f){(void)s;(void)f;return fieldCurrent;}
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f,const OverworldWildSpawn *s){
    assert(f==&field&&s==&state.spawns[1]);++currentSpawnCalls;return objectCurrent;
}
static BOOL OverworldCombat_IsReady(void){++combatReadyCalls;return combatReady;}
static u8 PrepareCombat(const OverworldWildSpawnState *s,u8 slot,OverworldMotionPlan *plan){
    assert(s==&state&&slot==1&&plan&&currentSpawnCalls==1);
    assert(runtime.returnMoves[slot].phase!=OW_WILD_RETURN_NONE);
    ++combatPrepareCalls;*plan=combatPlan;return combatWork;
}
static struct {u8 (*prepare)(const OverworldWildSpawnState*,u8,OverworldMotionPlan*);}
    combatEntry={PrepareCombat};
#define OVERWORLD_COMBAT_ENTRY (&combatEntry)
static BOOL OverworldWildSpawns_MountIsActive(void){return mounted;}
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *out){
    assert(f==&field&&x==12&&y==20);out->surfaceId=surfaceId;return surfaceFound;
}
static s32 OverworldWildSpawns_GetObjectGroundBaseYAt(FieldSystem *f,LocalMapObject *o,int x,int y){
    assert(f==&field&&o==&object&&x==12&&y==20);return groundHeight;
}
static OverworldMotionDecision OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
    OverworldWildSpawnState *s,int slot,FieldSystem *f,u16 allowed,int x,int y,int tx,int ty){
    ++landingCalls;assert(s==&state&&slot==1&&f==&field&&x==12&&y==20&&tx==x&&ty==y);
    assert(allowed==(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL|
        (runtime.returnMoves[1].plan.kind==OVERWORLD_MOTION_KIND_WALK?0x8000:0)));
    return landingDecision;
}
static u8 OverworldWalk_DirectionFromDelta(int dx,int dy){assert(dx==-1&&dy==0);return 2;}
static void OverworldWildSpawns_InitPolicyCall(OverworldActorWalkPolicyCall *call,int slot,u8 op){
    memset(call,0,sizeof(*call));call->actorSlot=slot;call->operation=op;
}
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call){
    if(call->operation==OVERWORLD_ACTOR_WALK_POLICY_RESET)++resetCalls;
    else if(call->operation==OVERWORLD_ACTOR_WALK_POLICY_BUFFER_DIRECTION){
        ++bufferCalls;assert(call->direction==OW_WILD_WALK_DIRECTION_NONE);
    }else if(call->operation==OVERWORLD_ACTOR_WALK_POLICY_INPUT){
        ++inputCalls;assert(bufferCalls==inputCalls);assert(call->direction==2);
        assert((call->lane->walkOptions&OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION)==0);
        assert(call->flags==(OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED|
            OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID));
        inputFlags=call->flags;call->decision=OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP;
        call->stepDirection=inputDirection;call->travelTime=3;
    }else if(call->operation==OVERWORLD_ACTOR_WALK_POLICY_START_RESULT){
        ++resultCalls;resultValue=call->startResult;
    }else{
        assert(call->operation==OVERWORLD_ACTOR_WALK_POLICY_COMMIT);
        ++commitCalls;commitFlags=call->flags;
    }
    return reduceOK;
}
static OverworldMotionDecision OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
    OverworldWildSpawnState *s,FieldSystem *f,int slot,LocalMapObject *o,u8 direction,
    u8 distance,int x,int y,const OverworldWildBehaviorProfile *p,BOOL walk,u8 time){
    ++startCalls;assert(s==&state&&f==&field&&slot==1&&o==&object);
    assert(direction==2&&distance==1&&x==12&&y==20);
    assert(state.movementPreviousTileLocked[slot]==0&&state.movementStagedHopPending[slot]);
    assert(p->owner.hopTime==runtime.returnMoves[slot].lane.hopTime);
    if(walk){assert(walk==OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG&&time==3);}
    else assert(time==0);
    if(startDecision==OVERWORLD_MOTION_DECISION_ACCEPTED){
        runtime.returnMoves[slot].phase=OW_WILD_RETURN_RETURNING;
        runtime.returnMoves[slot].returnMotionIdentity=72;
    }
    return startDecision;
}
static void OverworldWildSpawns_ClearStagedHopTargetLocal(OverworldWildSpawnState *s,int slot){
    s->movementStagedHopPending[slot]=0;
}
static BOOL OverworldActorPolicy_Inspect(u8 slot,OverworldActorPolicyView *out){assert(slot==1);*out=policy;return policyKnown;}
static BOOL TerminalWalk(OverworldActorWalkPolicyCall *call,u8 acks,u16 path,u16 identity){
    ++terminalCalls;assert(acks==15&&path==7&&identity==71);
    assert(call->operation==OVERWORLD_ACTOR_WALK_POLICY_COMMIT);
    commitFlags=call->flags;call->reserved[3]=terminalPhase;return terminalOK;
}
static struct {BOOL (*terminalWalk)(OverworldActorWalkPolicyCall*,u8,u16,u16);} policyEntry={TerminalWalk};
static struct {typeof(policyEntry) *policy;} movementEntry={&policyEntry};
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&movementEntry)
static void OverworldWildSpawns_ClearCustomJumpLocal(OverworldWildSpawnState *s,int slot){
    ++clearCalls;assert(terminalCalls);OW_WILD_RUNTIME(s)->movementCustomMotionModes[slot]=0;
}
static BOOL OverworldWildSpawns_ExecuteWalkPolicy(OverworldWildDirectionStepContext *context,OverworldActorWalkPolicyCall *call){
    assert(context->state==&state&&context->fieldSystem==&field&&context->object==&object);
    assert(context->slot==1&&context->profile&&context->primitives);
    const OverworldWildBehaviorProfileData *lane=state.movementSpotStates[1]==OW_WILD_SPOT_STATE_TIRED
        ?&context->profile->tired:&context->profile->owner;
    assert(context->allowedTile==lane->chillAllowedTerrainMask&&call->lane==lane);
    assert(call->operation==OVERWORLD_ACTOR_WALK_POLICY_COMMIT);++executeCalls;return TRUE;
}
static void OverworldWildSpawns_CommitDeferredChainMovementPause(OverworldWildSpawnState *s,int slot,
    OverworldWildBehaviorProfile *p){
    assert(s==&state&&slot==1&&p);++chainPauseCalls;
}
'''

ADAPTER_DRIVER = r'''
static void SetupAdapter(u8 kind){
    memset(&state,0,sizeof(state));memset(&runtime,0,sizeof(runtime));
    memset(&snapshot,0,sizeof(snapshot));memset(&policy,0,sizeof(policy));
    memset(&object,0,sizeof(object));
    state.movementRuntimeState=&runtime;state.movementFieldSystem=&field;
    state.spawns[1].active=1;state.spawns[1].object=&object;state.spawns[1].personality=99;
    runtime.returnMoves[1].phase=OW_WILD_RETURN_PENDING;
    runtime.returnMoves[1].fieldSystem=&field;
    runtime.returnMoves[1].subject=(OverworldActorHandle){1,2,3,4,5,0};
    runtime.returnMoves[1].plan=(OverworldMotionPlan){.kind=kind,.startX=12,.startY=20,
        .targetX=13,.targetY=20,.startBaseY=0,.targetBaseY=1024,.distance=1,.reservationId=71};
    runtime.returnMoves[1].originSurfaceId=77;runtime.returnMoves[1].deferredPause=7;
    runtime.returnMoves[1].lane.hopTime=4;
    runtime.returnMoves[1].lane.walkOptions=OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
    object.xCurr=13;object.yCurr=20;object.posVec[1]=1024;
    state.movementPreviousTileLocked[1]=1;
    snapshot.actor.handle=runtime.returnMoves[1].subject;snapshot.hasActor=1;
    snapshot.actor.active=1;snapshot.actor.subjectIdentity=99;snapshot.actor.role=1;
    snapshot.frame=396;
    fieldCurrent=objectCurrent=surfaceFound=policyKnown=reduceOK=terminalOK=TRUE;
    mounted=FALSE;surfaceId=77;groundHeight=0;
    landingDecision=startDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;
    inspectCalls=landingCalls=startCalls=bufferCalls=inputCalls=resultCalls=0;
    terminalCalls=clearCalls=executeCalls=resetCalls=0;inputDirection=2;
    commitCalls=chainPauseCalls=queryCalls=0;queryAvailable=TRUE;
    currentSpawnCalls=combatReadyCalls=combatPrepareCalls=0;combatReady=TRUE;
    combatWork=OVERWORLD_COMBAT_NONE;combatPlan=(OverworldMotionPlan){0};
    terminalPhase=OVERWORLD_MOTION_PHASE_IDLE;
    policy.pendingLastPathAdvance=7;runtime.movementMotionIdentities[1]=71;
}
int main(void){
    /* Borrowed Combat admission keeps Ready/current-object checks before
     * prepare. No work preserves the exact current return record. */
    for(int gate=0;gate<3;++gate){
        SetupAdapter(OVERWORLD_MOTION_KIND_HOP);
        if(gate==0)combatReady=FALSE;if(gate==1)objectCurrent=FALSE;
        OverworldReturnMoveWildContext ctx={&state,&field,&adapterOps,1};
        OverworldWildReturnMove saved=runtime.returnMoves[1];
        OverworldMotionPlan plan={.version=99};
        assert(OverworldReturnMoveWild_CombatWork(&ctx,&plan)==OVERWORLD_COMBAT_NONE);
        assert(memcmp(&saved,&runtime.returnMoves[1],sizeof(saved))==0);
        assert(combatReadyCalls==1&&currentSpawnCalls==(gate!=0)&&combatPrepareCalls==(gate==2));
        assert(plan.version==(gate==2?0:99));
    }
    /* Every nonzero work cancels before caller-specific plan validation.
     * An invalid/zero plan still cancels, and other actors keep their records. */
    for(u8 phase=OW_WILD_RETURN_OUTWARD;phase<=OW_WILD_RETURN_RETURNING;++phase)
        for(u8 work=OVERWORLD_COMBAT_KNOCKBACK;work<=OVERWORLD_COMBAT_CRASH_PLAYING;++work)
            for(int invalid=0;invalid<2;++invalid){
        SetupAdapter(OVERWORLD_MOTION_KIND_HOP);runtime.returnMoves[1].phase=phase;
        runtime.returnMoves[2]=runtime.returnMoves[1];combatWork=work;
        OverworldWildReturnMove saved=runtime.returnMoves[1],other=runtime.returnMoves[2];
        if(!invalid)combatPlan=(OverworldMotionPlan){.version=OVERWORLD_MOTION_MODEL_VERSION,
            .kind=OVERWORLD_MOTION_KIND_HOP,.duration=8};
        OverworldReturnMoveWildContext ctx={&state,&field,&adapterOps,1};
        OverworldMotionPlan plan={.version=99};
        assert(OverworldReturnMoveWild_CombatWork(&ctx,&plan)==work);
        assert(combatReadyCalls==1&&currentSpawnCalls==1&&combatPrepareCalls==1);
        saved.phase=OW_WILD_RETURN_NONE;
        assert(memcmp(&saved,&runtime.returnMoves[1],sizeof(saved))==0);
        assert(memcmp(&other,&runtime.returnMoves[2],sizeof(other))==0);
        assert(memcmp(&plan,&combatPlan,sizeof(plan))==0);
    }
    /* Exact handle/control/context gates reject before destination or motion work. */
    for(int bad=0;bad<20;++bad){
        if(bad==9)continue; /* A pursuit claim does not cancel a pending return. */
        SetupAdapter(OVERWORLD_MOTION_KIND_HOP);
        switch(bad){
        case 0:runtime.returnMoves[1].phase=0;break;
        case 1:runtime.returnMoves[1].fieldSystem=&otherField;break;
        case 2:state.movementSpotStates[1]=1;break;case 3:fieldCurrent=FALSE;break;
        case 4:objectCurrent=FALSE;break;case 5:state.movementActorControlModes[1]=1;break;
        case 6:state.movementSpawnRunActive[1]=1;break;case 7:state.captureTargetMask=2;break;
        case 8:runtime.throwState.carrierMask=2;break;case 9:runtime.throwState.targetMask=2;break;
        case 10:runtime.throwState.recoveringMask=2;break;
        case 11:runtime.spawnPresentations.distanceDespawnPendingMask=2;break;
        case 12:runtime.throwState.targets[1]=3;break;
        case 13:snapshot.actor.handle.generation++;break;case 14:snapshot.actor.handle.fieldEpoch++;break;
        case 15:snapshot.actor.handle.mapGeneration++;break;
        case 16:snapshot.actor.handle.encounterGeneration++;break;
        case 17:snapshot.actor.subjectIdentity++;break;case 18:snapshot.actor.inputOwnership=1;break;
        case 19:snapshot.actor.role=3;break;
        }
        assert(!OverworldWildSpawns_IsReturnMoveCurrent(&state,1));
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==0&&landingCalls==0&&startCalls==0);
        if(bad!=0)assert(state.movementCooldowns[1]==7);
    }
    /* Unrelated held/recovery bits do not cancel the current autonomous pair. */
    SetupAdapter(OVERWORLD_MOTION_KIND_HOP);runtime.throwState.targetMask=2;
    assert(OverworldWildSpawns_IsReturnMoveCurrent(&state,1));
    OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING&&startCalls==1);
    SetupAdapter(OVERWORLD_MOTION_KIND_HOP);runtime.throwState.targetMask=4;
    runtime.throwState.recoveringMask=4;assert(OverworldWildSpawns_IsReturnMoveCurrent(&state,1));
    for(int bad=0;bad<6;++bad){
        SetupAdapter(OVERWORLD_MOTION_KIND_HOP);
        switch(bad){case 0:object.xCurr++;break;case 1:object.yCurr++;break;
        case 2:object.posVec[1]++;break;case 3:surfaceId++;break;
        case 4:surfaceFound=FALSE;break;case 5:groundHeight++;break;}
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==0&&landingCalls==0&&startCalls==0);
    }
    for(u8 kind=OVERWORLD_MOTION_KIND_WALK;kind<=OVERWORLD_MOTION_KIND_HOP;++kind){
        SetupAdapter(kind);OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING&&startCalls==1);
        assert(runtime.returnMoves[1].returnMotionIdentity==72&&state.movementCooldowns[1]==0);
        assert(resetCalls==0&&executeCalls==0);
        if(kind==OVERWORLD_MOTION_KIND_WALK)
            assert(inputCalls==1&&resultCalls==1&&resultValue==OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED);
        /* Both landing and actual admission preserve enum-valued busy decisions. */
        for(int gate=0;gate<2;++gate)for(int busy=0;busy<3;++busy){
            SetupAdapter(kind);
            OverworldMotionDecision d=busy==0?OVERWORLD_MOTION_DECISION_RESERVED:
                busy==1?OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY:OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
            if(gate)startDecision=d;else landingDecision=d;
            OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
            assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_PENDING&&runtime.returnMoves[1].retryFrames==1);
            assert(state.movementCooldowns[1]==0&&state.movementStagedHopPending[1]==0);
            snapshot.frame++;
            OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
            assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_PENDING&&runtime.returnMoves[1].retryFrames==2);
            landingDecision=startDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;
            snapshot.frame++;
            OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
            assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING);
            SetupAdapter(kind);startDecision=d;
            for(int retry=0;retry<3;++retry){
                snapshot.frame=396+retry;
                OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
            }
            assert(runtime.returnMoves[1].phase==0&&state.movementCooldowns[1]==7&&resetCalls==0);
        }
        SetupAdapter(kind);landingDecision=OVERWORLD_MOTION_DECISION_BLOCKED;
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==0&&startCalls==0&&state.movementCooldowns[1]==7);
        SetupAdapter(kind);startDecision=OVERWORLD_MOTION_DECISION_BLOCKED;
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==0&&state.movementStagedHopPending[1]==0);
    }
    /* Native RED: three same-frame RESERVED calls must spend one retry and
     * one attempt. A free endpoint on the next frame may start the return. */
    for(u8 kind=OVERWORLD_MOTION_KIND_WALK;kind<=OVERWORLD_MOTION_KIND_HOP;++kind)
        for(int gate=0;gate<2;++gate){
        SetupAdapter(kind);
        if(gate)startDecision=OVERWORLD_MOTION_DECISION_RESERVED;
        else landingDecision=OVERWORLD_MOTION_DECISION_RESERVED;
        for(int sameFrame=0;sameFrame<3;++sameFrame)
            OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(snapshot.frame==396&&runtime.returnMoves[1].phase==OW_WILD_RETURN_PENDING);
        assert(runtime.returnMoves[1].retryFrames==1&&landingCalls==1&&startCalls==gate);
        assert(state.movementCooldowns[1]==0&&resetCalls==0&&executeCalls==0);
        snapshot.frame=397;landingDecision=startDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING);
        assert(runtime.returnMoves[1].returnMotionIdentity==72&&landingCalls==2&&startCalls==gate+1);
        /* Two later distinct busy frames end the bounded retry window. */
        SetupAdapter(kind);
        if(gate)startDecision=OVERWORLD_MOTION_DECISION_RESERVED;
        else landingDecision=OVERWORLD_MOTION_DECISION_RESERVED;
        for(int frameOffset=0;frameOffset<3;++frameOffset){
            snapshot.frame=396+frameOffset;
            for(int sameFrame=0;sameFrame<3;++sameFrame)
                OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
            if(frameOffset<2){
                assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_PENDING);
                assert(runtime.returnMoves[1].retryFrames==frameOffset+1);
            }
        }
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE&&state.movementCooldowns[1]==7);
        assert(landingCalls==3&&startCalls==3*gate&&resetCalls==0&&executeCalls==0);
        /* Stale ownership cancels even during a duplicate-frame call. */
        SetupAdapter(kind);landingDecision=OVERWORLD_MOTION_DECISION_RESERVED;
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        snapshot.actor.handle.generation++;
        OverworldWildSpawns_TryStartReturnMove(&state,&field,1);
        assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_NONE&&landingCalls==1&&startCalls==0);
        assert(state.movementCooldowns[1]==7);
    }
    for(int returning=0;returning<2;++returning)for(int bad=0;bad<6;++bad){
        SetupAdapter(OVERWORLD_MOTION_KIND_HOP);
        OverworldReturnMoveWildContext ctx={&state,&field,&adapterOps,1};
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        runtime.returnMoves[1].phase=returning?OW_WILD_RETURN_RETURNING:OW_WILD_RETURN_OUTWARD;
        runtime.returnMoves[1].returnMotionIdentity=72;
        if(returning){runtime.movementMotionIdentities[1]=72;object.xCurr=12;object.yCurr=20;}
        u8 flags=OVERWORLD_RETURN_MOVE_BEFORE_WALK;
        if(bad==1)runtime.movementMotionIdentities[1]++;
        if(bad==2)object.xCurr++;if(bad==3)object.yCurr++;
        if(bad==4)flags|=OVERWORLD_RETURN_MOVE_COMBAT_OWNED;
        if(bad==5)flags|=OVERWORLD_RETURN_MOVE_DESPAWN;
        assert(!OverworldReturnMoveWild_Finish(&ctx,&p,&primitives,flags));
        if(bad){assert(runtime.returnMoves[1].phase==0);continue;}
        assert(memcmp(&p.owner,&runtime.returnMoves[1].lane,sizeof(p.owner))==0);
        assert(memcmp(&p.tired,&p.owner,sizeof(p.owner))==0);
        assert(primitives.chillLocomotion==2&&primitives.tiredLocomotion==2);
        assert(OverworldReturnMoveWild_Finish(&ctx,&p,&primitives,OVERWORLD_RETURN_MOVE_AFTER_WALK)==!returning);
        assert(runtime.returnMoves[1].phase==(returning?OW_WILD_RETURN_NONE:OW_WILD_RETURN_PENDING));
    }
    /* A shared Walk must close its exact terminal transaction before local clear.
     * Outward never advances chain; return does. Neither starts a follow-on skid. */
    for(int returning=0;returning<2;++returning)for(int pending=0;pending<3;++pending){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);
        runtime.returnMoves[1].phase=returning?OW_WILD_RETURN_RETURNING:OW_WILD_RETURN_OUTWARD;
        runtime.movementCustomMotionModes[1]=OW_WILD_CUSTOM_MOTION_WALK;
        terminalOK=pending!=1;terminalPhase=pending==2?OVERWORLD_MOTION_PHASE_COMMIT_PENDING:OVERWORLD_MOTION_PHASE_IDLE;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        BOOL waiting=OverworldWildSpawns_FinishReturnMove(&state,1,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL);
        assert(terminalCalls==1&&executeCalls==0&&resetCalls==0);
        assert((commitFlags&OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED)==(returning?8:0));
        assert(waiting==(pending!=0)&&clearCalls==(pending==0));
        assert(runtime.returnMoves[1].phase==(returning?OW_WILD_RETURN_RETURNING:OW_WILD_RETURN_OUTWARD));
    }
    /* The shared START dispatch does not require profile storage, and a
     * cleared record cannot make an unrelated later request. */
    SetupAdapter(OVERWORLD_MOTION_KIND_HOP);
    assert(!OverworldWildSpawns_FinishReturnMove(&state,1,NULL,NULL,OVERWORLD_RETURN_MOVE_START));
    assert(runtime.returnMoves[1].phase==OW_WILD_RETURN_RETURNING&&startCalls==1&&queryCalls==1);
    SetupAdapter(OVERWORLD_MOTION_KIND_HOP);runtime.returnMoves[1].phase=0;
    assert(!OverworldWildSpawns_FinishReturnMove(&state,1,NULL,NULL,OVERWORLD_RETURN_MOVE_START));
    assert(startCalls==0&&landingCalls==0&&queryCalls==1);
    /* The same terminal dispatch also owns ordinary phase-NONE shared Walks.
     * IDLE and SETTLING both close once; missing ACK/terminal phase keeps mode. */
    for(int pending=0;pending<4;++pending){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);runtime.returnMoves[1].phase=0;
        runtime.movementCustomMotionModes[1]=OW_WILD_CUSTOM_MOTION_WALK;
        terminalOK=pending!=1;
        terminalPhase=pending==2?OVERWORLD_MOTION_PHASE_COMMIT_PENDING:
            pending==3?OVERWORLD_MOTION_PHASE_SETTLING:OVERWORLD_MOTION_PHASE_IDLE;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        BOOL waiting=OverworldWildSpawns_FinishReturnMove(&state,1,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL);
        assert(queryCalls==1&&terminalCalls==1&&commitCalls==0);
        assert(commitFlags==(OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED|
            OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED));
        assert(waiting==(pending==1||pending==2));
        assert(clearCalls==(pending==0||pending==3));
        assert(executeCalls==clearCalls&&chainPauseCalls==0&&resetCalls==0);
    }
    /* Legacy COMMIT and skid/chain follow-on still use the native callbacks.
     * Explicit combat/despawn stop closes COMMIT without follow-on work. */
    for(int shared=0;shared<2;++shared)for(int stop=0;stop<2;++stop)
        for(int skid=0;skid<3;++skid){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);runtime.returnMoves[1].phase=0;
        runtime.movementCustomMotionModes[1]=shared?OW_WILD_CUSTOM_MOTION_WALK:0;
        policy.pendingSkid=skid!=0;policy.walkMomentum.skidRemaining=skid==2;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        BOOL waiting=OverworldWildSpawns_FinishReturnMove(&state,1,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL|(stop?OVERWORLD_RETURN_MOVE_STOP_AFTER_COMMIT:0));
        assert(terminalCalls==shared&&commitCalls==!shared&&clearCalls==shared);
        assert(executeCalls==!stop&&chainPauseCalls==(!stop&&skid==1));
        assert(waiting==(!stop&&skid!=0)&&resetCalls==0);
        assert(commitFlags==(OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED|
            OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED));
    }
    /* The moved native context preserves the actual owner/tired lane mask. */
    for(int tired=0;tired<2;++tired)for(int shared=0;shared<2;++shared){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);runtime.returnMoves[1].phase=0;
        state.movementSpotStates[1]=tired?OW_WILD_SPOT_STATE_TIRED:0;
        runtime.movementCustomMotionModes[1]=shared?OW_WILD_CUSTOM_MOTION_WALK:0;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        p.owner.chillAllowedTerrainMask=0x0123;p.tired.chillAllowedTerrainMask=0x0456;
        assert(!OverworldWildSpawns_FinishReturnMove(&state,1,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL));
        assert(executeCalls==1&&terminalCalls==shared&&commitCalls==!shared);
    }
    /* Throw reservations skip legacy COMMIT, but shared accepted Walk still
     * requires its exact terminal close. Neither starts a skid or chain. */
    for(int shared=0;shared<2;++shared){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);runtime.returnMoves[1].phase=0;
        runtime.movementCustomMotionModes[1]=shared?OW_WILD_CUSTOM_MOTION_WALK:0;
        runtime.throwState.targets[1]=3;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        assert(OverworldWildSpawns_FinishReturnMove(&state,1,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL));
        assert(terminalCalls==shared&&clearCalls==shared&&commitCalls==0);
        assert(executeCalls==0&&chainPauseCalls==0&&resetCalls==0);
    }
    /* Missing object, missing policy, failed legacy COMMIT, or missing package
     * cannot dispatch movement through a stale or uncommitted terminal. */
    for(int missing=0;missing<4;++missing){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);runtime.returnMoves[1].phase=0;
        if(missing==0)state.spawns[1].object=NULL;
        if(missing==1)policyKnown=FALSE;
        if(missing==2)reduceOK=FALSE;
        if(missing==3)queryAvailable=FALSE;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        BOOL waiting=OverworldWildSpawns_FinishReturnMove(&state,1,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL);
        assert(waiting==(missing==0||missing==3));
        assert(resetCalls==(missing==0)&&commitCalls==(missing==2));
        assert(terminalCalls==0&&clearCalls==0&&executeCalls==0&&chainPauseCalls==0);
    }
    /* Object-NULL teardown uses the old RESET branch directly. Only the
     * active mount's shared follower slot preserves its owned Walk policy. */
    for(int follower=0;follower<2;++follower)for(int riding=0;riding<2;++riding){
        SetupAdapter(OVERWORLD_MOTION_KIND_WALK);int slot=follower?OW_WILD_FOLLOWER_SLOT:1;
        state.spawns[slot].object=NULL;mounted=riding;
        OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={0};
        assert(OverworldWildSpawns_FinishReturnMove(&state,slot,&p,&primitives,
            OVERWORLD_RETURN_MOVE_WALK_TERMINAL));
        assert(resetCalls==(!follower||!riding));
        assert(terminalCalls==0&&commitCalls==0&&clearCalls==0&&executeCalls==0&&chainPauseCalls==0);
    }
    return 0;
}
'''



REQUEST_BRIDGE = r'''
static struct {u32 (*getContext)(void);} compatEntry={OverworldWildRuntime_GetFieldContext};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compatEntry)
static BOOL QueryOrigin(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *out){
    assert((f==&field||f==NULL)&&x>=12&&y>=20);out->surfaceId=77;return 1;
}
static const OverworldReturnMoveWildOps requestOps={
    .querySurface=QueryOrigin,.resolveWalkPause=OverworldWildSpawns_ResolveWalkPause};
'''
REQUEST_WRAPPER = r'''
static OverworldMotionDecision OverworldWildRuntime_RequestMotion(
    OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorProfileData *lane,
    u8 kind,u8 visibility,u8 arc,u8 facing,u16 duration,u8 spin,u8 sway,u16 surface){
    OverworldReturnMoveWildRequest call={.context={s,s->movementFieldSystem,&requestOps,slot},
        .lane=lane,.kind=kind,.visibilityPolicy=visibility,.arcHeightQ4=arc,.facing=facing,
        .duration=duration,.spinSpeed=spin,.swayWidth=sway,.targetSurfaceId=surface};
    return OverworldReturnMoveWild_Request(&call);
}
'''
ADAPTER_WRAPPER = r'''
static const OverworldReturnMoveWildOps adapterOps={
    .currentField=OverworldWildSpawns_IsPresentationFieldContextCurrent,
    .currentSpawn=OverworldWildSpawns_IsCurrentSpawnObject,
    .mountActive=OverworldWildSpawns_MountIsActive,
    .querySurface=OverworldWildSpawns_QuerySurface,.groundBaseY=OverworldWildSpawns_GetObjectGroundBaseYAt,
    .classifyLanding=OverworldWildSpawns_ClassifyBehaviorHopLandingTile,
    .startTimed=OverworldWildSpawns_StartPreparedCustomJumpCommandTimed,
    .clearStaged=OverworldWildSpawns_ClearStagedHopTargetLocal,
    .initPolicyCall=OverworldWildSpawns_InitPolicyCall,.reduceWalk=OverworldWildSpawns_ReduceWalk,
    .directionFromDelta=OverworldWalk_DirectionFromDelta,
    .clearCustomJump=OverworldWildSpawns_ClearCustomJumpLocal,
    .executeWalk=OverworldWildSpawns_ExecuteWalkPolicy,
    .commitChain=OverworldWildSpawns_CommitDeferredChainMovementPause};
#define sOverworldWildReturnOps adapterOps
typedef struct OverworldQueryCodeAddonEntry {
    BOOL (*returnFinish)(const OverworldReturnMoveWildContext *,OverworldWildBehaviorProfile *,
        OverworldWildBehaviorPrimitives *,u8);
} OverworldQueryCodeAddonEntry;
static const OverworldQueryCodeAddonEntry queryEntry={OverworldReturnMoveWild_Finish};
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem *f,void *unused){
    assert(f==&field&&unused==NULL);++queryCalls;return queryAvailable?&queryEntry:NULL;
}
static BOOL OverworldWildSpawns_IsReturnMoveCurrent(OverworldWildSpawnState *s,int slot){
    OverworldReturnMoveWildContext call={s,s->movementFieldSystem,&adapterOps,slot};
    return OverworldReturnMoveWild_IsCurrent(&call);
}
static void OverworldWildSpawns_TryStartReturnMove(OverworldWildSpawnState *s,FieldSystem *f,int slot){
    OverworldReturnMoveWildContext call={s,f,&adapterOps,slot};
    OverworldReturnMoveWild_TryStart(&call);
}
'''

class ReturnMoveRuntimeTests(unittest.TestCase):
    def test_actual_request_arm_inverse_return_and_rejection_guards(self):
        source = (ROOT / "lib/overworld/overworld_return_move_wild.c").read_text()
        return_header = (ROOT / "include/overworld_return_move_wild.h").read_text()
        state_header = (ROOT / "include/overworld_wild_runtime_state_internal.h").read_text()
        actor_header = (ROOT / "include/overworld_actor_system.h").read_text()
        data_header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        phases = re.search(r"enum \{\s*OW_WILD_RETURN_NONE.*?\};", state_header, re.S).group()
        getter = next(line for line in data_header.splitlines()
                      if line.startswith("#define OW_WILD_BEHAVIOR_RETURNS_AFTER_MOVE("))
        bodies = "\n".join(extract_function(source, name, returns) for name, returns in (
            ("OverworldReturnMoveWild_CurrentSubject", "BOOL"),
            ("OverworldReturnMoveWild_Request", "OverworldMotionDecision")))
        call_types = "\n".join(typedef(return_header, name) for name in (
            "OverworldWildDirectionStepContext", "OverworldReturnMoveWildOps",
            "OverworldReturnMoveWildContext", "OverworldReturnMoveWildRequest"))
        call_types = "typedef struct OverworldWildSpawnState OverworldWildSpawnState;\n" + \
            "typedef struct OverworldWildSpawn OverworldWildSpawn;\n" + call_types
        geometry = (ROOT / "src/pokemon_move_history_overlay/overworld_hop_geometry.c").read_text()
        geometry_body = extract_function(geometry, "OverworldActorHopGeometry_NextCell", "void")
        geometry_body = geometry_body.replace("static void ", "void ", 1)
        program = "\n".join((PRELUDE, '#include "overworld_actor_hop_geometry.h"', geometry_body, getter, phases,
            typedef(actor_header, "OverworldActorHandle"),
            typedef(actor_header, "OverworldActorQuery"),
            typedef(data_header, "OverworldWildBehaviorProfileData"),
            typedef(state_header, "OverworldWildReturnMove"),
            typedef(data_header, "OverworldWildBehaviorProfile"),
            typedef(data_header, "OverworldWildBehaviorPrimitives"),
            call_types, FIXTURE, REQUEST_BRIDGE, bodies, REQUEST_WRAPPER, DRIVER))
        with tempfile.TemporaryDirectory(prefix="return-move-runtime-") as directory:
            src, exe = Path(directory) / "check.c", Path(directory) / "check"
            src.write_text(program)
            command = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-DOVERWORLD_MOTION_HOST",
                       "-I", str(ROOT / "include"),
                       "-I", str(ROOT / "src/pokemon_move_history_task6_overlay"), str(src),
                       str(ROOT / "lib/overworld/overworld_motion_model.c"), "-o", str(exe)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_actual_return_adapter_identity_busy_retry_and_terminal_guards(self):
        source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        moved_source = (ROOT / "lib/overworld/overworld_return_move_wild.c").read_text()
        return_header = (ROOT / "include/overworld_return_move_wild.h").read_text()
        state_header = (ROOT / "include/overworld_wild_runtime_state_internal.h").read_text()
        actor_header = (ROOT / "include/overworld_actor_system.h").read_text()
        data_header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        walk_header = (ROOT / "include/overworld_wild_movement.h").read_text()
        combat_header = (ROOT / "include/overworld_combat.h").read_text()
        combat_constants = "\n".join(line for line in combat_header.splitlines()
            if line.startswith(("#define OVERWORLD_COMBAT_NONE ",
                "#define OVERWORLD_COMBAT_KNOCKBACK ", "#define OVERWORLD_COMBAT_FAINTED ",
                "#define OVERWORLD_COMBAT_CRASH_SETTLE ", "#define OVERWORLD_COMBAT_CRASH_PLAYING ")))
        phases = re.search(r"enum \{\s*OW_WILD_RETURN_NONE.*?\};", state_header, re.S).group()
        operations = re.search(r"typedef enum OverworldActorWalkPolicyOperation \{.*?\} OverworldActorWalkPolicyOperation;",
                               walk_header, re.S).group()
        walk_constants = "\n".join(line for line in walk_header.splitlines()
                                   if line.startswith(("#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_",
                                                       "#define OVERWORLD_ACTOR_WALK_STEP_"))
                                   and not line.endswith("\\"))
        decisions = re.search(r"typedef enum OverworldActorWalkPolicyDecision \{.*?\} OverworldActorWalkPolicyDecision;",
                              walk_header, re.S).group()
        results = re.search(r"typedef enum OverworldActorWalkPolicyStartResult \{.*?\} OverworldActorWalkPolicyStartResult;",
                            walk_header, re.S).group()
        bodies = "\n".join(extract_function(moved_source, name, returns) for name, returns in (
            ("OverworldReturnMoveWild_CombatWork", "u8"),
            ("OverworldReturnMoveWild_CurrentOwner", "BOOL"),
            ("OverworldReturnMoveWild_IsCurrent", "BOOL"),
            ("OverworldReturnMoveWild_TryStart", "void"),
            ("OverworldReturnMoveWild_FinishWalk", "BOOL"),
            ("OverworldReturnMoveWild_Finish", "BOOL")))
        terminal_wrapper = extract_function(source, "OverworldWildSpawns_FinishReturnMove", "BOOL")
        flags = re.search(r"enum \{\s*OVERWORLD_RETURN_MOVE_BEFORE_WALK.*?\};", return_header, re.S).group()
        call_types = "\n".join(typedef(return_header, name) for name in (
            "OverworldReturnMoveWildOps", "OverworldReturnMoveWildContext", "OverworldReturnMoveWildRequest"))
        # The local context typedef needs the state type; put it before fixture callbacks.
        fixture = ADAPTER_FIXTURE.replace("static OverworldWildSpawnState state;",
            typedef(return_header, "OverworldWildDirectionStepContext") + "\n" + call_types + "\nstatic OverworldWildSpawnState state;")
        program = "\n".join((ADAPTER_PRELUDE, phases, flags, operations, decisions, results,
            walk_constants, combat_constants,
            typedef(actor_header, "OverworldActorHandle"), typedef(actor_header, "OverworldActorQuery"),
            typedef(data_header, "OverworldWildBehaviorProfileData"),
            typedef(data_header, "OverworldWildBehaviorProfile"),
            typedef(data_header, "OverworldWildBehaviorPrimitives"),
            typedef(walk_header, "OverworldActorWalkPolicyCall"),
            typedef(state_header, "OverworldWildReturnMove"), fixture, bodies, ADAPTER_WRAPPER,
            terminal_wrapper, ADAPTER_DRIVER))
        with tempfile.TemporaryDirectory(prefix="return-move-adapter-") as directory:
            src, exe = Path(directory) / "check.c", Path(directory) / "check"
            src.write_text(program)
            compiled = subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"), str(src), "-o", str(exe)],
                capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
