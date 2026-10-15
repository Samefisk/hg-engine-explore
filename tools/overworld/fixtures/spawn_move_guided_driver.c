
#define sys_AllocMemory Allocate
#define GF_ExpHeap_FndGetTotalFreeSize FreeSize
static unsigned resolves,destinations,startups,personalities,finishes,removes,starts,acceptedCalls;
static BOOL destinationReady,occupiedOrigin;static int normalMode,startMode,preparedStatus;
static unsigned prepares,guards,placements,constructors;static BOOL committing;static BOOL guardReady=TRUE,placementReady=TRUE,constructorReady=TRUE;static int prepareResult=1;static OverworldWildBehaviorPrimitives primitives;
static const OverworldActorSystemState *NativeActors(void){return &actors;}
static void NativeWorld(OverworldWildSpawnState *s,u8 slot,OverworldPickupRouteWildWorld*out){*out=world;out->state=s;out->field=s->movementFieldSystem;out->slot=slot;out->subjectObject=s->spawns[slot].object;}
static u16 NativeAllowed(const OverworldWildBehaviorProfile*p,u8 state){(void)p;(void)state;return 1;}
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_DIRECTION_STEP_STARTED 1
#define OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT 1
typedef struct OverworldWildDirectionStepContext {OverworldWildSpawnState*state;FieldSystem*field;LocalMapObject*object;const OverworldWildBehaviorProfile*profile;const OverworldWildBehaviorPrimitives*primitives;u8 slot;u16 allowed;u8 jump,unused;} OverworldWildDirectionStepContext;
static const OverworldActorSystemState *OverworldWildSpawns_RouteActorState(void){return &actors;}
static u16 OverworldWildSpawns_GetAllowedTileForSpotState(const OverworldWildBehaviorProfile*p,u8 phase){(void)p;(void)phase;return 1;}
static BOOL OverworldActorPolicy_Inspect(int n,OverworldActorPolicyView*p){return Inspect(n,p);}
static void PublishEnd(void){
 OverworldActorRuntimeSlot *s=&actors.slots[0];
 s->snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_IDLE;s->snapshot.reservationId=0;
 s->snapshot.logicalX=s->motion.plan.targetX;s->snapshot.logicalY=s->motion.plan.targetY;
 s->snapshot.commitSequence++;s->motion.commitPublished=1;
 objects[0].xCurr=s->motion.plan.targetX;objects[0].yCurr=s->motion.plan.targetY;
 objects[0].posVec[0]=((u32)objects[0].xCurr<<16)+0x8000;
 objects[0].posVec[2]=((u32)objects[0].yCurr<<16)+0x8000;
 objects[0].posVec[1]=s->motion.plan.targetBaseY;
}
/* Only the stock START seam is mocked. The synchronous END order matches
 * TryStartPlannedTeleport(duration0); actual caller/EntryTick/Confirm execute. */
static BOOL OverworldWildSpawns_TryStartPlannedTeleport(OverworldWildSpawnState*s,FieldSystem*f,int n,const OverworldWildBehaviorProfile*p,u16 a,int mode,const u8*dirs,int count,int x,int y,int q,int r){
 (void)s;(void)f;(void)p;(void)a;(void)mode;(void)dirs;(void)count;(void)q;(void)r;starts++;
 if(!startMode)return FALSE;
 actors.slots[n].motion.plan=(OverworldMotionPlan){0};
 actors.slots[n].motion.plan.startX=objects[n].xCurr;actors.slots[n].motion.plan.startY=objects[n].yCurr;
 actors.slots[n].motion.plan.startBaseY=objects[n].posVec[1];
 actors.slots[n].motion.plan.targetX=x;actors.slots[n].motion.plan.targetY=y;actors.slots[n].motion.plan.targetBaseY=64;
 actors.slots[n].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;actors.slots[n].snapshot.reservationId=1;
 if(startMode==2)PublishEnd();return TRUE;
}
static BOOL OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(OverworldWildSpawnState*s,FieldSystem*f,int n,const OverworldWildBehaviorProfile*p,u16 a,int x,int y,int tx,int ty,int q){(void)s;(void)f;(void)n;(void)p;(void)a;(void)x;(void)y;(void)tx;(void)ty;(void)q;NEVER();}
static int OverworldWildSpawns_TryStartLedgeJumpCommand(OverworldWildDirectionStepContext*c,int d,int x,int y){(void)c;(void)d;(void)x;(void)y;NEVER();}
static int OverworldWildSpawns_TryStartSingleDirectionMovementStep(OverworldWildDirectionStepContext*c,const OverworldActorPolicyView*p,int d,int b){(void)c;(void)p;(void)d;(void)b;NEVER();}

