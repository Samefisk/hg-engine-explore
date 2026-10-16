#!/usr/bin/env python3
"""Production-C controls for the unlinked origin-aware native edge adapter.

The native seams are stubbed at their read-only boundary. This checks the
actual classifier and route integration, not linked game behavior or pacing.
"""
from pathlib import Path
import hashlib
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "lib/overworld/overworld_pickup_route_native.c"
HEADER = ROOT / "include/overworld_pickup_route_native.h"
HARNESS = r'''
#include "overworld_pickup_route_native.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"native route line%d: %s\n",__LINE__,#x);return 1; } } while(0)
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
#define LIMIT OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT
#define GROUND OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND
typedef OverworldPickupRouteEdgeResult Result;
typedef struct { unsigned vertical; } Lane;
typedef struct {
 OverworldPickupRouteNativeTile tile[5][80];s32 base[5][80];unsigned char body[5][80],reserved[5][80];
 unsigned bindingFail,terrainFail,supportFail,occupancyFail,reservationFail,policyFail,hopFail,reachFail;
 int missingX,missingY,missingSupportX,relativeX,relativeDelta,blockFromBehavior;
 int observedOriginX,observedOriginY,observedBase,observedSourceBehavior,observedTargetBehavior;
 int observedIncludePlayer,observedKind,observedStride,repositionBlocked,obstacle,forceSupportBlocked;
 unsigned calls,supportCalls,hopSamples,liveObjectX,liveObjectY,liveObjectBase;
 unsigned terrainCalls;u16 terrainMasks[8];
} World;
static World world;
static Lane lane;
static OverworldPickupRouteQuery query;
static OverworldPickupRouteNativePolicy policy;
static OverworldPickupRouteNativeContext context;
static unsigned callsBefore;
static Result Binding(void *raw,const OverworldPickupRouteQuery *q) {
 World *w=raw;++w->calls;
 if(q==0) return w->bindingFail?(Result)w->bindingFail:LEGAL;
 if(q->subject.encounterGeneration!=5 || q->cargo.encounterGeneration!=7) return INVALID;
 return w->bindingFail?(Result)w->bindingFail:LEGAL;
}
static Result Terrain(void *raw,s16 x,s16 y,u16 wantedMask,OverworldPickupRouteNativeTile *tile) {
 World *w=raw;++w->calls;
 w->terrainMasks[(w->terrainCalls++)&7]=wantedMask;
 if(w->terrainFail)return (Result)w->terrainFail;
 if(x==w->missingX && y==w->missingY)return DEFERRED;
 *tile=w->tile[y][x];return LEGAL;
}
static Result Support(void *raw,const OverworldPickupRoutePosition *origin,s16 x,s16 y,
 const OverworldPickupRouteNativeTile *tile,s32 *height) {
 World *w=raw;++w->calls;++w->supportCalls;(void)tile;
 w->observedOriginX=origin->x;w->observedOriginY=origin->y;w->observedBase=origin->baseY;
 if(w->supportFail)return (Result)w->supportFail;
 if(w->forceSupportBlocked)return BLOCKED;
 if(x==w->missingSupportX)return DEFERRED;
 *height=x==w->relativeX?origin->baseY+w->relativeDelta:w->base[y][x];return LEGAL;
}
static Result Occupancy(void *raw,const OverworldActorHandle *subject,
 const OverworldPickupRoutePosition *pose,u8 includePlayer) {
 World *w=raw;++w->calls;w->observedIncludePlayer=includePlayer;
 if(subject!=0 && subject->slot!=query.subject.slot)return INVALID;
 if(w->occupancyFail)return (Result)w->occupancyFail;
 if(w->body[pose->y][pose->x])return BLOCKED;
 return includePlayer && (w->tile[pose->y][pose->x].flags&OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER)?BLOCKED:LEGAL;
}
static Result Reservations(void *raw,const OverworldActorHandle *subject,const OverworldPickupRoutePosition *pose) {
 World *w=raw;++w->calls;
 if(subject->fieldEpoch!=query.subject.fieldEpoch)return INVALID;
 if(w->reservationFail)return (Result)w->reservationFail;
 return w->reserved[pose->y][pose->x]?BLOCKED:LEGAL;
}
static Result EdgePolicy(void *raw,const OverworldPickupRouteNativePolicy *p,u8 kind,
 const OverworldPickupRoutePosition *from,const OverworldPickupRouteNativeTile *source,
 const OverworldPickupRoutePosition *to,const OverworldPickupRouteNativeTile *target) {
 World *w=raw;++w->calls;(void)p;(void)from;(void)to;
 if(kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LANDING_ONLY) return w->policyFail?(Result)w->policyFail:LEGAL;
 w->observedSourceBehavior=source->behavior;w->observedTargetBehavior=target->behavior;w->observedKind=kind;
 if(w->policyFail)return (Result)w->policyFail;
 if(source->behavior==w->blockFromBehavior)return BLOCKED;
 if(kind==OVERWORLD_PICKUP_ROUTE_NATIVE_REPOSITION && w->repositionBlocked)return BLOCKED;
 return LEGAL;
}
static Result Hop(void *raw,const OverworldPickupRouteNativePolicy *p,u8 kind,u16 distance,
 const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to) {
 World *w=raw;++w->calls;(void)from;(void)to;
 w->observedKind=kind;w->observedStride=distance;w->hopSamples=2u*(distance-1u);
 if(w->hopFail)return (Result)w->hopFail;
 if(w->obstacle && !((const Lane*)p->resolvedLane)->vertical)return BLOCKED;
 return LEGAL;
}
static Result PickupReach(void *raw,const OverworldPickupRouteNativePolicy *p,
 const OverworldPickupRoutePosition *goal,const OverworldPickupRoutePosition *cargo) {
 World *w=raw;++w->calls;(void)p;
 if(w->reachFail)return (Result)w->reachFail;
 int dx=goal->x-cargo->x,dy=goal->y-cargo->y;
 if(dx<0)dx=-dx;if(dy<0)dy=-dy;
 return dx<=1 && dy<=1 && goal->baseY==cargo->baseY?LEGAL:BLOCKED;
}
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *world) { (void)world; return 0; }
static const OverworldPickupRouteNativeSeams seams={Binding,Terrain,Support,Occupancy,Reservations,EdgePolicy,Hop,PickupReach};
static void Reset(void) {
 memset(&world,0,sizeof(world));memset(&query,0,sizeof(query));memset(&policy,0,sizeof(policy));memset(&context,0,sizeof(context));
 for(int y=0;y<5;y++)for(int x=0;x<80;x++) {
  world.tile[y][x]=(OverworldPickupRouteNativeTile){GROUND,1,(u8)(x+10*y),0,0};world.base[y][x]=64;
 }
 world.missingX=world.missingY=world.missingSupportX=world.relativeX=world.blockFromBehavior=-1;
 world.liveObjectX=0;world.liveObjectY=0;world.liveObjectBase=9;lane.vertical=0;
 query.version=OVERWORLD_PICKUP_ROUTE_VERSION;query.size=sizeof(query);
 query.subject=(OverworldActorHandle){0,2,3,4,5,0};query.cargo=(OverworldActorHandle){1,6,3,4,7,0};
 query.bounds=(OverworldPickupRouteBounds){0,0,79,4};query.origin=(OverworldPickupRoutePosition){0,1,64,GROUND,0};
 query.cargoPosition=(OverworldPickupRoutePosition){7,1,64,GROUND,0};
 query.scopeRevision=query.movementPolicyRevision=query.goalRevision=query.dynamicRevision=1;
 policy.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;policy.size=sizeof(policy);policy.allowedTerrainMask=1;policy.playerTerrainMask=16;
 policy.allowedKinds=15;policy.directions=3;policy.hopMinDistance=1;policy.hopMaxDistance=8;
 policy.flags=OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL|OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE;
 policy.resolvedLane=&lane;
 context.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;context.size=sizeof(context);
 context.query=&query;context.policy=&policy;context.seams=&seams;context.world=&world;
}
static Result Classify(OverworldPickupRoutePosition origin,int dx,int dy,u8 kind,OverworldPickupRoutePosition *out) {
 OverworldPickupRouteEdge edge={(s16)dx,(s16)dy,OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(kind,123)};
 callsBefore=world.calls;
 Result result=OverworldPickupRouteNative_Classify(&context,&origin,&edge,out);
 if(world.calls-callsBefore!=context.lastWork.total) {fprintf(stderr,"seam count differs\n");return INVALID;}
 if(world.liveObjectX!=0 || world.liveObjectY!=0 || world.liveObjectBase!=9) {fprintf(stderr,"live pose changed\n");return INVALID;}
 return result;
}
int main(void) {
 OverworldPickupRoutePosition out={-7,-7,-7,7,0},unchanged=out,origin={4,1,64,GROUND,0};
 Reset();CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL);
 CHECK(out.x==5 && out.y==1 && out.baseY==64 && out.surfaceId==GROUND);
 CHECK(world.observedOriginX==4 && world.observedOriginY==1 && world.observedBase==64);
 CHECK(world.observedSourceBehavior==14 && world.observedTargetBehavior==15 && context.lastWork.total==9);
 CHECK(world.terrainCalls==2&&world.terrainMasks[0]==0xFFFF&&world.terrainMasks[1]==1);
 printf("cardinal Walk:9 bounded seams, hypothetical source=(4,1,64), live source unchanged\n");
 /* A cached live source behavior cannot replace the hypothetical source. */
 world.blockFromBehavior=14;out=unchanged;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED && !memcmp(&out,&unchanged,sizeof(out)));
 Reset();world.tile[1][5].surfaceId=0xFFFE;world.tile[1][5].terrainMask=4;
 policy.allowedTerrainMask=5;world.relativeX=5;world.relativeDelta=128;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL && out.baseY==192 && out.surfaceId==0xFFFE);
 /* Absolute support is not added to the source height. */
 world.relativeX=-1;world.base[1][5]=512;world.tile[1][5].surfaceId=8;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL && out.baseY==512);
 origin.baseY=512;origin.surfaceId=7;world.base[1][4]=512;world.tile[1][4].surfaceId=7;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==BLOCKED);
 world.tile[1][5].surfaceId=GROUND;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==LEGAL);
 Reset();origin=(OverworldPickupRoutePosition){4,1,64,GROUND,0};
 CHECK(Classify(origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL && context.lastWork.total==17);
 CHECK(context.lastWork.terrain==4 && context.lastWork.support==4 && context.lastWork.occupancy==3 && context.lastWork.reservations==1);
 printf("diagonal Walk:17 bounded seams, both corner supports/bodies checked, endpoint reservation only\n");
 for(int side=0;side<2;side++) {
  Reset();world.body[side?2:1][side?4:5]=1;out=unchanged;
  CHECK(Classify(origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED && !memcmp(&out,&unchanged,sizeof(out)));
 }
 Reset();world.reserved[1][5]=world.reserved[2][4]=1;
 CHECK(Classify(origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL);
 world.reserved[2][5]=1;CHECK(Classify(origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED);
 Reset();world.tile[1][5].flags=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_SCRIPTED;policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_AVOID_SCRIPTED;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED);
 Reset();world.tile[1][5].flags=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED);
 policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED); /* Player is not automatically Interest. */
 world.tile[1][5].flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL && world.observedIncludePlayer==0);
 CHECK(Classify(origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED); /* Guard never ignores player. */
 Reset();CHECK(Classify(origin,8,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==LEGAL);
 CHECK(context.lastWork.total==10 && world.hopSamples==14 && world.observedStride==8);
 printf("Hop stride8:10 bounded seams plus14 native clearance fractions, no start/reservation writes\n");
 CHECK(Classify(origin,9,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==BLOCKED);
 CHECK(Classify(origin,2,1,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==BLOCKED);
 policy.directions=1;CHECK(Classify(origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==BLOCKED);
 CHECK(Classify(origin,2,0,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE,&out)==LEGAL && world.observedKind==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);
 CHECK(Classify(origin,2,2,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE,&out)==BLOCKED);
 /* Reposition legality belongs to the origin-aware resolved-policy seam. */
 CHECK(Classify(origin,2,1,OVERWORLD_PICKUP_ROUTE_NATIVE_REPOSITION,&out)==LEGAL);
 world.repositionBlocked=1;CHECK(Classify(origin,2,1,OVERWORLD_PICKUP_ROUTE_NATIVE_REPOSITION,&out)==BLOCKED);
 Reset();world.obstacle=1;CHECK(Classify(origin,4,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==BLOCKED);
 lane.vertical=1;CHECK(Classify(origin,4,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out)==LEGAL);
 /* No hidden Cargo range: origin and Cargo can be more than32 tiles apart. */
 query.cargoPosition.x=79;origin.x=45;
 CHECK(Classify(origin,1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL && out.x==46);
 /* Failed reads/checks propagate without publishing output. */
 for(unsigned stage=0;stage<8;stage++)for(unsigned status=DEFERRED;status<=LIMIT;status++) {
  Reset();out=unchanged;
  switch(stage) {case 0:world.bindingFail=status;break;case 1:world.terrainFail=status;break;
   case 2:world.supportFail=status;break;case 3:world.occupancyFail=status;break;
   case 4:world.reservationFail=status;break;case 5:world.policyFail=status;break;
   case 6:world.hopFail=status;break;default:world.reachFail=status;break;}
  Result r=stage==7?OverworldPickupRouteNative_PickupGoal(&context,6,1,&out):Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,&out);
  CHECK(r==(Result)status && !memcmp(&out,&unchanged,sizeof(out)));
 }
 Reset();world.missingX=5;world.missingY=1;out=unchanged;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==DEFERRED);
 Reset();world.missingSupportX=5;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==DEFERRED);
 world.missingSupportX=-1;world.forceSupportBlocked=1;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID);
 Reset();world.terrainFail=99;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID);
 Reset();query.subject.encounterGeneration++;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID && context.lastWork.total==1);
 Reset();query.subject.fieldEpoch++;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID && context.lastWork.total==0);
 Reset();query.scopeRevision=0;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID);
 Reset();CHECK(Classify((OverworldPickupRoutePosition){4,1,65,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID);
 CHECK(Classify((OverworldPickupRoutePosition){79,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==BLOCKED);
 /* A legal standing goal is beside Cargo, physically reachable and current. */
 Reset();CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&out)==LEGAL && context.lastWork.total==7);
 CHECK(OverworldPickupRouteNative_PickupGoal(&context,7,1,&out)==BLOCKED);
 CHECK(OverworldPickupRouteNative_PickupGoal(&context,5,1,&out)==BLOCKED);
 world.base[1][6]=128;CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&out)==BLOCKED);
 world.base[1][6]=64;world.body[1][6]=1;CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&out)==BLOCKED);
 world.body[1][6]=0;world.reserved[1][6]=1;CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&out)==BLOCKED);
 world.reserved[1][6]=0;world.tile[1][6].flags=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER;
 policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&out)==BLOCKED);
 /* A distant surface origin does not veto an otherwise reachable goal. */
 Reset();query.origin.surfaceId=7;world.tile[1][0].surfaceId=7;
 world.tile[1][6].surfaceId=8;
 CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&out)==LEGAL && out.surfaceId==8);
 printf("pickup standing goal:7 bounded seams, occupied Cargo/player rejected, physical height/reach checked\n");
 /* Real START/placement needs no Cargo or fabricated Actor handle. */
 Reset();query.cargo.generation=0;out=unchanged;
 OverworldPickupRouteNativeLandingCall bare={OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),
  &policy,&seams,&world,0,{4,1,64,GROUND,0},5,2,&out,0};
 CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL && out.x==5 && out.y==2);
 CHECK(Classify(bare.origin,1,1,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==INVALID);
 world.body[1][5]=1;out=unchanged;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==BLOCKED && !memcmp(&out,&unchanged,sizeof(out)));
 world.body[1][5]=0;world.missingSupportX=5;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==DEFERRED);
 world.missingSupportX=-1;policy.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;
 world.blockFromBehavior=14;CHECK(OverworldPickupRouteNative_Landing(&bare)==BLOCKED);
 world.blockFromBehavior=-1;CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL);
 bare.targetY=1;world.blockFromBehavior=14;CHECK(OverworldPickupRouteNative_Landing(&bare)==BLOCKED);
 world.blockFromBehavior=-1;CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL);
 bare.version--;CHECK(OverworldPickupRouteNative_Landing(&bare)==INVALID);
 printf("bare Landing: no Cargo/no invented handle, strict corners and deferred support preserved\n");

 /* Known-disallowed placement terrain must not query support. This is the
  * actual surface-only Hoothoot mask from the measured resumed spawn call. */
 Reset();policy.flags=0;policy.allowedTerrainMask=448;out=unchanged;
 OverworldPickupRouteNativeWork bareWork;
 bare=(OverworldPickupRouteNativeLandingCall){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(bare),
  &policy,&seams,&world,0,{4,1,64,GROUND,0},5,1,&out,&bareWork};
 world.missingSupportX=5;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==BLOCKED && world.supportCalls==0);
 CHECK(world.terrainMasks[0]==448);
 CHECK(bareWork.terrain==1 && bareWork.support==0 && bareWork.total==2 && !memcmp(&out,&unchanged,sizeof(out)));
 /* Unknown terrain remains unknown. A malformed tile stays invalid. */
 world.missingX=5;world.missingY=1;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==DEFERRED && world.supportCalls==0);
 world.missingX=-1;world.tile[1][5].flags=8;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==INVALID && world.supportCalls==0);
 /* Allowed absolute roof and relative canopy preserve support and height. */
 Reset();policy.flags=0;policy.allowedTerrainMask=448;
 world.tile[1][5].terrainMask=128;world.tile[1][5].surfaceId=8;world.base[1][5]=512;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL && out.baseY==512 && world.supportCalls==1);
 world.tile[1][5].terrainMask=64;world.tile[1][5].surfaceId=0xFFFE;
 world.relativeX=5;world.relativeDelta=128;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL && out.baseY==192 && world.supportCalls==2);
 world.missingSupportX=5;out=unchanged;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==DEFERRED && world.supportCalls==3 && !memcmp(&out,&unchanged,sizeof(out)));
 /* Guard removes only Player; a permitted target keeps Player support. */
 Reset();policy.allowedTerrainMask=17;policy.flags=OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL;
 bare.targetY=2;world.tile[1][5].terrainMask=16;world.missingSupportX=5;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==BLOCKED && world.supportCalls==0 && bareWork.total==2);
 CHECK(world.terrainCalls==1&&world.terrainMasks[0]==1);
 policy.flags=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
 bare.targetY=1;world.missingSupportX=-1;world.tile[1][5].flags=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER|OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL && world.supportCalls==1 && world.observedIncludePlayer==0);
 CHECK(world.terrainMasks[1]==17);
 /* Source terrain is not a target veto. Both ordinary and walk-edge source
  * support still run and propagate unavailable support. */
 Reset();world.tile[1][4].terrainMask=16;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==LEGAL && context.lastWork.support==2);
 CHECK(world.terrainMasks[0]==0xFFFF&&world.terrainMasks[1]==1);
 world.missingSupportX=4;
 CHECK(Classify((OverworldPickupRoutePosition){4,1,64,GROUND,0},1,0,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,&out)==DEFERRED && context.lastWork.support==1);
 Reset();policy.flags=OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;bare.targetY=1;
 world.tile[1][4].terrainMask=16;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==LEGAL && bareWork.support==2);
 world.missingSupportX=4;
 CHECK(OverworldPickupRouteNative_Landing(&bare)==DEFERRED && bareWork.support==2);
 printf("known-disallowed Target/Guard: zero support; permitted support/source/unknown/Player unchanged\n");
 /* Same native callback feeds the frozen production route, including detour. */
 Reset();query.bounds=(OverworldPickupRouteBounds){0,0,7,2};world.body[1][1]=world.body[1][2]=1;world.body[1][7]=1;
 static OverworldPickupRouteEdge candidates[]={{1,0,0},{-1,0,1},{0,1,2},{0,-1,3}};
 OverworldPickupRoutePosition goal;CHECK(OverworldPickupRouteNative_PickupGoal(&context,6,1,&goal)==LEGAL);
 OverworldPickupRouteNode nodes[32];OverworldPickupRouteCachedEdge edges[128];OverworldPickupRouteVisited visited[64]={{0}};
 OverworldPickupRouteWorkspace workspace={nodes,edges,visited,32,128,64,0};OverworldPickupRouteState state;OverworldPickupRouteResult route;
 query.edges=candidates;query.edgeCount=4;query.goals=&goal;query.goalCount=1;query.legalEdge=OverworldPickupRouteNative_Classify;query.context=&context;
 CHECK(OverworldPickupRoute_Begin(&state,&query,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 unsigned frames=0;
 do {OverworldPickupRoute_Resume(&state,&query,16,&route);CHECK(route.workUsed<=16 && ++frames<1000);}while(route.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(route.status==OVERWORLD_PICKUP_ROUTE_REACHABLE && route.nextStep.x==0 && route.nextStep.y==2 && route.edgeTag==2);
 printf("frozen production route + native adapter: detour next=(0,2), current tag2, frames%u\n",frames);
 printf("production native adapter origin/terrain/support/diagonal/surface/occupancy/reservation/Hop/goal/deferred controls passed\n");
 return 0;
}
'''
ARM_LAYOUT = r'''
#include "overworld_pickup_route_native.h"
_Static_assert(sizeof(OverworldPickupRouteNativePolicy)==24,"ARM policy");
_Static_assert(sizeof(OverworldPickupRouteNativeTile)==8,"ARM tile");
_Static_assert(sizeof(OverworldPickupRouteNativeWork)==16,"ARM work");
_Static_assert(sizeof(OverworldPickupRouteNativeSeams)==32,"ARM seams");
_Static_assert(sizeof(OverworldPickupRouteNativeContext)==36,"ARM context");
_Static_assert(sizeof(OverworldPickupRouteNativeLandingCall)==44,"ARM landing call");
#include "overworld_pickup_route_wild.h"
_Static_assert(sizeof(OverworldPickupRouteWildOps)==76,"ARM Wild ops");
_Static_assert(sizeof(OverworldPickupRouteWildWorld)==76,"ARM Wild world");
#include "overworld_pickup_landing_wild.h"
_Static_assert(sizeof(OverworldPickupRouteWildLandingCall)==44,"ARM Wild landing call");
'''


