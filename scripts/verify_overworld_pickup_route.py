#!/usr/bin/env python3
"""Focused production-C check for the unlinked pickup route query; no game run.

Retained pre-correction red (source SHA 9d5378a1cbf4dd70b51d37c660efada461b2aefb83d3e6a5c4a3ef43573f861c):
96 frames, endpoints every8/work16/H512 ->11restarts,clear128/512,0edges,0nodes.
Static open73x8/N256/work16 ->222frames,RESOURCE_LIMIT,256nodes,maxX34,923edges,3538work.
Detour ->goal(3,1),13nodes, no predecessor or nextStep API.
"""
from pathlib import Path
import hashlib
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "lib/overworld/overworld_pickup_route.c"
HEADER = ROOT / "include/overworld_pickup_route.h"
HARNESS = r'''
#include "overworld_pickup_route.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"pickup route line%d: %s\n",__LINE__,#x);return 1; } } while(0)
typedef struct { char cells[80][80];unsigned calls;int cargoX,cargoY,deferred,invalid,resource,wrongXY,oneway,layered,blockExact,wrongExactHeight; } World;
static OverworldPickupRouteEdge candidates[]={{1,0,10},{-1,0,11},{0,1,12},{0,-1,13}};
static OverworldPickupRoutePosition goals[3];
static OverworldPickupRouteNode nodes[256];
static OverworldPickupRouteCachedEdge cache[512];
static OverworldPickupRouteVisited table[512];
static OverworldPickupRouteWorkspace workspace={nodes,cache,table,256,512,512,0};
static OverworldPickupRouteState state;
static OverworldPickupRouteResult result;
static OverworldPickupRouteEdgeResult Legal(void *context,const OverworldPickupRoutePosition *from,
 const OverworldPickupRouteEdge *edge,OverworldPickupRoutePosition *to)
{
 World *world=context;++world->calls;
 if(edge->tag==30 && (world->blockExact || world->wrongExactHeight)) {
  if(world->blockExact)return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
  to->baseY=128;to->surfaceId=8;return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL;
 }
 if(world->deferred) return OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED;
 if(world->invalid) return (OverworldPickupRouteEdgeResult)world->invalid;
 if(world->resource) return OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT;
 if(world->wrongXY) { ++to->x;return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL; }
 if(world->layered) {
  if(from->x==0 && to->x==1) {to->baseY=edge->tag?128:0;to->surfaceId=edge->tag?8:0;return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL;}
  if(from->x==1 && from->baseY==128 && from->surfaceId==8 && to->x==2) {to->baseY=128;to->surfaceId=8;return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL;}
  return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
 }
 if(world->oneway && (edge->dx!=1 || edge->dy!=0)) return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
 if(world->cells[to->y][to->x]=='#' || (to->x==world->cargoX && to->y==world->cargoY)) return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
 to->baseY=from->baseY;to->surfaceId=from->surfaceId;return OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL;
}
static OverworldPickupRouteQuery Query(World *world,int width,int height)
{
 OverworldPickupRouteQuery q={0};memset(world,0,sizeof(*world));
 q.version=OVERWORLD_PICKUP_ROUTE_VERSION;q.size=sizeof(q);
 q.subject=(OverworldActorHandle){0,2,3,4,5,0};q.cargo=(OverworldActorHandle){1,6,3,4,7,0};
 q.bounds=(OverworldPickupRouteBounds){0,0,width-1,height-1};
 q.origin=(OverworldPickupRoutePosition){0,height>1?1:0,0,0,0};
 q.cargoPosition=(OverworldPickupRoutePosition){width-1,q.origin.y,0,0,0};
 q.scopeRevision=q.movementPolicyRevision=q.goalRevision=q.dynamicRevision=1;
 q.edges=candidates;q.edgeCount=4;q.goals=goals;q.goalCount=1;q.legalEdge=Legal;q.context=world;
 goals[0]=(OverworldPickupRoutePosition){width-2,q.origin.y,0,0,0};
 world->cargoX=q.cargoPosition.x;world->cargoY=q.cargoPosition.y;return q;
}
static int Step(OverworldPickupRouteQuery *q,u32 budget)
{
 unsigned prior=((World*)q->context)->calls;
 OverworldPickupRoute_Resume(&state,q,budget,&result);
 CHECK(result.workUsed<=budget && ((World*)q->context)->calls-prior<=result.workUsed);
 CHECK(result.edgeCalls==((World*)q->context)->calls);return 0;
}
static int Finish(OverworldPickupRouteQuery *q,u32 budget,OverworldPickupRouteStatus expected,unsigned *frames)
{
 unsigned count=0;
 do {CHECK(!Step(q,budget));CHECK(++count<20000);} while(result.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(result.status==expected);if(frames)*frames=count;return 0;
}
int main(void)
{
 World world;unsigned frames;
 /* An exact XY score is still only a candidate. A blocked edge must fall
  * back; a different support height must not earn the pickup-goal proof. */
 OverworldPickupRouteEdge fast[]={{2,0,30},{1,0,10},{-1,0,11},{0,1,12},{0,-1,13}};
 OverworldPickupRouteQuery q=Query(&world,4,3);q.edges=fast;q.edgeCount=5;world.blockExact=1;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,&frames));CHECK(result.nextStep.x==1 && result.edgeTag==10);
 q=Query(&world,4,3);q.edges=fast;q.edgeCount=5;world.wrongExactHeight=1;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,&frames));CHECK(result.pickupPosition.baseY==0 && result.nextStep.x==1 && result.edgeTag==10);
 puts("score0 exact edge: blocked/height candidates still require full native route proof");
 q=Query(&world,5,3);
 OverworldPickupRouteVisited before[512];memcpy(before,table,sizeof(table));
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!memcmp(before,table,sizeof(table))); /* Begin does no H-entry clear. */
 CHECK(!Step(&q,0));CHECK(result.workUsed==0 && world.calls==0 && state.nodeCount==0);
 world.cells[1][1]=world.cells[1][2]='#';
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,&frames));
 CHECK(result.pickupPosition.x==3 && result.pickupPosition.y==1 && result.hasNextStep);
 CHECK(result.nextStep.x==0 && result.nextStep.y==2 && result.edgeTag==12);
 printf("detour: frames%u next=(%d,%d) tag%u\n",frames,result.nextStep.x,result.nextStep.y,result.edgeTag);
 /* Wide distant map: goal-directed search must not fan out into capacity. */
 q=Query(&world,73,40);CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,&frames));
 CHECK(result.pickupPosition.x==71 && result.nextStep.x==1 && result.visitedNodes<100);
 printf("far open73x40: frames%u work%u nodes%u edgeCalls%u next=(%d,%d)\n",frames,result.totalWork,result.visitedNodes,result.edgeCalls,result.nextStep.x,result.nextStep.y);
 /* Cargo, Subject AND current occupancy change every8frames, no idle dwell. */
 q=Query(&world,80,40);q.cargoPosition.x=74;goals[0].x=73;world.cargoX=74;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 unsigned moves=0,frame;
 for(frame=0;frame<256;frame++) {
  if(frame && frame%8==0) {
   ++moves;q.origin.x=(s16)(frame/8);q.cargoPosition.x=(s16)(74+(moves&1));
   q.cargoPosition.y=(s16)(1+(moves&1));goals[0].x=q.cargoPosition.x-1;goals[0].y=q.cargoPosition.y;
   ++q.goalRevision;++q.dynamicRevision;world.cargoX=q.cargoPosition.x;world.cargoY=q.cargoPosition.y;
  }
  CHECK(!Step(&q,16));
  if(result.status==OVERWORLD_PICKUP_ROUTE_REACHABLE)break;
  CHECK(result.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 }
 CHECK(frame<256 && moves>=2 && world.calls>0 && result.pickupPosition.x-result.origin.x>32);
 CHECK(result.origin.x==q.origin.x && result.origin.y==q.origin.y && result.cargoPosition.x==q.cargoPosition.x);
 CHECK(result.goalRevision==q.goalRevision && result.dynamicRevision==q.dynamicRevision);
 CHECK(result.nextStep.x==q.origin.x+1 && result.nextStep.y==q.origin.y && result.edgeTag==10);
 printf("moving endpoints+occupancy: frames%u moves%u work16 nodes%u edgeCalls%u origin%d goal%d next%d\n",frame+1,moves,result.visitedNodes,result.edgeCalls,result.origin.x,result.pickupPosition.x,result.nextStep.x);
 /* Directed terrain: a new origin cannot inherit an old-root reverse route. */
 q=Query(&world,5,1);world.oneway=1;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 q.origin.x=2;goals[0].x=0;++q.goalRevision;
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_UNREACHABLE,0));
 printf("directed new-origin reverse route rejected\n");
 /* Old FREE edge changes to blocked: path proof must select an actual detour. */
 q=Query(&world,5,3);CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));CHECK(result.nextStep.x==1);
 world.cells[1][1]='#';++q.dynamicRevision;
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 CHECK(result.nextStep.x==0 && result.nextStep.y==2 && result.dynamicRevision==2);
 /* Complete blocking cannot return stale REACHABLE; reopening is not sticky. */
 q=Query(&world,5,1);CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 world.cells[0][1]='#';++q.dynamicRevision;
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_UNREACHABLE,0));
 world.cells[0][1]=0;++q.dynamicRevision;
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 printf("changed blocking edges: detour, no-route, reopened route passed\n");
 /* Same XY, different height/surface and opaque edge tags remain distinct. */
 q=Query(&world,4,1);world.layered=1;
 OverworldPickupRouteEdge layered[]={{1,0,0},{1,0,1}};q.edges=layered;q.edgeCount=2;
 goals[0]=(OverworldPickupRoutePosition){2,0,128,8,0};
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,1,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 CHECK(result.nextStep.x==1 && result.nextStep.baseY==128 && result.nextStep.surfaceId==8 && result.edgeTag==1);
 /* Deferred search and deferred path proof keep their exact candidate. */
 q=Query(&world,5,3);world.deferred=1;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Step(&q,1000));CHECK(result.status==OVERWORLD_PICKUP_ROUTE_PENDING && world.calls==1 && result.workUsed<1000);
 CHECK(!Step(&q,16));CHECK(result.workUsed==1 && world.calls==2 && result.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 world.deferred=0;CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 world.deferred=1;++q.dynamicRevision;
 CHECK(!Step(&q,1000));CHECK(result.status==OVERWORLD_PICKUP_ROUTE_PENDING && result.workUsed<1000);
 CHECK(!Step(&q,16));CHECK(result.workUsed==1 && result.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 world.deferred=0;CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_REACHABLE,0));
 /* Capacities and generation wrap remain resource failures, never no-route. */
 OverworldPickupRouteNode tinyNodes[2];OverworldPickupRouteCachedEdge tinyEdges[4];
 OverworldPickupRouteVisited tinyTable[4]={{0}};
 OverworldPickupRouteWorkspace tiny={tinyNodes,tinyEdges,tinyTable,2,4,4,0};
 q=Query(&world,5,1);CHECK(OverworldPickupRoute_Begin(&state,&q,&tiny)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT,0));
 tiny.generation=0xFFFFFFFFu;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&tiny)==OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT);
 workspace.edgeCapacity=1;q=Query(&world,5,1);
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT,0));workspace.edgeCapacity=512;
 /* Every full-handle field and static compatibility owner fail closed. */
 for(unsigned changed=0;changed<15;changed++) {
  q=Query(&world,5,3);OverworldPickupRouteQuery current=q;
  CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
  switch(changed) {
  case 0:current.subject.slot=2;break;case 1:current.subject.generation++;break;
  case 2:current.subject.fieldEpoch++;break;case 3:current.subject.mapGeneration++;break;
  case 4:current.subject.encounterGeneration++;break;case 5:current.subject.reserved++;break;
  case 6:current.cargo.slot=2;break;case 7:current.cargo.generation++;break;
  case 8:current.cargo.fieldEpoch++;break;case 9:current.cargo.mapGeneration++;break;
  case 10:current.cargo.encounterGeneration++;break;case 11:current.cargo.reserved++;break;
  case 12:current.scopeRevision++;break;case 13:current.movementPolicyRevision++;break;case 14:current.edgeCount--;break;
  }
  CHECK(!Step(&current,1));CHECK(result.status==OVERWORLD_PICKUP_ROUTE_INVALID && result.workUsed==0 && world.calls==0);
 }
 q=Query(&world,3,1);goals[0]=q.cargoPosition;
 CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
 CHECK(!Finish(&q,16,OVERWORLD_PICKUP_ROUTE_INVALID,0));
 for(int mode=0;mode<4;mode++) {
  q=Query(&world,3,1);world.invalid=mode==0?OVERWORLD_PICKUP_ROUTE_EDGE_INVALID:mode==3?-1:0;
  world.resource=mode==1;world.wrongXY=mode==2;
  CHECK(OverworldPickupRoute_Begin(&state,&q,&workspace)==OVERWORLD_PICKUP_ROUTE_PENDING);
  CHECK(!Finish(&q,16,mode==1?OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT:OVERWORLD_PICKUP_ROUTE_INVALID,0));
 }
 printf("production pickup-route moving/directed/dynamic/height/budget/deferred/identity/resource controls passed\n");
 return 0;
}
'''
ARM_LAYOUT = r'''
#include "overworld_pickup_route.h"
_Static_assert(sizeof(OverworldPickupRouteQuery)==96,"ARM query");
_Static_assert(sizeof(OverworldPickupRouteState)==184,"ARM state");
_Static_assert(sizeof(OverworldPickupRouteWorkspace)==24,"ARM workspace");
_Static_assert(sizeof(OverworldPickupRouteNode)==24,"ARM node");
_Static_assert(sizeof(OverworldPickupRouteCachedEdge)==16,"ARM cached edge");
_Static_assert(sizeof(OverworldPickupRouteVisited)==8,"ARM visited slot");
_Static_assert(sizeof(OverworldPickupRouteResult)==108,"ARM result");
'''

