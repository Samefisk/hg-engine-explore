
#include <assert.h>
static unsigned reads,heightReads,worldReads,blockedX,oldY,currentOkay=1,compactMode;
static s32 compactHeight;static s32 targetHeightDelta;static u16 targetSurfaceDelta;static s16 specialX,specialY;static u16 compactSurface=0xFFFF;
static FieldSystem f;static LocalMapObject player;static PlayerAvatar avatar;
static OverworldPickupRouteEdgeResult B(void*w,const OverworldPickupRouteQuery*q){(void)w;return q==NULL || OverworldPickupRoute_QueryCurrent(q)?LEGAL:INVALID;}
static OverworldPickupRouteEdgeResult T(void*w,s16 x,s16 y,u16 mask,OverworldPickupRouteNativeTile*out){OverworldPickupRouteWildWorld*world=w;if(world->entryMemo){if(!world->entryMemo->budget)return DEFERRED;world->entryMemo->budget--;world->entryMemo->used++;}(void)y;(void)mask;reads++;worldReads++;*out=(OverworldPickupRouteNativeTile){compactSurface+(x==specialX&&y==specialY?targetSurfaceDelta:0),1,0,0,0};return x==(int)blockedX?BLOCKED:LEGAL;}
static OverworldPickupRouteEdgeResult S(void*w,const OverworldPickupRoutePosition*from,s16 x,s16 y,const OverworldPickupRouteNativeTile*t,s32*out){(void)w;(void)from;(void)x;(void)y;(void)t;reads+=8;heightReads++;*out=compactHeight+(x==specialX&&y==specialY?targetHeightDelta:0);return LEGAL;}
static OverworldPickupRouteEdgeResult O(void*w,const OverworldActorHandle*a,const OverworldPickupRoutePosition*p,u8 include){(void)w;(void)a;(void)p;(void)include;reads++;return LEGAL;}
static OverworldPickupRouteEdgeResult R(void*w,const OverworldActorHandle*a,const OverworldPickupRoutePosition*p){(void)w;(void)a;(void)p;reads++;return LEGAL;}
static OverworldPickupRouteEdgeResult E(void*w,const OverworldPickupRouteNativePolicy*p,u8 k,const OverworldPickupRoutePosition*a,const OverworldPickupRouteNativeTile*b,const OverworldPickupRoutePosition*c,const OverworldPickupRouteNativeTile*z){(void)w;(void)p;(void)k;(void)b;(void)z;return compactMode || k==0xFF || (c->x-a->x==1 && c->y==a->y)?LEGAL:BLOCKED;}
static OverworldPickupRouteEdgeResult H(void*w,const OverworldPickupRouteNativePolicy*p,u8 k,u16 d,const OverworldPickupRoutePosition*a,const OverworldPickupRoutePosition*b){(void)w;(void)p;(void)k;(void)d;(void)a;(void)b;assert(0);return INVALID;}
static OverworldPickupRouteEdgeResult P(void*w,const OverworldPickupRouteNativePolicy*p,const OverworldPickupRoutePosition*a,const OverworldPickupRoutePosition*b){(void)w;(void)p;(void)a;(void)b;assert(0);return INVALID;}
static const OverworldPickupRouteNativeSeams seams={B,T,S,O,R,E,H,P};
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void*w){(void)w;return &seams;}
static u8 CurrentTest(void*w,const OverworldEntryRouteRequest*r){(void)w;return currentOkay && r->serial==7 && r->slot==0 && r->fieldEpoch==1 && r->mapGeneration==2 && r->expectedSlotGeneration==4;}
static OverworldCargoQueryStorage storage;
static OverworldCargoQueryBuffers buffers;
static OverworldCargoQueryState ledger;
static OverworldEntryRouteSearch search;
static OverworldEntryRoutePath path;
static OverworldEntryRouteReceipt receipt;
static void Init(void){memset(&storage,0,sizeof(storage));OverworldCargoQuery_BindStorage(&storage,&buffers);OverworldCargoQuery_Init(&ledger,&storage);avatar.mapObject=&player;f.playerAvatar=&avatar;player.xCurr=20;player.yCurr=10;blockedX=0xFFFF;reads=heightReads=worldReads=0;currentOkay=1;compactMode=0;compactHeight=0;compactSurface=0xFFFF;targetHeightDelta=targetSurfaceDelta=0;specialX=specialY=-1;memset(&path,0,sizeof(path));}
#define TEST(c) do{if(!(c)){fprintf(stderr,"entry-host:%d %s\n",__LINE__,#c);return 1;}}while(0)

