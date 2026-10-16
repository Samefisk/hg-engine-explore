#!/usr/bin/env python3
"""Bounded production-C Wild seams and explicit-origin height controls.

Host native structs contain only named fields read by these functions. They
are seam fixtures, not ARM offset proof. Native header ARM sizes are checked by
the existing native verifier. No live object, archive, motion, or reservation
is written by the production query functions.
"""
from pathlib import Path
import hashlib
import re
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WILD=ROOT/'lib/overworld/overworld_pickup_route_wild.c'
RUNTIME=ROOT/'src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c'
HOP=ROOT/'src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c'


def function(source,name,return_type):
    start=source.index(name+'(')
    brace=source.index('{',start); depth=1;end=brace+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return 'static '+return_type+' '+source[start:end]+'\n'


PROLOG=r'''
#include "overworld_pickup_route_native.h"
#include <stddef.h>
/* Use the real pointer-free catalog/header/profile types. Native engine
 * structs below remain only named host seams. */
#define TYPES_H
#define OVERWORLD_BEHAVIOR_HOST
typedef int BOOL;
typedef int8_t s8;
#include "overworld_wild_behavior_data.h"
#include "overworld_pickup_route_wild.h"
#include "overworld_pickup_landing_wild.h"
#include "overworld_target_bindings.h"
#include "overworld_behavior_condition_runtime.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"Wild query line%d: %s\n",__LINE__,#x);return 1;} }while(0)
#define TRUE 1
#define FALSE 0
#define FX32_SHIFT 12
#define OW_WILD_RUNTIME_FX32_ONE (1<<12)
#define MAPOBJECTFLAG_ACTIVE 1
#define MAPOBJECTFLAG_SINGLE_MOVEMENT (1u<<1)
#define MAPOBJECTFLAG_UNK23 (1u<<23)
#define MAPOBJECTFLAG_UNK29 (1u<<29)
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_HELPER_THROW_TARGET_ENCODE(slot) ((u8)((slot)+1))
#define OVERWORLD_WILD_OCCUPANCY_OBJECTS 0
#define OVERWORLD_WILD_OCCUPANCY_NONPLAYER 1
#define OVERWORLD_WILD_OCCUPANCY_SURFACE 2
#define OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER 3
#include "overworld_motion_model.h"
#define OVERWORLD_ACTOR_HOP_PLAN_VECTOR 0
#define OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY 1
#define OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY 2
#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY 1
#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT 2
#define OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32 (1<<12)
typedef struct VecFx32 {s32 x,y,z;} VecFx32;
typedef struct LocalMapObject {u32 flags,flags2;int xrange,yrange,xInit,yInit,xCurr,yCurr;u32 posVec[3];u8 cachedBehavior;} LocalMapObject;
typedef struct OverworldWildSpawn {u8 active;u16 encounterGeneration;u32 personality;LocalMapObject *object;} OverworldWildSpawn;
typedef struct PlayerAvatar {LocalMapObject *mapObject;} PlayerAvatar;
struct FieldSystem {int identity;PlayerAvatar *playerAvatar;};
typedef struct OverworldWildBehaviorConditionRuntime {
 OverworldTargetBindingsState bindings[10];
 OverworldBehaviorConditionPreparedActor actors[10];
 struct {OverworldBehaviorConditionWorldView world;u8 valid;} frame;
 OverworldBehaviorConditionResult result;
 u32 activeApplicationMasks[10];s16 targetX[10],targetY[10];u16 targetValidMask;
} OverworldWildBehaviorConditionRuntime;
typedef struct OverworldWildOverlayRuntimeState {struct {u8 targets[10];u16 targetMask,carrierMask;} throwState;OverworldWildBehaviorConditionRuntime *conditions;} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {FieldSystem *movementFieldSystem;OverworldWildOverlayRuntimeState *movementRuntimeState;OverworldWildSpawn spawns[10];u8 movementSpotStates[10];} OverworldWildSpawnState;
typedef struct OverworldActorPolicyView {u8 chainPauseAction,chainStepsRemaining;} OverworldActorPolicyView;
typedef struct OverworldActorRuntimeSlot {OverworldActorStateSnapshot snapshot;struct {u16 targetSurfaceId;} policy;} OverworldActorRuntimeSlot;
typedef struct OverworldActorSystemState {u32 frame;u16 fieldEpoch,mapGeneration;OverworldActorRuntimeSlot slots[10];} OverworldActorSystemState;
typedef struct OverworldActorHopPlanCall {const void *profile;const OverworldWildBehaviorProfileData *lane;FieldSystem *fieldSystem;const OverworldWildSurfaceCatalog *surfaceCatalog;LocalMapObject *object;s32 startBaseY,targetBaseY;s16 startX,startY,targetX,targetY,deltaX,deltaY;u32 trajectory;u8 operation,spotState,direction,distance;} OverworldActorHopPlanCall;
static int nativeHeightReady=1,nativeHeightDelta,nativeOrigin,queryHasHit;
static int behaviorCalls,landCalls,surfaceCalls,occupancyCalls,seamsAdmissionCalls;
static OverworldWildSurfaceHit queryHit;
static BOOL NativeHeight(FieldSystem *field,VecFx32 *position,BOOL flag) {
 (void)field;(void)flag;nativeOrigin=position->y;
 if(!nativeHeightReady)return FALSE;position->y+=nativeHeightDelta;return TRUE;
}
#define OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT NativeHeight
static BOOL OverworldWildRuntime_QuerySurface(FieldSystem *field,const OverworldWildSurfaceCatalog *catalog,int x,int y,OverworldWildSurfaceHit *hit) {
 (void)field;(void)catalog;(void)x;(void)y;++surfaceCalls;if(!queryHasHit)return FALSE;*hit=queryHit;return TRUE;
}
'''
SEAMS=r'''
static u32 Trajectory(u8 time,u8 distance,s32 delta,u16 options) {(void)time;(void)distance;(void)delta;(void)options;return (2u<<16)|4;}
static s32 Arc(u32 elapsed,u32 total,u8 height) {(void)elapsed;(void)total;(void)height;return 4096;}
static const struct {u32 (*calculateJumpTrajectory)(u8,u8,s32,u16);s32 (*calculateJumpArc)(u32,u32,u8);} surfaceEntry={Trajectory,Arc};
#undef OVERWORLD_WILD_SURFACE_SERVICE_ENTRY
#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY (&surfaceEntry)
static const struct {
 BOOL (*querySurface)(FieldSystem *,const OverworldWildSurfaceCatalog *,int,int,OverworldWildSurfaceHit *);
 BOOL (*resolveBaseYAt)(FieldSystem *,const OverworldWildSurfaceHit *,s32,u32,int,int,s32 *);
} runtimeEntry={OverworldWildRuntime_QuerySurface,OverworldWildRuntime_ResolveBaseYAt};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
'''
HARNESS=r'''
static FieldSystem field;
static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime;
static OverworldActorSystemState actors;
static LocalMapObject objects[2];
static LocalMapObject player,heldCarrier;
static PlayerAvatar avatar;
static OverworldWildBehaviorConditionRuntime conditions;
static OverworldBehaviorConditionEntryState conditionStates[3];
static int objectsOccupy;
static OverworldPickupRouteWildWorld world;
static OverworldWildBehaviorDataBlob behaviorData;
static OverworldPickupRouteQuery query;
static OverworldPickupRouteNativePolicy policy;
static OverworldPickupRouteNativeContext context;
static OverworldActorPolicyView actorPolicy;
static OverworldWildBehaviorProfileData lane;
static int missingTileX=-1,bodyX=-1,bodyY=-1,blockSource=-1;
static int observedFromX,observedFromY,observedFromBase,ignorePlayer,hopVectorCalls,hopTrajectoryCalls,pickupCalls;
static LocalMapObject *observedIgnored,*observedCollisionIgnored;
static BOOL Playable(FieldSystem *f,int x,int y) {(void)f;return x>=0&&x<20&&y>=0&&y<10;}
static u8 Behavior(FieldSystem *f,int x,int y) {(void)f;(void)y;++behaviorCalls;return x==missingTileX?0xFF:(u8)x;}
static BOOL Surf(u8 behavior) {(void)behavior;return FALSE;}
static BOOL PlayerTile(FieldSystem *f,int x,int y) {(void)f;return x==19&&y==9;}
static BOOL PlayerFront(FieldSystem *f,int x,int y) {(void)f;(void)x;(void)y;return FALSE;}
static BOOL Land(FieldSystem *f,int x,int y) {(void)f;(void)x;(void)y;++landCalls;return TRUE;}
static BOOL Scripted(FieldSystem *f,int x,int y) {(void)f;return x==18&&y==8;}
static BOOL CurrentObject(FieldSystem *f,LocalMapObject *object) {return f==&field&&(object==&objects[0]||object==&objects[1]||object==&player);}
static BOOL Occupied(FieldSystem *f,LocalMapObject *ignored,LocalMapObject *collision,int x,int y,s32 height,int mode) {
 (void)f;(void)height;++occupancyCalls;observedIgnored=ignored;observedCollisionIgnored=collision;
 ignorePlayer=mode==OVERWORLD_WILD_OCCUPANCY_NONPLAYER||mode==OVERWORLD_WILD_OCCUPANCY_SURFACE;
 if(objectsOccupy) {
  LocalMapObject *current[]={&objects[0],&objects[1],&heldCarrier};
  for(unsigned i=0;i<3;i++) {
   LocalMapObject *o=current[i];
   if((o->flags&MAPOBJECTFLAG_ACTIVE)&&o!=ignored&&o!=collision&&o->xCurr==x&&o->yCurr==y
      &&(mode<OVERWORLD_WILD_OCCUPANCY_SURFACE||(s32)o->posVec[1]==height))return TRUE;
  }
 }
 return (x==bodyX&&y==bodyY)||(PlayerTile(f,x,y)&&!ignorePlayer);
}
static const OverworldActorSystemState *ActorState(void) {return &actors;}
static BOOL InspectPolicy(u8 slot,OverworldActorPolicyView *view) {if(slot!=0)return FALSE;*view=actorPolicy;return TRUE;}
static BOOL WalkTerrain(FieldSystem *f,const void *raw,int x,int y,s8 *heightDirection) {
 const VecFx32 *from=raw;(void)f;(void)x;(void)y;*heightDirection=0;
 observedFromX=from->x;observedFromY=from->z;observedFromBase=from->y;return FALSE;
}
static BOOL SourceBlock(u8 behavior) {return behavior==blockSource;}
static BOOL TargetBlock(u8 behavior) {(void)behavior;return FALSE;}
static const OverworldPickupRouteWildDirectionBlock sourceBlocks[4]={SourceBlock,SourceBlock,SourceBlock,SourceBlock};
static const OverworldPickupRouteWildDirectionBlock targetBlocks[4]={TargetBlock,TargetBlock,TargetBlock,TargetBlock};
static OverworldMotionDecision HopPlan(OverworldActorHopPlanCall *call) {
 if(call->operation==OVERWORLD_ACTOR_HOP_PLAN_VECTOR) {
  ++hopVectorCalls;call->distance=(u8)(call->deltaX<0?-call->deltaX:call->deltaX);
  if(call->distance==0)call->distance=(u8)(call->deltaY<0?-call->deltaY:call->deltaY);
  return OVERWORLD_MOTION_DECISION_ACCEPTED;
 }
 ++hopTrajectoryCalls;return OverworldActorHopPlanner_PlanTrajectory(call);
}
static OverworldPickupRouteEdgeResult FixturePickupReach(void *raw,const OverworldPickupRoutePosition *standing,const OverworldPickupRoutePosition *cargo) {
 (void)raw;++pickupCalls;int dx=standing->x-cargo->x,dy=standing->y-cargo->y;
 return dx>=-1&&dx<=1&&dy>=-1&&dy<=1&&standing->baseY==cargo->baseY?OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL:OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
}
static const OverworldPickupRouteWildOps ops={OVERWORLD_PICKUP_ROUTE_WILD_VERSION,sizeof(ops),
 Playable,Behavior,OverworldWildRuntime_QuerySurface,OverworldWildRuntime_ResolveBaseYAt,
 Surf,PlayerTile,PlayerFront,Land,Scripted,CurrentObject,Occupied,ActorState,InspectPolicy,
 HopPlan,WalkTerrain,sourceBlocks,targetBlocks,FixturePickupReach};
static void Reset(void) {
 memset(&state,0,sizeof(state));memset(&runtime,0,sizeof(runtime));memset(&actors,0,sizeof(actors));memset(&objects,0,sizeof(objects));
 memset(&conditions,0,sizeof(conditions));memset(conditionStates,0,sizeof(conditionStates));memset(&heldCarrier,0,sizeof(heldCarrier));objectsOccupy=0;
 player=(LocalMapObject){.flags=MAPOBJECTFLAG_ACTIVE,.xCurr=19,.yCurr=9};
 avatar.mapObject=&player;field.playerAvatar=&avatar;
 memset(&world,0,sizeof(world));memset(&query,0,sizeof(query));memset(&policy,0,sizeof(policy));memset(&context,0,sizeof(context));
 missingTileX=bodyX=bodyY=blockSource=-1;queryHasHit=0;nativeHeightReady=1;nativeHeightDelta=0;
 actorPolicy=(OverworldActorPolicyView){0,0};lane=(OverworldWildBehaviorProfileData){.spawnHopTime=4,.hopTime=4};
 actors.fieldEpoch=3;actors.mapGeneration=4;state.movementFieldSystem=&field;state.movementRuntimeState=&runtime;
 runtime.conditions=&conditions;
 for(int i=0;i<2;i++) {
  objects[i].flags=MAPOBJECTFLAG_ACTIVE;objects[i].xrange=objects[i].yrange=-1;
  objects[i].xCurr=i;objects[i].yCurr=1;objects[i].posVec[1]=9;
  state.spawns[i]=(OverworldWildSpawn){1,(u16)(5+i),(u32)(100+i),&objects[i]};
 actors.slots[i].snapshot.active=1;actors.slots[i].snapshot.subjectIdentity=100+i;
  actors.slots[i].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
  actors.slots[i].snapshot.handle=(OverworldActorHandle){(u16)i,(u16)(2+i),3,4,(u16)(5+i),0};
 }
 conditions.bindings[0].subject=actors.slots[0].snapshot.handle;
 query.version=OVERWORLD_PICKUP_ROUTE_VERSION;query.size=sizeof(query);
 query.subject=actors.slots[0].snapshot.handle;query.cargo=actors.slots[1].snapshot.handle;
 query.bounds=(OverworldPickupRouteBounds){0,0,19,9};query.origin=(OverworldPickupRoutePosition){4,1,100,0xFFFF,0};
 query.cargoPosition=(OverworldPickupRoutePosition){8,1,100,0xFFFF,0};
 query.scopeRevision=query.movementPolicyRevision=query.goalRevision=query.dynamicRevision=1;
 world.version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION;world.size=sizeof(world);world.field=&field;world.state=&state;
 world.subjectObject=world.heightObject=&objects[0];world.catalog=(const OverworldWildSurfaceCatalog *)&field;world.ops=&ops;
 world.scopeRevision=world.movementPolicyRevision=world.dynamicRevision=1;world.finalTargetX=world.finalTargetY=-1;
 policy.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;policy.size=sizeof(policy);policy.allowedTerrainMask=1;
 policy.playerTerrainMask=16;policy.allowedKinds=3;policy.directions=3;policy.hopMinDistance=1;policy.hopMaxDistance=8;
 policy.flags=OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL|OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE;
 policy.resolvedProfile=&lane;policy.resolvedLane=&lane;
 context.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;context.size=sizeof(context);context.query=&query;context.policy=&policy;context.world=&world;
 hopVectorCalls=hopTrajectoryCalls=pickupCalls=0;observedFromX=observedFromY=observedFromBase=0;
 behaviorCalls=landCalls=surfaceCalls=occupancyCalls=seamsAdmissionCalls=0;
}
static void CertifyCatalog(void) {
 memset(&behaviorData,0,sizeof(behaviorData));behaviorData.header=sWildExpectedBlobHeader;
 world.behaviorData=&behaviorData;
 world.catalog=(const OverworldWildSurfaceCatalog *)behaviorData.surfaceModels;
}
static void Claim(void) {
 runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_ENCODE(1);
 runtime.throwState.targetMask=1u<<1;runtime.throwState.carrierMask=1;
}
static void Interest(u8 kind) {
 if(world.behaviorData==NULL)CertifyCatalog();
 behaviorData.conditionEntries[0].applicationIndex=0;
 conditions.actors[0]=(OverworldBehaviorConditionPreparedActor){
  .subject=actors.slots[0].snapshot.handle,.states=conditionStates,.count=1,.stateCapacity=3,.valid=1};
 conditionStates[0]=(OverworldBehaviorConditionEntryState){
  .targetKind=kind,.targetSlot=1,.targetGeneration=actors.slots[1].snapshot.handle.generation,
  .targetEncounterGeneration=actors.slots[1].snapshot.handle.encounterGeneration,
  .flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE};
 conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=(OverworldTargetBinding){
  .target={.kind=kind,.actor=actors.slots[1].snapshot.handle},.flags=OVERWORLD_TARGET_BINDING_BOUND};
 conditions.frame.valid=1;conditions.frame.world.subject=actors.slots[0].snapshot.handle;
 conditions.result.resolvedTarget=conditions.bindings[0].bindings[0].target;
 conditions.result.activeApplicationMask=conditions.activeApplicationMasks[0]=1;
 conditions.targetValidMask=1;
 LocalMapObject *target=kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER?&player:&objects[1];
 conditions.targetX[0]=target->xCurr;conditions.targetY[0]=target->yCurr;
}
static OverworldPickupRouteEdgeResult Edge(int dx,int dy,u8 kind,OverworldPickupRoutePosition *output) {
 OverworldPickupRouteEdge edge={(s16)dx,(s16)dy,OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(kind,0)};
 return OverworldPickupRouteNative_Classify(&context,&query.origin,&edge,output);
}
int main(void) {
 OverworldPickupRoutePosition output;
 LocalMapObject before;
 Reset();before=objects[0];CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(context.seams==OverworldPickupRouteWild_GetSeams(&world));
 CHECK(observedFromX==(4*16+8)*4096&&observedFromY==(1*16+8)*4096&&observedFromBase==100);
 CHECK(!memcmp(&before,&objects[0],sizeof(before))&&observedIgnored==&objects[0]&&observedCollisionIgnored==NULL);
 blockSource=4;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 blockSource=-1;objects[0].xCurr=4;objects[0].xrange=2;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 /* Current route origin must agree with real START; future nodes follow the
  * same init-current offset after completed custom Walk rebases. */
 Reset();objects[0].xCurr=objects[0].xInit=4;objects[0].yInit=1;objects[0].xrange=objects[0].yrange=1;
 CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 OverworldPickupRouteNativeTile rangeTile={0};
 OverworldPickupRoutePosition rangeTarget=query.origin;rangeTarget.x++;
 world.routeRead=0;CHECK(EdgePolicy(&world,&policy,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&query.origin,&rangeTile,&rangeTarget,&rangeTile)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 before=objects[0];query.origin.x=12;
 CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(!memcmp(&before,&objects[0],sizeof(before)));
 rangeTarget=query.origin;rangeTarget.x++;world.routeRead=0;
 CHECK(EdgePolicy(&world,&policy,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&query.origin,&rangeTile,&rangeTarget,&rangeTile)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 objects[0].xInit=3;
 CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL); /* Future completion resets a nonzero offset. */
 query.origin.x=objects[0].xCurr;
 CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED); /* Current root still uses actual init. */
 rangeTarget=query.origin;rangeTarget.x++;world.routeRead=0;
 CHECK(EdgePolicy(&world,&policy,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&query.origin,&rangeTile,&rangeTarget,&rangeTile)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 query.origin.x=12;
 objects[0].xInit=4;objects[0].xrange=0;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 objects[0].xrange=1;objects[0].yInit=0;query.origin.x=objects[0].xCurr;
 CHECK(Edge(0,1,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 objects[0].xrange=0;objects[0].xInit=5;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 query.origin.x=12;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 puts("production Walk range: current START agreement, projected future rebase, real offset/range rejection, no object writes");
 Reset();world.catalog=NULL;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED);
 Reset();missingTileX=5;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED);
 Reset();nativeHeightReady=0;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED);
 Reset();query.dynamicRevision++;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 Reset();state.spawns[1].encounterGeneration++;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 Reset();actors.slots[2].snapshot.reservationId=9;actors.slots[2].snapshot.handle.fieldEpoch=3;
 actors.slots[2].snapshot.targetX=5;actors.slots[2].snapshot.targetY=1;actors.slots[2].policy.targetSurfaceId=0xFFFF;
 CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 actors.slots[2].policy.targetSurfaceId=8;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 Reset();objects[0].xCurr=4;actorPolicy.chainPauseAction=0x96;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 actorPolicy.chainPauseAction=0x95;CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 actorPolicy.chainStepsRemaining=0x20;CHECK(Edge(3,0,1,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 actorPolicy=(OverworldActorPolicyView){0,0};CHECK(Edge(3,0,1,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(hopVectorCalls==1&&hopTrajectoryCalls==1);
 Reset();missingTileX=5;CHECK(Edge(3,0,1,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&hopTrajectoryCalls==0);
 Reset();CHECK(OverworldPickupRouteNative_PickupGoal(&context,7,1,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&pickupCalls==1);
 /* Bare landing: explicit current Player Interest permission, held carrier
  * ignore and native-ground fallback retained, no reservation consumed. */
 Reset();world.collisionIgnoredObject=&objects[1];world.finalTargetX=19;world.finalTargetY=9;
 policy.allowedTerrainMask|=16;policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);query.cargo.generation=0;
 OverworldPickupRouteNativeLandingCall bare={OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
  {19,8,9,0xFFFF,0},19,9,&output,NULL};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&ignorePlayer);
 CHECK(observedCollisionIgnored==&objects[1]&&!world.routeRead);
 policy.flags&=~OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 conditionStates[0].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 nativeHeightReady=0;bare.targetX=18;bare.targetY=8;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&output.baseY==9);
 /* Bare real Walk uses the same policy, with no cached live source. */
 Reset();policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;
 bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
  {4,1,100,0xFFFF,0},5,1,&output,NULL};
 before=objects[0];objects[0].cachedBehavior=0;blockSource=4;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 blockSource=0;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(observedFromBase==100&&observedFromX==(4*16+8)*4096);
 policy.flags&=~OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL;bare.targetY=2;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 bodyX=5;bodyY=1;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 CHECK(!memcmp(&before,&objects[0],sizeof(before)));
 /* The production seams admit only one full, current Interest. All other
  * objects and destination reservations stay blockers; no native pose writes. */
 Reset();objects[0].xCurr=4;objects[1].xCurr=5;objectsOccupy=1;
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);
 policy.allowedTerrainMask=16;policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
  {4,1,9,0xFFFF,0},5,1,&output,NULL};
 before=objects[0];
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(observedIgnored==&objects[1]&&!ignorePlayer);
 CHECK(!memcmp(&before,&objects[0],sizeof(before)));
 bodyX=5;bodyY=1;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 bodyX=bodyY=-1;
 policy.flags&=~OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 conditionStates[0].targetGeneration++;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);conditions.targetValidMask=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);conditions.actors[0].subject.generation++;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 conditions.actors[0].subject=actors.slots[0].snapshot.handle;
 conditions.activeApplicationMasks[0]=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);
 /* A while-true condition needs no persistent binding. Its own full current
  * publication grants the same exact tile; old bindings cannot replace it. */
 memset(&conditions.bindings[0].bindings[0],0,sizeof(OverworldTargetBinding));
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.bindings[0].bindings[0]=(OverworldTargetBinding){
  .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER},.flags=OVERWORLD_TARGET_BINDING_BOUND};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.frame.world.subject=actors.slots[1].snapshot.handle;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.frame.world.subject=actors.slots[0].snapshot.handle;conditions.frame.world.reservedBinding=1;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.frame.world.reservedBinding=0;conditions.frame.valid=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.frame.valid=1;conditions.result.activeApplicationMask=2;
 conditions.result.resolvedTarget.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.result.activeApplicationMask=1;
 conditions.actors[0].valid=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 conditions.actors[0].valid=1;conditions.actors[0].count=33;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 conditions.actors[0].count=1;
 /* Repeat the real publication fold: later application target wins; its
  * last NONE entry falls through to the prior target application. Bind-only
  * entries do not replace a contributed target. */
 policy.allowedTerrainMask=17;
 conditions.actors[0].count=2;conditions.actors[0].catalogEntryIndexes[1]=1;
 behaviorData.conditionEntries[1].applicationIndex=1;
 conditionStates[1]=(OverworldBehaviorConditionEntryState){
  .targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER,.flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE};
 conditions.activeApplicationMasks[0]=3;conditions.targetX[0]=19;conditions.targetY[0]=9;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 bare.targetX=19;bare.targetY=9;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 conditions.actors[0].count=3;conditions.actors[0].catalogEntryIndexes[2]=2;
 behaviorData.conditionEntries[2].applicationIndex=1;
 conditionStates[2]=(OverworldBehaviorConditionEntryState){
  .targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE,.flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE};
 conditions.targetX[0]=5;conditions.targetY[0]=1;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 bare.targetX=5;bare.targetY=1;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 behaviorData.conditionOptions[2].bindOnly=1;conditions.targetX[0]=19;conditions.targetY[0]=9;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 bare.targetX=19;bare.targetY=9;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 behaviorData.conditionEntries[1].applicationIndex=32;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 behaviorData.conditionEntries[1].applicationIndex=1;
 conditions.actors[0].catalogEntryIndexes[1]=255;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 conditions.actors[0].catalogEntryIndexes[1]=1;
 behaviorData.conditionOptions[2].bindOnly=0;
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);bare.targetX=5;bare.targetY=1;policy.allowedTerrainMask=16;
 /* The captured full identity stays current while its actor moves. Admit
  * its current tile, never the old published coordinate alone. */
 objects[1].xCurr=6;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 bare.targetX=6;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(observedIgnored==&objects[1]&&conditions.targetX[0]==5&&conditions.targetY[0]==1);
 /* Return uses this same real landing adapter with the complete terrain
  * mask. The moving Interest may occupy the saved return origin. */
 OverworldPickupRouteWildLandingCall returnLanding={.state=&state,.field=&field,
  .behaviorData=&behaviorData,.ops=&ops,.slot=0,
  .allowedTile=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL,
  .x=6,.y=1,.finalTargetX=6,.finalTargetY=1};
 CHECK(OverworldPickupLandingWild_Classify(&returnLanding)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 bodyX=6;bodyY=1;
 CHECK(OverworldPickupLandingWild_Classify(&returnLanding)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 bodyX=bodyY=-1;
 CHECK(conditions.targetX[0]==5&&conditions.targetY[0]==1);
 conditions.targetX[0]=6;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 objects[1].xCurr=5;conditions.targetX[0]=5;bare.targetX=5;
 heldCarrier=(LocalMapObject){.flags=MAPOBJECTFLAG_ACTIVE,.xCurr=5,.yCurr=1};
 world.collisionIgnoredObject=&heldCarrier;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(observedIgnored==&objects[1]&&observedCollisionIgnored==&heldCarrier);
 world.collisionIgnoredObject=NULL;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 heldCarrier.flags=0;
 policy.allowedTerrainMask=17;
 CHECK(Edge(1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 actors.slots[2].snapshot.reservationId=1;actors.slots[2].snapshot.handle.fieldEpoch=3;
 actors.slots[2].snapshot.targetX=5;actors.slots[2].snapshot.targetY=1;actors.slots[2].policy.targetSurfaceId=0xFFFF;
 CHECK(Edge(1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 actors.slots[2].snapshot.reservationId=0;
 CHECK(OverworldPickupRouteNative_PickupGoal(&context,5,1,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 bare.targetX=19;bare.targetY=9;CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&ignorePlayer);
 policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;
 bare.origin=(OverworldPickupRoutePosition){19,8,9,0xFFFF,0};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 Interest(OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 world.state=NULL;world.subjectObject=NULL;policy.flags&=~OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&ignorePlayer);
 puts("production Interest tile: exact actor/Player/spawn and transient target, own published winner survives warm/foreign scratch, missing/stale/recycled publication rejects, other blockers/held carrier/reservations/standing guards preserved");
 /* Exact production height leaf: absolute/relative/unavailable/skip native. */
 Reset();s32 height=-7;queryHit=(OverworldWildSurfaceHit){700,8,0,0};
 CHECK(OverworldWildRuntime_ResolveBaseYAt(&field,&queryHit,100,0,1,1,&height)&&height==700);
 nativeHeightDelta=20;queryHit=(OverworldWildSurfaceHit){12,0xFFFE,4,0};
 CHECK(OverworldWildRuntime_ResolveBaseYAt(&field,&queryHit,100,0,1,1,&height)&&height==132&&nativeOrigin==100);
 nativeHeightReady=0;height=-7;
 CHECK(!OverworldWildRuntime_ResolveBaseYAt(&field,&queryHit,100,0,1,1,&height)&&height==-7);
 CHECK(OverworldWildRuntime_ResolveBaseYAt(&field,&queryHit,100,MAPOBJECTFLAG_UNK23,1,1,&height)&&height==100);
 queryHasHit=1;CHECK(OverworldWildRuntime_GetGroundBaseY(&field,world.catalog,&objects[0],1,1)==9);
 /* Exact production shared Hop caller keeps explicit origin and distinguishes
  * unavailable geometry from a negative path proof, with legacy fallback. */
 nativeHeightReady=1;nativeHeightDelta=10;queryHit=(OverworldWildSurfaceHit){0,0xFFFE,4,0};
 OverworldActorHopPlanCall hop={0};hop.lane=&lane;hop.fieldSystem=&field;hop.surfaceCatalog=world.catalog;hop.object=&objects[0];
 hop.startBaseY=hop.targetBaseY=100;hop.startX=0;hop.targetX=2;hop.distance=2;hop.operation=1;hop.spotState=2;
 CHECK(OverworldActorHopPlanner_PlanTrajectory(&hop)==OVERWORLD_MOTION_DECISION_ACCEPTED&&nativeOrigin==100);
 nativeHeightReady=0;CHECK(OverworldActorHopPlanner_PlanTrajectory(&hop)==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY);
 hop.spotState=0;CHECK(OverworldActorHopPlanner_PlanTrajectory(&hop)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 /* Exact production atomic pickup: current claim and identities, completed
  * motion receipt, native command completion, strict height and caller reach.
  * None of these reads may cancel or change the accepted motion or claim. */
 Reset();Claim();before=objects[0];OverworldWildOverlayRuntimeState claimBefore=runtime;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&pickupCalls==1);
 CHECK(!memcmp(&before,&objects[0],sizeof(before))&&!memcmp(&claimBefore,&runtime,sizeof(runtime)));
 runtime.throwState.targetMask=0;CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 Claim();runtime.throwState.carrierMask=0;CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 Claim();runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_ENCODE(2);
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 Claim();actors.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 actors.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;state.spawns[1].encounterGeneration++;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 Reset();Claim();query.cargo.generation++;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 for(int i=0;i<2;i++) {
  Reset();Claim();actors.slots[i].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
  OverworldActorStateSnapshot movingBefore=actors.slots[i].snapshot;
  CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED);
  CHECK(!memcmp(&movingBefore,&actors.slots[i].snapshot,sizeof(movingBefore))&&pickupCalls==0);
  actors.slots[i].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_IDLE;actors.slots[i].snapshot.reservationId=9;
  CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED);
  actors.slots[i].snapshot.reservationId=0;objects[i].flags|=MAPOBJECTFLAG_SINGLE_MOVEMENT;
  CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&pickupCalls==0);
 }
 Reset();Claim();nativeHeightReady=0;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&pickupCalls==0);
 Reset();Claim();objects[1].xCurr=5;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED&&pickupCalls==1);
 state.movementRuntimeState=NULL;
 CHECK(OverworldPickupRouteWild_AtomicPickup(&world,&query.subject,&query.cargo)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 /* An ordinary-ground tile cannot satisfy the measured surface-only mask.
  * Its target read must not run the native LAND collision query. */
 Reset();policy.allowedTerrainMask=448;policy.flags=0;
 OverworldPickupRouteNativeWork work;
 bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
  {4,1,100,0xFFFF,0},5,1,&output,&work};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 CHECK(landCalls==0&&work.support==0&&occupancyCalls==0);
 /* Only the actual current package can prove a catalog miss before stock
  * behavior. A loaded surface hit still takes the full canonical path. */
 Reset();CertifyCatalog();policy.allowedTerrainMask=448;policy.flags=0;
 missingTileX=5;nativeHeightReady=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 CHECK(surfaceCalls==1&&behaviorCalls==0&&landCalls==0&&work.support==0&&occupancyCalls==0);
 /* The no-surface fact applies to every nonzero surface-only subset. */
 const u16 surfaces[]={4,64,128,256,512,448,OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL};
 for(unsigned i=0;i<sizeof(surfaces)/sizeof(surfaces[0]);i++) {
  Reset();CertifyCatalog();policy.allowedTerrainMask=surfaces[i];policy.flags=0;
  CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
  CHECK(surfaceCalls==1&&behaviorCalls==0&&landCalls==0&&work.support==0&&occupancyCalls==0);
 }
 Reset();CertifyCatalog();policy.allowedTerrainMask=448;policy.flags=0;queryHasHit=1;
 queryHit=(OverworldWildSurfaceHit){700,8,OW_WILD_SURFACE_TYPE_ROOFTOP,0};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&output.baseY==700);
 CHECK(surfaceCalls==1&&behaviorCalls==1&&landCalls==0&&work.support==1&&occupancyCalls==1);
 bodyX=5;bodyY=1;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED&&occupancyCalls==2);
 bodyX=-1;missingTileX=5;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&work.support==0&&occupancyCalls==2);
 /* Even a catalog hit of the wrong type keeps native unknown semantics. */
 queryHit.surfaceType=OW_WILD_SURFACE_TYPE_FLOWERBED;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&work.support==0);
 missingTileX=-1;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED&&work.support==0);
 /* Relevant relative-canopy height failure remains DEFERRED in a route. */
 Reset();CertifyCatalog();queryHasHit=1;nativeHeightReady=0;
 queryHit=(OverworldWildSurfaceHit){12,OW_WILD_SURFACE_ID_NATIVE_CANOPY,OW_WILD_SURFACE_TYPE_CANOPY,0};
 policy.allowedTerrainMask=4;
 CHECK(OverworldPickupRouteNative_PickupGoal(&context,7,1,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED);
 CHECK(surfaceCalls==1&&behaviorCalls==1&&context.lastWork.support==1&&occupancyCalls==0&&pickupCalls==0);
 /* SOURCE stays complete; ground TARGETs keep native LAND/support reads. */
 Reset();CertifyCatalog();CHECK(Edge(1,0,0,&output)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(behaviorCalls==2&&landCalls==2&&surfaceCalls==2&&context.lastWork.support==2&&occupancyCalls==1);
 /* Mixed surface+LAND masks cannot skip the native ground read. */
 Reset();CertifyCatalog();policy.allowedTerrainMask=449;policy.flags=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 CHECK(behaviorCalls==1&&landCalls==1&&surfaceCalls==1&&work.support==1&&occupancyCalls==1);
 missingTileX=5;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&surfaceCalls==1&&landCalls==1);
 /* Unknown provenance cannot earn a fast negative. */
 Reset();policy.allowedTerrainMask=448;policy.flags=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 CHECK(behaviorCalls==1&&surfaceCalls==1&&landCalls==0&&work.support==0);
 missingTileX=5;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&behaviorCalls==2&&surfaceCalls==1);
 world.catalog=NULL;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&behaviorCalls==2&&surfaceCalls==1);
 /* Every header byte and mismatched catalog is rejected before any lookup. */
 CHECK(sizeof(behaviorData.header)==84);
 for(unsigned i=0;i<sizeof(behaviorData.header);i++) {
  Reset();CertifyCatalog();policy.allowedTerrainMask=448;policy.flags=0;
  ((u8 *)&behaviorData.header)[i]^=1;
  CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
  CHECK(surfaceCalls==0&&behaviorCalls==0&&landCalls==0&&work.support==0&&occupancyCalls==0);
 }
 /* Reject every unaligned address before reading the mixed-field header.
  * The byte immediately after the header is outside this admission check. */
 Reset();CertifyCatalog();
 ((u8 *)&behaviorData)[sizeof(behaviorData.header)]^=1;
 CHECK(CatalogCompatible(&world));
 static union {u32 align;u8 bytes[sizeof(behaviorData)+4];} shiftedBlob;
 for(unsigned shift=1;shift<4;shift++) {
  Reset();CertifyCatalog();policy.allowedTerrainMask=448;policy.flags=0;
  memcpy(shiftedBlob.bytes+shift,&behaviorData,sizeof(behaviorData.header));
  world.behaviorData=(const OverworldWildBehaviorDataBlob *)(shiftedBlob.bytes+shift);
  world.catalog=(const OverworldWildSurfaceCatalog *)(shiftedBlob.bytes+shift
    +__builtin_offsetof(OverworldWildBehaviorDataBlob,surfaceModels));
  CHECK(!CatalogCompatible(&world));
  CHECK(OverworldPickupRouteWild_GetSeams(&world)==NULL);
  CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
  CHECK(surfaceCalls==0&&behaviorCalls==0&&landCalls==0&&work.support==0&&occupancyCalls==0);
 }
 Reset();CertifyCatalog();policy.allowedTerrainMask=448;policy.flags=0;
 world.catalog=(const OverworldWildSurfaceCatalog *)&field;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID&&surfaceCalls==0&&behaviorCalls==0);
 world.catalog=NULL;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID&&surfaceCalls==0&&behaviorCalls==0);
 Reset();CertifyCatalog();policy.allowedTerrainMask=448;policy.flags=0;bare.targetX=20;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED&&surfaceCalls==0&&behaviorCalls==0);
 bare.targetX=5;
 /* The actual real START/placement adapter carries the package proof. */
 Reset();CertifyCatalog();missingTileX=5;
 OverworldPickupRouteWildLandingCall landing={.field=&field,.behaviorData=&behaviorData,.ops=&ops,
  .slot=-1,.allowedTile=448,.x=5,.y=1,.finalTargetX=5,.finalTargetY=1};
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_TERRAIN);
 CHECK(surfaceCalls==1&&behaviorCalls==0&&landCalls==0&&occupancyCalls==0);
 printf("bare Landing package admissions: %d\n",seamsAdmissionCalls);
 CHECK(seamsAdmissionCalls==1);
 landing.behaviorData=NULL;
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE);
 CHECK(surfaceCalls==1&&behaviorCalls==0&&landCalls==0&&occupancyCalls==0&&seamsAdmissionCalls==1);
 Reset();CertifyCatalog();queryHasHit=1;
 queryHit=(OverworldWildSurfaceHit){700,8,OW_WILD_SURFACE_TYPE_ROOFTOP,0};
 landing.behaviorData=&behaviorData;
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 CHECK(seamsAdmissionCalls==1&&surfaceCalls==1&&behaviorCalls==1&&landCalls==0&&occupancyCalls==1);
 Reset();CertifyCatalog();missingTileX=5;landing.state=&state;landing.slot=0;landing.behaviorData=&behaviorData;
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_TERRAIN);
 CHECK(seamsAdmissionCalls==1&&surfaceCalls==2&&behaviorCalls==0&&landCalls==0&&occupancyCalls==0);
 landing.behaviorData=NULL;
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE&&surfaceCalls==2);
 landing.behaviorData=&behaviorData;behaviorData.header.surfaceModelsOffset++;
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE
   && surfaceCalls==2&&seamsAdmissionCalls==2);
 landing.ops=NULL;
 CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE
   && surfaceCalls==2&&seamsAdmissionCalls==3);
 puts("production Terrain wanted-mask: known surface misses skip native reads; valid hits/source/ground/unknown support stay canonical; raw/malformed catalogs cannot prove absence");
 puts("production Wild callbacks: origin/no object writes, full binding/revisions, native Walk, grid, reservations, loaded Hop and caller pickup reach passed");
 puts("production Runtime height/shared Hop: absolute, relative, unavailable/deferred and legacy fallback passed");
 puts("production AtomicPickup: exact claim/current handles, both motion/native guards, height/reach, no cancellation or native writes passed");
 return 0;
}
'''



