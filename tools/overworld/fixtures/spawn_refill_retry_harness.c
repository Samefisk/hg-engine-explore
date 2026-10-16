/* Named stock/native seams plus bounded actual-C refill/queue controls.
 * Used by test_spawn_refill_budget.py; no ROM-derived data or recorded run. */

#include <assert.h>
#define OVERWORLD_POPULATION_HOST 1
#include "overworld_population_model.h"
static OverworldPopulationState retryPopulation;
static int retrySchedules[64], retryScheduleCount;
static u8 OverworldWildSpawns_PopulationControl(u8 operation,u16 delay) {
 OverworldPopulationInput input={.version=OVERWORLD_POPULATION_INPUT_VERSION,.size=sizeof(input),.fieldEpoch=actors.fieldEpoch};
 OverworldPopulationResult result;
 if(operation==OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT)return retryPopulation.refillArmed;
 assert(operation==OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL);
 assert(retryScheduleCount<64);retrySchedules[retryScheduleCount++]=delay;
 input.kind=OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL;input.value=delay;
 assert(OverworldPopulation_Apply(&retryPopulation,&input,&result)!=OVERWORLD_POPULATION_DECISION_INVALID);return 0;
}
static void RetryWait(unsigned frames) {
 while(frames--){OverworldPopulationInput i={.version=OVERWORLD_POPULATION_INPUT_VERSION,.size=sizeof(i),.fieldEpoch=actors.fieldEpoch,.kind=OVERWORLD_POPULATION_INPUT_FRAME,.flags=OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE};OverworldPopulationResult r;OverworldPopulation_Apply(&retryPopulation,&i,&r);}
}

static BOOL OverworldWildSpawns_IsMovementFieldContextCurrent(OverworldWildSpawnState*s,FieldSystem*f){return retryFieldCurrent && s->movementFieldSystem==f && s->mapGeneration==actors.mapGeneration;}
#define SPECIES_BULBASAUR 1
#define OW_WILD_LAND_SURF_MAX_SPAWNS 6
#define OW_WILD_HEADBUTT_SLOT_START 6
#define OW_WILD_FISH_SLOT_START 8
#define OW_WILD_SPAWN_TERRAIN_LAND 0
#define OW_WILD_SPAWN_TERRAIN_SURF 1
#define OW_WILD_SPAWN_TERRAIN_HEADBUTT 2
#define OW_WILD_SPAWN_TERRAIN_FISHING 3
#define OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES 1
#define OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING 4
#define OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN 10
#define OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN 4
#define OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT 10
#define OW_WILD_FISHING_SPAWN_CHANCE_PERCENT 20
#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 60
#define OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES 8
#define OW_WILD_REFILL_FAILED_RETRY_FRAMES 15
#define OW_WILD_REFILL_SHORT_RETRY_LIMIT 3
static struct{u8 spawnWarmupPhase;}sOverworldWildFlags;
static BOOL retryEnabled=TRUE;
static void*OverworldWildSpawns_GetHelperOverlayEntry(void){return &field;}
static u32 OverworldWildSpawns_GetSpriteID(int species,int form){(void)species;(void)form;return 0;}
static void*OverworldWildSpawns_GetBehaviorDataBlob(void){return &field;}
static BOOL OverworldWildSpawns_ReconcileFollowerSelection(OverworldWildSpawnState*s,FieldSystem*f){(void)s;(void)f;return TRUE;}
static BOOL OverworldWildSpawns_TrySpawnFollower(OverworldWildSpawnState*s,FieldSystem*f,BOOL*c){(void)s;(void)f;*c=FALSE;return FALSE;}
static BOOL OverworldWildSpawns_IsEnabledMap(FieldSystem*f){(void)f;return retryEnabled;}
static BOOL OverworldWildSpawns_TryGetFreeSlot(OverworldWildSpawnState*s,u8 first,u8 last,int*slot){for(int n=first;n<last;n++)if(n!=7&&!s->spawns[n].active&&s->movementRuntimeState->queuedSpawnSlotPlusOne!=n+1){*slot=n;return TRUE;}return FALSE;}
static u32 retryRandomValues[32];static unsigned retryRandomIndex,retryRandomCount;
static u32 gf_rand(void){assert(retryRandomIndex<retryRandomCount);return retryRandomValues[retryRandomIndex++];}