def main():
    compiler = shutil.which("cc")
    clang = shutil.which("clang")
    if not compiler or not clang:
        raise SystemExit("host C compiler and ARM-layout clang are required")
    with tempfile.TemporaryDirectory(prefix="pickup-native-") as temporary:
        directory = Path(temporary)
        harness = directory / "check.c"
        harness.write_text(HARNESS)
        binary = directory / "check"
        command = [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
                   "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include")]
        route = ROOT / "lib/overworld/overworld_pickup_route.c"
        subprocess.run(command + [str(SOURCE), str(route), str(harness), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        source = SOURCE.read_text()
        mutants = {
            "hypothetical support origin": ("context->world, origin, x, y, tile, &pose->baseY",
                                            "context->world, origin ? &context->query->origin : origin, x, y, tile, &pose->baseY"),
            "both diagonal guards": ("for (u8 i = 0; i < 2; i++)", "for (u8 i = 0; i < 1; i++)"),
            "endpoint reservation": ("result = Reservation(context, &target);\n    if (result == LEGAL)",
                                     "result = LEGAL;\n    if (result == LEGAL)"),
            "known-disallowed support query": ("if (destinationGuard >= 0) {", "if (0) {"),
            "guard Player retained": ("if (destinationGuard) wantedMask &= ~context->policy->playerTerrainMask;",
                                      "if (0) wantedMask &= ~context->policy->playerTerrainMask;"),
            "source target-veto": ("ReadPose(context, origin, origin->x, origin->y, &source, &sourceTile, -1);",
                                   "ReadPose(context, origin, origin->x, origin->y, &source, &sourceTile, 0);"),
        }
        for name, (old, new) in mutants.items():
            if source.count(old) != 1:
                raise SystemExit("mutation boundary changed: " + name)
            mutant = directory / "mutant.c"
            mutant.write_text(source.replace(old, new))
            subprocess.run(command + [str(mutant), str(route), str(harness), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            if result.returncode == 0:
                raise SystemExit("failed to reject mutant: " + name)
            print("rejected mutant:", name)
        layout = directory / "layout.c"
        layout.write_text(ARM_LAYOUT)
        subprocess.run([clang, "-target", "arm-none-eabi", "-ffreestanding", "-fsyntax-only",
                        "-std=c11", "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include"),
                        str(layout)], check=True)
        print("ARM: Policy24 + Seams32 + Context36 =92 extra persistent bytes; Tile8, Work16 included in Context")
    for filename in (SOURCE, HEADER, Path(__file__)):
        print(filename.relative_to(ROOT), hashlib.sha256(filename.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