/* Mock only the stock planner callback. Actual Entry memo/native classifier,
 * typed kind/direction and full endpoint checks remain the production code. */
static OverworldMotionDecision CompactHop(OverworldActorHopPlanCall*c){
 if(c->operation==OVERWORLD_ACTOR_HOP_PLAN_VECTOR){int dx=Abs(c->deltaX),dy=Abs(c->deltaY);c->distance=dx>dy?dx:dy;return OVERWORLD_MOTION_DECISION_ACCEPTED;}
 assert(c->operation==OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN || c->operation==OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP);
 c->clearanceCursor->readsUsed=0;c->clearanceCursor->phase=OVERWORLD_ACTOR_HOP_CLEARANCE_DONE;return OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static int CompactWitnessControls(OverworldPickupRouteState witness){
 static const s8 delta[8][2]={{0,-1},{0,1},{-1,0},{1,0},{-1,-1},{1,-1},{-1,1},{1,1}};
 static const u8 opposite[8]={1,0,3,2,7,6,5,4};
 OverworldPickupRouteExtension ext=*witness.query.extension;
 OverworldPickupRouteEdge edge;witness.query.edges=&edge;witness.query.edgeCount=1;witness.query.extension=&ext;
 witness.rootNode=0;witness.goalNode=1;witness.nodeCount=2;witness.cachedEdgeCount=1;
 storage.workspace.nodes[1].parent=0;storage.workspace.nodes[1].parentEdge=0;
 storage.workspace.edges[0]=(OverworldPickupRouteCachedEdge){witness.query.dynamicRevision,witness.searchStamp,1,0,0,LEGAL,0};
 unsigned cases=0;
 for(unsigned kind=0;kind<5;kind++)for(unsigned direction=0;direction<(kind==2?4:8);direction++){
  unsigned distance=kind==0?1:kind==2?2:3;
  u16 tag=kind==4?(OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT|direction):OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(kind,direction);
  OverworldPickupRoutePosition origin={100,100,123456,23,0};
  OverworldPickupRoutePosition endpoint={100+delta[direction][0]*distance,100+delta[direction][1]*distance,-65432,31,0};
  for(unsigned reverse=0;reverse<2;reverse++){
   ext.flags=reverse?OVERWORLD_PICKUP_ROUTE_EXTENSION_REVERSE:0;
   ext.kind=reverse?OVERWORLD_PICKUP_ROUTE_EXTENSION_PREPARED:OVERWORLD_PICKUP_ROUTE_EXTENSION_ENTRY_ACTOR;
   witness.query.subject=reverse?(OverworldActorHandle){0}:search.receipt.actor;
   edge=(OverworldPickupRouteEdge){delta[direction][0]*distance,delta[direction][1]*distance,tag};
   storage.workspace.nodes[0].position=origin;storage.workspace.nodes[1].position=endpoint;
   if(reverse){edge.dx=-edge.dx;edge.dy=-edge.dy;edge.tag=(tag&~7u)|opposite[tag&7];storage.workspace.nodes[0].position=endpoint;storage.workspace.nodes[1].position=origin;}
   u16 got=0xFFFF;OverworldPickupRoutePosition pose={0};
   TEST(OverworldPickupRoute_CopyForwardWitness(&witness,&got,&pose,1)==1);
   TEST(got==tag && !memcmp(&pose,&endpoint,sizeof(pose)));
   if(kind!=3){u16 command;OverworldPickupRouteEdge decoded;
    TEST(OverworldPickupRoute_CopyForwardCommands(&witness,&command,1)==1);
    TEST(OverworldPickupRoute_CommandEdge(command,&decoded));
    TEST(decoded.tag==tag && decoded.dx==delta[direction][0]*(int)distance && decoded.dy==delta[direction][1]*(int)distance);
   }
   cases++;
  }
 }
 for(unsigned d=0;d<8;d++)for(unsigned limit=0;limit<2;limit++){
  u16 distance=limit?255:1,tag=OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,d);OverworldPickupRouteEdge decoded;
  TEST(OverworldPickupRoute_CommandEdge(tag|(distance<<3),&decoded));
  TEST(decoded.dx==delta[d][0]*(int)distance && decoded.dy==delta[d][1]*(int)distance && decoded.tag==tag);
 }
 printf("compact witness: %u forward/reverse native tag and full-height/surface copies PASS\n",cases);
 return 0;
}
static int CompactValidationControls(void){
 static const s8 delta[8][2]={{0,-1},{0,1},{-1,0},{1,0},{-1,-1},{1,-1},{-1,1},{1,1}};
 OverworldPickupRouteEdge edges[]={{-1,0,2},{1,0,3},{0,-1,0},{0,1,1}};
 OverworldPickupRouteBounds bounds={-32768,-32768,32767,32767};
 unsigned validated=0;
 for(unsigned kind=0;kind<5;kind++)for(unsigned direction=0;direction<(kind==2?4:8);direction++){
  if(kind==3)continue;
  Init();compactMode=1;compactHeight=8192;compactSurface=23;
  OverworldActorHandle actor={0,9,1,2,55};
  OverworldEntryRouteRequest request={.version=1,.size=sizeof(request),.serial=7,.fieldEpoch=1,.mapGeneration=2,.actor=actor,.expectedSlotGeneration=4,.operation=OVERWORLD_ENTRY_ROUTE_GUIDE};
  request.origin=(OverworldPickupRoutePosition){100,100,8192,23,0};
  unsigned distance=kind==0?1:kind==2?2:3;
  request.destination=(OverworldPickupRoutePosition){100+delta[direction][0]*distance,100+delta[direction][1]*distance,8192,23,0};
  OverworldPickupRouteWildOps hopOps={.hopPlan=CompactHop};
  OverworldPickupRouteWildWorld world={.field=&f,.ops=&hopOps,.subjectObject=&player};
  OverworldPickupRouteNativePolicy policy={.version=3,.size=sizeof(policy),.allowedTerrainMask=1,.allowedKinds=31,.directions=3,.hopMinDistance=1,.hopMaxDistance=255,.resolvedProfile=&f,.resolvedLane=&f};
  TEST(OverworldEntryRoute_Begin(&search,&request,&world,&policy,&ledger,edges,4,&bounds,1,2,1,CurrentTest,NULL)==OVERWORLD_PICKUP_ROUTE_PENDING);
  path.actor=actor;path.serial=7;path.policy=2;path.scope=1;path.valid=1;path.count=1;path.expected=request.origin;path.target=request.destination;
  u16 tag=kind==4?(OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT|direction):OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(kind,direction);
  path.commands[0]=tag|(distance<<3);
  OverworldEntryRouteReceipt beforeReady={0};TEST(!OverworldEntryRoute_Guide(&path,&actor,&path.expected,2,&beforeReady));
  OverworldPickupRouteStatus status;unsigned updates=0;
  do{unsigned before=reads;status=OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt);TEST(reads-before<=8);TEST(++updates<=20);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);
  TEST(status==OVERWORLD_PICKUP_ROUTE_REACHABLE && path.stepRead);
  TEST(search.memo.edge.dx==delta[direction][0]*(int)distance && search.memo.edge.dy==delta[direction][1]*(int)distance);
  TEST(search.memo.edge.tag==tag && receipt.edgeTag==tag);
  TEST(!memcmp(&receipt.nextStep,&request.destination,sizeof(receipt.nextStep)));
  /* The immutable FINAL destination still requires its exact support. */
  specialX=request.destination.x;specialY=request.destination.y;
  for(unsigned changed=0;changed<2;changed++){
   OverworldEntryRoute_ResetMemo(&search);targetHeightDelta=changed?0:1;targetSurfaceDelta=changed?1:0;
   updates=0;do{status=OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt);TEST(++updates<=20);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);
   TEST(status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE && !path.stepRead);
  }
  targetHeightDelta=targetSurfaceDelta=0;validated++;
 }
 /* Unknown/zero commands and overflowing decoded XY fail before any read. */
 for(unsigned axis=0;axis<2;axis++)for(unsigned reverse=0;reverse<2;reverse++)for(unsigned ready=0;ready<2;ready++){
  path.expected=(OverworldPickupRoutePosition){100,100,8192,23,0};
  s16 from=reverse?-32768:32767;
  if(axis)path.expected.y=from;else path.expected.x=from;
  u16 direction=axis?(reverse?0:1):(reverse?2:3);path.commands[0]=(1u<<3)|direction;
  search.memo.guideReady=ready;unsigned before=reads;OverworldEntryRouteReceipt prior=receipt;
  TEST(OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt)==OVERWORLD_PICKUP_ROUTE_INVALID && reads==before && !memcmp(&prior,&receipt,sizeof(prior)));
 }
 path.expected=(OverworldPickupRoutePosition){100,100,8192,23,0};
 for(unsigned bad=0;bad<3;bad++){
  path.commands[0]=bad==0?3:bad==1?0x080B:0xC00B;unsigned before=reads;
  TEST(OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt)==OVERWORLD_PICKUP_ROUTE_INVALID && reads==before);
 }
 /* Intermediate support may change. Full admission materializes and freezes
  * its current full endpoint; no command grants an unclassified START. */
 Init();compactMode=1;compactHeight=8192;compactSurface=23;
 OverworldActorHandle actor={0,9,1,2,55};
 OverworldEntryRouteRequest r={.version=1,.size=sizeof(r),.serial=7,.fieldEpoch=1,.mapGeneration=2,.actor=actor,.expectedSlotGeneration=4,.operation=OVERWORLD_ENTRY_ROUTE_GUIDE,.origin={100,100,8192,23,0},.destination={102,100,8192,23,0}};
 OverworldPickupRouteWildWorld world={.field=&f,.subjectObject=&player};
 OverworldPickupRouteNativePolicy policy={.version=3,.size=sizeof(policy),.allowedTerrainMask=1,.allowedKinds=1,.directions=1};
 TEST(OverworldEntryRoute_Begin(&search,&r,&world,&policy,&ledger,edges,4,&bounds,1,2,1,CurrentTest,NULL)==OVERWORLD_PICKUP_ROUTE_PENDING);
 path=(OverworldEntryRoutePath){.actor=actor,.expected=r.origin,.target=r.destination,.serial=7,.policy=2,.scope=1,.valid=1,.count=2,.commands={11,11}};
 specialX=101;specialY=100;targetHeightDelta=1;
 unsigned updates=0;OverworldPickupRouteStatus status;
 do{status=OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt);TEST(++updates<20);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);
 TEST(status==OVERWORLD_PICKUP_ROUTE_REACHABLE && receipt.nextStep.baseY==8193 && path.nextStep.baseY==8193);
 OverworldActorRuntimeSlot slot={0};slot.snapshot.handle=actor;slot.snapshot.commitSequence=2;slot.motion.commitPublished=1;
 slot.motion.plan.startX=slot.motion.plan.startY=100;slot.motion.plan.startBaseY=8192;slot.motion.plan.targetX=101;slot.motion.plan.targetY=100;slot.motion.plan.targetBaseY=8193;
 path.accepted=path.stepRead=1;path.acceptedSequence=1;OverworldPickupRoutePosition wrong=path.nextStep;wrong.baseY--;
 TEST(!OverworldEntryRoute_Confirm(&path,&actor,&wrong,&slot) && path.next==0);
 path.accepted=1;TEST(OverworldEntryRoute_Confirm(&path,&actor,&path.nextStep,&slot) && path.next==1 && !path.stepRead);
 printf("compact validation: %u directed Walk/Hop/Ledge/Teleport edges, exact tags, final height/surface rejects and8 pre-cast bounds PASS\n",validated);
 puts("changed intermediate terrain re-admitted; exact endpoint frozen before START/END; unknown commands rejected PASS");
 return 0;
}

