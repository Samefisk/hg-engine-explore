/* Actual shared allocation/publication/drain, with only heap callbacks mocked.
 * Query graph, Cargo reducer and all nine retained paths are product C. */
/* ACTUAL DRAIN OWNER */
static int AllocationControls(void){
 for(unsigned failed=1;failed<=2;failed++){
  Reset();failAllocation=failed;
  CHECK(AcquireQuery(&call)==NULL && runtime.pickupQuery==NULL && allocations==failed);
  CHECK(frees==failed-1);
  /* Fragmentation may refuse either block despite ample total free bytes.
   * The next normal request retries cleanly, without partial publication. */
  failAllocation=0;NativeQuery*q=AcquireQuery(&call);CHECK(q && runtime.pickupQuery==q);
  CHECK(q->allocation.version==OVERWORLD_FIELD_QUERY_ALLOCATION_VERSION && q->allocation.auxiliary && q->allocation.destroy==DestroyQuery);
  unsigned released=frees;CHECK(OverworldWildSpawns_DrainQuery(&runtime) && runtime.pickupQuery==NULL && frees==released+2);
  CHECK(OverworldWildSpawns_DrainQuery(&runtime) && frees==released+2);
 }
 for(unsigned heap=0;heap<2;heap++){
  Reset();heap4Free=sizeof(NativeAuxiliary)+OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE+OVERWORLD_FIELD_QUERY_ALLOCATION_MARGIN;
  heap11Free=sizeof(NativeQuery)+OVERWORLD_FIELD_QUERY_CORE_HEAP_RESERVE+OVERWORLD_FIELD_QUERY_ALLOCATION_MARGIN;
  if(heap)heap11Free--;else heap4Free--;
  CHECK(!AcquireQuery(&call) && !runtime.pickupQuery && !allocations && !frees);
  if(heap)heap11Free++;else heap4Free++;
  CHECK(AcquireQuery(&call) && allocations==2);
 }
 Reset();NativeQuery*q=AcquireQuery(&call);CHECK(q);
 OverworldCargoQueryWildAllocation saved=q->allocation;
 for(unsigned bad=0;bad<3;bad++){
  q->allocation=saved;if(!bad)q->allocation.version++;else if(bad==1)q->allocation.auxiliary=NULL;else q->allocation.destroy=NULL;
  CHECK(!OverworldWildSpawns_DrainQuery(&runtime) && runtime.pickupQuery==q && !frees);
 }
 q->allocation=saved;CHECK(OverworldWildSpawns_DrainQuery(&runtime) && !runtime.pickupQuery && frees==2);
 CHECK(OverworldWildSpawns_DrainQuery(NULL));
 puts("actual split query: reserve boundaries, fragmentation/rollback, complete publication, versioned nested drain and double drain PASS");
 return 0;
}
static int AllPathsAndCargo(void){
 Reset();NativeQuery*q=AcquireQuery(&call);CHECK(q);
 CHECK(q->storage.workspace.nodes==AUX(q)->nodes && q->storage.workspace.edges==q->cachedEdges
  && q->storage.workspace.visited==q->visited && q->storage.workspace.visitedValid==AUX(q)->visitedValid
  && q->storage.changes==AUX(q)->changes && q->storage.changesValid==AUX(q)->changesValid);
 for(unsigned slot=0;slot<10;slot++)if(slot!=7){
  OverworldEntryRoutePath*p=EntryPath(q,slot);p->actor=(OverworldActorHandle){slot,slot+1,3,4,slot+9,0};
  p->serial=100+slot;p->scope=200+slot;p->policy=300+slot;p->valid=1;p->count=96;
  p->origin=p->expected=(OverworldPickupRoutePosition){100,100,slot*12345,slot+17,0};
  p->target=(OverworldPickupRoutePosition){196,100,slot*12345,slot+17,0};
  for(unsigned n=0;n<96;n++)p->commands[n]=11;
 }
 OverworldEntryRoutePath saved[9];memcpy(saved,q->entryPaths,sizeof(saved));
 CHECK(!Finish() && output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE && allocations==2);
 CHECK(!memcmp(saved,q->entryPaths,sizeof(saved)));
 CHECK(q->storage.workspace.nodeCapacity==256 && q->storage.workspace.edgeCapacity==512 && q->storage.workspace.visitedCapacity==512);
 CHECK(!OverworldCargoQuery_Unchanged(&q->state,&q->state.goal,&q->state.goal,q->dynamicRevision+1));
 unsigned released=frees;CHECK(OverworldWildSpawns_DrainQuery(&runtime) && frees==released+2 && !runtime.pickupQuery);
 puts("actual Cargo completes with all9 full96-command paths retained; capacities and owner pointers intact PASS");
 return 0;
}
static int DrainSpans(void){
 const u8 stages[]={0,OW_WILD_SPAWN_MOVE_DESTINATION_PENDING,OW_WILD_SPAWN_ROUTE_READY,OW_WILD_SPAWN_ROUTE_PENDING,OW_WILD_SPAWN_STARTUP_PENDING};
 for(unsigned owned=0;owned<2;owned++)for(unsigned stage=0;stage<sizeof(stages);stage++){
  Reset();if(owned)CHECK(AcquireQuery(&call));
  memset(&runtime.queuedSpawn,0xA5,sizeof(runtime.queuedSpawn));memset(&runtime.queuedSpawnGuard,0xC7,sizeof(runtime.queuedSpawnGuard));
  memset(&runtime.entryRouteReceipt,0xD9,sizeof(runtime.entryRouteReceipt));memset(runtime.entryRouteSerial,0xEB,sizeof(runtime.entryRouteSerial));
  memset(runtime.returnMoves,0x71,sizeof(runtime.returnMoves));
  runtime.queuedSpawnSlotPlusOne=1;runtime.queuedSpawnSerial=0x12345678;runtime.refillQueuedSerial=0x9ABCDEF0;
  runtime.refillPositionChecksRemaining=stages[stage];runtime.queuedSpawnTerrain=3;
  runtime.refillFailureStreak=0x17;runtime.refillTerrainMask=0x35;runtime.refillLandSurfSlot=0x53;
  memset(conditions.bindings,0x67,sizeof(conditions.bindings));conditions.frame.world.bindings=&conditions.bindings[0];conditions.frame.valid=1;
  OverworldWildOverlayRuntimeState expected=runtime;OverworldWildBehaviorConditionRuntime expectedConditions=conditions;
  expected.pickupQuery=NULL;
  if(stage>=1 && stage<=3){expected.queuedSpawnSlotPlusOne=0;expected.refillPositionChecksRemaining=0;memset(&expected.queuedSpawn,0,sizeof(expected.queuedSpawn));memset(&expected.queuedSpawnGuard,0,sizeof(expected.queuedSpawnGuard));}
  if(!expected.queuedSpawnSlotPlusOne){expected.queuedSpawnSerial=0;expected.refillQueuedSerial=0;}
  memset(&expected.entryRouteReceipt,0,sizeof(expected.entryRouteReceipt));memset(expected.entryRouteSerial,0,sizeof(expected.entryRouteSerial));
  memset(expectedConditions.bindings,0,sizeof(expectedConditions.bindings));expectedConditions.frame.world.bindings=NULL;expectedConditions.frame.valid=0;
  CHECK(OverworldWildSpawns_DrainQuery(&runtime));
  CHECK(!memcmp(&runtime,&expected,sizeof(runtime)) && !memcmp(&conditions,&expectedConditions,sizeof(conditions)));
  CHECK(frees==owned*2);
  CHECK(OverworldWildSpawns_DrainQuery(&runtime) && frees==owned*2 && !memcmp(&runtime,&expected,sizeof(runtime)));
 }
 puts("actual Drain: all packet/guard/receipt/serial bytes cleared, pending stages exact, neighbor sentinels retained PASS");return 0;
}
int main(void){if(AllocationControls() || AllPathsAndCargo())return 1;return DrainSpans();}