# Pure-Grass placement cost/decision control using the existing named Wild fixture.
GRASS_DRIVER = r'''

static int Check(void) {
 OverworldPickupRoutePosition output;
 OverworldPickupRouteNativeWork work;
 OverworldPickupRouteNativeLandingCall bare;
 const int nonGrass[]={0,1,4,5,6,7};
 int batchSurface=0,batchBehavior=0;
 for(int x=0;x<8;x++) {
  Reset();CertifyCatalog();policy.allowedTerrainMask=8;policy.flags=0;
  bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
   {4,1,100,0xFFFF,0},x,1,&output,&work};
  int result=OverworldPickupRouteNative_Landing(&bare);
  CHECK(result==(x==2||x==3?OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL:OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED));
  CHECK(behaviorCalls==1&&work.support==(x==2||x==3?1:0)&&occupancyCalls==(x==2||x==3?1:0));
  batchSurface+=surfaceCalls;batchBehavior+=behaviorCalls;
 }
 printf("batch eight: surface=%d behavior=%d\n",batchSurface,batchBehavior);
 for(unsigned n=0;n<sizeof(nonGrass)/sizeof(nonGrass[0]);n++) {
  for(int type=-1;type<5;type++) {
   Reset();CertifyCatalog();policy.allowedTerrainMask=8;policy.flags=0;
   queryHasHit=type>=0;queryHit=(OverworldWildSurfaceHit){700,8,type>=0?type:0,0};
   bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
    {4,1,100,0xFFFF,0},nonGrass[n],1,&output,&work};
   CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
   CHECK(behaviorCalls==1&&work.support==0&&occupancyCalls==0);
  }
 }
 for(int x=2;x<=3;x++) for(int type=-1;type<5;type++) {
  Reset();CertifyCatalog();policy.allowedTerrainMask=8;policy.flags=0;
  queryHasHit=type>=0;queryHit=(OverworldWildSurfaceHit){700,8,type>=0?type:0,0};
  bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
   {4,1,100,0xFFFF,0},x,1,&output,&work};
  CHECK(OverworldPickupRouteNative_Landing(&bare)==(type>=0?OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED:OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL));
  CHECK(surfaceCalls==1&&behaviorCalls==1&&work.support==(type>=0?0:1));
 }
 /* Unknown terrain, malformed/current-owner admission and unloaded world stay exact. */
 Reset();CertifyCatalog();policy.allowedTerrainMask=8;policy.flags=0;missingTileX=5;
 bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),&policy,NULL,&world,NULL,
  {4,1,100,0xFFFF,0},5,1,&output,&work};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&surfaceCalls==0&&work.support==0);
 missingTileX=-1;world.catalog=NULL;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID&&surfaceCalls==0);
 Reset();CertifyCatalog();world.field=NULL;policy.allowedTerrainMask=8;policy.flags=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID&&behaviorCalls==0&&surfaceCalls==0);
 Reset();CertifyCatalog();world.version++;policy.allowedTerrainMask=8;policy.flags=0;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID&&behaviorCalls==0&&surfaceCalls==0);
 for(unsigned n=0;n<sizeof(behaviorData.header);n++) {
  Reset();CertifyCatalog();policy.allowedTerrainMask=8;policy.flags=0;((u8 *)&behaviorData.header)[n]^=1;
  CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID&&behaviorCalls==0&&surfaceCalls==0);
 }
 Reset();policy.allowedTerrainMask=8;policy.flags=0;world.catalog=NULL;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&behaviorCalls==0&&surfaceCalls==0);
 /* Mixed masks and source reads are never covered by the pure-Grass shortcut. */
 Reset();CertifyCatalog();policy.allowedTerrainMask=8|64;policy.flags=0;queryHasHit=1;
 queryHit=(OverworldWildSurfaceHit){700,8,OW_WILD_SURFACE_TYPE_ROOFTOP,0};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&surfaceCalls==1);
 Reset();CertifyCatalog();OverworldPickupRouteNativeTile tile;
 CHECK(Terrain(&world,5,1,0xFFFF,&tile)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&surfaceCalls==1);
 /* Entry resumed cursor yields before its actual read and preserves the catalog guard. */
 Reset();CertifyCatalog();OverworldEntryRouteMemo memo={0};world.entryMemo=&memo;
 CHECK(Terrain(&world,5,1,8,&tile)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&behaviorCalls==0&&surfaceCalls==0);
 memo.budget=2;
 if (EXPECT_FAST_GRASS) {
  CHECK(Terrain(&world,5,1,8,&tile)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&behaviorCalls==1&&memo.used==2&&surfaceCalls==0);
 } else {
  CHECK(Terrain(&world,5,1,8,&tile)==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED&&behaviorCalls==1&&memo.used==2&&surfaceCalls==0);
  memo.budget=4;
  CHECK(Terrain(&world,5,1,8,&tile)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL&&behaviorCalls==1&&surfaceCalls==1);
 }
 puts("actual C: Grass decisions/canonical veto/source/mixed/unknown/current catalog+world/Entry physical budget respected");
 return 0;
}
int main(void) { return Check(); }

'''