int main(void){
 Init();
 OverworldEntryRouteRequest request={0};request.version=1;request.size=sizeof(request);request.serial=7;request.slot=0;request.fieldEpoch=1;request.mapGeneration=2;request.expectedSlotGeneration=4;request.physical.rangeX=request.physical.rangeY=-1;
 request.destination=(OverworldPickupRoutePosition){12,10,0,0xFFFF,0};
 OverworldPickupRouteWildWorld world={0};world.field=&f;
 OverworldPickupRouteNativePolicy policy={0};policy.version=3;policy.size=sizeof(policy);policy.allowedTerrainMask=1;policy.allowedKinds=1;policy.directions=1;policy.flags=2;
 OverworldPickupRouteEdge edges[]={{-1,0,2},{1,0,3},{0,-1,0},{0,1,1}};
 OverworldPickupRouteBounds bounds={0,0,40,20};
 TEST(OverworldEntryRoute_Begin(&search,&request,&world,&policy,&ledger,edges,4,&bounds,1,2,1,CurrentTest,NULL)==OVERWORLD_PICKUP_ROUTE_PENDING);
 unsigned updates=0;OverworldPickupRouteStatus status;
 do{unsigned before=reads;status=OverworldEntryRoute_Resume(&search,1,NULL,0,1,&path,&receipt);TEST(reads-before<=8);TEST(receipt.readsUsed==reads-before);TEST(++updates<=241);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);
 printf("status=%u updates=%u reads=%u nodes=%u phase=%u origin=%d,%d steps=%u\n",status,updates,reads,ledger.route.nodeCount,ledger.route.phase,path.origin.x,path.origin.y,path.count);
 TEST(status==OVERWORLD_PICKUP_ROUTE_REACHABLE && path.origin.x==7 && path.target.x==12 && path.count==5);
 for(unsigned i=0;i<path.count;i++)TEST(path.commands[i]==11);
 printf("prepared route: %u bounded updates, %u reads, %u native height calls\n",updates,reads,heightReads);
 currentOkay=0;unsigned before=reads;TEST(OverworldEntryRoute_Resume(&search,1,NULL,0,1,&path,&receipt)==OVERWORLD_PICKUP_ROUTE_INVALID && reads==before);
 currentOkay=1;
 OverworldActorHandle actor={0,9,1,2,55};path.actor=actor;path.noProgress=73;
 request.operation=OVERWORLD_ENTRY_ROUTE_GUIDE;request.actor=actor;request.origin=path.origin;
 TEST(OverworldEntryRoute_Begin(&search,&request,&world,&policy,&ledger,edges,4,&bounds,1,2,1,CurrentTest,NULL)==OVERWORLD_PICKUP_ROUTE_PENDING);
 updates=0;
 do{unsigned before=reads;status=OverworldEntryRoute_Resume(&search,1,NULL,0,1,&path,&receipt);TEST(reads-before<=8);TEST(++updates<=241);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);
 TEST(status==OVERWORLD_PICKUP_ROUTE_REACHABLE && path.noProgress==73 && path.count==5);
 updates=0;do{status=OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt);TEST(++updates<20);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);TEST(status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
 path.accepted=1;path.acceptedSequence=10;
 OverworldActorRuntimeSlot slot={0};slot.snapshot.handle=actor;slot.snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_IDLE;slot.snapshot.commitSequence=11;slot.motion.commitPublished=1;
 slot.motion.plan.startX=path.expected.x;slot.motion.plan.startY=path.expected.y;slot.motion.plan.startBaseY=path.expected.baseY;
 slot.motion.plan.targetX=path.nextStep.x;slot.motion.plan.targetY=path.nextStep.y;slot.motion.plan.targetBaseY=0;
 TEST(OverworldEntryRoute_Confirm(&path,&actor,&path.nextStep,&slot) && path.next==1);
 updates=0;do{status=OverworldEntryRoute_ValidateStep(&search,&path,1,NULL,0,1,&receipt);TEST(++updates<20);}while(status==OVERWORLD_PICKUP_ROUTE_PENDING);TEST(status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
 path.accepted=1;path.acceptedSequence=11;unsigned next=path.next;slot.motion.plan.startX=path.expected.x;slot.motion.plan.targetX=path.nextStep.x;
 TEST(!OverworldEntryRoute_Confirm(&path,&actor,&path.nextStep,&slot) && path.next==next);
 for(unsigned i=0;i<120;i++)TEST(!OverworldEntryRoute_IdleStall(&path,&actor,1,0));
 TEST(OverworldEntryRoute_IdleStall(&path,&actor,0,1));actor.generation++;
 TEST(!OverworldEntryRoute_IdleStall(&path,&actor,1,1));
 /* Exact bounded path copy: capacity96 admits96, rejects97 with no partial output. */
 OverworldPickupRouteState witness=ledger.route;
 witness.rootNode=0;witness.goalNode=96;witness.nodeCount=98;witness.cachedEdgeCount=97;
 witness.status=OVERWORLD_PICKUP_ROUTE_REACHABLE;witness.searchStamp=7;
 witness.proofRevision=witness.query.dynamicRevision;
 for(unsigned i=0;i<98;i++) {
   storage.workspace.nodes[i]=(OverworldPickupRouteNode){0};storage.workspace.nodes[i].position=(OverworldPickupRoutePosition){i,10,0,0xFFFF,0};
   storage.workspace.nodes[i].searchStamp=7;storage.workspace.nodes[i].parent=i?i-1:0;storage.workspace.nodes[i].parentEdge=i?i-1:0;
   if(i<97)storage.workspace.edges[i]=(OverworldPickupRouteCachedEdge){witness.query.dynamicRevision,7,i+1,0,1,OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL,0};
 }
 TEST(OVERWORLD_ENTRY_ROUTE_MAX_STEPS==96);
 TEST(OverworldPickupRoute_CopyForwardCommands(&witness,path.commands,OVERWORLD_ENTRY_ROUTE_MAX_STEPS)==96);
 OverworldEntryRoutePath saved=path;witness.goalNode=97;
 TEST(OverworldPickupRoute_CopyForwardCommands(&witness,path.commands,OVERWORLD_ENTRY_ROUTE_MAX_STEPS)==0xFFFF);
 TEST(!memcmp(&path.commands,&saved.commands,sizeof(path.commands)));
 TEST(!CompactWitnessControls(witness));
 TEST(!CompactValidationControls());
 puts("actual96-step witness bound: exact96 copied;97 rejected without partial output PASS");
 puts("actual Entry route/ledger/full-handle/commit/offscreen controls PASS");return 0;
}