/* ACTUAL START OWNER */
static BOOL NativeStart(OverworldWildSpawnState*s,int slot,LocalMapObject*o,const OverworldWildBehaviorProfile*p,const OverworldWildBehaviorPrimitives*pr,const OverworldEntryRouteReceipt*r,u32*seq){return OverworldWildSpawns_StartEntryEdge(s,slot,o,p,pr,r,seq);}
static void NativeFinish(OverworldWildSpawnState*s,FieldSystem*f,int slot,LocalMapObject*o,int x,int y,u8 phase){
 (void)f;(void)o;(void)x;(void)y;finishes++;
 if(phase){s->movementSpawnRunTargetX[slot]=s->movementSpawnRunTargetY[slot]=0;s->movementSpawnRunActive[slot]=0;}
}
static void NativeRemove(OverworldWildSpawnState*s,FieldSystem*f,int slot){(void)s;(void)f;(void)slot;removes++;}
static BOOL NativeOccupied(FieldSystem*f,int x,int y){(void)f;(void)x;(void)y;return occupiedOrigin;}
static void NativeResolve(OverworldWildPreparedSpawn*p,OverworldWildSpawnTerrain t,int forced){(void)t;resolves++;if(forced==16)normalMode=1;p->behaviorResolution.primitives.spawnLocomotion=normalMode?1:3;}
static BOOL NativeLimit(OverworldWildSpawnState*s,u8 k,const OverworldWildBehaviorProfile*p){(void)s;(void)k;(void)p;return FALSE;}
static BOOL NativeDestination(OverworldWildSpawnState*s,FieldSystem*f,OverworldWildSpawnTerrain t,const OverworldWildBehaviorProfile*p,OverworldWildSpawnPosition*v){
 (void)f;(void)t;(void)p;destinations++;if(!destinationReady){if(s->movementRuntimeState)s->movementRuntimeState->refillPositionChecksRemaining=0xFF;return FALSE;}v->startX=31;v->startY=40;return TRUE;}
static s32 NativeGroundHeight(FieldSystem*f,LocalMapObject*object,int x,int y){(void)f;(void)object;(void)x;(void)y;startups++;return 64;}
static BOOL NativePersonality(FieldSystem*f,OverworldWildPreparedSpawn*p){(void)f;personalities++;p->encounter.personality++;return TRUE;}
static OverworldWildHelperPrepareResult NativePreparePacket(OverworldWildSpawnState*s,FieldSystem*f,OverworldWildSpawnTerrain t,int slot,OverworldWildPreparedSpawn*p){(void)s;(void)f;(void)t;(void)slot;prepares++;if(prepareResult!=1)return prepareResult;*p=(OverworldWildPreparedSpawn){0};p->encounter.species=74;p->encounter.level=5;p->nativeUnobserved[259]=91;return 1;}
static BOOL NativeGuard(OverworldWildSpawnState*s,FieldSystem*f,const OverworldWildPreparedSpawn*p,int slot,OverworldWildQueuedSpawnGuard*g){(void)f;(void)p;(void)slot;guards++;if(committing && s->movementRuntimeState->queuedSpawnSlotPlusOne){fprintf(stderr,"queue not consumed before guard\n");abort();}*g=(OverworldWildQueuedSpawnGuard){0};return guardReady;}
static BOOL NativePlacement(OverworldWildSpawnState*s,FieldSystem*f,int x,int y){(void)s;(void)f;(void)x;(void)y;placements++;return !placementReady;}
static BOOL NativeConstructor(OverworldWildSpawnState*s,FieldSystem*f,OverworldWildSpawnTerrain t,int slot,const OverworldWildPreparedSpawn*p){(void)f;(void)t;(void)slot;(void)p;constructors++;if(s->movementRuntimeState->queuedSpawnSlotPlusOne || s->movementRuntimeState->refillPositionChecksRemaining){fprintf(stderr,"queue not consumed before constructor\n");abort();}return constructorReady;}
static const OverworldEntryRouteNativeOps sOverworldWildEntryNativeOps={
 OVERWORLD_ENTRY_NATIVE_MAGIC,1,sizeof(OverworldEntryRouteNativeOps),NativeActors,NativeWorld,NativeAllowed,NativeStart,NativeFinish,NativeRemove,NativeOccupied,NativeResolve,NativeLimit,NativeDestination,NativeGroundHeight,NativePersonality,NativePreparePacket,NativeGuard,NativePlacement,NativeConstructor};