def grass_source(wild=None, *, expected_fast=True):
    """Actual tile reducer/Native Landing; named engine seams, not live ownership."""
    source=WILD.read_text() if wild is None else wild
    motion=(ROOT/'include/overworld_motion_model.h').read_text()
    decision=motion[motion.index('typedef enum OverworldMotionDecision {'):motion.index('} OverworldMotionDecision;')+len('} OverworldMotionDecision;')]
    unit=PROLOG.replace('typedef int BOOL;', 'typedef int BOOL;\n#define TRUE 1\n#define FALSE 0').replace('#include "overworld_motion_model.h"',decision)
    unit+='typedef OverworldPickupRouteEdgeResult Result;\n#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL\n#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED\n#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID\n#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED\n'
    # Existing named host seams. Only members read by the production tile reducer.
    unit+=r"""
    typedef struct OverworldEntryRouteTerrainCursor {s16 x,y;u16 wanted;u8 phase,hitValid;OverworldPickupRouteNativeTile tile;OverworldWildSurfaceHit hit;} OverworldEntryRouteTerrainCursor;
    typedef struct OverworldEntryRouteMemo {u8 budget,used;OverworldEntryRouteTerrainCursor terrain;} OverworldEntryRouteMemo;
    static LocalMapObject *InterestObject(const OverworldPickupRouteWildWorld *world) {(void)world;return NULL;}
    static OverworldMotionDecision OverworldActorHopPlanner_PlanTrajectory(OverworldActorHopPlanCall *call) {(void)call;return OVERWORLD_MOTION_DECISION_PROFILE;}
    static Result FixtureBinding(void *raw,const OverworldPickupRouteQuery *query) {
     OverworldPickupRouteWildWorld *w=raw;(void)query;
     return w->field!=NULL?LEGAL:INVALID;
    }
    static Result FixtureSupport(void *raw,const OverworldPickupRoutePosition *origin,s16 x,s16 y,const OverworldPickupRouteNativeTile *tile,s32 *height) {
     (void)raw;(void)x;(void)y;(void)tile;*height=origin->baseY;return LEGAL;
    }
    static Result FixtureOccupancy(void *raw,const OverworldActorHandle *subject,const OverworldPickupRoutePosition *pose,u8 include) {
     (void)raw;(void)subject;(void)pose;(void)include;++occupancyCalls;return LEGAL;
    }
    static Result FixtureEdge(void *raw,const OverworldPickupRouteNativePolicy *policy,u8 kind,const OverworldPickupRoutePosition *from,const OverworldPickupRouteNativeTile *source,const OverworldPickupRoutePosition *to,const OverworldPickupRouteNativeTile *target) {
     (void)raw;(void)policy;(void)kind;(void)from;(void)source;(void)to;(void)target;return LEGAL;
    }
    """
    begin=source.index('static const OverworldWildBehaviorDataBlobHeader sWildExpectedBlobHeader = {')
    end=source.index('static int Abs(',begin)
    unit+=source[begin:end]
    for name,ret in [('TileBudget','BOOL'),('TileStep','Result'),('Terrain','Result')]: unit+=function(source,name,ret)
    unit+=r"""
    static const OverworldPickupRouteNativeSeams sSeams={.binding=FixtureBinding,.terrain=Terrain,.support=FixtureSupport,.occupancy=FixtureOccupancy,.edgePolicy=FixtureEdge};
    """
    body=function(source,'OverworldPickupRouteWild_GetSeams','const OverworldPickupRouteNativeSeams *')
    body=body.replace('static const OverworldPickupRouteNativeSeams * OverworldPickupRouteWild_GetSeams','const OverworldPickupRouteNativeSeams * OverworldPickupRouteWild_GetSeams')
    unit+=body
    fixture=HARNESS.split('int main(void) {',1)[0]
    fixture=fixture.replace('OverworldWildRuntime_ResolveBaseYAt','FixtureHeight')
    unit+='static BOOL FixtureHeight(FieldSystem *f,const OverworldWildSurfaceHit *hit,s32 origin,u32 flags,int x,int y,s32 *height) {(void)f;(void)hit;(void)flags;(void)x;(void)y;*height=origin;return TRUE;}\n'
    unit+=fixture
    # Exercise the actual production TileStep through the actual Native Landing.
    # Native engine callbacks remain the named fixture seams above. No motion test.
    unit+='#define EXPECT_FAST_GRASS '+str(int(expected_fast))+'\n'+GRASS_DRIVER
    return unit

