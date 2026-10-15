#include <assert.h>
static unsigned reads,heightReads,behaviorReads,terrainReads,hopCalls,ownerOkay=1,midBehavior=2,walkBlocked,occupancyBlocked;
static FieldSystem f;static LocalMapObject player;static PlayerAvatar avatar;
static OverworldWildBehaviorProfile profile;
static u8 Behavior(FieldSystem *field,int x,int y){(void)field;(void)x;(void)y;reads++;behaviorReads++;return midBehavior;}
static BOOL Blocked(FieldSystem *field,int x,int y){(void)field;(void)x;(void)y;reads++;return walkBlocked;}
static BOOL MidOccupancy(FieldSystem *field,LocalMapObject *ignored,LocalMapObject *collision,int x,int y,s32 h,int mode){(void)field;(void)ignored;(void)collision;(void)x;(void)y;(void)h;(void)mode;reads++;return occupancyBlocked;}
static int WalkHeight(FieldSystem *field,const void *v,int x,int y,u8 *kind){(void)field;(void)v;(void)x;(void)y;reads+=8;heightReads++;*kind=0;return 0;}
static BOOL NoDirection(u8 b){(void)b;return 0;}
static const OverworldPickupRouteWildDirectionBlock directionBlocks[4]={NoDirection,NoDirection,NoDirection,NoDirection};
static OverworldMotionDecision HopPlan(OverworldActorHopPlanCall *call){
 if(call->operation==OVERWORLD_ACTOR_HOP_PLAN_VECTOR){int dx=Abs(call->deltaX),dy=Abs(call->deltaY);call->distance=dx>dy?dx:dy;return OVERWORLD_MOTION_DECISION_ACCEPTED;}
 assert(call->operation==OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN || call->operation==OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP);hopCalls++;call->clearanceCursor->readsUsed=0;call->clearanceCursor->phase=OVERWORLD_ACTOR_HOP_CLEARANCE_DONE;return OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static const OverworldPickupRouteWildOps ops={.version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION,.size=sizeof(OverworldPickupRouteWildOps),.behavior=Behavior,.occupancy=MidOccupancy,.walkHeight=WalkHeight,.blockedTerrain=Blocked,.sourceDirectionBlocks=directionBlocks,.targetDirectionBlocks=directionBlocks,.hopPlan=HopPlan};
static OverworldPickupRouteEdgeResult B(void *raw,const OverworldPickupRouteQuery *query){OverworldPickupRouteWildWorld *w=raw;return !ownerOkay || w->field!=&f || w->ops!=&ops || w->ops->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION || (query && (!OverworldPickupRoute_QueryCurrent(query) || query->scopeRevision!=w->scopeRevision || query->movementPolicyRevision!=w->movementPolicyRevision || query->dynamicRevision!=w->dynamicRevision))?INVALID:LEGAL;}
static OverworldPickupRouteEdgeResult T(void *raw,s16 x,s16 y,u16 wanted,OverworldPickupRouteNativeTile *tile){OverworldPickupRouteWildWorld *w=raw;(void)x;(void)y;(void)wanted;if(!w->entryMemo->budget)return DEFERRED;w->entryMemo->budget--;w->entryMemo->used++;reads++;terrainReads++;*tile=(OverworldPickupRouteNativeTile){0xFFFF,1,2,0,0};return LEGAL;}
static OverworldPickupRouteEdgeResult S(void *raw,const OverworldPickupRoutePosition *from,s16 x,s16 y,const OverworldPickupRouteNativeTile *tile,s32 *height){(void)raw;(void)from;(void)x;(void)y;(void)tile;reads+=8;heightReads++;*height=0;return LEGAL;}
static OverworldPickupRouteEdgeResult O(void *raw,const OverworldActorHandle *subject,const OverworldPickupRoutePosition *pose,u8 include){(void)raw;(void)subject;(void)pose;(void)include;reads++;return occupancyBlocked?BLOCKED:LEGAL;}
static OverworldPickupRouteEdgeResult R(void *raw,const OverworldActorHandle *subject,const OverworldPickupRoutePosition *pose){(void)raw;(void)subject;(void)pose;reads++;return LEGAL;}
static OverworldPickupRouteEdgeResult E(void *raw,const OverworldPickupRouteNativePolicy *p,u8 kind,const OverworldPickupRoutePosition *from,const OverworldPickupRouteNativeTile *source,const OverworldPickupRoutePosition *to,const OverworldPickupRouteNativeTile *target){
 if(kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LANDING_ONLY)return LEGAL;
 OverworldPickupRouteWildWorld *w=raw;OverworldEntryRouteMemo *m=w->entryMemo;
 if(!m->movementStarted){m->movementInput=(OverworldPreparedMovementInput){0};OverworldPreparedMovementInput *i=&m->movementInput;i->version=1;i->size=sizeof(*i);i->profile=p->resolvedProfile;i->lane=p->resolvedLane;i->field=w->field;i->ops=w->ops;i->from=*from;i->to=*to;i->source=*source;i->target=*target;i->kind=kind;i->directions=p->directions;i->rangeX=i->rangeY=-1;i->anchorX=from->x;i->anchorY=from->y;i->blockedTerrain=Blocked;m->movement=(OverworldPreparedMovementCursor){0};m->movement.version=1;m->movement.size=sizeof(m->movement);m->movement.input=i;OverworldPickupRouteEdgeResult d=OverworldPreparedMovement_Begin(&m->movement);m->movementStarted=1;if(m->movement.phase==OVERWORLD_PREPARED_MOVEMENT_DONE)return d;}
 m->movement.readBudget=m->budget;OverworldPickupRouteEdgeResult d=OverworldPreparedMovement_Step(&m->movement);assert(m->movement.readsUsed<=m->budget);m->budget-=m->movement.readsUsed;m->used+=m->movement.readsUsed;return d;
}
static OverworldPickupRouteEdgeResult H(void *raw,const OverworldPickupRouteNativePolicy *p,u8 kind,u16 distance,const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to){(void)raw;(void)p;(void)kind;(void)distance;(void)from;(void)to;assert(0);return INVALID;}
static OverworldPickupRouteEdgeResult P(void *raw,const OverworldPickupRouteNativePolicy *p,const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to){(void)raw;(void)p;(void)from;(void)to;assert(0);return INVALID;}
static const OverworldPickupRouteNativeSeams seams={B,T,S,O,R,E,H,P};
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *world){(void)world;return &seams;}
static u8 CurrentTest(void *owner,const OverworldEntryRouteRequest *r){(void)owner;return ownerOkay && r->serial==7 && r->slot==0 && r->fieldEpoch==1 && r->mapGeneration==2;}
static OverworldCargoQueryStorage storage;static OverworldCargoQueryState ledger;static OverworldEntryRouteSearch search;
static OverworldPickupRouteEdge edge;static OverworldPickupRoutePosition output;
static void Init(u8 direction,u8 level,u8 behavior,u8 kind){
 memset(&storage,0,sizeof(storage));storage.workspace=(OverworldPickupRouteWorkspace){storage.nodes,storage.edges,storage.visited,OVERWORLD_CARGO_QUERY_NODES,OVERWORLD_CARGO_QUERY_EDGES,OVERWORLD_CARGO_QUERY_HASH,0};OverworldCargoQuery_Init(&ledger,&storage);
 reads=heightReads=behaviorReads=terrainReads=hopCalls=walkBlocked=occupancyBlocked=0;ownerOkay=1;midBehavior=behavior;profile=(OverworldWildBehaviorProfile){0};profile.owner.jumpLevel=level;avatar.mapObject=&player;f.playerAvatar=&avatar;player.xCurr=player.yCurr=20;
 static const s8 delta[4][2]={{0,-1},{0,1},{-1,0},{1,0}};static const u8 opposite[4]={1,0,3,2};int distance=kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE?2:1;
 edge=(OverworldPickupRouteEdge){-delta[direction][0]*distance,-delta[direction][1]*distance,OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(kind,opposite[direction])};
 OverworldEntryRouteRequest request={0};request.version=1;request.size=sizeof(request);request.serial=7;request.slot=0;request.fieldEpoch=1;request.mapGeneration=2;request.physical.rangeX=request.physical.rangeY=-1;request.destination=(OverworldPickupRoutePosition){10,10,0,0xFFFF,0};
 OverworldPickupRouteWildWorld world={0};world.field=&f;world.ops=&ops;world.scopeRevision=1;world.movementPolicyRevision=2;world.dynamicRevision=1;
 OverworldPickupRouteNativePolicy policy={0};policy.version=3;policy.size=sizeof(policy);policy.allowedTerrainMask=1;policy.allowedKinds=1u<<kind;policy.directions=1;policy.flags=2;policy.resolvedProfile=&profile;policy.resolvedLane=&profile.owner;
 OverworldPickupRouteBounds bounds={0,0,40,40};assert(OverworldEntryRoute_Begin(&search,&request,&world,&policy,&ledger,&edge,1,&bounds,1,2,1,CurrentTest,NULL)==OVERWORLD_PICKUP_ROUTE_PENDING);
 memset(&output,0xA5,sizeof(output));
}
static OverworldPickupRouteEdgeResult One(u8 budget){unsigned before=reads;search.memo.budget=budget;search.memo.used=0;OverworldPickupRouteEdgeResult d=Edge(&search,&search.query.origin,&edge,&output);assert(reads-before<=budget && search.memo.used==reads-before);return d;}
static unsigned calls;
static OverworldPickupRouteEdgeResult Complete(void){OverworldPickupRouteEdgeResult d;calls=0;do{d=One(8);assert(++calls<32);}while(d==DEFERRED);return d;}
int main(int argc,char **argv){
 unsigned negativeReads=0,negativeHeight=0,positiveReads=0,positiveHeight=0,walkReads=0,walkHeight=0,cases=0,boundaryReads=0;
 for(u8 direction=0;direction<4;direction++)for(u8 level=0;level<4;level++)for(unsigned bi=0;bi<8;bi++){
  static const u8 behaviors[]={0,2,55,56,57,58,59,60};u8 behavior=behaviors[bi];Init(direction,level,behavior,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);OverworldPickupRoutePosition prior=output;
  unsigned ledgeIndex=behavior-56;u8 legal=ledgeIndex<=3 && level!=0 && (ledgeIndex^(direction^(2|(direction>>1))))<=(level>=2);
  OverworldPickupRouteEdgeResult d=Complete();assert(d==(legal?LEGAL:BLOCKED));if(!legal)assert(!memcmp(&prior,&output,sizeof(output)));else assert(output.x==10+edge.dx && output.y==10+edge.dy && output.baseY==0 && output.surfaceId==0xFFFF);
  if(!legal){negativeReads+=reads;negativeHeight+=heightReads;if(argc>1 && !strcmp(argv[1],"savings")){assert(reads==1 && heightReads==0 && terrainReads==0 && calls==1);}}
  else {positiveReads+=reads;positiveHeight+=heightReads;assert(hopCalls==2);}
  cases++;
 }
 for(u8 direction=0;direction<4;direction++){Init(direction,1,2,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK);assert(Complete()==LEGAL);walkReads+=reads;walkHeight+=heightReads;}
 Init(0,1,0xFF,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);assert(One(0)==DEFERRED && reads==0);assert(One(1)==DEFERRED);if(argc>1){assert(reads==1 && heightReads==0);midBehavior=58;assert(Complete()==LEGAL);}
 for(unsigned fault=0;fault<5;fault++){Init(0,1,58,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);if(fault==0)ownerOkay=0;if(fault==1)search.policy.version=0;if(fault==2)search.query.bounds.maxX=5;if(fault==3)search.world.scopeRevision++;if(fault==4)search.policy.directions=0;OverworldPickupRoutePosition prior=output;assert(Complete()==INVALID);assert(!memcmp(&output,&prior,sizeof(output)));if(argc>1 && fault!=2)assert(reads==0);}
 Init(0,1,58,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);assert(One(7)==DEFERRED && heightReads==0);unsigned before=reads;assert(One(8)==DEFERRED && heightReads==1 && reads-before==8);assert(Complete()==LEGAL);
 /* Invalid/out-of-scope inputs skip only the early gate and preserve the old
  * full path. A negative predecessor is invalid before any world read even
  * when the query itself permits a negative lower bound. */
 Init(3,1,2,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);search.query.bounds.minX=-4;search.query.origin.x=0;assert(Complete()==INVALID && reads==0 && behaviorReads==0);
 Init(2,1,2,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);search.query.bounds.maxX=32767;search.query.origin.x=32767;assert(Complete()==INVALID && reads==0 && behaviorReads==0);
 Init(2,1,2,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);search.query.origin.x=39;assert(Complete()==INVALID);assert(behaviorReads==0);boundaryReads+=reads;
 Init(2,1,2,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);search.query.bounds.minX=-4;search.query.origin.x=-1;assert(Complete()==INVALID);assert(behaviorReads==0);boundaryReads+=reads;
 Init(0,1,2,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);search.query.origin.reserved=1;assert(Complete()==INVALID && reads==0);
 Init(0,1,58,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);search.policy.directions=OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL;assert(Complete()==BLOCKED);
 Init(0,1,58,OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE);occupancyBlocked=1;assert(Complete()==BLOCKED);
 printf("{\"cases\":%u,\"negativeReads\":%u,\"negativeHeightCalls\":%u,\"positiveReads\":%u,\"positiveHeightCalls\":%u,\"walkReads\":%u,\"walkHeightCalls\":%u,\"boundaryReads\":%u,\"pendingReadLimitOwnerBoundsControls\":true}\n",cases,negativeReads,negativeHeight,positiveReads,positiveHeight,walkReads,walkHeight,boundaryReads);
 return 0;
}