def main():
    compiler=shutil.which("cc")
    if not compiler:raise SystemExit("host C compiler unavailable")
    with tempfile.TemporaryDirectory(prefix="pickup-route-") as temporary:
        directory=Path(temporary);harness=directory/"check.c";harness.write_text(HARNESS);binary=directory/"check"
        command=[compiler,"-std=c99","-Wall","-Wextra","-Werror","-O2","-DOVERWORLD_ACTOR_SYSTEM_HOST","-I",str(ROOT/"include")]
        subprocess.run(command+[str(SOURCE),str(harness),"-o",str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
        source=SOURCE.read_text()
        mutants={
            "work budget":("used<budget","used<=budget"),
            "directed current-origin proof":("if(node->parent==NONE) { Restart(s);break; }","if(node->parent==NONE) { s->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;break; }"),
            "current dynamic edge proof":("if(e->dynamicRevision!=current->dynamicRevision || e->decision!=OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL)","if(e->decision!=OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL)"),
        }
        for name,(old,new) in mutants.items():
            if source.count(old)!=1:raise SystemExit("mutation boundary changed: "+name)
            mutated=directory/"mutant.c";mutated.write_text(source.replace(old,new))
            subprocess.run(command+[str(mutated),str(harness),"-o",str(binary)],check=True)
            failed=subprocess.run([str(binary)],capture_output=True,text=True)
            if failed.returncode==0:raise SystemExit("failed to reject mutant: "+name)
            print("rejected mutant:",name)
        clang=shutil.which("clang")
        if not clang:raise SystemExit("clang unavailable for exact ARM layout control")
        layout=directory/"layout.c";layout.write_text(ARM_LAYOUT)
        subprocess.run([clang,"-target","arm-none-eabi","-ffreestanding","-fsyntax-only","-std=c11","-DOVERWORLD_ACTOR_SYSTEM_HOST","-I",str(ROOT/"include"),str(layout)],check=True)
        print("ARM layout: State184 + Workspace24 + 24N + 16M + 8H; Result108; N256/M512/H512=18640 bytes")
    for filename in (SOURCE,HEADER,Path(__file__)):
        print(filename.relative_to(ROOT),hashlib.sha256(filename.read_bytes()).hexdigest())
if __name__=="__main__":main()