ENTRY_ROOT_DRIVER = r'''
static const OverworldPickupRouteNativeSeams rootSeams={.binding=MemoBinding,.terrain=MemoTerrain,.support=MemoSupport,.occupancy=MemoOccupancy,.edgePolicy=FixtureEdge};
static OverworldEntryRouteMemo memo;
static OverworldEntryRoutePhysical preparedPhysical;
static OverworldPickupRoutePosition output;
static OverworldPickupRouteNativeLandingCall rootCall;
static void SetupRoot(void) {
 Reset();CertifyCatalog();objectsOccupy=1;objects[0].xCurr=4;objects[0].yCurr=1;
 memset(&memo,0,sizeof(memo));memo.native=&sSeams;memo.valid=1;world.entryMemo=&memo;
 rootCall=(OverworldPickupRouteNativeLandingCall){.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,.size=sizeof(rootCall),.policy=&policy,.seams=&rootSeams,.world=&world,.origin={4,1,9,0xFFFF,0},.targetX=4,.targetY=1,.destination=&output};
 policy.flags=0;
}
static int Root(void) {
 SetupRoot();int results[4],reads[4];
 for(int n=0;n<4;n++){memo.cursor=0;memo.budget=8;memo.used=0;results[n]=OverworldPickupRouteNative_Landing(&rootCall);reads[n]=memo.used;}
 printf("root decisions=%d,%d,%d,%d reads=%d,%d,%d,%d ignoredExact=%d\n",results[0],results[1],results[2],results[3],reads[0],reads[1],reads[2],reads[3],observedIgnored==&objects[0]);
 CHECK(results[0]==DEFERRED&&results[1]==DEFERRED&&results[2]==DEFERRED&&results[3]==LEGAL);
 CHECK(reads[0]==8&&reads[1]==1&&reads[2]==8&&reads[3]==1);
 CHECK(observedIgnored==&objects[0]&&observedCollisionIgnored==NULL);
 SetupRoot();world.entryMemo=NULL;rootCall.seams=&sSeams;
 CHECK(OverworldPickupRouteNative_Landing(&rootCall)==BLOCKED&&observedIgnored==NULL);
 SetupRoot();objects[1].xCurr=4;objects[1].yCurr=1;
 int d=DEFERRED;for(int n=0;n<4;n++){memo.cursor=0;memo.budget=8;memo.used=0;d=OverworldPickupRouteNative_Landing(&rootCall);}CHECK(d==BLOCKED&&observedIgnored==&objects[0]);
 SetupRoot();world.subjectObject=world.heightObject=NULL;preparedPhysical=(OverworldEntryRoutePhysical){.flags=50209,.rangeX=-1,.rangeY=-1,.targetX=4,.targetY=1};world.preparedPhysical=&preparedPhysical;
 for(int n=0;n<4;n++){memo.cursor=0;memo.budget=8;memo.used=0;d=OverworldPickupRouteNative_Landing(&rootCall);}CHECK(d==BLOCKED&&observedIgnored==NULL);
 /* Prepared root has no live Subject to ignore. It stays legal only when
  * every actual object is absent, retaining real world occupancy. */
 SetupRoot();world.subjectObject=world.heightObject=NULL;world.preparedPhysical=&preparedPhysical;objects[0].flags=0;
 for(int n=0;n<4;n++){memo.cursor=0;memo.budget=8;memo.used=0;d=OverworldPickupRouteNative_Landing(&rootCall);}CHECK(d==LEGAL);
 SetupRoot();world.field=NULL;memo.budget=8;memo.used=0;
 CHECK(OverworldPickupRouteNative_Landing(&rootCall)==INVALID&&memo.used==0);
 SetupRoot();objects[0].flags=0;memo.budget=8;memo.used=0;
 CHECK(OverworldPickupRouteNative_Landing(&rootCall)==INVALID&&memo.used==0);
 SetupRoot();world.landingPolicy=2;memo.budget=8;memo.used=0;
 CHECK(OverworldPickupRouteNative_Landing(&rootCall)==INVALID&&memo.used==0);
 /* Native Binding with a non-NULL query retains full handle, Field,
  * revision, and landing-policy guards through the Entry wrapper. */
 SetupRoot();query.legalEdge=OverworldPickupRouteNative_Classify;
 CHECK(MemoBinding(&world,&query)==LEGAL);
 query.subject.generation++;CHECK(MemoBinding(&world,&query)==INVALID);
 query.subject.generation--;world.scopeRevision++;CHECK(MemoBinding(&world,&query)==INVALID);
 world.scopeRevision--;world.landingPolicy=1;CHECK(MemoBinding(&world,&query)==INVALID);
 puts("Entry root actual-C controls passed");return 0;
}
int main(void){return Root();}
'''