/* REFILL RETRY CONTROLS */

static void RetryReset(void){
 Reset();retryMutation=0;memset(spawns.spawns,0,sizeof(spawns.spawns));spawns.spawns[7].active=1;
 spawns.headbuttSpawnCooldown=spawns.fishingSpawnCooldown=255;runtime.residentData=&retryResident;retryResident.pendingFlags=0;
 field.savedata=&field;sOverworldWildFlags.spawnWarmupPhase=2;retryFieldCurrent=retryEnabled=TRUE;
 normalMode=TRUE;destinationReady=TRUE;destinationTerminal=FALSE;prepareResult=1;
 guardReady=placementReady=constructorReady=TRUE;committing=FALSE;
 prepares=guards=placements=constructors=resolves=destinations=personalities=0;
 retryScheduleCount=retryRandomIndex=retryRandomCount=0;
 OverworldPopulationInput input={.version=OVERWORLD_POPULATION_INPUT_VERSION,.size=sizeof(input),.kind=OVERWORLD_POPULATION_INPUT_RESET,.fieldEpoch=actors.fieldEpoch};OverworldPopulationResult result;
 OverworldPopulation_Apply(&retryPopulation,&input,&result);
}
static int RetryControls(void){
 // READY ends the terrain series except the slot's alternate Land/Surf
 // attempt (bit 8), and cannot count a queued body.
 RetryReset();spawns.spawns[1].active=spawns.spawns[2].active=1;
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
 CHECK(prepares==1 && constructors==0 && runtime.queuedSpawnSlotPlusOne==1);
 CHECK(runtime.refillQueuedSerial==runtime.queuedSpawnSerial && runtime.refillTerrainMask==8);
 CHECK(retryScheduleCount==1 && retrySchedules[0]==59 && runtime.refillFailureStreak==OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE);
 committing=TRUE;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 CHECK(constructors==1 && spawns.spawns[0].active && !runtime.refillQueuedSerial && !runtime.refillTerrainMask);
 CHECK(retryScheduleCount==2 && retrySchedules[1]==7 && !runtime.refillFailureStreak); // 3 spawned: sparse interval
 unsigned oldConstructors=constructors;int oldSchedules=retryScheduleCount;
 OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 CHECK(constructors==oldConstructors && retryScheduleCount==oldSchedules);
 puts("READY is admission only; exact successful construction counts density once PASS");
 // Fewer than four land/surf Pokemon keep the base wait; the follower never counts; four restore the density wait.
 RetryReset();spawns.spawns[1].active=spawns.spawns[2].active=spawns.spawns[3].active=1;
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));committing=TRUE;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 CHECK(constructors==1 && retryScheduleCount==2 && retrySchedules[1]==239);
 puts("refill wait stays 15 below four spawned Pokemon (follower excluded) and scales from four PASS");
 // Moving spawn spans FF/FE/FD. No preparation, RNG, or timer repeats while pending.
 RetryReset();normalMode=FALSE;destinationReady=FALSE;
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));u32 serial=runtime.queuedSpawnSerial;
 CHECK(runtime.refillQueuedSerial==serial && runtime.refillPositionChecksRemaining==0xff);
 for(int n=0;n<4;n++)OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 CHECK(retryScheduleCount==1 && runtime.refillFailureStreak==OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE && runtime.refillQueuedSerial==serial);
 CHECK(prepares==1 && resolves==1 && !constructors && retryRandomIndex==0);
 destinationTerminal=TRUE;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 // A failed preferred Land commit still owes slot 0 its alternate Surf
 // attempt: no wait yet, and the next refill update runs it.
 CHECK(!runtime.queuedSpawnSlotPlusOne && !runtime.refillQueuedSerial && runtime.refillTerrainMask==8);
 CHECK(runtime.refillLandSurfSlot==0 && retryScheduleCount==1 && runtime.refillFailureStreak==OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE);
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
 CHECK(prepares==2 && runtime.queuedSpawnTerrain==OW_WILD_SPAWN_TERRAIN_SURF && !runtime.refillTerrainMask);
 for(int n=0;n<4 && runtime.queuedSpawnSlotPlusOne;n++)OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 // The alternate failing ends the series with the ordinary failure wait.
 CHECK(!runtime.queuedSpawnSlotPlusOne && !runtime.refillQueuedSerial && runtime.refillFailureStreak==1);
 CHECK(retryScheduleCount==2 && retrySchedules[1]==7);
 oldSchedules=retryScheduleCount;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
 CHECK(retryScheduleCount==oldSchedules && runtime.refillFailureStreak==1);
 RetryWait(7);CHECK(retryPopulation.refillArmed);RetryWait(1);CHECK(!retryPopulation.refillArmed);
 puts("async terminal Land failure tries Surf for the slot, then retries after the 8-frame sparse wait; pending and repeated receipt have no timing effect PASS");
 // Existing queue field/serial must still own the result after all borrowed callbacks.
 for(int fault=0;fault<3;fault++){
  RetryReset();CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  if(fault==0)runtime.queuedSpawnSerial++;if(fault==1)retryFieldCurrent=FALSE;if(fault==2)spawns.mapGeneration++;
  constructorReady=FALSE;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
  CHECK(retryScheduleCount==1 && runtime.refillFailureStreak==OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE);
 }
 puts("stale queue serial, current-field loss and map generation cannot publish retry timing PASS");
 // Direct public normal and Move queues are excluded, even with a prior failure streak.
 for(int moving=0;moving<2;moving++){
  RetryReset();runtime.refillFailureStreak=2;normalMode=!moving;destinationReady=!moving;
  OverworldWildPreparedSpawn external={0};external.encounter.species=74;external.encounter.level=5;
  if(moving)CHECK(!OverworldWildSpawns_FinalizePreparedSpawn(&spawns,&field,0,0,&external));
  else {external.startup.locomotion=1;CHECK(OverworldWildSpawns_ArmEntryQueue(&spawns,0,0,&external));}
  CHECK(runtime.queuedSpawnSlotPlusOne==1 && !runtime.refillQueuedSerial);
  destinationTerminal=TRUE;constructorReady=FALSE;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
  CHECK(retryScheduleCount==0 && runtime.refillFailureStreak==2);
 }
 puts("manual normal/Move queues retain their existing timing and do not consume natural failure streak PASS");
 // Four completed failed series: three short delays then one density backoff.
 RetryReset();spawns.spawns[2].active=spawns.spawns[3].active=spawns.spawns[4].active=spawns.spawns[5].active=1;prepareResult=0;
 for(int series=0;series<4;series++){
  unsigned p=prepares;CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  CHECK(prepares==p+1 && runtime.refillTerrainMask==8);
  p=prepares;CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  CHECK(prepares==p+1 && runtime.refillTerrainMask==0);
  CHECK(retrySchedules[retryScheduleCount-1]==(series<3?7:239));
  CHECK(runtime.refillFailureStreak==(series<3?series+1:0));
  RetryWait(series<3?15:240);CHECK(!retryPopulation.refillArmed);
 }
 puts("one terrain attempt/update; three short retries then normal density backoff PASS");
 // Sparse area: the fourth failed series still waits only the base interval.
 RetryReset();spawns.spawns[4].active=spawns.spawns[5].active=1;prepareResult=0;
 for(int series=0;series<4;series++){
  CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  CHECK(retrySchedules[retryScheduleCount-1]==7);RetryWait(8);
 }
 puts("two spawned Pokemon: every failed-series wait stays at the 8-frame sparse interval PASS");
 // Every actual Wild slot works. Follower7 stays excluded and optional groups do not inflate density.
 for(int slot=0;slot<10;slot++){
  if(slot==7)continue;RetryReset();
  if(slot<6){for(int n=0;n<slot;n++)spawns.spawns[n].active=1;}
  else {
   for(int n=0;n<6;n++)spawns.spawns[n].active=1;
   spawns.headbuttSpawnCooldown=spawns.fishingSpawnCooldown=0;
   retryRandomValues[0]=slot<8?0:99;retryRandomValues[1]=slot<8?99:0;retryRandomCount=2;
   if(slot==8||slot==9)spawns.spawns[6].active=1;
   if(slot==9)spawns.spawns[8].active=1;
  }
  CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  CHECK(prepares==1 && runtime.queuedSpawnSlotPlusOne==slot+1 && runtime.refillQueuedSerial==runtime.queuedSpawnSerial);
  OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
  CHECK(constructors==1 && spawns.spawns[slot].active && spawns.spawns[7].active);
  CHECK(retrySchedules[retryScheduleCount-1]==(slot<3?7:slot<6?(slot+1)*60-1:359));
  CHECK(retryRandomIndex==(slot<6?0:2));
 }
 puts("all9 Wild slots; follower7 unchanged; optional groups/density and gate RNG order preserved PASS");
 RetryReset();runtime.refillFailureStreak=2;for(int n=0;n<6;n++)spawns.spawns[n].active=1;
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));CHECK(!prepares && retrySchedules[retryScheduleCount-1]==359 && !runtime.refillFailureStreak);
 // Execute the exact existing FieldBusy queue/lifecycle block, plus unsupported-map path.
 RetryReset();runtime.refillFailureStreak=3;runtime.refillQueuedSerial=99;runtime.refillTerrainMask=8;runtime.refillPositionChecksRemaining=0xff;runtime.queuedSpawnSlotPlusOne=1;
 RetryFieldBusy(&spawns);CHECK(!runtime.refillFailureStreak && !runtime.refillQueuedSerial && !runtime.refillTerrainMask && !runtime.refillPositionChecksRemaining && !runtime.queuedSpawnSlotPlusOne);
 runtime.refillFailureStreak=3;runtime.refillQueuedSerial=99;retryEnabled=FALSE;
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));CHECK(!runtime.refillFailureStreak && !runtime.refillQueuedSerial);

 puts("full slots back off; exact FieldBusy and unsupported-map lifecycle clears PASS");
 // Both output parts are named. Pending/manual/empty never carry a natural delay.
 RetryReset();normalMode=FALSE;destinationReady=FALSE;
 CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
 OverworldEntryRouteNativeControl packet={.operation=OVERWORLD_ENTRY_NATIVE_COMMIT};
 u32 value=OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet);
 CHECK(OVERWORLD_ENTRY_COMMIT_OUTCOME(value)==OVERWORLD_ENTRY_COMMIT_PENDING && !OVERWORLD_ENTRY_COMMIT_REFILL_DELAY(value));
 destinationTerminal=TRUE;packet=(OverworldEntryRouteNativeControl){.operation=OVERWORLD_ENTRY_NATIVE_COMMIT};
 value=OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet);
 // The preferred Land failure carries no delay: slot 0 still owes Surf.
 CHECK(OVERWORLD_ENTRY_COMMIT_OUTCOME(value)==OVERWORLD_ENTRY_COMMIT_FAILED && !OVERWORLD_ENTRY_COMMIT_REFILL_DELAY(value));
 CHECK(runtime.refillTerrainMask==8 && !runtime.refillQueuedSerial && retryScheduleCount==1);
 destinationTerminal=FALSE;CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
 CHECK(runtime.queuedSpawnSlotPlusOne==1 && runtime.queuedSpawnTerrain==OW_WILD_SPAWN_TERRAIN_SURF && !runtime.refillTerrainMask);
 destinationTerminal=TRUE;packet=(OverworldEntryRouteNativeControl){.operation=OVERWORLD_ENTRY_NATIVE_COMMIT};
 value=OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet);
 CHECK(OVERWORLD_ENTRY_COMMIT_OUTCOME(value)==OVERWORLD_ENTRY_COMMIT_FAILED && OVERWORLD_ENTRY_COMMIT_REFILL_DELAY(value)==15);
 CHECK(runtime.refillFailureStreak==1 && !runtime.refillQueuedSerial && retryScheduleCount==1);
 packet=(OverworldEntryRouteNativeControl){.operation=OVERWORLD_ENTRY_NATIVE_COMMIT};
 value=OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet);
 CHECK(value==OVERWORLD_ENTRY_COMMIT_NONE && runtime.refillFailureStreak==1);
 puts("COMMIT distinguishes PENDING/FAILED/empty and consumes ownership before the resident timer PASS");
 for(int fault=1;fault<=6;fault++) {
  RetryReset();CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  retryMutation=fault;OverworldWildSpawns_CommitQueuedSpawn(&spawns,&field);
  CHECK(constructors==1 && retryScheduleCount==1);
  CHECK(runtime.refillFailureStreak==OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE);
 }
 puts("post-constructor epoch, map generation, Field, Runtime and serial rebound cannot publish a delay PASS");
 // FinishRefill is the existing52-byte Control with one strict private subtype.
 RetryReset();runtime.refillFailureStreak=OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE|2;
 packet=(OverworldEntryRouteNativeControl){.operation=OVERWORLD_ENTRY_NATIVE_FINISH_REFILL,.queryOperation=OVERWORLD_ENTRY_REFILL_FAILED};
 value=OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet);
 CHECK(value==15 && runtime.refillFailureStreak==3 && retryScheduleCount==0);
 packet=(OverworldEntryRouteNativeControl){.operation=OVERWORLD_ENTRY_NATIVE_FINISH_REFILL,.queryOperation=OVERWORLD_ENTRY_REFILL_FAILED};
 CHECK(!OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet) && runtime.refillFailureStreak==3);
 for(int bad=0;bad<13;bad++) {
  RetryReset();runtime.refillFailureStreak=OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE|2;
  packet=(OverworldEntryRouteNativeControl){.version=1,.size=sizeof(packet),.ops=&sOverworldWildEntryNativeOps,.state=&spawns,.field=&field,.operation=OVERWORLD_ENTRY_NATIVE_FINISH_REFILL,.queryOperation=OVERWORLD_ENTRY_REFILL_FAILED};
  OverworldEntryRouteCommand command={0};command.nativeControl=&packet;call.entry=&command;call.routeOperation=1;call.heapId=4;
  switch(bad){case 0:packet.value=1;break;case 1:packet.queryOperation=2;break;case 2:packet.terrain=1;break;case 3:packet.accepted=1;break;case 4:packet.usableIdle=1;break;case 5:packet.profile=&profile;break;case 6:packet.primitives=&primitives;break;case 7:packet.prepared=&runtime.queuedSpawn;break;case 8:packet.object=&objects[0];break;case 9:packet.receipt=&runtime.entryRouteReceipt;break;case 10:packet.startCommitSequence=1;break;case 11:packet.reserved[0]=1;break;case 12:packet.operation=10;break;}
  OverworldWildOverlayRuntimeState prior=runtime;
  CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID && !memcmp(&runtime,&prior,sizeof(runtime)));
 }
 for(int bad=0;bad<7;bad++) {
  RetryReset();runtime.refillFailureStreak=OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE|2;
  switch(bad){case 0:runtime.queuedSpawnSlotPlusOne=1;break;case 1:runtime.refillQueuedSerial=99;break;case 2:runtime.refillTerrainMask=8;break;case 3:runtime.refillPositionChecksRemaining=1;break;case 4:runtime.refillFailureStreak=2;break;case 5:retryFieldCurrent=FALSE;break;case 6:spawns.mapGeneration++;break;}
  u8 prior=runtime.refillFailureStreak;packet=(OverworldEntryRouteNativeControl){.operation=OVERWORLD_ENTRY_NATIVE_FINISH_REFILL,.queryOperation=OVERWORLD_ENTRY_REFILL_FAILED};
  CHECK(!OverworldWildSpawns_EntryControl(&spawns,&field,0,NULL,&packet) && runtime.refillFailureStreak==prior);
 }
 puts("typed FinishRefill once-only receipt;13 wrong packets and7 pending/stale/empty-series states rejected PASS");return 0;

}
int main(void){if(NativeControls())return 1;return RetryControls();}
