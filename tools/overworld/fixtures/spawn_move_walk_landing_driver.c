static OverworldPickupRouteWildLandingCall landing;
static void SetupWalk(void) {
 Reset();CertifyCatalog();heightReject=rawBlocked=targetBlock=walkHeightCalls=rawCalls=sourceCalls=targetCalls=0;
 objects[0].xCurr=4;objects[0].yCurr=4;objects[0].xInit=objects[0].yInit=4;
 landing=(OverworldPickupRouteWildLandingCall){.state=&state,.field=&field,.behaviorData=&behaviorData,.ops=&ops,.slot=0,
  .allowedTile=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND|OVERWORLD_PICKUP_LANDING_WILD_STRICT_DIAGONAL_MARKER,
  .x=5,.y=4,.finalTargetX=5,.finalTargetY=4};
}
static OverworldPreparedMovementInput PhysicalInput(void) {
 OverworldPreparedMovementInput i={0};i.version=OVERWORLD_PREPARED_MOVEMENT_VERSION;i.size=sizeof(i);i.field=&field;i.ops=&ops;
 i.from=(OverworldPickupRoutePosition){4,4,9,0xffff,0};i.to=(OverworldPickupRoutePosition){5,4,9,0xffff,0};
 i.source.behavior=4;i.target.behavior=5;i.rangeX=i.rangeY=-1;i.anchorX=i.anchorY=4;i.directions=3;i.blockedTerrain=RawBlockedExact;
 return i;
}
int main(void) {
 SetupWalk();OverworldMotionDecision actual=OverworldPickupLandingWild_Classify(&landing);
 printf("strict bare Walk decision=%d height=%d collision=%d source=%d target=%d\n",actual,walkHeightCalls,rawCalls,sourceCalls,targetCalls);
 CHECK(actual==OVERWORLD_MOTION_DECISION_ACCEPTED && walkHeightCalls==1 && rawCalls==1 && sourceCalls==1 && targetCalls==1);
 CHECK(observedFromX==(4*16+8)*4096 && observedFromY==(4*16+8)*4096 && observedFromBase==9);
 CHECK(objects[0].xCurr==4 && objects[0].yCurr==4 && objects[0].posVec[1]==9);
 for(int direction=0;direction<4;direction++) {
  static const int dx[4]={0,0,-1,1},dy[4]={-1,1,0,0};SetupWalk();landing.x=4+dx[direction];landing.y=4+dy[direction];
  CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_ACCEPTED && walkHeightCalls==1 && rawCalls==1);
 }
 SetupWalk();heightReject=-1;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && walkHeightCalls==1 && !rawCalls && !sourceCalls);
 SetupWalk();heightReject=1;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && walkHeightCalls==1 && !rawCalls);
 SetupWalk();rawBlocked=1;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && walkHeightCalls==1 && rawCalls==1 && !sourceCalls);
 SetupWalk();blockSource=4;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && sourceCalls==1 && !targetCalls);
 SetupWalk();targetBlock=1;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && targetCalls==1);
 SetupWalk();targetBlock=1;blockSource=4;objects[0].flags2=4;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_ACCEPTED && walkHeightCalls==1 && rawCalls==1 && !sourceCalls && !targetCalls);
 SetupWalk();objects[0].xrange=0;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && !walkHeightCalls);
 SetupWalk();bodyX=5;bodyY=4;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_OCCUPIED && !walkHeightCalls);
 SetupWalk();landing.x=landing.y=5;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_ACCEPTED && occupancyCalls==3 && !walkHeightCalls);
 SetupWalk();landing.x=landing.y=5;bodyX=5;bodyY=4;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_OCCUPIED && !walkHeightCalls);
 SetupWalk();missingTileX=5;CHECK(OverworldPickupLandingWild_Classify(&landing)!=OVERWORLD_MOTION_DECISION_ACCEPTED && !walkHeightCalls);
 SetupWalk();behaviorData.header.surfaceModelsOffset++;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE && !walkHeightCalls);
 SetupWalk();FieldSystem other={0};landing.field=&other;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE && !walkHeightCalls);
 SetupWalk();landing.field=NULL;CHECK(OverworldPickupLandingWild_Classify(&landing)==OVERWORLD_MOTION_DECISION_PROFILE && !walkHeightCalls);
 /* Only bare physical Walk can omit the pair. Partial pairs are always bad. */
 SetupWalk();OverworldPreparedMovementInput i=PhysicalInput();OverworldWildBehaviorProfile profile={0};
 CHECK(OverworldPreparedMovement_Run(&i)==LEGAL && walkHeightCalls==1);
 i.profile=&profile;CHECK(OverworldPreparedMovement_Run(&i)==INVALID);i.profile=NULL;i.lane=&lane;CHECK(OverworldPreparedMovement_Run(&i)==INVALID);
 i.lane=NULL;i.kind=OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE;i.to.x=6;CHECK(OverworldPreparedMovement_Run(&i)==INVALID);
 i.kind=OVERWORLD_PREPARED_MOVEMENT_TELEPORT;CHECK(OverworldPreparedMovement_Run(&i)==INVALID);
 i.kind=OVERWORLD_PICKUP_ROUTE_NATIVE_WALK;i.to.x=5;i.directions=2;CHECK(OverworldPreparedMovement_Run(&i)==BLOCKED);
 i.directions=0;CHECK(OverworldPreparedMovement_Run(&i)==INVALID);
 i.profile=&profile;i.lane=&lane;i.directions=1;i.to.y=5;CHECK(OverworldPreparedMovement_Run(&i)==BLOCKED);i.directions=2;CHECK(OverworldPreparedMovement_Run(&i)==LEGAL);
 /* The real saved reducer keeps its conservative8-token height admission. */
 SetupWalk();i=PhysicalInput();OverworldPreparedMovementCursor c={.version=OVERWORLD_PREPARED_MOVEMENT_VERSION,.size=sizeof(c),.input=&i};
 CHECK(OverworldPreparedMovement_Begin(&c)==DEFERRED && !walkHeightCalls);c.readBudget=7;
 CHECK(OverworldPreparedMovement_Step(&c)==DEFERRED && !walkHeightCalls && !c.readsUsed);c.readBudget=8;
 CHECK(OverworldPreparedMovement_Step(&c)==DEFERRED && walkHeightCalls==1 && c.readsUsed==8 && !rawCalls);c.readBudget=1;
 CHECK(OverworldPreparedMovement_Step(&c)==LEGAL && rawCalls==1 && c.readsUsed==1 && sourceCalls==1 && targetCalls==1);
 puts("actual Landing/Native/EdgePolicy/Prepared Walk chain; stock height/collision/directions/range, diagonal sides, occupancy/catalog/Field and kind/pair/budget guards PASS");return 0;
}
