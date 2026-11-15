/* The real final COMMIT owns READY-origin admission. The visible constructor
 * is the native spawn callback, counted before any successful birth. */
static unsigned readyOccupancies;
static BOOL OriginOccupied(FieldSystem*f,int x,int y){(void)f;CHECK(x==30 && y==40);readyOccupancies++;return occupiedOrigin;}
static int OriginControls(void){
 for(unsigned mode=0;mode<6;mode++){
  Reset();field.savedata=&field;normalMode=FALSE;destinationReady=TRUE;preparedStatus=OVERWORLD_PICKUP_ROUTE_REACHABLE;
  constructors=guards=placements=readyOccupancies=0;occupiedOrigin=FALSE;guardReady=placementReady=constructorReady=TRUE;committing=TRUE;
  runtime.queuedSpawnSlotPlusOne=1;runtime.queuedSpawnSerial=7;runtime.refillPositionChecksRemaining=OW_WILD_SPAWN_ROUTE_READY;
  OverworldWildPreparedSpawn*p=&runtime.queuedSpawn;p->encounter.species=74;p->encounter.level=5;
  p->position.startX=30;p->position.startY=40;p->startup.targetX=31;p->startup.targetY=40;p->startup.locomotion=3;
  p->behaviorResolution.primitives.spawnLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN;
  player.xCurr=17;player.yCurr=40;
  if(mode==0)player.xCurr=18;
  if(mode==1)occupiedOrigin=TRUE;
  if(mode==2)field.playerAvatar=NULL;
  if(mode==4){player.xCurr=30;player.yCurr=29;}
  if(mode==5){field.playerAvatar=NULL;runtime.refillPositionChecksRemaining=0;p->behaviorResolution.primitives.spawnLocomotion=1;}
  OverworldEntryRouteNativeOps ops=sOverworldWildEntryNativeOps;ops.occupied=OriginOccupied;
  OverworldEntryRouteNativeControl c={.ops=&ops,.state=&spawns,.field=&field};
  unsigned result=NativeCommitOnce(&call,&c,&spawns,&field);
  CHECK(!runtime.queuedSpawnSlotPlusOne && !runtime.refillPositionChecksRemaining);
  if(mode<3){CHECK(result==OVERWORLD_ENTRY_COMMIT_FAILED && !guards && !placements && !constructors);CHECK(readyOccupancies==(mode==1));}
  else{CHECK(result==OVERWORLD_ENTRY_COMMIT_SUCCESS && guards==1 && placements==1 && constructors==1);CHECK(readyOccupancies==(mode!=5));}
 }
 puts("actual READY commit: moved Player rejects before guard/constructor; occupied/null origin rejects;13/11 boundary admits; normal spawn unchanged PASS");return 0;
}
int main(void){return OriginControls();}