typedef struct OverworldQueryCodeAddonEntry {OverworldPickupRouteStatus(*cargoWildTick)(const OverworldCargoQueryWildCall*,OverworldCargoQueryResult*);} OverworldQueryCodeAddonEntry;
static const OverworldQueryCodeAddonEntry callerEntry={OverworldCargoQueryWild_Tick};
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem*f,void*p){(void)p;return f?&callerEntry:NULL;}
static void OverworldWildSpawns_InitRouteWorld(OverworldWildSpawnState*s,u8 slot,OverworldPickupRouteWildWorld*out){NativeWorld(s,slot,out);}
static OverworldPickupRouteStatus ProvedGuide(const OverworldCargoQueryWildCall*c,OverworldCargoQueryResult*r){
 if(c->entry==NULL || c->entry->nativeControl!=NULL){fprintf(stderr,"recursive control packet\n");abort();}
 if(c->entry->request.operation==OVERWORLD_ENTRY_ROUTE_PREPARE){
  *c->entry->receipt=(OverworldEntryRouteReceipt){.version=1,.size=sizeof(OverworldEntryRouteReceipt),.serial=runtime.queuedSpawnSerial,.origin={30,40,0,0xffff,0},.target={31,40,64,23,0},.status=preparedStatus};return preparedStatus;}
 if(c->entry->request.operation==OVERWORLD_ENTRY_ROUTE_GUIDE && !c->entry->accepted && c->profile!=NULL){
  NativeQuery*q=runtime.pickupQuery;OverworldEntryRoutePath *path=&q->entryPaths[0];
  return OverworldEntryRoute_Guide(path,&c->entry->request.actor,&c->entry->request.origin,path->policy,c->entry->receipt)?1:3;
 }
 if(c->entry->accepted)acceptedCalls++;
 return OverworldCargoQueryWild_Tick(c,r);
}

/* ACTUAL GUIDE AND CALLER */