def entry_root_source(wild, src):
    physical_type=re.search(r'typedef struct OverworldEntryRoutePhysical\s*\{.*?\}\s*OverworldEntryRoutePhysical;', (ROOT/'include/overworld_entry_route.h').read_text(), re.S)
    if physical_type is None: raise AssertionError('actual prepared physical type changed')
    unit=grass_source(wild).split('#define EXPECT_FAST_GRASS',1)[0]
    unit=unit.replace('typedef struct OverworldEntryRouteMemo {u8 budget,used;OverworldEntryRouteTerrainCursor terrain;} OverworldEntryRouteMemo;', '''typedef struct OverworldEntryRouteMemoRead {OverworldPickupRouteNativeTile tile;OverworldWildSurfaceHit hit;s32 height;u8 operation,result,hitValid,reserved;} OverworldEntryRouteMemoRead;
#define OVERWORLD_ENTRY_ROUTE_MEMO_READS 40
#define LIMIT OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT
typedef struct OverworldEntryRouteMemo {u8 budget,used,valid,count,cursor,terminal,reserved;u16 physicalPlayerMask;OverworldEntryRouteTerrainCursor terrain;OverworldEntryRouteMemoRead reads[40];const OverworldPickupRouteNativeSeams *native;} OverworldEntryRouteMemo;''')
    unit=unit.replace('typedef struct OverworldEntryRouteMemoRead {', physical_type.group(0)+'\n'+'typedef struct OverworldEntryRouteMemoRead {',1)
    functions=''
    for name,ret in [('HandleMatches','BOOL'),('Bound','BOOL'),('MountedPlayerPresentation','LocalMapObject *'),('Binding','Result')]:
        f=function(wild,name,ret)
        if name=='Binding': f=f.replace(' Binding(', ' NativeBinding(',1)
        functions+=f
    unit=unit.replace(function(unit,'FixtureBinding','Result'),functions,1)
    unit=unit.replace(function(unit,'FixtureSupport','Result'),function(wild,'Support','Result'),1)
    unit=unit.replace(function(unit,'FixtureOccupancy','Result'),function(wild,'Occupancy','Result'),1)
    unit=unit.replace('.binding=FixtureBinding,.terrain=Terrain,.support=FixtureSupport,.occupancy=FixtureOccupancy', '.binding=NativeBinding,.terrain=Terrain,.support=Support,.occupancy=Occupancy',1)
    funcs=''
    for name,ret in [('Read','OverworldEntryRouteMemoRead *'),('Cached','u8'),('Missing','OverworldPickupRouteEdgeResult'),('Save','void'),('Binding','OverworldPickupRouteEdgeResult'),('Terrain','OverworldPickupRouteEdgeResult'),('Support','OverworldPickupRouteEdgeResult'),('Occupancy','OverworldPickupRouteEdgeResult')]:
        f=function(src,name,ret)
        if name in ('Binding','Terrain','Support','Occupancy'): f=f.replace(' '+name+'(', ' Memo'+name+'(',1)
        funcs+=f
    return unit+funcs+ENTRY_ROOT_DRIVER

