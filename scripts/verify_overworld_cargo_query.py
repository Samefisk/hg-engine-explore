#!/usr/bin/env python3
"""Bounded actual-C Cargo scheduler/route/native controls; no game run.

Reuse the existing native adapter's read-only host seams. All selection,
goal scanning, throttling, graph/search and next-edge code is production C.
"""
from pathlib import Path
import hashlib
import importlib.util
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "lib/overworld/overworld_cargo_query.c"
HEADER = ROOT / "include/overworld_cargo_query.h"
spec = importlib.util.spec_from_file_location("native_controls", ROOT / "scripts/verify_overworld_pickup_route_native.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
PRELUDE = native.HARNESS.split("int main(void)", 1)[0]
HARNESS = r'''
#include "overworld_cargo_query.h"
static OverworldCargoQueryStorage storage;
static OverworldCargoQueryState scheduler;
static OverworldCargoQueryInput input;
static OverworldCargoQueryResult output;
static OverworldBehaviorConditionWorldView bindingsWorld;
static OverworldPickupRouteEdge walkEdges[]={{1,0,0},{-1,0,1},{0,1,2},{0,-1,3}};
static unsigned positionCalls, positionFail;
static OverworldCargoQueryChangedTile changes[513];
static Result ReadPosition(void *raw,const OverworldActorHandle *actor,OverworldPickupRoutePosition *out) {
 World *w=raw;++positionCalls;
 if(positionFail) return (Result)positionFail;
 if(actor->encounterGeneration!=7 && actor->encounterGeneration!=8)return INVALID;
 unsigned n=actor->encounterGeneration==7?0:1;
 const OverworldBehaviorConditionActorObservation *observation=&bindingsWorld.actors[n];
 *out=(OverworldPickupRoutePosition){observation->x,observation->y,w->base[observation->y][observation->x],GROUND,0};
 return LEGAL;
}
static void Setup(int width,int height,int cargoX,int cargoY) {
 Reset();memset(&storage,0,sizeof(storage));memset(&bindingsWorld,0,sizeof(bindingsWorld));
 positionCalls=positionFail=0;
 storage.workspace=(OverworldPickupRouteWorkspace){storage.nodes,storage.edges,storage.visited,256,512,512,0};
 OverworldCargoQuery_Init(&scheduler,&storage);
 query.bounds=(OverworldPickupRouteBounds){0,0,width-1,height-1};query.cargoPosition.x=cargoX;query.cargoPosition.y=cargoY;
 query.edges=walkEdges;query.edgeCount=4;query.origin.y=height>1?1:0;
 bindingsWorld.subject=query.subject;bindingsWorld.subjectX=query.origin.x;bindingsWorld.subjectY=query.origin.y;
 bindingsWorld.actorCount=1;bindingsWorld.subjectRoleMask=1;
 bindingsWorld.actors[0]=(OverworldBehaviorConditionActorObservation){query.cargo,cargoX,cargoY,1,0,3,0};
 input=(OverworldCargoQueryInput){.version=OVERWORLD_CARGO_QUERY_VERSION,.size=sizeof(input),
  .runtime=&context,.bindingsWorld=&bindingsWorld,.seed=&query,.readPosition=ReadPosition,
  .changedTiles=changes,.changesComplete=1,.requestKey=19,.eligibleActorMask=1,.pickupDistance=1,.internalWork=16};
 policy.allowedKinds=1;policy.directions=1;
 world.body[cargoY][cargoX]=1;
}
static int Tick(void) {
 unsigned before=world.calls,positions=positionCalls;
 ++bindingsWorld.frame;
 OverworldCargoQuery_Tick(&scheduler,&input,&output);
 input.changedTileCount=0;
 CHECK(output.lastWork.edgeQueries+output.lastWork.goalQueries<=1);
 CHECK(output.lastWork.positionReads<=1 && positionCalls-positions==output.lastWork.positionReads);
 CHECK(output.lastWork.routeUnits<=input.internalWork);
 CHECK(output.lastWork.witnessProbes<=16*512 && output.lastWork.changeProbes<=512*8);
 CHECK(world.calls-before==output.lastWork.native.total);
 CHECK(context.query==&query && scheduler.runtime==0);
 CHECK(world.liveObjectX==0 && world.liveObjectY==0 && world.liveObjectBase==9);
 CHECK(output.eligibleActorMask==0 || output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
 return 0;
}

static OverworldPickupRouteEdge hopEdges[48];
static void HopSetup(void) {
 Setup(16,5,8,1);query.origin.x=8;query.origin.y=4;bindingsWorld.subjectX=8;bindingsWorld.subjectY=4;
 unsigned n=0;static const signed char dirs[8][2]={{0,-1},{0,1},{-1,0},{1,0},{-1,-1},{1,-1},{-1,1},{1,1}};
 for(unsigned distance=1;distance<=6;distance++)for(unsigned dir=0;dir<8;dir++)
  hopEdges[n++]=(OverworldPickupRouteEdge){dirs[dir][0]*distance,dirs[dir][1]*distance,OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,dir)};
 query.edges=hopEdges;query.edgeCount=48;policy.allowedKinds=1u<<OVERWORLD_PICKUP_ROUTE_NATIVE_HOP;policy.directions=3;
 policy.hopMinDistance=1;policy.hopMaxDistance=6;world.hopFail=0;
}
static int HopFinish(unsigned limit,unsigned *updates) {
 unsigned n=0;do{CHECK(!Tick());CHECK(++n<limit);}while(output.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE);*updates=n;return 0;
}
static int ColdHopPursuit(void) {
 unsigned frames;HopSetup();CHECK(!HopFinish(256,&frames));
 printf("cold48-hop: updates%u nodes%u goal(%d,%d) next(%d,%d)\n",frames,scheduler.route.nodeCount,output.route.pickupPosition.x,output.route.pickupPosition.y,output.route.nextStep.x,output.route.nextStep.y);
 CHECK(frames<=5);CHECK(output.route.pickupPosition.x==8 && output.route.pickupPosition.y==2);
 /* Nearest standing goal is blocked: whole original pickup-square remains. */
 HopSetup();world.body[2][8]=1;CHECK(!HopFinish(512,&frames));
 CHECK(output.route.pickupPosition.x!=8 || output.route.pickupPosition.y!=2);
 CHECK(output.route.pickupPosition.x>=7 && output.route.pickupPosition.x<=9 && output.route.pickupPosition.y<=2);
 printf("blocked-nearest: updates%u goal(%d,%d)\n",frames,output.route.pickupPosition.x,output.route.pickupPosition.y);
 /* Unknown height may never grant an edge/goal or Cargo eligibility. */
 HopSetup();world.supportFail=DEFERRED;for(unsigned n=0;n<12;n++){CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask && !output.route.hasNextStep);}
 /* Invalid identity and native resource result retain terminal reasons. */
 HopSetup();bindingsWorld.actors[0].actor.encounterGeneration=99;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID);
 HopSetup();world.reachFail=LIMIT;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT);
 puts("PASS priority fallback, unknown height, identity, resource; all per-Tick budgets preserved");return 0;}

static int Finish(unsigned limit,unsigned *frames,OverworldPickupRouteStatus expected) {
 unsigned n=0;do {CHECK(!Tick());CHECK(++n<limit);}while(output.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(output.status==expected);if(frames)*frames=n;return 0;
}
static int SparseMoving(unsigned moveSubject,unsigned distant) {
 Setup(distant?73:8,3,distant?72:7,1);unsigned edges=0,goals=0,frame;
 for(frame=0;frame<512;frame++) {
  changes[0]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[0].x,bindingsWorld.actors[0].y};
  world.body[bindingsWorld.actors[0].y][bindingsWorld.actors[0].x]=0;
  bindingsWorld.actors[0].x=(s16)((distant?71:6)+(frame&1));
  world.body[1][bindingsWorld.actors[0].x]=1;
  changes[1]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[0].x,1};
  input.changedTileCount=2;
  if(moveSubject) {
   /* Native occupancy excludes only this validated Subject; its origin still
    * changes and must be found on the current forward predecessor path. */
   query.origin.x=(s16)(frame&1);bindingsWorld.subjectX=query.origin.x;
  }
  ++query.dynamicRevision;bindingsWorld.frame+=15;
  CHECK(!Tick());edges+=output.lastWork.edgeQueries;goals+=output.lastWork.goalQueries;
  if(output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE)break;
  CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 }
 printf("Sparse16 moving-every-Tick: frames%u edges%u goals%u phase%u nodes%u status%u\n",
  frame+1,edges,goals,scheduler.route.phase,scheduler.route.nodeCount,output.status);
 CHECK(frame<512 && edges>0 && goals>0);
 CHECK(output.eligibleActorMask==1 && output.route.hasNextStep);
 CHECK((output.route.nextStep.x!=query.origin.x || output.route.nextStep.y!=query.origin.y)
  && output.route.nextStep.x>=query.origin.x-1 && output.route.nextStep.x<=query.origin.x+1
  && output.route.nextStep.y>=query.origin.y-1 && output.route.nextStep.y<=query.origin.y+1);
 CHECK(output.route.origin.x==query.origin.x && output.route.origin.y==query.origin.y);
 CHECK(output.route.cargoPosition.x==bindingsWorld.actors[0].x);
 CHECK(output.route.cargo.encounterGeneration==7 && output.route.dynamicRevision==query.dynamicRevision);
 CHECK(!scheduler.goalDirty && scheduler.checkedDynamicRevision==query.dynamicRevision);
 CHECK(output.route.pickupPosition.x!=bindingsWorld.actors[0].x || output.route.pickupPosition.y!=1);
 CHECK(output.route.pickupPosition.x>=bindingsWorld.actors[0].x-1 && output.route.pickupPosition.x<=bindingsWorld.actors[0].x+1);
 CHECK(output.route.pickupPosition.y>=0 && output.route.pickupPosition.y<=2);
 return 0;
}
static int SuffixChange(void) {
 Setup(73,1,72,0);input.internalWork=4;unsigned frame;
 for(frame=0;frame<4000;frame++) {
  CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING);
  if(scheduler.route.phase==OVERWORLD_PICKUP_ROUTE_PHASE_PROOF && scheduler.route.proofLength>=8)break;
 }
 CHECK(frame<4000);
 const OverworldPickupRouteNode *goal=&storage.nodes[scheduler.route.goalNode];
 CHECK(goal->parent< scheduler.route.nodeCount);
 OverworldPickupRoutePosition blocked=storage.nodes[goal->parent].position;
 world.body[blocked.y][blocked.x]=1;++query.dynamicRevision;
 changes[0]=(OverworldCargoQueryChangedTile){blocked.x,blocked.y};input.changedTileCount=1;
 CHECK(!Tick());CHECK(!output.eligibleActorMask);
 CHECK(!Finish(4000,0,OVERWORLD_PICKUP_ROUTE_UNREACHABLE));
 CHECK(!output.eligibleActorMask);
 puts("Changed checked suffix rejects its old directed route");return 0;
}
static int WitnessStampChecks(void) {
 Setup(8,3,7,1);CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 OverworldPickupRouteState saved=scheduler.route;OverworldPickupRouteQuery current=scheduler.query;
 current.dynamicRevision++;
 scheduler.route.reserved[0]=OVERWORLD_PICKUP_ROUTE_PROOF_SUFFIX_CURRENT;scheduler.route.hashIndex=current.dynamicRevision;
 CHECK(OverworldPickupRoute_Resume(&scheduler.route,&current,0,&output.route)==OVERWORLD_PICKUP_ROUTE_REACHABLE);
 CHECK(!scheduler.route.reserved[0] && scheduler.route.proofRevision==current.dynamicRevision);
 scheduler.route=saved;scheduler.route.reserved[0]=OVERWORLD_PICKUP_ROUTE_PROOF_SUFFIX_CURRENT;
 scheduler.route.hashIndex=current.dynamicRevision+1;
 CHECK(OverworldPickupRoute_Resume(&scheduler.route,&current,0,&output.route)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!output.route.hasNextStep && !scheduler.route.reserved[0]);
 scheduler.route=saved;scheduler.route.reserved[0]=2;scheduler.route.hashIndex=current.dynamicRevision;
 CHECK(OverworldPickupRoute_Resume(&scheduler.route,&current,0,&output.route)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!output.route.hasNextStep && !scheduler.route.reserved[0]);
 puts("Current suffix witness consumed once; wrong revision/unknown flags cannot retain completion");return 0;
}
static int PromoteSameCargo(void) {
 Setup(12,3,11,1);CHECK(!Finish(1000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 CHECK(!scheduler.required && output.eligibleActorMask==1 && output.route.hasNextStep);
 u32 generation=storage.workspace.generation,stamp=scheduler.route.searchStamp;
 u16 nodes=scheduler.route.nodeCount;OverworldPickupRoutePosition next=output.route.nextStep;
 input.requiredCargo=&bindingsWorld.actors[0].actor;
 CHECK(!Tick());
 printf("same Cargo promotion: priorNodes%u nodes%u generation%u->%u searchStamp%u->%u status%u required%u\n",
  nodes,scheduler.route.nodeCount,generation,storage.workspace.generation,stamp,scheduler.route.searchStamp,output.status,scheduler.required);
 CHECK(storage.workspace.generation==generation && scheduler.route.searchStamp==stamp && scheduler.route.nodeCount==nodes);
 CHECK(scheduler.required && output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE && output.eligibleActorMask==1);
 CHECK(!memcmp(&output.route.nextStep,&next,sizeof(next)) && output.route.hasNextStep);
 CHECK(!memcmp(&output.route.cargo,&bindingsWorld.actors[0].actor,sizeof(output.route.cargo)));
 CHECK(output.route.origin.x==query.origin.x && output.route.origin.y==query.origin.y && output.route.dynamicRevision==query.dynamicRevision);
 CHECK(!scheduler.goalDirty && scheduler.checkedDynamicRevision==query.dynamicRevision);
 return 0;
}

static void CurrentOrigin(int x,int y) {query.origin.x=x;query.origin.y=y;bindingsWorld.subjectX=x;bindingsWorld.subjectY=y;}
static int CurrentGoal(void) {
 Setup(8,3,4,1);CurrentOrigin(3,1);input.requiredCargo=&bindingsWorld.actors[0].actor;
 CHECK(!Finish(300,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 printf("near current: goal(%d,%d) origin(%d,%d) next=%u total%u\n",output.route.pickupPosition.x,output.route.pickupPosition.y,output.route.origin.x,output.route.origin.y,output.route.hasNextStep,world.calls);
 CHECK(!output.route.hasNextStep && output.route.pickupPosition.x==3 && output.route.pickupPosition.y==1);
 CHECK(output.eligibleActorMask==1 && output.route.cargo.encounterGeneration==7);
 return 0;
}
static int EnterRange(void) {
 Setup(8,3,7,1);input.requiredCargo=&bindingsWorld.actors[0].actor;
 CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));CHECK(output.route.hasNextStep);
 CurrentOrigin(6,1);++query.dynamicRevision;changes[0]=(OverworldCargoQueryChangedTile){0,1};changes[1]=(OverworldCargoQueryChangedTile){6,1};input.changedTileCount=2;
 CHECK(!Finish(300,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 CHECK(!output.route.hasNextStep && output.route.origin.x==6 && output.route.pickupPosition.x==6 && output.route.pickupPosition.y==1);
 puts("pursuit enters legal reach: current native standing goal, no extra START");return 0;
}
static int RejectCurrent(void) {
 Setup(8,3,4,1);CurrentOrigin(3,1);world.reserved[1][3]=1;
 CHECK(!Finish(300,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));CHECK(output.route.hasNextStep);
 CHECK(output.route.pickupPosition.x!=3 || output.route.pickupPosition.y!=1);
 puts("blocked current goal resumes all ordinary goals, no starvation");
 Setup(8,3,4,1);CurrentOrigin(3,1);world.missingX=3;world.missingY=1;
 for(unsigned n=0;n<5;n++){CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);CHECK(output.lastWork.goalQueries==1);}
 world.missingX=world.missingY=-1;CHECK(!Finish(300,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));CHECK(!output.route.hasNextStep);
 Setup(8,3,4,1);CurrentOrigin(3,1);world.reachFail=DEFERRED;
 CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
 world.reachFail=INVALID;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID && !output.eligibleActorMask);
 Setup(8,3,4,1);CurrentOrigin(3,1);OverworldActorHandle wrong=bindingsWorld.actors[0].actor;wrong.encounterGeneration++;input.requiredCargo=&wrong;
 CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID && !output.eligibleActorMask && !output.lastWork.goalQueries);
 puts("current goal still requires native availability, reach and full Cargo identity");return 0;
}
int main(void) {
 CHECK(!ColdHopPursuit());
 CHECK(!PromoteSameCargo()); CHECK(!CurrentGoal());CHECK(!EnterRange());CHECK(!RejectCurrent());
 CHECK(!WitnessStampChecks());CHECK(!SuffixChange());
 CHECK(!SparseMoving(0,1));CHECK(!SparseMoving(0,0));CHECK(!SparseMoving(1,0));CHECK(!SparseMoving(1,1));
 /* Moving onto the retained exploratory goal needs a fresh goal, not INVALID. */
 Setup(8,3,7,1);CHECK(!Tick());CHECK(scheduler.goalValid);
 changes[0]=(OverworldCargoQueryChangedTile){7,1};world.body[1][7]=0;
 bindingsWorld.actors[0].x=scheduler.goal.x;bindingsWorld.actors[0].y=scheduler.goal.y;
 world.body[scheduler.goal.y][scheduler.goal.x]=1;changes[1]=(OverworldCargoQueryChangedTile){scheduler.goal.x,scheduler.goal.y};
 input.changedTileCount=2;++query.dynamicRevision;
 CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
 CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 CHECK(output.route.cargoPosition.x==bindingsWorld.actors[0].x && output.route.cargoPosition.y==bindingsWorld.actors[0].y);
 CHECK(!scheduler.goalDirty && scheduler.checkedDynamicRevision==query.dynamicRevision);
 unsigned frames;
 Setup(8,3,7,1);world.body[1][1]=world.body[1][2]=1;for(int x=0;x<8;x++)world.body[0][x]=1;
 CHECK(!Finish(2000,&frames,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 CHECK(output.eligibleActorMask==1 && output.route.hasNextStep && output.route.nextStep.x==0 && output.route.nextStep.y==2);
 CHECK(output.route.edgeTag==2 && output.route.cargo.encounterGeneration==7);
 printf("Cargo detour: frames%u next(%d,%d) tag%u, one native edge/goal per frame\n",frames,output.route.nextStep.x,output.route.nextStep.y,output.route.edgeTag);
 unsigned before=world.calls,positions=positionCalls;
 CHECK(OverworldCargoQuery_Tick(&scheduler,&input,&output)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!output.eligibleActorMask && !output.lastWork.native.total && world.calls==before && positionCalls==positions);
 Setup(73,5,72,1);CHECK(!Finish(4000,&frames,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 CHECK(output.route.pickupPosition.x==71 && output.route.visitedNodes<100 && output.route.nextStep.x==1);
 printf("Cargo distant open73x5: frames%u nodes%u, no distance cap\n",frames,output.route.visitedNodes);
 /* Real scheduler cadence: both endpoints and relevant occupancy every8
  * frames; no still/idle admission. Per-frame quota stays exactly one. */
 Setup(80,5,74,1);unsigned moves=0,frame;
 for(frame=0;frame<2000;frame++) {
  if(frame && frame%8==0) {
   changes[0]=(OverworldCargoQueryChangedTile){query.origin.x,query.origin.y};
   changes[1]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[0].x,bindingsWorld.actors[0].y};
   ++moves;world.body[bindingsWorld.actors[0].y][bindingsWorld.actors[0].x]=0;
   query.origin.x=(s16)(moves%12);bindingsWorld.subjectX=query.origin.x;
   bindingsWorld.actors[0].x=(s16)(74+(moves&1));bindingsWorld.actors[0].y=(s16)(1+(moves&1));
   world.body[bindingsWorld.actors[0].y][bindingsWorld.actors[0].x]=1;
   changes[2]=(OverworldCargoQueryChangedTile){query.origin.x,query.origin.y};
   changes[3]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[0].x,bindingsWorld.actors[0].y};input.changedTileCount=4;
   ++query.goalRevision;++query.dynamicRevision;
  }
  CHECK(!Tick());if(output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE)break;
  CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 }
 if(frame==2000) printf("RED global revision: frames2000 moves%u nodes%u phase%u proofLength%u actualEdgeQueries%u pending; quota1 cannot finish whole-path invalidation every8\n",moves,scheduler.route.nodeCount,scheduler.route.phase,scheduler.route.proofLength,scheduler.route.edgeCalls);
 CHECK(frame<2000 && moves>=2 && output.route.origin.x==query.origin.x);
 CHECK(output.route.cargoPosition.x==bindingsWorld.actors[0].x && output.route.cargoPosition.y==bindingsWorld.actors[0].y);
 CHECK(output.route.dynamicRevision==query.dynamicRevision && output.eligibleActorMask==1);
 CHECK(output.route.hasNextStep && output.route.nextStep.x==query.origin.x+1);
 printf("Cargo+Subject move every8/work16/one edge: frames%u moves%u nodes%u next%d\n",frame+1,moves,output.route.visitedNodes,output.route.nextStep.x);
 /* Current occupancy invalidates a formerly accepted next step. */
 Setup(8,3,7,1);CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));CHECK(output.route.nextStep.x==1);
 world.body[1][1]=1;query.dynamicRevision++;changes[0]=(OverworldCargoQueryChangedTile){1,1};input.changedTileCount=1;
 CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));CHECK(output.route.nextStep.x==0 && output.route.nextStep.y!=1);
 /* Directed native edges: a moved origin cannot inherit the old root's
  * forward graph as a reverse route to newly moved Cargo. */
 Setup(8,1,7,0);world.oneWay=1;CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 query.origin.x=7;bindingsWorld.subjectX=7;
 world.body[0][7]=0;world.body[0][2]=1;bindingsWorld.actors[0].x=2;
 query.dynamicRevision++;
 changes[0]=(OverworldCargoQueryChangedTile){0,0};changes[1]=(OverworldCargoQueryChangedTile){7,0};
 changes[2]=(OverworldCargoQueryChangedTile){2,0};input.changedTileCount=3;
 CHECK(!Finish(4000,0,OVERWORLD_PICKUP_ROUTE_UNREACHABLE));CHECK(!output.eligibleActorMask);
 /* Candidate0 has no legal standing pose. Candidate1 is selected only after
  * its current route proof, and mask is observation1 rather than actor slot. */
 Setup(8,3,2,1);bindingsWorld.actorCount=2;input.eligibleActorMask=3;
 for(int y=0;y<3;y++)for(int x=1;x<=3;x++)world.body[y][x]=1;
 bindingsWorld.actors[1]=(OverworldBehaviorConditionActorObservation){{5,6,3,4,8,0},7,1,1,0,3,0};
 world.body[1][7]=1;
 /* Route to candidate1 is reachable via a Hop over the closed first island. */
 static OverworldPickupRouteEdge hopEdges[]={{4,0,OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,5)},{1,0,0},{-1,0,1},{0,1,2},{0,-1,3}};
 query.edges=hopEdges;query.edgeCount=5;policy.allowedKinds=3;
 /* Native host binding has exact allowed candidate identities. */
 CHECK(!Finish(4000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));CHECK(output.eligibleActorMask==2 && output.route.cargo.slot==5);
 printf("Candidate scan preserves observation mask; no eligibility before reachability\n");
 /* A required stale Cargo never falls back to a different eligible actor. */
 input.requiredCargo=&bindingsWorld.actors[1].actor;
 CHECK(!Finish(4000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 OverworldActorHandle missing=*input.requiredCargo;missing.encounterGeneration++;
 input.requiredCargo=&missing;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID && !output.eligibleActorMask);
 Setup(8,3,7,1);positionFail=DEFERRED;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
 positionFail=0;world.missingX=6;world.missingY=0;
 CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
 world.missingX=world.missingY=-1;CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_REACHABLE));
 Setup(8,1,7,0);world.body[0][1]=1;CHECK(!Finish(4000,0,OVERWORLD_PICKUP_ROUTE_UNREACHABLE));CHECK(!output.eligibleActorMask);
 Setup(8,3,7,1);storage.workspace.nodeCapacity=1;CHECK(!Finish(2000,0,OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT));
 Setup(8,3,7,1);input.internalWork=0;CHECK(!Tick());CHECK(!output.lastWork.native.total && !positionCalls);
 input.internalWork=17;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID);
 Setup(8,3,7,1);CHECK(!Tick());unsigned generation=storage.workspace.generation;
 bindingsWorld.subjectRoleMask=2;CHECK(!Tick());CHECK(scheduler.roleMask==2 && storage.workspace.generation>=generation);
 input.readPosition=0;CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID);
 OverworldCargoQuery_Clear(&scheduler);CHECK(!scheduler.runtime && !scheduler.route.query.legalEdge && !scheduler.query.legalEdge);
 printf("Cargo scheduler identity/role/occupancy/deferred/no-route/resource/quota/lifecycle controls passed\n");return 0;
}
'''
LEDGER_HARNESS = r'''
#include "overworld_cargo_query.c"
#include <stdio.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"ledger line%d: %s\n",__LINE__,#x);return 1;}}while(0)
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *world) {(void)world;return 0;}
int main(void) {
 OverworldCargoQueryStorage storage={0};OverworldCargoQueryState s;
 OverworldCargoQueryChangedTile tiles[513]={{1,0}};
 OverworldCargoQueryInput input={.changedTiles=tiles,.changesComplete=1};
 OverworldCargoQuery_Init(&s,&storage);
 OverworldPickupRoutePosition from={0,0,64,0xFFFF,0},to={2,2,64,0xFFFF,0};
 s.query.dynamicRevision=1;CHECK(Observe(&s,&input));CHECK(Unchanged(&s,&from,&to,1));
 s.query.dynamicRevision=2;input.changedTileCount=1;
 CHECK(Observe(&s,&input));CHECK(!Unchanged(&s,&from,&to,1)); /* Diagonal side guard. */
 to=(OverworldPickupRoutePosition){4,0,128,7,0};
 CHECK(!Unchanged(&s,&from,&to,1)); /* Hop corridor, height ignored conservatively. */
 CHECK(Unchanged(&s,&from,&to,2));
 /* Repeated updates coalesce at one tile; an unrelated tile permits reuse. */
 s.query.dynamicRevision=3;tiles[0]=(OverworldCargoQueryChangedTile){20,20};
 CHECK(Observe(&s,&input));CHECK(Unchanged(&s,&from,&to,2));
 /* Force nine colliding keys into an eight-probe set, evicting old history.
  * Old receipt becomes unknown even when its changed tile is no longer stored. */
 s.query.dynamicRevision=4;input.changedTileCount=9;
 for(int n=0;n<9;n++)tiles[n]=(OverworldCargoQueryChangedTile){(s16)(1+512*n),0};
 CHECK(Observe(&s,&input));CHECK(s.evictionFloor>=4 && !Unchanged(&s,&from,&to,2));
 s.query.dynamicRevision=5;input.changesComplete=0;input.changedTileCount=0;
 CHECK(Observe(&s,&input));CHECK(!Unchanged(&s,&from,&to,5));
 s.query.dynamicRevision=6;input.changesComplete=1;input.changedTileCount=513;
 CHECK(Observe(&s,&input));CHECK(!s.changesKnown && !Unchanged(&s,&from,&to,6));
 input.changedTileCount=0;s.query.dynamicRevision=7;
 CHECK(Observe(&s,&input));CHECK(!Unchanged(&s,&from,&to,5));CHECK(Unchanged(&s,&from,&to,7));
 input.changedTileCount=1;CHECK(!Observe(&s,&input)); /* Facts changed without revision. */
 unsigned gen=storage.changeGeneration;OverworldCargoQuery_Clear(&s);
 CHECK(storage.changeGeneration==gen+1 && !s.runtime && !s.route.query.legalEdge);
 storage.changeGeneration=0xFFFFFFFFu;s.query.dynamicRevision=8;input.changedTileCount=0;
 CHECK(Observe(&s,&input));CHECK(!Unchanged(&s,&from,&to,8));
 puts("production ledger coalescing/guard/Hop/eviction/unknown/overflow/generation controls passed");return 0;
}
'''


def main():
    cc = shutil.which("cc")
    clang = shutil.which("clang")
    if not cc or not clang:
        raise SystemExit("host compiler and ARM layout clang are required")
    # Keep the existing native seam behavior, allowing exactly the second
    # candidate identity used by this scheduler fixture. No query logic mock.
    prelude = PRELUDE.replace("q->cargo.encounterGeneration!=7", "(q->cargo.encounterGeneration!=7 && q->cargo.encounterGeneration!=8)")
    prelude = prelude.replace("unsigned calls,supportCalls,hopSamples", "int oneWay;unsigned calls,supportCalls,hopSamples")
    prelude = prelude.replace("w->observedSourceBehavior=source->behavior;", "if(w->oneWay && (to->x<=from->x || to->y!=from->y))return BLOCKED;\n w->observedSourceBehavior=source->behavior;")
    prelude = prelude[:prelude.index("static Result Classify(")].replace("static unsigned callsBefore;\n", "")
    with tempfile.TemporaryDirectory(prefix="cargo-query-") as temporary:
        directory = Path(temporary)
        harness = directory / "check.c"
        harness.write_text(prelude + HARNESS)
        binary = directory / "check"
        command = [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                   "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include")]
        native_source = ROOT / "lib/overworld/overworld_pickup_route_native.c"
        route_source = ROOT / "lib/overworld/overworld_pickup_route.c"
        subprocess.run(command + [str(SOURCE), str(native_source), str(route_source), str(harness), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        ledger = directory / "ledger.c"
        ledger.write_text(LEDGER_HARNESS)
        subprocess.run(command + ["-I", str(ROOT / "lib/overworld"), str(native_source), str(route_source),
                                  str(ledger), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        source = SOURCE.read_text()
        mutants = {
            "one native unit per frame": ("if(s->unitUsed) { s->edgeOwed=2;return DEFERRED; }", "if(s->unitUsed>3) { s->edgeOwed=2;return DEFERRED; }"),
            "full Cargo encounter identity": ("#define Handle(a,b) Equal(a,b,12)", "#define Handle(a,b) Equal(a,b,8)"),
            "eligibility only after proof": ("else if(status==REACHABLE) {", "else if(status==PENDING || status==REACHABLE) {"),
            "changed-edge corridor witness": ("&& Touches(tile->x,tile->y,from,to)) return 0;", "&& Touches(tile->x,tile->y,from,to) && 0) return 0;"),
            "changed checked suffix": ("ProofUnchanged(s,(u16)(work*OVERWORLD_CARGO_QUERY_CHANGES))", "(ProofUnchanged(s,(u16)(work*OVERWORLD_CARGO_QUERY_CHANGES)),1)"),
        }
        for name, (old, new) in mutants.items():
            if source.count(old) != 1:
                raise SystemExit("mutation boundary changed: " + name)
            mutant = directory / "mutant.c"
            mutant.write_text(source.replace(old, new))
            subprocess.run(command + [str(mutant), str(native_source), str(route_source), str(harness), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            if result.returncode == 0:
                raise SystemExit("failed to reject mutant: " + name)
            print("rejected mutant:", name)
        layout = directory / "layout.c"
        layout.write_text('#include "overworld_cargo_query.h"\n'
                          '_Static_assert(sizeof(OverworldCargoQueryStorage)==24604,"ARM storage");\n'
                          '_Static_assert(sizeof(OverworldCargoQueryState)==416,"ARM state");\n'
                          '_Static_assert(sizeof(OverworldCargoQueryInput)==40,"ARM input");\n'
                          '_Static_assert(sizeof(OverworldCargoQueryResult)==140,"ARM result");\n')
        layouts = subprocess.run([clang, "-target", "arm-none-eabi", "-ffreestanding", "-fsyntax-only", "-std=c11",
                                  "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include"),
                                  "-Xclang", "-fdump-record-layouts", str(layout)], capture_output=True, text=True, check=True).stdout
        for name in ("OverworldCargoQueryState", "OverworldCargoQueryInput", "OverworldCargoQueryResult", "OverworldCargoQueryWork"):
            marker = "| struct " + name + "\n"
            if marker not in layouts:
                raise SystemExit("missing ARM layout: " + name)
            section = layouts.split(marker, 1)[1].split("*** Dumping", 1)[0]
            print(name, section.split("[sizeof=", 1)[1].split("]", 1)[0])
    for file in (SOURCE, HEADER, Path(__file__)):
        print(file.relative_to(ROOT), hashlib.sha256(file.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