static int CompactSlotControls(void){
 _Static_assert(OVERWORLD_ENTRY_ROUTE_MAX_STEPS==96,"trip capacity stays96");
 _Static_assert(sizeof(((OverworldEntryRoutePath*)0)->edgeTags)==192,"exact96 native tags");
 _Static_assert(sizeof(((OverworldEntryRoutePath*)0)->endpoints)==1152,"exact96 full endpoints");
 _Static_assert(sizeof(OverworldEntryRoutePath)==1424,"compact pointer-free path");
 _Static_assert(sizeof(((NativeQuery*)0)->entryPaths)/sizeof(OverworldEntryRoutePath)==9,"nine admitted Wild paths retained");
 Reset();call.heapId=4;
 freeBytes=sizeof(NativeQuery)+OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE-1;
 CHECK(!AcquireQuery(&call) && !allocations && !runtime.pickupQuery);
 freeBytes=sizeof(NativeQuery)+OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE;
 NativeQuery*one=AcquireQuery(&call);CHECK(one && allocations==1 && runtime.pickupQuery==one);
 CHECK(AcquireQuery(&call)==one && allocations==1);
 CHECK(one->storage.workspace.nodeCapacity==OVERWORLD_CARGO_QUERY_NODES
  && one->storage.workspace.edgeCapacity==OVERWORLD_CARGO_QUERY_EDGES
  && one->storage.workspace.visitedCapacity==OVERWORLD_CARGO_QUERY_HASH);
 unsigned admitted=0;
 for(unsigned n=0;n<10;n++){
  Reset();call.heapId=4;world.slot=n;call.routeOperation=1;
  OverworldEntryRouteReceipt r={0};OverworldEntryRouteCommand c={0};call.entry=&c;c.receipt=&r;
  c.request=(OverworldEntryRouteRequest){.version=1,.size=sizeof(c.request),.serial=7,.fieldEpoch=3,.mapGeneration=4,.expectedSlotGeneration=2,.slot=n,.operation=OVERWORLD_ENTRY_ROUTE_PREPARE};
  runtime.queuedSpawnSerial=7;runtime.queuedSpawnSlotPlusOne=n+1;
  actors.slots[n].snapshot.handle=(OverworldActorHandle){n,2,3,4,5,0};actors.slots[n].snapshot.active=0;spawns.spawns[n].active=0;
  if(n==7){CHECK(EntryTick(&call,&output,(u8[1]){0})==INVALID && !allocations);continue;}
  NativeQuery*q=AcquireQuery(&call);CHECK(q);q->entry.world=world;q->prepared=runtime.queuedSpawn;
  CHECK(EntryCurrent(q,&c.request));
  c.request.expectedSlotGeneration++;CHECK(!EntryCurrent(q,&c.request));c.request.expectedSlotGeneration--;
  c.request.slot=10;CHECK(!EntryCurrent(q,&c.request));c.request.slot=n;
  /* The real ADOPT reducer uses this full current slot/object/encounter,
   * then GUIDE recognizes arrival and RETIRE clears only this path. */
  objects[n]=objects[0];objects[n].flags=1;objects[n].xCurr=objects[n].yCurr=4;
  objects[n].posVec[0]=objects[n].posVec[2]=(4u<<16)+0x8000;objects[n].posVec[1]=64;
  actors.slots[n].snapshot.active=1;actors.slots[n].snapshot.subjectIdentity=1000;
  actors.slots[n].snapshot.logicalX=actors.slots[n].snapshot.logicalY=4;actors.slots[n].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_IDLE;
  actors.slots[n].policy.targetSurfaceId=23;
  spawns.spawns[n]=(OverworldWildSpawn){objects+n,1000,5,1};world.subjectObject=objects+n;
  spawns.movementSpawnRunActive[n]=1;spawns.movementSpawnRunTargetX[n]=spawns.movementSpawnRunTargetY[n]=4;
  OverworldEntryRoutePath*path=EntryPath(q,n);CHECK(path==&q->entryPaths[n-(n>7)]);path->valid=1;path->serial=7;
  path->origin=path->target=(OverworldPickupRoutePosition){4,4,64,23,0};path->count=96;path->edgeTags[95]=OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT|7;
  path->endpoints[95]=(OverworldPickupRoutePosition){31,31,65536,29,0};
  runtime.queuedSpawnSlotPlusOne=0;c.request.operation=OVERWORLD_ENTRY_ROUTE_ADOPT;c.request.actor=actors.slots[n].snapshot.handle;
  c.request.physical.rangeX=c.request.physical.rangeY=-1;u8 publish=0;
  CHECK(EntryTick(&call,&output,&publish)==OVERWORLD_PICKUP_ROUTE_REACHABLE && publish && !memcmp(&r.actor,&c.request.actor,sizeof(r.actor)));
  c.request.operation=OVERWORLD_ENTRY_ROUTE_GUIDE;c.request.destination=path->target;call.profile=NULL;
  CHECK(EntryTick(&call,&output,&publish)==OVERWORLD_PICKUP_ROUTE_REACHABLE && !publish && !memcmp(&r.target,&path->target,sizeof(r.target)));
  CHECK(path->count==96 && path->edgeTags[95]==(OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT|7) && path->endpoints[95].baseY==65536 && path->endpoints[95].surfaceId==29);
  c.request.operation=OVERWORLD_ENTRY_ROUTE_RETIRE;
  CHECK(EntryTick(&call,&output,&publish)==OVERWORLD_PICKUP_ROUTE_REACHABLE && !path->valid);admitted++;
 }
 CHECK(admitted==9);
 puts("compact path ownership: all9 admissible Wild slots including8/9; follower7 rejected; full ADOPT/arrival/RETIRE;96 endpoints and tags retained PASS");return 0;
}