def main():
    compiler=shutil.which('cc')
    if not compiler: raise SystemExit('host C compiler required')
    runtime=RUNTIME.read_text();hop=HOP.read_text()
    motion=(ROOT/'include/overworld_motion_model.h').read_text()
    decision=motion[motion.index('typedef enum OverworldMotionDecision {'):motion.index('} OverworldMotionDecision;')+len('} OverworldMotionDecision;')]
    prolog=PROLOG.replace('#include "overworld_motion_model.h"',decision)
    # The fast-path header must be the same compiled84-byte layout used by
    # the loaded Wild owner's actual Resolver admission, not a looser mirror.
    resolver=(ROOT/'lib/overworld/overworld_behavior_resolver.c').read_text()
    expected=resolver[resolver.index('static const OverworldWildBehaviorDataBlobHeader sExpectedBlobHeader = {'):]
    expected=expected[:expected.index('\n};')+3].replace('sExpectedBlobHeader','sWildExpectedBlobHeader')
    if expected not in WILD.read_text():
        raise SystemExit('Wild fast-path header differs from actual Resolver admission')
    unit=prolog+function(runtime,'OverworldWildRuntime_ResolveBaseYAt','BOOL')+function(runtime,'OverworldWildRuntime_GetGroundBaseY','s32')+SEAMS
    geometry_header=(ROOT/'src/pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h').read_text()
    geometry_type=re.search(r'typedef struct OverworldActorHopGeometry\s*\{.*?\}\s*OverworldActorHopGeometry;',geometry_header,re.S)
    if geometry_type is None:
        raise SystemExit('missing production crossed-cell value')
    unit+=geometry_type.group(0)+function((ROOT/'src/pokemon_move_history_overlay/overworld_hop_geometry.c').read_text(),'OverworldActorHopGeometry_NextCell','void')
    unit+=function((ROOT/'src/pokemon_move_history_overlay/overworld_hop_lerp.c').read_text(),'OverworldActorHopPlanner_LerpFx32','s32')+function(hop,'OverworldActorHopPlanner_PlanTrajectory','OverworldMotionDecision')
    wild=WILD.read_text().split('typedef OverworldPickupRouteEdgeResult Result;',1)[1]
    admission='const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *raw)'
    if wild.count(admission)!=1:
        raise SystemExit('actual Wild package-admission function changed')
    # Count entry into the whole actual admission body, including Native's
    # fallback. Only its symbol name changes; no callback/guard is mirrored.
    wild=wild.replace(admission,admission.replace('_GetSeams(', '_HostActualGetSeams('),1)
    unit+=wild+r'''
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *raw) {
    ++seamsAdmissionCalls;
    return OverworldPickupRouteWild_HostActualGetSeams(raw);
}
'''
    landing=(ROOT/'lib/overworld/overworld_pickup_landing_wild.c').read_text()
    landing=re.sub(r'^#include "[^"\n]+"\n','',landing,flags=re.MULTILINE)
    unit=unit.replace('\n#define LEGAL','\ntypedef OverworldPickupRouteEdgeResult Result;\n#define LEGAL',1)+landing+HARNESS
    # This removes only placement attributes from extracted helpers. Bodies and
    # native field access are the current production code, without copied logic.
    with tempfile.TemporaryDirectory(prefix='pickup-wild-') as temporary:
        directory=Path(temporary);check=directory/'check.c';check.write_text(unit);binary=directory/'check'
        command=[compiler,'-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-sign-compare','-O2','-DOVERWORLD_ACTOR_SYSTEM_HOST','-I',str(ROOT/'include')]
        subprocess.run(command+[str(ROOT/'lib/overworld/overworld_pickup_route_native.c'),str(check),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
        mutants={
            'origin height':('position.y=originBaseY;','position.y=9;'),
            'unknown height':('if (world->routeRead) return DEFERRED;','if (world->routeRead) { *height=origin->baseY; return LEGAL; }'),
            'changed Cargo':('|| !Bound(world,system,&query->cargo)',''),
            'future Walk anchor not rebased':('!world->routeRead || (from->x==object->xCurr && from->y==object->yCurr)','1'),
        }
        for name,(old,new) in mutants.items():
            if unit.count(old)!=1:raise SystemExit('mutation boundary changed: '+name)
            check.write_text(unit.replace(old,new))
            subprocess.run(command+[str(ROOT/'lib/overworld/overworld_pickup_route_native.c'),str(check),'-o',str(binary)],check=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            if result.returncode==0:raise SystemExit('failed to reject mutant: '+name)
            print('rejected mutant:',name)
    for filename in (WILD,RUNTIME,HOP,Path(__file__)):
        print(filename.relative_to(ROOT),hashlib.sha256(filename.read_bytes()).hexdigest())


if __name__=='__main__':main()
