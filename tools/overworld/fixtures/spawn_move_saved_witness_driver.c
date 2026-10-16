static OverworldEntryRouteReceipt reply;
static OverworldEntryRouteCommand command;
static NativeQuery *owned;
static OverworldEntryRoutePath *savedPath;
static unsigned returnedSteps, largestReads;
static int SetupPoseToken(void){
 Reset();fixtureSurface=0xFFFF;fixtureHeight=0x7fffffff;
 profile.owner.hopAllowNonCardinal=0;profile.owner.hopTime=1;profile.owner.hopMinDistance=profile.owner.hopMaxDistance=1;
 objects[0].flags=50209;objects[0].xrange=objects[0].yrange=-1;
 objects[0].posVec[0]=((u32)objects[0].xCurr<<16)+0x8000;objects[0].posVec[2]=((u32)objects[0].yCurr<<16)+0x8000;
 actors.slots[0].snapshot.logicalX=objects[0].xCurr;actors.slots[0].snapshot.logicalY=objects[0].yCurr;
 CHECK(actors.slots[0].policy.targetSurfaceId==0);
 call.routeOperation=OVERWORLD_FIELD_ROUTE_ENTRY;call.heapId=OVERWORLD_FIELD_QUERY_HEAP_ID;call.locomotion=1;call.allowedTerrainMask=1;world.slot=0;
 owned=AcquireQuery(&call);CHECK(owned&&Scope(&world,owned));OverworldPickupRouteNativePolicy p;CHECK(Policy(owned,&call,&p));
 savedPath=EntryPath(owned,0);*savedPath=(OverworldEntryRoutePath){0};
 savedPath->valid=1;savedPath->serial=7;savedPath->scope=owned->scopeRevision;savedPath->policy=owned->policyRevision;savedPath->count=6;
 savedPath->origin=savedPath->expected=(OverworldPickupRoutePosition){4,4,64,0xFFFF,0};savedPath->target=(OverworldPickupRoutePosition){10,4,64,0xFFFF,0};
 for(int n=0;n<6;n++){savedPath->endpoints[n]=(OverworldPickupRoutePosition){5+n,4,64,0xFFFF,0};savedPath->edgeTags[n]=3;}
 command=(OverworldEntryRouteCommand){0};call.entry=&command;command.receipt=&reply;
 command.request=(OverworldEntryRouteRequest){.version=1,.size=sizeof(command.request),.serial=7,.fieldEpoch=3,.mapGeneration=4,.actor=actors.slots[0].snapshot.handle,.origin={4,4,64,0,0},.destination=savedPath->target,.physical={50209,0,-1,-1,10,4},.slot=0,.operation=OVERWORLD_ENTRY_ROUTE_ADOPT};
 runtime.queuedSpawnSerial=7;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE);CHECK(savedPath->valid&&savedPath->policy==owned->policyRevision);
 command.request.operation=OVERWORLD_ENTRY_ROUTE_GUIDE;command.usableIdle=1;runtime.entryRouteSerial[0]=7;
 spawns.movementSpawnRunActive[0]=1;spawns.movementSpawnRunTargetX[0]=10;spawns.movementSpawnRunTargetY[0]=4;
 returnedSteps=largestReads=0;return 0;
}
static int Advance(void){
 actors.frame++;OverworldPickupRouteStatus status=OverworldCargoQueryWild_Tick(&call,&output);
 if(reply.readsUsed>largestReads)largestReads=reply.readsUsed;
 if(reply.hasNextStep)returnedSteps++;
 return status;
}
static int CheckPoseToken(void){
 CHECK(!SetupPoseToken());unsigned updates=0;
 for(;updates<20;updates++){int status=Advance();printf("update=%u status=%u reads=%u next=%u nodes=%u rootSurface=%u policySurface=%u\n",updates+1,status,reply.readsUsed,reply.hasNextStep,owned->state.route.nodeCount,owned->entry.query.origin.surfaceId,actors.slots[0].policy.targetSurfaceId);CHECK(largestReads<=8);if(reply.hasNextStep)break;}
 CHECK(updates<12);CHECK(reply.status==OVERWORLD_PICKUP_ROUTE_REACHABLE&&reply.hasNextStep&&reply.nextStep.x==5&&reply.nextStep.y==4&&reply.nextStep.baseY==64&&reply.nextStep.surfaceId==0xFFFF);
 CHECK(savedPath->scope==owned->scopeRevision&&savedPath->policy==owned->policyRevision&&actors.slots[0].policy.targetSurfaceId==0);
 CHECK(owned->state.route.nodeCount==0);
 puts("saved full ground witness used before graph search; actual source/target physical classification retained PASS");return 0;
}
static int InvalidControls(void){
 /* A surface0 is a real catalog token; never map all policy0 values to ground. */
 CHECK(!SetupPoseToken());fixtureSurface=0;savedPath->origin.surfaceId=savedPath->expected.surfaceId=savedPath->target.surfaceId=0;for(int n=0;n<6;n++)savedPath->endpoints[n].surfaceId=0;
 for(int n=0;n<20&&!returnedSteps;n++)Advance();CHECK(returnedSteps==1&&reply.nextStep.surfaceId==0&&largestReads<=8&&owned->state.route.nodeCount==0);
 /* Stale actor request is rejected before any physical query. */
 CHECK(!SetupPoseToken());command.request.actor.generation++;unsigned before=nativeCalls;CHECK(Advance()==OVERWORLD_PICKUP_ROUTE_INVALID&&nativeCalls==before&&!returnedSteps);
 /* The surface token is not enough when the physical standing height differs. */
 CHECK(!SetupPoseToken());objects[0].posVec[1]=65;command.request.origin.baseY=65;
 for(int n=0;n<12;n++)Advance();CHECK(!returnedSteps&&largestReads<=8&&owned->state.route.nodeCount!=0);
 /* The native full source support stays authoritative even after root resolves. */
 CHECK(!SetupPoseToken());for(int n=0;n<3;n++)Advance();CHECK(owned->entryRootReady);
 fixtureSurface=23;objects[1].xCurr=4;objects[1].yCurr=4;objects[1].flags^=2;
 int status=0;for(int n=0;n<12&&status==OVERWORLD_PICKUP_ROUTE_PENDING;n++)status=Advance();CHECK(status==OVERWORLD_PICKUP_ROUTE_INVALID&&!returnedSteps&&largestReads<=8);
 /* Source height remains a fresh physical fact after root admission. */
 CHECK(!SetupPoseToken());for(int n=0;n<3;n++)Advance();fixtureHeight=65;objects[1].xCurr=4;objects[1].yCurr=4;objects[1].flags^=2;
 status=0;for(int n=0;n<12&&status==OVERWORLD_PICKUP_ROUTE_PENDING;n++)status=Advance();CHECK(status==OVERWORLD_PICKUP_ROUTE_INVALID&&!returnedSteps&&largestReads<=8);
 /* A changed loaded scope invalidates the root before any physical edge. */
 CHECK(!SetupPoseToken());for(int n=0;n<3;n++)Advance();before=nativeCalls;*(u32 *)(slots[0]+0x860)=1;
 CHECK(Advance()==OVERWORLD_PICKUP_ROUTE_PENDING&&!returnedSteps&&nativeCalls==before&&!owned->entry.active);
 /* Ready proof must be thrown away when another object claims its next tile. */
 CHECK(!SetupPoseToken());for(int n=0;n<8;n++)Advance();CHECK(owned->entry.memo.guideReady&&!returnedSteps);
 objects[1].xCurr=5;objects[1].yCurr=4;
 status=0;for(int n=0;n<12&&status==OVERWORLD_PICKUP_ROUTE_PENDING;n++)status=Advance();CHECK(status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE&&!returnedSteps&&largestReads<=8);
 /* Changed full policy cannot borrow the old witness, even when XYZ match. */
 CHECK(!SetupPoseToken());for(int n=0;n<3;n++)Advance();profile.owner.continueWhenArrived++;
 for(int n=0;n<12;n++)Advance();CHECK(!returnedSteps&&largestReads<=8&&savedPath->policy!=owned->policyRevision);
 /* A Field-owner change rejects before physical work or any saved step. */
 CHECK(!SetupPoseToken());spawns.movementFieldSystem=NULL;before=nativeCalls;CHECK(Advance()==OVERWORLD_PICKUP_ROUTE_INVALID&&nativeCalls==before&&!returnedSteps);
 puts("surface0, full height, stale Actor/Field, source surface, changed occupancy/ready and policy controls PASS");return 0;
}
int main(void){if(CheckPoseToken())return 1;return InvalidControls();}