static int NativeControls(void){
 CHECK(!CompactSlotControls());
 Reset();field.savedata=&field;resolves=destinations=startups=personalities=0;destinationReady=normalMode=FALSE;preparedStatus=PENDING;
 OverworldWildPreparedSpawn external={0};external.encounter.species=74;external.encounter.level=5;external.nativeUnobserved[259]=91;
 CHECK(!OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&external));
 CHECK(resolves==1 && destinations==0 && !startups && !personalities && runtime.queuedSpawnSlotPlusOne==1 && runtime.refillPositionChecksRemaining==0xFB && runtime.entryRouteReceipt.queued==1 && runtime.queuedSpawnSerial==1);
 OverworldWildPreparedSpawn owned=runtime.queuedSpawn;memset(&external,0,sizeof(external));CHECK(!memcmp(&owned,&runtime.queuedSpawn,sizeof(owned)));
 external=owned;external.nativeUnobserved[259]++;CHECK(!OverworldWildSpawns_ArmEntryQueue(&spawns,0,0,&external));CHECK(!memcmp(&owned,&runtime.queuedSpawn,sizeof(owned)) && runtime.queuedSpawnSerial==1);
 CHECK(!OverworldWildSpawns_ArmEntryQueue(&spawns,0,1,&runtime.queuedSpawn));
 CHECK(!OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&runtime.queuedSpawn));CHECK(resolves==1 && destinations==1 && runtime.refillPositionChecksRemaining==0xFF && !personalities);
 destinationReady=TRUE;CHECK(!OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&runtime.queuedSpawn));CHECK(destinations==2 && runtime.refillPositionChecksRemaining==0xFE && !startups && !personalities);
 CHECK(!OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&runtime.queuedSpawn));CHECK(destinations==2 && runtime.refillPositionChecksRemaining==0xFD && !personalities);
 preparedStatus=1;CHECK(!OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&runtime.queuedSpawn));CHECK(runtime.refillPositionChecksRemaining==0xFC && !personalities);
 CHECK(OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&runtime.queuedSpawn));CHECK(personalities==1 && resolves==1 && destinations==2 && !startups);
 puts("actual native wrappers/reducer: complete packet before yield, one resolve, FF/FE/FD/FC barriers and recursive null control PASS");
 for(unsigned follower=0;follower<2;follower++){
  Reset();field.savedata=&field;spawns.movementRuntimeState=NULL;resolves=destinations=startups=personalities=0;normalMode=TRUE;destinationReady=!follower;
  external=(OverworldWildPreparedSpawn){0};external.encounter.species=74;external.encounter.level=5;
  CHECK(OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,follower?7:0,&external));
  CHECK(resolves==1 && destinations==1 && startups==0 && personalities==!follower && allocations==0);
  field.playerAvatar=NULL;external.startup.locomotion=0;
  CHECK(OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,follower?7:0,&external));
 }
 puts("normal Wild and follower7 finalization keep BOOL admission without Runtime/graph allocation PASS");
 Reset();OverworldEntryRouteNativeControl c={0};OverworldEntryRouteCommand command={0};command.nativeControl=&c;
 c.version=1;c.size=sizeof(c);c.ops=&sOverworldWildEntryNativeOps;c.state=&spawns;c.field=&field;c.slot=0;c.operation=OVERWORLD_ENTRY_NATIVE_READY;c.prepared=&external;
 call.entry=&command;call.routeOperation=1;call.heapId=4;external.position.startX=20;external.position.startY=20;
 player.xCurr=7;player.yCurr=20;occupiedOrigin=FALSE;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==1 && c.value);
 player.xCurr=8;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==1 && !c.value);player.xCurr=7;
 occupiedOrigin=TRUE;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==1 && !c.value);occupiedOrigin=FALSE;
 OverworldEntryRouteNativeControl saved=c;OverworldEntryRouteNativeOps badOps=sOverworldWildEntryNativeOps;
 for(unsigned bad=0;bad<15;bad++){
  c=saved;call.world=&world;call.heapId=4;command.nativeControl=&c;badOps=sOverworldWildEntryNativeOps;
  switch(bad){case 0:c.version++;break;case 1:c.size--;break;case 2:c.reserved[0]=1;break;case 3:c.reserved[1]=1;break;case 4:c.operation=99;break;case 5:c.accepted=2;break;case 6:c.usableIdle=2;break;case 7:c.ops=NULL;break;case 8:badOps.magic++;c.ops=&badOps;break;case 9:badOps.size--;c.ops=&badOps;break;case 10:badOps.start=NULL;c.ops=&badOps;break;case 11:c.field=NULL;break;case 12:c.slot=10;break;case 13:c.slot=7;break;case 14:call.heapId=3;break;}
  OverworldWildOverlayRuntimeState prior=runtime;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==3 && !memcmp(&prior,&runtime,sizeof(prior)));
 }
 puts("current READY safe distance/occupancy and15 typed packet/owner/callback rejection controls PASS");
 for(int mode=0;mode<3;mode++){
  Reset();starts=acceptedCalls=0;startMode=mode;call.heapId=4;runtime.entryRouteSerial[0]=7;spawns.movementSpawnRunActive[0]=1;spawns.movementSpawnRunTargetX[0]=5;spawns.movementSpawnRunTargetY[0]=4;
  actors.slots[0].snapshot.logicalX=actors.slots[0].snapshot.logicalY=4;actors.slots[0].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_IDLE;actors.slots[0].snapshot.commitSequence=10;actors.slots[0].policy.targetSurfaceId=23;
  objects[0].posVec[0]=objects[0].posVec[2]=(4u<<16)+0x8000;
  NativeQuery*q=AcquireQuery(&call);CHECK(q);OverworldEntryRoutePath*path=&q->entryPaths[0];path->valid=1;path->serial=7;path->policy=3;path->actor=actors.slots[0].snapshot.handle;
  path->origin=path->expected=(OverworldPickupRoutePosition){4,4,64,23,0};path->target=path->endpoints[0]=(OverworldPickupRoutePosition){5,4,64,23,0};path->count=1;path->edgeTags[0]=OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT|3;
  CHECK(OverworldWildSpawns_TryStartGuidedEntry(&spawns,0,&objects[0],&profile,&primitives)==(mode!=0));CHECK(starts==1 && acceptedCalls==(unsigned)(mode!=0) && !path->next);
  if(!mode){CHECK(!path->accepted && actors.slots[0].snapshot.commitSequence==10);continue;}CHECK(path->accepted && path->acceptedSequence==10);
  if(mode==1){OverworldEntryRouteReceipt r;CHECK(OverworldWildSpawns_QueryEntry(&spawns,&field,0,NULL,2,NULL,0,0,0,&r)==0 && !path->next);PublishEnd();}
  OverworldEntryRouteReceipt r;CHECK(OverworldWildSpawns_QueryEntry(&spawns,&field,0,NULL,2,NULL,0,0,0,&r)==1);CHECK(path->next==1 && !path->accepted && actors.slots[0].snapshot.commitSequence==11);
 }
 NativeQuery*q=runtime.pickupQuery;OverworldEntryRoutePath*path=&q->entryPaths[0];path->count=2;path->next=1;path->accepted=0;
 OverworldEntryRouteReceipt receipt;
 CHECK(OverworldWildSpawns_QueryEntry(&spawns,&field,0,NULL,OVERWORLD_ENTRY_ROUTE_GUIDE,NULL,1,0,12,&receipt)==INVALID && !path->accepted);
 CHECK(OverworldWildSpawns_QueryEntry(&spawns,&field,0,NULL,OVERWORLD_ENTRY_ROUTE_GUIDE,NULL,1,0,9,&receipt)==INVALID && !path->accepted);
 puts("actual Wild START order: failed untouched; asynchronous END waits; synchronous Teleport END credited; stale sequence rejects PASS");
 for(int failure=0;failure<6;failure++){
  Reset();field.savedata=&field;normalMode=TRUE;destinationReady=TRUE;prepareResult=1;guardReady=placementReady=constructorReady=TRUE;committing=FALSE;
  prepares=guards=placements=constructors=resolves=0;
  if(failure==1)prepareResult=2;if(failure==2)prepareResult=0;if(failure==3)guardReady=FALSE;
  int result=OverworldWildSpawns_SpawnOne(&spawns,&field,0,0);
  CHECK(prepares==1 && constructors==0);
  if(failure==1 || failure==2){CHECK(result==prepareResult && resolves==0 && !runtime.queuedSpawnSlotPlusOne);continue;}
  if(failure==3){CHECK(!result && !runtime.queuedSpawnSlotPlusOne);continue;}
  CHECK(result==1 && runtime.queuedSpawnSlotPlusOne==1 && resolves==1 && guards==1 && runtime.queuedSpawn.nativeUnobserved[259]==91);
  if(failure==4)runtime.queuedSpawnGuard.owner[15]^=1;
  if(failure==5)placementReady=FALSE;
  committing=TRUE;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
  CHECK(!runtime.queuedSpawnSlotPlusOne && !runtime.refillPositionChecksRemaining && resolves==1);
  if(failure==4){CHECK(!constructors && !placements && !spawns.justSpawned);continue;}
  if(failure==5){CHECK(!constructors && placements==1 && !spawns.justSpawned);continue;}
  CHECK(constructors==1 && placements==1 && spawns.justSpawned);
 }
 puts("actual COMMIT/SPAWN: prepare once, pending/fail result, consume before guard/constructor, full guard mismatch, physical reject and final BOOL PASS");return 0;
}


static int PreparedPolicyParity(void) {
 Reset();objects[0].flags=50209;objects[0].flags2=0;
 objects[0].xCurr=objects[0].xInit=552;objects[0].yCurr=objects[0].yInit=370;
 objects[0].xrange=objects[0].yrange=-1;
 profile.owner.hopAllowNonCardinal=0;call.routeOperation=OVERWORLD_FIELD_ROUTE_ENTRY;
 NativeQuery q={0};OverworldPickupRouteNativePolicy p;
 OverworldEntryRoutePhysical prepared={.flags=objects[0].flags,.flags2=objects[0].flags2,.rangeX=-1,.rangeY=-1,.targetX=558,.targetY=370};
 CHECK(Policy(&q,&call,&p));u32 live=q.policyRevision;
 world.subjectObject=NULL;world.preparedPhysical=&prepared;
 CHECK(Policy(&q,&call,&p));u32 beforeBirth=q.policyRevision;
 printf("policy live=%u prepared=%u\n",live,beforeBirth);
 CHECK(live==beforeBirth);
 /* Both finite ranges are equivalent at initial zero relative anchors. */
 for(int axis=0;axis<2;axis++) {
  objects[0].xrange=prepared.rangeX=axis? -1:2;
  objects[0].yrange=prepared.rangeY=axis? 3:-1;
  world.subjectObject=NULL;CHECK(Policy(&q,&call,&p));beforeBirth=q.policyRevision;
  world.subjectObject=&objects[0];CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==beforeBirth);
  if(axis)objects[0].yInit++;else objects[0].xInit++;
  CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=beforeBirth);
  objects[0].xInit=552;objects[0].yInit=370;
 }
 objects[0].xrange=prepared.rangeX=-1;objects[0].yrange=prepared.rangeY=-1;
 world.subjectObject=NULL;CHECK(Policy(&q,&call,&p));beforeBirth=q.policyRevision;
 world.subjectObject=&objects[0];objects[0].xInit-=8;objects[0].yInit+=9;
 CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==beforeBirth);
 objects[0].flags^=1u<<23;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=beforeBirth);objects[0].flags^=1u<<23;
 objects[0].flags2^=1u<<2;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=beforeBirth);objects[0].flags2^=1u<<2;
 actorPolicy.chainPauseAction=0x90;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=beforeBirth);actorPolicy.chainPauseAction=0;
 profile.owner.hopTime++;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=beforeBirth);
 puts("actual Policy prepared/live parity and finite anchors/flags/chains preserved PASS");return 0;
}

int main(void){return NativeControls();}
