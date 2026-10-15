/* Production Cargo setup and real Cargo/Native/Route reducers. Native engine
 * structs expose only used named fields; they do not claim native ARM layout.
 * The read-only seams below describe an open, loaded native map, not motion. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_cargo_query.h"
#include "overworld_target_bindings.h"
typedef struct OverworldWildBehaviorProfile OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorConditionOptions OverworldWildBehaviorConditionOptions;
#include "overworld_cargo_query_wild.h"

#define CHECK(x) do { if(!(x)) { fprintf(stderr,"Cargo Wild line%d: %s\n",__LINE__,#x); return 1; } }while(0)
#define FX32_SHIFT 12
typedef struct VecFx32 {s32 x,y,z;} VecFx32;
typedef OverworldPickupRouteEdgeResult Result;
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define TRUE 1
#define FALSE 0
#define MAPOBJECTFLAG_ACTIVE 1u
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_HELPER_THROW_TARGET_NONE 0
#define OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG 0x80
#define OW_WILD_HELPER_THROW_TARGET_DECODE(value) (((value)&0x3Fu)-1u)
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER 16
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(mode) (((mode)&3)<2)
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode) (((mode)&3)!=0)
#define NATIVE_GROUND 0xFFFF
#define EXCLUDED_ID 0xF0

typedef struct LocalMapObject {
    u32 flags,flags2; s32 id,xCurr,yCurr,xInit,yInit,xrange,yrange,curFacing,xPrev,yPrev;
    u32 posVec[3];
} LocalMapObject;
typedef struct MapObjectMan { LocalMapObject *objects; u32 object_count; } MapObjectMan;
typedef struct PlayerAvatar { LocalMapObject *mapObject; } PlayerAvatar;
struct FieldSystem { MapObjectMan *mapObjectMan; PlayerAvatar *playerAvatar; void *map_matrix; const u8 *land; };
typedef struct OverworldWildSpawn {
    LocalMapObject *object; u32 personality; u16 encounterGeneration; u8 active;
} OverworldWildSpawn;
typedef struct OverworldWildBehaviorProfileData {
    u8 hopAllowNonCardinal,hopMinDistance,hopMaxDistance,hopAllowVerticalObstacles;
    u8 hopTime,hopElevationTimeScale,hopElevationArcScale;
    u8 continueWhenArrived;
} OverworldWildBehaviorProfileData;
struct OverworldWildBehaviorProfile { OverworldWildBehaviorProfileData owner; };
struct OverworldWildBehaviorConditionOptions { u8 captureBinding,pickupHeight,pickupDistance,usesBinding; };
#define OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED 2
/* Named host fields only; Policy consumes these fields, not their ARM layout. */
typedef struct OverworldActorPolicyView {
    struct { u8 skidRemaining; } walkMomentum;
    u8 chainPauseAction,chainStepsRemaining,pendingStep,motionPhase,pendingSkid;
} OverworldActorPolicyView;
typedef struct OverworldActorRuntimeSlot {
    OverworldActorStateSnapshot snapshot; struct {u16 targetSurfaceId;} policy;
} OverworldActorRuntimeSlot;
typedef struct OverworldActorSystemState { OverworldActorRuntimeSlot slots[10];u16 fieldEpoch,mapGeneration; } OverworldActorSystemState;
#include "cargo_prepared_production.inc"
typedef struct OverworldWildBehaviorConditionRuntime {
    struct { OverworldBehaviorConditionWorldView world;
        struct { u8 reserved[3]; } candidates[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
        u8 valid; } frame;
    OverworldTargetBindingsState bindings[10];
    OverworldBehaviorConditionPreparedActor actors[10];
} OverworldWildBehaviorConditionRuntime;
typedef struct OverworldWildOverlayRuntimeState {
    OverworldWildBehaviorConditionRuntime *conditions; void *pickupQuery;
    struct {u8 targets[10];u16 targetMask,carrierMask,recoveringMask;} throwState;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    OverworldWildOverlayRuntimeState *movementRuntimeState;FieldSystem *movementFieldSystem; u16 mapGeneration;
    OverworldWildSpawn spawns[10];
    u16 captureTargetMask;
    u8 movementActorControlModes[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;

#include "cargo_motion_decision_production.inc"
#include "cargo_query_wild_production.inc"

static FieldSystem field;
static MapObjectMan manager;
static PlayerAvatar avatar;
static LocalMapObject objects[64],player;
static OverworldWildSpawnState spawns;
static OverworldWildOverlayRuntimeState runtime;
static OverworldWildBehaviorConditionRuntime conditions;
static OverworldActorSystemState actors;
static OverworldActorPolicyView actorPolicy;
static OverworldPickupRouteWildWorld world;
static OverworldCargoQueryWildCall call;
static OverworldWildBehaviorProfile profile;
static OverworldWildBehaviorConditionOptions options;
static OverworldCargoQueryResult output;
static _Alignas(void *) u8 land[0xD0];
static _Alignas(u32) u8 slots[4][0x868];
static u8 matrix[2];
static u32 freeBytes,allocations,positionReads,nativeCalls;
static int missingX=-1,blockedX=-1;
static u8 expectedSubjectSlot,expectedCargoSlot;

static const OverworldActorSystemState *ActorState(void) { return &actors; }
static BOOL Current(FieldSystem *f,LocalMapObject *o) {
    return f==&field && o>=objects && o<objects+64;
}
static u8 Behavior(FieldSystem *f,int x,int y) { (void)f;(void)y; return x==missingX?0xFF:0; }
static BOOL Surface(FieldSystem *f,const OverworldWildSurfaceCatalog *c,int x,int y,OverworldWildSurfaceHit *h) {
    (void)f;(void)c;(void)x;(void)y;(void)h;return 0;
}
static BOOL Base(FieldSystem *f,const OverworldWildSurfaceHit *s,s32 y,u32 flags,int x,int z,s32 *out) {
    (void)f;(void)s;(void)flags;(void)x;(void)z;++positionReads;*out=y;return 1;
}
static BOOL Inspect(u8 slot,OverworldActorPolicyView *out) { if(slot>=10)return 0;*out=actorPolicy;return 1; }
static void *Allocate(u32 heap,u32 bytes) { (void)heap;++allocations;return calloc(1,bytes); }
static u32 FreeSize(u32 heap) { (void)heap;return freeBytes; }
static BOOL WalkTerrain(FieldSystem *f,const void *position,int x,int y,s8 *direction) {
    (void)f;(void)position;(void)x;(void)y;*direction=0;return FALSE;
}
static BOOL DirectionBlock(u8 behavior) { (void)behavior;return FALSE; }
static const OverworldPickupRouteWildDirectionBlock directionBlocks[4]={DirectionBlock,DirectionBlock,DirectionBlock,DirectionBlock};
static const OverworldPickupRouteWildOps ops={
    .version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION,.size=sizeof(ops),
    .behavior=Behavior,.querySurface=Surface,.resolveBaseYAt=Base,
    .currentObject=Current,.actorState=ActorState,.inspectPolicy=Inspect,
    .walkTerrain=WalkTerrain,.sourceDirectionBlocks=directionBlocks,.targetDirectionBlocks=directionBlocks,
};

/* Stock reads/occupancy are the only stubbed seams; all search/cache work is
 * the actual production reducer. There are no native writes or reservations. */
static OverworldPickupRouteEdgeResult Bind(void *raw,const OverworldPickupRouteQuery *q) {
    ((OverworldPickupRouteWildWorld *)raw)->routeRead=q!=NULL;++nativeCalls;
    return q->subject.slot==expectedSubjectSlot
        && Same(&q->subject,&actors.slots[expectedSubjectSlot].snapshot.handle,12)
        && q->cargo.slot<10 && (expectedCargoSlot==255 || q->cargo.slot==expectedCargoSlot)
        && Same(&q->cargo,&actors.slots[q->cargo.slot].snapshot.handle,12)?LEGAL:OVERWORLD_PICKUP_ROUTE_EDGE_INVALID;
}
static OverworldPickupRouteEdgeResult Terrain(void *raw,s16 x,s16 y,u16 wantedMask,OverworldPickupRouteNativeTile *out) {
    (void)raw;if(x==missingX)return DEFERRED;
    if(x==blockedX)return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
    if(x<0||x>63||y<0||y>31)return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
    *out=(OverworldPickupRouteNativeTile){NATIVE_GROUND,(u16)(wantedMask&1),0,0,0};return LEGAL;
}
static OverworldPickupRouteEdgeResult Support(void *raw,const OverworldPickupRoutePosition *from,
    s16 x,s16 y,const OverworldPickupRouteNativeTile *tile,s32 *out) {
    (void)raw;(void)x;(void)y;(void)tile;*out=from->baseY;return LEGAL;
}
static OverworldPickupRouteEdgeResult Occupancy(void *raw,const OverworldActorHandle *subject,
    const OverworldPickupRoutePosition *at,u8 includePlayer) {
    (void)raw;(void)includePlayer;
    for(int n=0;n<64;n++)if((objects[n].flags&1) && &objects[n]!=spawns.spawns[subject->slot].object
        && objects[n].id!=EXCLUDED_ID && objects[n].xCurr==at->x && objects[n].yCurr==at->y)
        return OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
    return LEGAL;
}
static OverworldPickupRouteEdgeResult Reservations(void *raw,const OverworldActorHandle *subject,
    const OverworldPickupRoutePosition *at) { (void)raw;(void)subject;(void)at;return LEGAL; }
#undef INVALID
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
#include "cargo_walk_policy_production.inc"
#undef INVALID
#define INVALID OVERWORLD_PICKUP_ROUTE_INVALID
static OverworldPickupRouteEdgeResult Hop(void *raw,const OverworldPickupRouteNativePolicy *p,u8 kind,u16 distance,
    const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to) {
    (void)raw;(void)p;(void)kind;(void)distance;(void)from;(void)to;return LEGAL;
}
static OverworldPickupRouteEdgeResult Reach(void *raw,const OverworldPickupRouteNativePolicy *p,
    const OverworldPickupRoutePosition *at,const OverworldPickupRoutePosition *cargo) {
    (void)raw;(void)p;int dx=at->x-cargo->x,dy=at->y-cargo->y;
    return dx>=-1&&dx<=1&&dy>=-1&&dy<=1&&at->baseY==cargo->baseY?LEGAL:OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
}
static const OverworldPickupRouteNativeSeams seams={Bind,Terrain,Support,Occupancy,Reservations,EdgePolicy,Hop,Reach};
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *raw) { (void)raw;return &seams; }

/* The current native throw facts/position and authored-options callbacks are
 * host seams. Observe, binding validation and while-true evaluation below are
 * production C; a pending route must not manufacture new route admission. */
typedef struct OverworldWildBehaviorDataBlob {
    struct { u8 conditionEntryCount; } header;
    OverworldWildBehaviorConditionOptions conditionOptions[32];
} OverworldWildBehaviorDataBlob;
#define OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE (1u<<0)
#define OVERWORLD_CONDITION_NATIVE_CALL_VERSION 1
#define OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS 2
typedef struct OverworldConditionNativeCall {
    OverworldWildBehaviorConditionRuntime *runtime;
    OverworldWildSpawnState *state;
    FieldSystem *field;
    const OverworldWildBehaviorDataBlob *blob;
    u32 blobSize,allowedTerrainMask;
    u16 version,size;
    u8 slot,operation;
    OverworldPickupRouteWildWorld *targetAccessWorld;
} OverworldConditionNativeCall;
typedef BOOL (*PlayerHealthThrowIsCurrentSpawnFunc)(FieldSystem *,const OverworldWildSpawn *);
typedef BOOL (*PlayerHealthThrowQueryTargetFunc)(OverworldWildSpawnState *,int,int,u8,u32);
typedef struct PlayerHealthThrowServiceEntry {
    u32 (*observe)(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,
        const OverworldWildBehaviorDataBlob *,const OverworldWildBehaviorConditionRuntime *,
        PlayerHealthThrowIsCurrentSpawnFunc,PlayerHealthThrowQueryTargetFunc);
    BOOL (*bindingPosition)(OverworldWildSpawnState *,u8,u8,OverworldTargetBindingPosition *);
} PlayerHealthThrowServiceEntry;
typedef struct OverworldCargoReadWildObservationCall {
    OverworldCargoQueryWildCall cargo;
    OverworldWildBehaviorConditionRuntime *conditions;
    const PlayerHealthThrowServiceEntry *throwService;
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn;
    PlayerHealthThrowQueryTargetFunc queryTarget;
} OverworldCargoReadWildObservationCall;
static int forcedRouteStatus=-1;
static u8 forcedRouteFlags;
static OverworldCargoQueryResult observedRoute;
static const OverworldWildBehaviorConditionOptions *OverworldCargoReadWild_Options(
    const OverworldPickupRouteWildWorld *w) { (void)w;return &options; }
static OverworldPickupRouteStatus OverworldCargoReadWild_Route(
    const OverworldCargoQueryWildCall *c,OverworldCargoQueryResult *r) {
    if(forcedRouteStatus>=0) {
        *r=(OverworldCargoQueryResult){0};r->status=forcedRouteStatus;r->flags=forcedRouteFlags;
        observedRoute=*r;
        return forcedRouteStatus;
    }
    OverworldCargoQueryWildCall route=*c;
    route.options=OverworldCargoReadWild_Options(route.world);
    OverworldPickupRouteStatus status=OverworldCargoQueryWild_Tick(&route,r);
    observedRoute=*r;
    return status;
}
extern u8 OverworldPickupRoute_EqualValues(const void *,const void *,u8);
#include "cargo_release_production.inc"
#include "cargo_read_wild_observe_production.inc"
#include "../../../lib/overworld/overworld_target_bindings.c"
#include "../../../lib/overworld/overworld_behavior_conditions.c"
#include "../../../lib/overworld/overworld_vision.c"
static BOOL BindingPosition(OverworldWildSpawnState *s,u8 slot,u8 name,
    OverworldTargetBindingPosition *out) {
    OverworldBehaviorConditionWorldView current=s->movementRuntimeState->conditions->frame.world;
    current.subject=s->movementRuntimeState->conditions->bindings[slot].subject;
    return OverworldTargetBindings_Resolve(&conditions.bindings[slot],&current,name,out)==OVERWORLD_TARGET_BINDING_OK;
}
static u32 ThrowFacts(OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorProfile *p,
    const OverworldWildBehaviorDataBlob *b,const OverworldWildBehaviorConditionRuntime *c,
    PlayerHealthThrowIsCurrentSpawnFunc current,PlayerHealthThrowQueryTargetFunc target) {
    (void)p;(void)b;(void)c;(void)current;(void)target;OverworldTargetBindingPosition trigger;
    return (BindingPosition(s,slot,OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST,&trigger)
        ?OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID:0)|(u32)call.eligibleActorMask<<8;
}
static const PlayerHealthThrowServiceEntry throwService={ThrowFacts,BindingPosition};

static void Reset(void) {
    free(runtime.pickupQuery);
    memset(&spawns,0,sizeof(spawns));memset(&runtime,0,sizeof(runtime));memset(&conditions,0,sizeof(conditions));
    memset(&actors,0,sizeof(actors));memset(objects,0,sizeof(objects));memset(&world,0,sizeof(world));
    memset(land,0,sizeof(land));memset(slots,0,sizeof(slots));memset(&player,0,sizeof(player));
    memset(spawns.movementActorControlModes,OW_WILD_ACTOR_CONTROL_AUTONOMOUS,
        sizeof(spawns.movementActorControlModes));
    freeBytes=100000;allocations=positionReads=nativeCalls=0;missingX=blockedX=-1;actorPolicy=(OverworldActorPolicyView){0};
    forcedRouteStatus=-1;forcedRouteFlags=0;
    observedRoute=(OverworldCargoQueryResult){0};
    expectedSubjectSlot=0;expectedCargoSlot=1;
    manager=(MapObjectMan){objects,64};avatar.mapObject=&player;field=(FieldSystem){&manager,&avatar,matrix,land};
    matrix[0]=2;matrix[1]=1;
    for(int n=0;n<2;n++) {
        const void *ptr=slots[n];memcpy(land+0x90+sizeof(void *)*n,&ptr,sizeof(ptr));
        *(u32 *)(slots[n]+0x860)=n;*(u32 *)(slots[n]+0x864)=1;
        objects[n].flags=1;objects[n].id=100+n;objects[n].xCurr=4+n*8;objects[n].yCurr=4;
        objects[n].xrange=objects[n].yrange=-1;objects[n].posVec[1]=64;
        actors.slots[n].snapshot.active=1;actors.slots[n].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
        actors.slots[n].snapshot.subjectIdentity=1000+n;
        actors.slots[n].snapshot.handle=(OverworldActorHandle){n,2+n,3,4,5+n,0};
        spawns.spawns[n]=(OverworldWildSpawn){objects+n,1000+n,5+n,1};
        conditions.frame.world.actors[n]=(OverworldBehaviorConditionActorObservation){actors.slots[n].snapshot.handle,4+n*8,4,1,0,3,0};
    }
    spawns.movementRuntimeState=&runtime;spawns.movementFieldSystem=&field;spawns.mapGeneration=4;runtime.conditions=&conditions;
    actors.fieldEpoch=3;actors.mapGeneration=4;
    conditions.frame.valid=1;conditions.frame.world.frame=10;conditions.frame.world.actorCount=2;conditions.frame.world.playerValid=1;
    conditions.frame.world.subject=actors.slots[0].snapshot.handle;conditions.frame.world.subjectX=4;conditions.frame.world.subjectY=4;
    conditions.frame.world.subjectRoleMask=1;conditions.bindings[0].subject=actors.slots[0].snapshot.handle;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags=OVERWORLD_TARGET_BINDING_BOUND;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
    world.version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION;world.size=sizeof(world);world.field=&field;world.state=&spawns;
    world.subjectObject=world.heightObject=&objects[0];world.ops=&ops;world.catalog=(const void *)&field;
    profile.owner=(OverworldWildBehaviorProfileData){1,2,8,0,6,0,0,0};options=(OverworldWildBehaviorConditionOptions){2,16,1,1};
    call=(OverworldCargoQueryWildCall){.world=&world,.profile=&profile,.options=&options,
        .allocate=Allocate,.freeSize=FreeSize,.heapId=11,.eligibleActorMask=2,
        .allowedTerrainMask=1,.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_WALK};
}
static int Finish(void) {
    for(int n=0;n<1000;n++) {
        ++conditions.frame.world.frame;
        OverworldPickupRouteStatus status=OverworldCargoQueryWild_Tick(&call,&output);
        CHECK(status==PENDING||status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
        if(status==OVERWORLD_PICKUP_ROUTE_REACHABLE)return 0;
    }
    CHECK(0);return 1;
}
static int HasTile(const NativeQuery *q,int x,int y) {
    for(u16 n=0;n<q->changeCount;n++)if(q->changed[n].x==x&&q->changed[n].y==y)return 1;return 0;
}
static int PolicyChecks(void) {
    Reset();objects[0].xInit=objects[0].xCurr;objects[0].yInit=objects[0].yCurr;
    NativeQuery q={0};OverworldPickupRouteNativePolicy p;
    CHECK(Policy(&q,&call,&p));CHECK(q.edgeCount==8 && p.hopMinDistance==1 && p.hopMaxDistance==1);
    for(int n=0;n<q.edgeCount;n++)CHECK(q.edges[n].dx>=-1&&q.edges[n].dx<=1&&q.edges[n].dy>=-1&&q.edges[n].dy<=1
        && (q.edges[n].tag>>OVERWORLD_PICKUP_ROUTE_NATIVE_KIND_SHIFT)==OVERWORLD_PICKUP_ROUTE_NATIVE_WALK);
    call.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;CHECK(Policy(&q,&call,&p));CHECK(q.edgeCount==56&&p.allowedKinds==2);
    call.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    #define REVISED(statement) do {CHECK(Policy(&q,&call,&p));u32 revision=q.policyRevision;statement;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=revision);}while(0)
    REVISED(objects[0].flags2^=1u<<2);REVISED(objects[0].flags^=1u<<23);REVISED(objects[0].flags^=1u<<29);
    REVISED(objects[0].xrange=2);REVISED(objects[0].yrange=3);REVISED(objects[0].xInit++);REVISED(objects[0].yInit++);
    CHECK(Policy(&q,&call,&p));u32 stable=q.policyRevision;
    objects[0].xCurr++;objects[0].xInit++;objects[0].yCurr++;objects[0].yInit++;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==stable);
    REVISED(objects[0].xCurr++);REVISED(objects[0].yCurr++);
    REVISED(actorPolicy.chainPauseAction=0x90);REVISED(actorPolicy.chainStepsRemaining=0x20);
    REVISED(objects[0].xCurr++);REVISED(objects[0].yCurr++);
    #undef REVISED
    puts("production Policy: Walk stride1, Hop range, all movement hash dependencies");return 0;
}
static int HopOnlyPolicyChecks(void) {
    Reset();NativeQuery q={0};OverworldPickupRouteNativePolicy p;
    CHECK(Policy(&q,&call,&p));u32 walk=q.policyRevision;
    #define WALK_STABLE(statement) do {statement;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==walk);}while(0)
    WALK_STABLE(profile.owner.hopAllowVerticalObstacles=1);
    WALK_STABLE(profile.owner.hopTime++);
    WALK_STABLE(profile.owner.hopElevationTimeScale++);
    WALK_STABLE(profile.owner.hopElevationArcScale++);
    #undef WALK_STABLE
    call.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
    #define HOP_REVISED(statement) do {CHECK(Policy(&q,&call,&p));u32 revision=q.policyRevision;statement;CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=revision);}while(0)
    HOP_REVISED(profile.owner.hopAllowVerticalObstacles=0);
    HOP_REVISED(profile.owner.hopTime++);
    HOP_REVISED(profile.owner.hopElevationTimeScale++);
    HOP_REVISED(profile.owner.hopElevationArcScale++);
    #undef HOP_REVISED
    puts("production Policy: all four Hop-only inputs preserve Walk key and revise Hop key");return 0;
}
static int UnlimitedHopAnchorChecks(void) {
    Reset();call.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
    objects[0].xInit=objects[0].xCurr;objects[0].yInit=objects[0].yCurr;
    NativeQuery q={0};OverworldPickupRouteNativePolicy p;
    CHECK(Policy(&q,&call,&p));u32 unlimited=q.policyRevision;
    /* Native Hop advances current at its render midpoint before init rebase. */
    objects[0].xCurr++;objects[0].yCurr++;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==unlimited);
    objects[0].xInit=objects[0].xCurr;objects[0].yInit=objects[0].yCurr;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==unlimited);
    /* Keep each bounded axis sensitive to its own actual relative anchor. */
    objects[0].xrange=2;
    CHECK(Policy(&q,&call,&p));u32 boundedX=q.policyRevision;CHECK(boundedX!=unlimited);
    objects[0].yCurr++;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==boundedX);
    objects[0].xCurr++;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=boundedX);
    objects[0].xrange=-1;objects[0].yrange=2;
    CHECK(Policy(&q,&call,&p));u32 boundedY=q.policyRevision;CHECK(boundedY!=unlimited);
    objects[0].xCurr++;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision==boundedY);
    objects[0].yCurr++;
    CHECK(Policy(&q,&call,&p));CHECK(q.policyRevision!=boundedY);
    puts("production Policy: unlimited Hop start/midpoint/return key stable; each bounded axis retained");return 0;
}
static int MovingAnchorChecks(void) {
    Reset();profile.owner.hopAllowNonCardinal=0;
    objects[0].xInit=objects[0].xCurr;objects[0].yInit=objects[0].yCurr;
    objects[0].xrange=objects[0].yrange=2;
    u32 generation=0;u32 revision=0;int reached=0;
    for(int frame=0;frame<512;frame++) {
        conditions.frame.world.frame+=16;
        objects[0].xCurr=4+(frame&1);objects[0].xInit=objects[0].xCurr;
        objects[1].xCurr=12+(frame&1);
        OverworldPickupRouteStatus status=OverworldCargoQueryWild_Tick(&call,&output);
        CHECK(status==PENDING || status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
        NativeQuery *q=runtime.pickupQuery;
        CHECK(q && q->state.lastWork.routeUnits<=16);
        CHECK(q->state.lastWork.edgeQueries+q->state.lastWork.goalQueries<=1);
        if(!generation) { generation=q->storage.workspace.generation;revision=q->policyRevision; }
        CHECK(q->storage.workspace.generation==generation && q->policyRevision==revision);
        if(status==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
            CHECK(Same(&output.route.subject,&actors.slots[0].snapshot.handle,12));
            CHECK(Same(&output.route.cargo,&actors.slots[1].snapshot.handle,12));
            CHECK(output.route.origin.x==objects[0].xCurr && output.route.cargoPosition.x==objects[1].xCurr);
            CHECK(output.route.hasNextStep);
            int dx=output.route.nextStep.x-output.route.origin.x,dy=output.route.nextStep.y-output.route.origin.y;
            CHECK((dx==0 && (dy==1 || dy==-1)) || (dy==0 && (dx==1 || dx==-1)));
            reached=1;printf("moving finite-range anchor: current directed next step after %d sparse ticks\n",frame+1);break;
        }
    }
    CHECK(reached);return 0;
}
static int FootprintChecks(void) {
    Reset();NativeQuery q={0};q.changesComplete=1;
    CHECK(Observe(&q,&call,&actors,10));q.changeCount=0;q.changesComplete=1;
    objects[63]=(LocalMapObject){.flags=1,.id=EXCLUDED_ID,.xCurr=7,.yCurr=4,.posVec={0,64,0}};
    CHECK(Observe(&q,&call,&actors,10));CHECK(HasTile(&q,7,4));u32 revision=q.dynamicRevision;
    q.changeCount=0;objects[63].id=15;CHECK(Observe(&q,&call,&actors,10));CHECK(q.dynamicRevision>revision&&HasTile(&q,7,4));
    revision=q.dynamicRevision;u16 count=q.changeCount;CHECK(Observe(&q,&call,&actors,10));CHECK(q.dynamicRevision==revision&&q.changeCount==count);
    actors.slots[9].snapshot.reservationId=3;actors.slots[9].snapshot.handle.generation=2;
    actors.slots[9].snapshot.targetX=21;actors.slots[9].snapshot.targetY=8;actors.slots[9].policy.targetSurfaceId=7;
    CHECK(Observe(&q,&call,&actors,10));CHECK(HasTile(&q,21,8));
    actors.slots[9].snapshot.targetX=22;CHECK(Observe(&q,&call,&actors,10));CHECK(HasTile(&q,21,8)&&HasTile(&q,22,8));
    player.xCurr=30;player.yCurr=8;player.curFacing=3;CHECK(Observe(&q,&call,&actors,10));CHECK(HasTile(&q,31,8));
    player.curFacing=2;CHECK(Observe(&q,&call,&actors,10));CHECK(HasTile(&q,31,8)&&HasTile(&q,29,8));
    q.changeCount=CHANGES;q.changesComplete=1;objects[63].xCurr++;CHECK(Observe(&q,&call,&actors,10));CHECK(!q.changesComplete&&q.changeCount==CHANGES);
    puts("production Observe: all64 objects, ID reuse, reservations, player front, same-frame deltas, overflow");return 0;
}
static int OwnDependencyChecks(void) {
    Reset();NativeQuery q={0};q.changesComplete=1;
    CHECK(Observe(&q,&call,&actors,10));q.changeCount=0;q.changesComplete=1;
    u32 revision=q.dynamicRevision;objects[0].xCurr++;
    actors.slots[0].snapshot.reservationId=4;actors.slots[0].snapshot.targetX=20;actors.slots[0].snapshot.targetY=7;
    CHECK(Observe(&q,&call,&actors,11));
    CHECK(q.dynamicRevision>revision && q.objects[0].x==5 && q.reservations[0].x==20);
    CHECK(!HasTile(&q,4,4) && !HasTile(&q,5,4) && !HasTile(&q,20,7));
    objects[1].xCurr++;CHECK(Observe(&q,&call,&actors,12));CHECK(HasTile(&q,12,4)&&HasTile(&q,13,4));
    /* A stale same-slot generation cannot omit its object or reservation. */
    q.changeCount=0;conditions.bindings[0].subject.generation++;objects[0].xCurr++;
    actors.slots[0].snapshot.targetX++;
    CHECK(Observe(&q,&call,&actors,13));CHECK(HasTile(&q,5,4)&&HasTile(&q,6,4)&&HasTile(&q,20,7)&&HasTile(&q,21,7));
    conditions.bindings[0].subject=actors.slots[0].snapshot.handle;
    q.changeCount=0;world.subjectObject=&objects[1];objects[0].xCurr++;objects[1].xCurr++;
    CHECK(Observe(&q,&call,&actors,14));CHECK(HasTile(&q,6,4)&&HasTile(&q,7,4));
    CHECK(HasTile(&q,13,4)&&HasTile(&q,14,4));
    /* q.owner is not authority: switching to current Subject1 omits only1. */
    q.changeCount=0;world.slot=1;world.subjectObject=&objects[1];
    conditions.bindings[1].subject=actors.slots[1].snapshot.handle;
    q.owner=actors.slots[0].snapshot.handle;objects[0].xCurr++;objects[1].xCurr++;
    CHECK(Observe(&q,&call,&actors,15));CHECK(HasTile(&q,7,4)&&HasTile(&q,8,4));
    CHECK(!HasTile(&q,14,4)&&!HasTile(&q,15,4));
    /* A stale full handle must reject before reading an old object pointer. */
    Reset();OverworldActorHandle stale=actors.slots[0].snapshot.handle;stale.generation++;
    spawns.spawns[0].object=(LocalMapObject *)(uintptr_t)1;
    CHECK(!CurrentActor(&world,&actors,&stale));spawns.spawns[0].object=&objects[0];
    puts("Native Observe omits exact current self only; stale self, other object and owner switch remain conservative");return 0;
}
static int SetupChecks(void) {
    Reset();NativeQuery q={0};CHECK(Scope(&world,&q));CHECK(q.bounds.minX==0&&q.bounds.maxX==63&&q.bounds.maxY==31);
    land[0xC0]=1;CHECK(!Scope(&world,&q));land[0xC0]=0;*(u32 *)(slots[1]+0x860)=2;CHECK(!Scope(&world,&q));
    *(u32 *)(slots[1]+0x860)=1;*(u32 *)(slots[1]+0x864)=0;CHECK(Scope(&world,&q));CHECK(q.bounds.maxX==31);
    Reset();freeBytes=sizeof(NativeQuery)+1023;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==LIMIT&&allocations==0);
    Reset();conditions.frame.world.subject=actors.slots[1].snapshot.handle;conditions.frame.world.subjectX=99;conditions.frame.world.subjectY=99;
    conditions.frame.world.subjectRoleMask=4;conditions.frame.world.bindings=&conditions.bindings[1];
    conditions.frame.world.actors[0].x=99;conditions.frame.world.actors[1].x=99;
    CHECK(!Finish());NativeQuery *live=runtime.pickupQuery;
    CHECK(output.route.subject.slot==0&&output.route.origin.x==4&&output.route.cargoPosition.x==12&&live->state.roleMask==1);
    CHECK(conditions.frame.world.subject.slot==1&&conditions.frame.world.subjectX==99&&conditions.frame.world.actors[1].x==99);
    CHECK(!live->state.runtime);puts("production setup: stock loaded scope, heap guard, current local subject/candidates, no async stack borrow");return 0;
}
static int CacheChecks(void) {
    Reset();CHECK(!Finish());NativeQuery *q=runtime.pickupQuery;
    u32 calls=nativeCalls;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE);
    CHECK(nativeCalls==calls&&output.eligibleActorMask==2);
    objects[1].xCurr++;u32 oldObserved=q->state.observedRevision;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING&&!output.eligibleActorMask);
    CHECK(q->dynamicRevision>oldObserved&&q->state.observedRevision==oldObserved&&q->changeCount&&HasTile(q,12,4)&&HasTile(q,13,4));
    ++conditions.frame.world.frame;CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->state.observedRevision==q->dynamicRevision&&!q->changeCount);
    CHECK(!Finish());objects[63]=(LocalMapObject){.flags=1,.id=15,.xCurr=7,.yCurr=4,.posVec={0,64,0}};
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING&&!output.eligibleActorMask&&q->changeCount);
    puts("production cache: exact duplicate reuse, same-frame Cargo/object changes, retained delta until reducer consumes it");
    /* Current eligibility is a dependency of the cached receipt too. A later
     * same-frame action must not publish an actor excluded by its caller. */
    Reset();CHECK(!Finish());call.eligibleActorMask=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==UNREACHABLE&&!output.eligibleActorMask);
    puts("production cache: empty eligibility ends search before same-frame stale receipt reuse");return 0;
}
/* A separate red entry keeps the existing passing controls intact. The real
 * native observer supplies slot bits; the condition World stores a compact
 * list. No setup callback fixes that mask on the fixture's behalf. */
static void MoveSlot(u8 from,u8 to,u8 role) {
    actors.slots[to]=actors.slots[from];memset(&actors.slots[from],0,sizeof(actors.slots[from]));
    actors.slots[to].snapshot.handle.slot=to;actors.slots[to].snapshot.role=role;
    spawns.spawns[to]=spawns.spawns[from];memset(&spawns.spawns[from],0,sizeof(spawns.spawns[from]));
    conditions.bindings[to]=conditions.bindings[from];memset(&conditions.bindings[from],0,sizeof(conditions.bindings[from]));
    conditions.bindings[to].subject=actors.slots[to].snapshot.handle;
}
static void SlotFixture(u8 subject,u8 cargo) {
    Reset();
    if(cargo!=1)MoveSlot(1,cargo,OVERWORLD_ACTOR_ROLE_WILD);
    if(subject!=0)MoveSlot(0,subject,OVERWORLD_ACTOR_ROLE_FOLLOWER);
    expectedSubjectSlot=subject;expectedCargoSlot=cargo;world.slot=subject;
    OverworldBehaviorConditionWorldView *view=&conditions.frame.world;
    view->subject=actors.slots[subject].snapshot.handle;
    view->subjectRoleMask=subject==7?2:1;view->actorCount=0;
    for(u8 slot=0;slot<10;slot++)if(spawns.spawns[slot].active) {
        LocalMapObject *object=spawns.spawns[slot].object;
        view->actors[view->actorCount++]=(OverworldBehaviorConditionActorObservation){
            actors.slots[slot].snapshot.handle,object->xCurr,object->yCurr,1,0,3,0};
    }
}
static void PrintHandle(const char *name,const OverworldActorHandle *handle) {
    printf("%s={slot:%u,generation:%u,fieldEpoch:%u,mapGeneration:%u,encounterGeneration:%u,reserved:%u}",
        name,handle->slot,handle->generation,handle->fieldEpoch,handle->mapGeneration,
        handle->encounterGeneration,handle->reserved);
}
static OverworldPickupRouteStatus MeasureMask(u16 mask,u16 *frames) {
    call.eligibleActorMask=mask;
    OverworldPickupRouteStatus status=PENDING;
    for(*frames=1;*frames<=1000;(*frames)++) {
        ++conditions.frame.world.frame;
        status=OverworldCargoQueryWild_Tick(&call,&output);
        if(status!=PENDING)return status;
    }
    return status;
}
static int SlotMaskCase(const char *name,u8 subject,u8 cargo) {
    u16 frames;
    SlotFixture(subject,cargo);
    printf("%s ",name);PrintHandle("subject",&actors.slots[subject].snapshot.handle);
    putchar(' ');PrintHandle("cargo",&actors.slots[cargo].snapshot.handle);
    printf(" compactSlots=[%u,%u]\n",conditions.frame.world.actors[0].actor.slot,
        conditions.frame.world.actors[1].actor.slot);
    u16 slotMask=1u<<cargo,compactMask=0;
    for(u8 n=0;n<conditions.frame.world.actorCount;n++)
        if(conditions.frame.world.actors[n].actor.slot==cargo)compactMask|=1u<<n;
    OverworldPickupRouteStatus status=MeasureMask(slotMask,&frames);
    printf("native slot input=%u correct compact input=%u status=%u frames=%u output=%u expected slot output=%u\n",
        slotMask,compactMask,status,frames,output.eligibleActorMask,slotMask);
    int failed=status!=OVERWORLD_PICKUP_ROUTE_REACHABLE
        || output.eligibleActorMask!=slotMask || output.route.cargo.slot!=cargo;
    CHECK(!failed && Same(&output.route.cargo,&actors.slots[cargo].snapshot.handle,12));
    u32 calls=nativeCalls;
    OverworldBehaviorConditionActorObservation swap=conditions.frame.world.actors[0];
    conditions.frame.world.actors[0]=conditions.frame.world.actors[1];
    conditions.frame.world.actors[1]=swap;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE);
    CHECK(output.eligibleActorMask==slotMask && nativeCalls==calls
        && Same(&output.route.cargo,&actors.slots[cargo].snapshot.handle,12));
    puts("same-frame reordered observations reuse exact Cargo and native slot mask");
    for(u8 n=0;n<conditions.frame.world.actorCount;n++)
        if(conditions.frame.world.actors[n].actor.slot==cargo)
            conditions.frame.world.actors[n].actor.encounterGeneration++;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING && !output.eligibleActorMask);
    SlotFixture(subject,cargo);
    conditions.bindings[subject].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.kind=
        OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    conditions.bindings[subject].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor=
        actors.slots[cargo].snapshot.handle;
    CHECK(MeasureMask(slotMask,&frames)==OVERWORLD_PICKUP_ROUTE_UNREACHABLE && !output.eligibleActorMask);
    /* A compact bit supplied as a native slot must never authorize Cargo. */
    SlotFixture(subject,cargo);status=MeasureMask(compactMask,&frames);
    CHECK(status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE && !output.eligibleActorMask);
    puts("stale full identity, captured Trigger and wrong-slot mask grant no Cargo");
    conditions.frame.world.actorCount=OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS+1;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID && !output.eligibleActorMask);
    return 0;
}
static int SlotMaskRegression(void) {
    int failed=SlotMaskCase("Wild hole",0,2);
    failed|=SlotMaskCase("Follower slot7 with Wild hole",7,2);
    free(runtime.pickupQuery);runtime.pickupQuery=NULL;
    if(failed)fprintf(stderr,"RED: native slot masks do not cross the compact World boundary correctly\n");
    return failed;
}
static int FollowerPrioritySetup(void) {
    Reset();
    for(u8 n=0;n<3 && !nativeCalls;n++) {
        ++conditions.frame.world.frame;
        CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    }
    CHECK(runtime.pickupQuery && nativeCalls==1);
    objects[2]=(LocalMapObject){.flags=1,.id=107,.xCurr=10,.yCurr=4,
        .xrange=-1,.yrange=-1,.posVec={0,64,0}};
    actors.slots[7].snapshot.active=1;
    actors.slots[7].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
    actors.slots[7].snapshot.subjectIdentity=1007;
    actors.slots[7].snapshot.handle=(OverworldActorHandle){7,9,3,4,12,0};
    spawns.spawns[7]=(OverworldWildSpawn){&objects[2],1007,12,1};
    conditions.bindings[7].subject=actors.slots[7].snapshot.handle;
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=
        (OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
            .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                .actor=actors.slots[1].snapshot.handle}};
    conditions.frame.world.actors[2]=(OverworldBehaviorConditionActorObservation){
        actors.slots[7].snapshot.handle,10,4,1,0,3,0};
    conditions.frame.world.actorCount=3;
    world.slot=7;world.subjectObject=world.heightObject=&objects[2];
    expectedSubjectSlot=7;
    options.usesBinding=OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST;
    return 0;
}
static int FollowerPriorityChecks(void) {
    CHECK(!FollowerPrioritySetup());
    NativeQuery *q=runtime.pickupQuery;
    OverworldTargetBindingsState before[10];memcpy(before,conditions.bindings,sizeof(before));
    u32 beforeCalls=nativeCalls;
    /* The Wild already used this queue's sole native call. Handoff cannot
     * manufacture a second call or admission by resetting the frame stamp. */
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->owner.slot==7 && q->valid && nativeCalls==beforeCalls);
    CHECK(!output.eligibleActorMask && !output.route.hasNextStep);
    CHECK(!memcmp(before,conditions.bindings,sizeof(before)) && allocations==1);
    ++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->state.query.subject.slot==7 && q->state.required
        && Same(&q->state.query.cargo,&actors.slots[1].snapshot.handle,12));
    CHECK(nativeCalls==beforeCalls+1 && output.lastWork.goalQueries==1
        && output.lastWork.edgeQueries==0 && output.lastWork.routeUnits<=16);
    /* The unfinished Wild cannot take the workspace back from the follower. */
    world.slot=0;world.subjectObject=world.heightObject=&objects[0];
    options.usesBinding=1;expectedSubjectSlot=0;beforeCalls=nativeCalls;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==7 && nativeCalls==beforeCalls);
    world.slot=7;world.subjectObject=world.heightObject=&objects[2];
    options.usesBinding=OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST;expectedSubjectSlot=7;
    CHECK(!Finish());
    CHECK(output.eligibleActorMask==2 && output.route.hasNextStep
        && output.route.origin.x==10 && output.route.nextStep.x==11
        && output.route.cargoPosition.x==12);
    CHECK(!memcmp(before,conditions.bindings,sizeof(before)) && allocations==1
        && !runtime.throwState.targetMask && !runtime.throwState.carrierMask
        && !runtime.throwState.targets[0] && !runtime.throwState.targets[7]);
    /* An incoming pursuit cannot change either owner's query rights. */
    CHECK(!FollowerPrioritySetup());q=runtime.pickupQuery;
    runtime.throwState.targetMask=(1u<<0)|(1u<<7);beforeCalls=nativeCalls;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->owner.slot==7 && q->valid && nativeCalls==beforeCalls);
    CHECK(runtime.throwState.targetMask==((1u<<0)|(1u<<7)));
    /* Every protected owner and invalid new identity leaves the current
     * query intact, with no native call, eligible Cargo or motion receipt. */
    for(u8 fault=0;fault<19;fault++) {
        CHECK(!FollowerPrioritySetup());q=runtime.pickupQuery;
        switch(fault) {
        case 0: conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
            (OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
                .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                    .actor=actors.slots[1].snapshot.handle}};break;
        case 1: runtime.throwState.targets[0]=2;break;
        case 2: runtime.throwState.targets[0]=0x42;break;
        case 3: runtime.throwState.carrierMask=1;break;
        case 4: spawns.movementActorControlModes[0]=OW_WILD_ACTOR_CONTROL_HELD;break;
        case 5: spawns.captureTargetMask=1;break;
        case 6: actors.slots[0].snapshot.reservationId=1;break;
        case 7: actors.slots[0].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;break;
        case 8: actors.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;break;
        case 9: actors.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;break;
        case 10: actors.slots[7].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;break;
        case 11: actors.slots[7].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;break;
        case 12: options.usesBinding=1;break;
        case 13: conditions.bindings[7].subject.generation++;break;
        case 14: conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor.generation++;break;
        case 15: world.subjectObject=&objects[0];break;
        case 16: actors.slots[0].snapshot.handle.generation++;break;
        case 17: conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags=3;break;
        case 18: call.eligibleActorMask=0;break;
        }
        OverworldCargoQueryState oldState=q->state;
        beforeCalls=nativeCalls;++conditions.frame.world.frame;
        OverworldPickupRouteStatus status=OverworldCargoQueryWild_Tick(&call,&output);
        /* No exact eligible Interest is INVALID. A wildcard search whose
         * sole eligible actor is its excluded aim ends UNREACHABLE. */
        CHECK(status==((fault==14 || fault==18)?INVALID:fault==12?UNREACHABLE:PENDING));
        if(q->owner.slot!=0 || nativeCalls!=beforeCalls || output.eligibleActorMask
            || output.route.hasNextStep || memcmp(&oldState,&q->state,sizeof(oldState)))
            fprintf(stderr,"Follower priority protected fault%u owner%u calls%u/%u\n",
                fault,q->owner.slot,nativeCalls,beforeCalls);
        CHECK(q->owner.slot==0 && nativeCalls==beforeCalls && !output.eligibleActorMask
            && !output.route.hasNextStep && !memcmp(&oldState,&q->state,sizeof(oldState)));
    }
    /* A carried owner no longer needs a Cargo route. Preserve that original
     * workspace release, without touching its held claim, bindings or move. */
    CHECK(!FollowerPrioritySetup());q=runtime.pickupQuery;
    runtime.throwState.targets[0]=0x82;
    runtime.throwState.carrierMask=1;runtime.throwState.targetMask=2;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
        (OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
            .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                .actor=actors.slots[1].snapshot.handle}};
    actors.slots[0].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
    actors.slots[0].snapshot.reservationId=1;
    OverworldActorStateSnapshot held=actors.slots[0].snapshot;
    memcpy(before,conditions.bindings,sizeof(before));beforeCalls=nativeCalls;
    ++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING && q->owner.slot==7);
    CHECK(nativeCalls==beforeCalls+1 && !output.eligibleActorMask && !output.route.hasNextStep
        && output.lastWork.edgeQueries+output.lastWork.goalQueries<=1
        && !memcmp(before,conditions.bindings,sizeof(before))
        && !memcmp(&held,&actors.slots[0].snapshot,sizeof(held))
        && runtime.throwState.targets[0]==0x82 && runtime.throwState.carrierMask==1
        && runtime.throwState.targetMask==2 && allocations==1);
    puts("Follower exact-Interest priority: same workspace/current full path; same-frame budget and19 ownership/identity controls");
    return 0;
}
/* A completed route belongs to its owner for the rest of that frame. A
 * second current claimant may wait for the next frame's single workspace
 * turn without taking the first claimant's binding, claim, or motion. */
static int ClaimedRouteCompetitionSetup(u8 three) {
    Reset();
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.kind=
        OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor=
        actors.slots[1].snapshot.handle;
    options.usesBinding=OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST;
    objects[2]=(LocalMapObject){.flags=1,.id=107,.xCurr=10,.yCurr=5,
        .xrange=-1,.yrange=-1,.posVec={0,64,0}};
    actors.slots[7].snapshot.active=1;
    actors.slots[7].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
    actors.slots[7].snapshot.subjectIdentity=1007;
    actors.slots[7].snapshot.handle=(OverworldActorHandle){7,9,3,4,12,0};
    spawns.spawns[7]=(OverworldWildSpawn){&objects[2],1007,12,1};
    conditions.bindings[7].subject=actors.slots[7].snapshot.handle;
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=
        (OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
            .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                .actor=actors.slots[1].snapshot.handle}};
    conditions.frame.world.actors[2]=(OverworldBehaviorConditionActorObservation){
        actors.slots[7].snapshot.handle,10,5,1,0,3,0};
    conditions.frame.world.actorCount=3;
    if(three) {
        objects[3]=(LocalMapObject){.flags=1,.id=102,.xCurr=11,.yCurr=6,
            .xrange=-1,.yrange=-1,.posVec={0,64,0}};
        actors.slots[2].snapshot.active=1;
        actors.slots[2].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
        actors.slots[2].snapshot.subjectIdentity=1002;
        actors.slots[2].snapshot.handle=(OverworldActorHandle){2,4,3,4,7,0};
        spawns.spawns[2]=(OverworldWildSpawn){&objects[3],1002,7,1};
        conditions.bindings[2].subject=actors.slots[2].snapshot.handle;
        conditions.bindings[2].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=
            conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
        conditions.frame.world.actors[3]=(OverworldBehaviorConditionActorObservation){
            actors.slots[2].snapshot.handle,11,6,1,0,3,0};
        conditions.frame.world.actorCount=4;
    }
    CHECK(!Finish());
    NativeQuery *q=runtime.pickupQuery;
    CHECK(q && q->valid && q->owner.slot==0 && q->cached.status==OVERWORLD_PICKUP_ROUTE_REACHABLE
        && output.eligibleActorMask==2);
    runtime.throwState.targets[0]=2;
    runtime.throwState.carrierMask=1;runtime.throwState.targetMask=2;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
        (OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
            .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                .actor=actors.slots[1].snapshot.handle}};
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
        conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO];
    runtime.throwState.targets[7]=2;runtime.throwState.carrierMask|=1u<<7;
    if(three) {
        conditions.bindings[2].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
            conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO];
        runtime.throwState.targets[2]=2;runtime.throwState.carrierMask|=1u<<2;
    }
    u32 beforeCalls=nativeCalls;
    world.slot=7;world.subjectObject=world.heightObject=&objects[2];expectedSubjectSlot=7;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->owner.slot==0 && nativeCalls==beforeCalls && !output.eligibleActorMask
        && !output.route.hasNextStep);
    return 0;
}
static int ClaimedRouteCompetitionChecks(void) {
    CHECK(!ClaimedRouteCompetitionSetup(0));
    NativeQuery *q=runtime.pickupQuery;
    OverworldCargoQueryResult first=q->cached;
    OverworldTargetBindingsState before[10];memcpy(before,conditions.bindings,sizeof(before));
    OverworldActorStateSnapshot original=actors.slots[0].snapshot;
    u32 beforeCalls=nativeCalls;
    world.slot=0;world.subjectObject=world.heightObject=&objects[0];expectedSubjectSlot=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE);
    CHECK(q->owner.slot==0 && nativeCalls==beforeCalls
        && Same(&output.route.subject,&first.route.subject,sizeof(first.route.subject))
        && Same(&output.route.cargo,&first.route.cargo,sizeof(first.route.cargo)));
    /* START has now accepted the first carrier's ordinary Walk. The later
     * query turn may change the shared workspace, but not this motion plan. */
    actors.slots[0].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
    actors.slots[0].snapshot.motionKind=1;
    actors.slots[0].snapshot.originX=4;actors.slots[0].snapshot.originY=4;
    actors.slots[0].snapshot.targetX=5;actors.slots[0].snapshot.targetY=4;
    actors.slots[0].snapshot.motionDuration=16;
    actors.slots[0].snapshot.motionElapsed=3;
    actors.slots[0].snapshot.reservationId=0x41;
    actors.slots[0].snapshot.lastCommandSequence=91;
    original=actors.slots[0].snapshot;
    ++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->owner.slot==0 && nativeCalls==beforeCalls && !output.eligibleActorMask);
    world.slot=7;world.subjectObject=world.heightObject=&objects[2];expectedSubjectSlot=7;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(q->owner.slot==7 && nativeCalls<=beforeCalls+1
        && output.lastWork.routeUnits<=16 && allocations==1);
    CHECK(!memcmp(before,conditions.bindings,sizeof(before))
        && !memcmp(&original,&actors.slots[0].snapshot,sizeof(original))
        && runtime.throwState.targets[0]==2 && runtime.throwState.targets[7]==2
        && runtime.throwState.carrierMask==(1u|(1u<<7))
        && runtime.throwState.targetMask==2);
    /* A queued bit is only a request from a still-current unheld claimant.
     * Removing that fact cannot steal a later frame from the first owner. */
    for(u8 fault=0;fault<6;fault++) {
        CHECK(!ClaimedRouteCompetitionSetup(0));q=runtime.pickupQuery;
        beforeCalls=nativeCalls;
        switch(fault) {
        case 0: conditions.bindings[7].subject.generation++;break;
        case 1: conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags=0;break;
        case 2: runtime.throwState.targets[7]|=OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG;break;
        case 3: spawns.captureTargetMask|=1u<<7;break;
        case 4: spawns.movementActorControlModes[7]=OW_WILD_ACTOR_CONTROL_HELD;break;
        case 5: actors.slots[7].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;break;
        }
        world.slot=0;world.subjectObject=world.heightObject=&objects[0];expectedSubjectSlot=0;
        ++conditions.frame.world.frame;
        CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE);
        CHECK(q->owner.slot==0 && nativeCalls==beforeCalls
            && output.eligibleActorMask==2 && output.route.hasNextStep);
    }
    puts("completed claimed query: same-frame owner receipt, next-frame waiter turn, unchanged claims and motion");
    return 0;
}
static int ClaimedRouteRoundRobinChecks(void) {
    CHECK(!ClaimedRouteCompetitionSetup(1));
    NativeQuery *q=runtime.pickupQuery;
    u32 calls=nativeCalls;
    /* Slot7 asked first. At the next frame the next queued slot after owner0
     * is slot2, independent of the order in which the callers are ticked. */
    world.slot=2;world.subjectObject=world.heightObject=&objects[3];expectedSubjectSlot=2;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==0 && nativeCalls==calls);
    world.slot=0;world.subjectObject=world.heightObject=&objects[0];expectedSubjectSlot=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE
        && q->owner.slot==0 && nativeCalls==calls);
    ++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==0 && nativeCalls==calls);
    world.slot=7;world.subjectObject=world.heightObject=&objects[2];expectedSubjectSlot=7;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==0 && nativeCalls==calls);
    world.slot=2;world.subjectObject=world.heightObject=&objects[3];expectedSubjectSlot=2;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==2 && nativeCalls<=calls+1
        && output.lastWork.routeUnits<=16);
    CHECK(!Finish() && q->owner.slot==2 && output.route.subject.slot==2);
    calls=nativeCalls;
    world.slot=0;world.subjectObject=world.heightObject=&objects[0];expectedSubjectSlot=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==2 && nativeCalls==calls);
    world.slot=2;world.subjectObject=world.heightObject=&objects[3];expectedSubjectSlot=2;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==OVERWORLD_PICKUP_ROUTE_REACHABLE
        && q->owner.slot==2 && nativeCalls==calls);
    ++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==2 && nativeCalls==calls);
    world.slot=7;world.subjectObject=world.heightObject=&objects[2];expectedSubjectSlot=7;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==7 && nativeCalls<=calls+1
        && output.lastWork.routeUnits<=16);
    CHECK(!Finish() && q->owner.slot==7 && output.route.subject.slot==7);
    calls=nativeCalls;
    ++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==7 && nativeCalls==calls);
    world.slot=0;world.subjectObject=world.heightObject=&objects[0];expectedSubjectSlot=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING
        && q->owner.slot==0 && nativeCalls<=calls+1
        && output.lastWork.routeUnits<=16);
    CHECK(runtime.throwState.targets[0]==2 && runtime.throwState.targets[2]==2
        && runtime.throwState.targets[7]==2
        && runtime.throwState.carrierMask==(1u|(1u<<2)|(1u<<7))
        && runtime.throwState.targetMask==2 && allocations==1);
    puts("three claimed routes: round robin0->2->7->0, one shared native turn per frame");
    return 0;
}
static int PendingClaimSetup(void) {
    SlotFixture(7,1);
    objects[1].xCurr=5;objects[1].yCurr=5;
    conditions.frame.world.actors[0].x=5;conditions.frame.world.actors[0].y=5;
    /* Distinct current native Wild Trigger0, Cargo1 and Follower7. */
    objects[2]=(LocalMapObject){.flags=1,.id=110,.xCurr=4,.yCurr=1,.posVec={0,64,0}};
    actors.slots[0].snapshot.active=1;actors.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
    actors.slots[0].snapshot.handle=(OverworldActorHandle){0,8,3,4,9,0};
    actors.slots[0].snapshot.subjectIdentity=1010;
    spawns.spawns[0]=(OverworldWildSpawn){&objects[2],1010,9,1};
    conditions.frame.world.actors[2]=(OverworldBehaviorConditionActorObservation){
        actors.slots[0].snapshot.handle,4,1,1,0,3,0};conditions.frame.world.actorCount=3;
    OverworldTargetBinding *trigger=&conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    trigger->target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    trigger->target.actor=actors.slots[0].snapshot.handle;
    call.eligibleActorMask=2;profile.owner.hopAllowNonCardinal=0;
    profile.owner.hopMinDistance=1;profile.owner.hopMaxDistance=6;
    call.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
    conditions.frame.world.bindings=&conditions.bindings[7];
    CHECK(!Finish());return 0;
}
static OverworldCargoReadWildObservationCall ReadCall(void) {
    OverworldCargoReadWildObservationCall read={.cargo=call,.conditions=&conditions,
        .throwService=&throwService};
    read.cargo.conditionNative=NULL;
    return read;
}
static int UnavailableCargoSetup(void) {
    CHECK(!FollowerPrioritySetup());
    /* Wild0 owns the real unfinished workspace and a bare claim on Cargo1.
     * Wild2 is current and unclaimed. Follower7's exact Interest is Wild0,
     * which native eligibility excludes while it owns another Cargo. */
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
        (OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
            .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                .actor=actors.slots[1].snapshot.handle}};
    runtime.throwState.targets[0]=2;
    runtime.throwState.carrierMask=1;runtime.throwState.targetMask=2;
    objects[3]=(LocalMapObject){.flags=1,.id=102,.xCurr=11,.yCurr=6,
        .xrange=-1,.yrange=-1,.posVec={0,64,0}};
    actors.slots[2].snapshot=(OverworldActorStateSnapshot){.active=1,
        .role=OVERWORLD_ACTOR_ROLE_WILD,.subjectIdentity=1002,
        .handle={2,4,3,4,7,0}};
    spawns.spawns[2]=(OverworldWildSpawn){&objects[3],1002,7,1};
    conditions.frame.world.actors[3]=(OverworldBehaviorConditionActorObservation){
        actors.slots[2].snapshot.handle,11,6,1,0,3,0};
    conditions.frame.world.actorCount=4;
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor=
        actors.slots[0].snapshot.handle;
    call.eligibleActorMask=4; /* Only the alternate, never exact Interest0. */
    return 0;
}
static int UnavailableCargoCase(u8 required) {
    CHECK(!UnavailableCargoSetup());
    NativeQuery *q=runtime.pickupQuery;
    if(!required) {
        world.slot=2;world.subjectObject=world.heightObject=&objects[3];
        expectedSubjectSlot=2;options.usesBinding=1;call.eligibleActorMask=0;
        conditions.bindings[2].subject=actors.slots[2].snapshot.handle;
        conditions.bindings[2].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=
            conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    }
    ++conditions.frame.world.frame;
    NativeQuery before=*q;
    OverworldTargetBindingsState bindingsBefore[10];
    memcpy(bindingsBefore,conditions.bindings,sizeof(bindingsBefore));
    OverworldWildOverlayRuntimeState runtimeBefore=runtime;
    u32 callsBefore=nativeCalls,readsBefore=positionReads,allocationsBefore=allocations;
    OverworldPickupRouteStatus status=OverworldCargoQueryWild_Tick(&call,&output);
    OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
    u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
    printf("unavailable %s: status%u observed%u abort%u owner%u frame%u stateFrame%u nodes%u nativeCalls%u unchanged%u\n",
        required?"exact Interest":"wildcard Cargo",status,observedRoute.status,(unsigned)abort,
        q->owner.slot,conditions.frame.world.frame,q->state.frame,q->state.route.nodeCount,
        nativeCalls,(unsigned)!memcmp(&before,q,sizeof(before)));
    CHECK(!memcmp(&before,q,sizeof(before)) && nativeCalls==callsBefore
        && positionReads==readsBefore && allocations==allocationsBefore);
    CHECK(!memcmp(bindingsBefore,conditions.bindings,sizeof(bindingsBefore))
        && !memcmp(&runtimeBefore,&runtime,sizeof(runtimeBefore)));
    CHECK(!output.flags && !output.eligibleActorMask && !output.route.hasNextStep
        && !output.lastWork.edgeQueries && !output.lastWork.goalQueries && !output.lastWork.routeUnits);
    CHECK(status==(required?INVALID:UNREACHABLE) && observedRoute.status==status);
    CHECK(abort && !observation);
    return 0;
}
static u32 HeldThrowFacts(OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorProfile *p,
    const OverworldWildBehaviorDataBlob *b,const OverworldWildBehaviorConditionRuntime *c,
    PlayerHealthThrowIsCurrentSpawnFunc current,PlayerHealthThrowQueryTargetFunc target) {
    return ThrowFacts(s,slot,p,b,c,current,target)|OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD;
}
static int AvailableCargoProtectionChecks(void) {
    for(u8 movingOwner=0;movingOwner<2;movingOwner++) {
        CHECK(!UnavailableCargoSetup());NativeQuery *q=runtime.pickupQuery;
        conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor=
            actors.slots[2].snapshot.handle;
        /* ELIGIBLE permits a moving target. Its reservation is not a reason
         * to abort this search, while another current owner remains protected. */
        actors.slots[2].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
        actors.slots[2].snapshot.reservationId=22;
        if(movingOwner) {
            conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO]=(OverworldTargetBinding){0};
            runtime.throwState.targets[0]=0;
            runtime.throwState.carrierMask=runtime.throwState.targetMask=0;
            actors.slots[0].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
            actors.slots[0].snapshot.reservationId=11;
        }
        NativeQuery before=*q;OverworldWildOverlayRuntimeState runtimeBefore=runtime;
        OverworldActorSystemState actorsBefore=actors;
        OverworldTargetBindingsState bindingsBefore[10];
        memcpy(bindingsBefore,conditions.bindings,sizeof(bindingsBefore));
        u32 callsBefore=nativeCalls,readsBefore=positionReads;
        ++conditions.frame.world.frame;
        OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
        u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
        CHECK(!abort && observedRoute.status==PENDING
            && (observation&OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID)
            && !(observation&(1023u<<8)));
        CHECK(!memcmp(&before,q,sizeof(before)) && nativeCalls==callsBefore
            && positionReads==readsBefore && allocations==1);
        CHECK(!memcmp(&runtimeBefore,&runtime,sizeof(runtimeBefore))
            && !memcmp(&actorsBefore,&actors,sizeof(actorsBefore))
            && !memcmp(bindingsBefore,conditions.bindings,sizeof(bindingsBefore)));
    }
    CHECK(!UnavailableCargoSetup());NativeQuery *q=runtime.pickupQuery;
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor=
        actors.slots[2].snapshot.handle;
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
        conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    runtime.throwState.targets[7]=0x83;
    runtime.throwState.carrierMask|=1u<<7;runtime.throwState.targetMask|=4;
    call.eligibleActorMask=0;
    NativeQuery before=*q;OverworldWildOverlayRuntimeState runtimeBefore=runtime;
    u32 callsBefore=nativeCalls;
    const PlayerHealthThrowServiceEntry heldService={HeldThrowFacts,BindingPosition};
    OverworldCargoReadWildObservationCall read=ReadCall();read.throwService=&heldService;
    BOOL abort=FALSE;observedRoute.status=0xFF;
    u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(!abort && (observation&OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD)
        && observedRoute.status==0xFF && nativeCalls==callsBefore);
    CHECK(!memcmp(&before,q,sizeof(before)) && !memcmp(&runtimeBefore,&runtime,sizeof(runtimeBefore)));
    puts("valid moving Cargo preserves foreign claim/motion; carried caller skips Cargo preflight");
    return 0;
}
static int EvaluateCargo(u32 observation,OverworldBehaviorConditionEntryState *state,
    OverworldBehaviorConditionEntryResult *out) {
    OverworldBehaviorConditionDefinition definition={.conditionId=57932,.applicationIndex=20,
        .kind=OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS,.activationMode=OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE,
        .targetKind=OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR,.chance=100,
        .terrainMask=OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID,
        .terrainOverrideMask=OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD|OVERWORLD_BEHAVIOR_ACTOR_FACT_RECOVERING};
    /* This fixture's real compact World is[Cargo1,Follower7,Trigger0]. The
     * production runtime's pickup filter converts the native slot1 receipt
     * into compact bit0 before the actual entry evaluator runs. */
    CHECK(conditions.frame.world.actors[0].actor.slot==1);
    OverworldBehaviorConditionEntryInput input={.eligibleActorMask=(observation>>(8+1))&1};
    conditions.frame.world.reserved[0]=observation;
    OverworldBehaviorConditionStatus status=OverworldBehaviorCondition_EvaluateEntry(
        &definition,&input,&conditions.frame.world,state,out);
    if(status!=OVERWORLD_BEHAVIOR_CONDITION_OK)
        printf("production cargo while-true status=%u nativeMask=%u active=%u\n",status,(observation>>8)&1023,out->active);
    CHECK(status==OVERWORLD_BEHAVIOR_CONDITION_OK);
    return 0;
}
static int AdmitCargo(void) {
    OverworldBehaviorConditionEntryState entry={0};OverworldBehaviorConditionEntryResult out;
    OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
    u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(!abort && !EvaluateCargo(observation,&entry,&out) && out.active);
    CHECK(OverworldTargetBindings_CaptureEntry(&conditions.bindings[7],&conditions.frame.world,
        &actors.slots[7].snapshot.handle,&out,OVERWORLD_TARGET_BINDING_CARGO,
        OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_OK);
    runtime.throwState.targets[7]=2;return 0;
}
static int PendingClaimChecks(void) {
    CHECK(!PendingClaimSetup());CHECK(!AdmitCargo());
    OverworldBehaviorConditionEntryState entry={.targetSlot=1,.targetGeneration=3,
        .targetEncounterGeneration=6,.targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
        .flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE|OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED};
    OverworldBehaviorConditionEntryResult evaluated;
    OverworldTargetBindingsState before=conditions.bindings[7];
    objects[1].xCurr=6;conditions.frame.world.actors[0].x=6;++conditions.frame.world.frame;
    OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
    u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(!abort && !EvaluateCargo(observation,&entry,&evaluated));
    printf("moving bound Cargo: pending while-true active=%u nativeMask=%u claim=%u\n",
        evaluated.active,(observation>>8)&1023,runtime.throwState.targets[7]);
    CHECK(evaluated.active && evaluated.conditionTrue);
    CHECK(!memcmp(&before,&conditions.bindings[7],sizeof(before)) && runtime.throwState.targets[7]==2);
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
    CHECK(output.flags==OVERWORLD_CARGO_QUERY_RETAIN_BOUND_CARGO && !output.eligibleActorMask && !output.route.hasNextStep);
    /* Reordered compact observations retain the same full current binding. */
    OverworldBehaviorConditionActorObservation swap=conditions.frame.world.actors[0];
    conditions.frame.world.actors[0]=conditions.frame.world.actors[2];conditions.frame.world.actors[2]=swap;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING && output.flags==OVERWORLD_CARGO_QUERY_RETAIN_BOUND_CARGO && !output.eligibleActorMask);
    conditions.frame.world.actors[2].actor.encounterGeneration++;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID && !output.flags && !output.eligibleActorMask);
    CHECK(!PendingClaimSetup());CHECK(!AdmitCargo());
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor.generation++;
    read=ReadCall();observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(abort && !observation);
    CHECK(!PendingClaimSetup());CHECK(!AdmitCargo());
    conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor.encounterGeneration++;
    read=ReadCall();observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(abort && !observation);
    CHECK(!PendingClaimSetup());CHECK(!AdmitCargo());
    forcedRouteStatus=PENDING;forcedRouteFlags=2;read=ReadCall();
    observation=OverworldCargoReadWild_Observe(&read,&abort);CHECK(abort && !observation);
    forcedRouteStatus=OVERWORLD_PICKUP_ROUTE_UNREACHABLE;forcedRouteFlags=0;
    observation=OverworldCargoReadWild_Observe(&read,&abort);CHECK(abort && !observation);
    forcedRouteStatus=LIMIT;observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(abort && !observation);
    /* Missing eligibility, new unbound Cargo, stale native identity and heap
     * exhaustion cannot acquire the retention flag or a START receipt. */
    forcedRouteStatus=-1;call.eligibleActorMask=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID && !output.flags && !output.eligibleActorMask);
    CHECK(!PendingClaimSetup());CHECK(!AdmitCargo());spawns.spawns[1].active=0;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID && !output.flags && !output.eligibleActorMask);
    CHECK(!PendingClaimSetup());CHECK(!AdmitCargo());spawns.spawns[0].personality++;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID && !output.flags && !output.eligibleActorMask);
    Reset();freeBytes=0;conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags=OVERWORLD_TARGET_BINDING_BOUND;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor=actors.slots[1].snapshot.handle;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==LIMIT && !output.flags && !output.eligibleActorMask);
    Reset();++conditions.frame.world.frame;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING && !output.flags && !output.eligibleActorMask);
    puts("production pending claim: current binding persists, no new admission; lost/stale/unknown/unreachable/resource controls");return 0;
}
static int UnavailableCargoRegression(void) {
    int failed=UnavailableCargoCase(1);
    failed|=UnavailableCargoCase(0);
    failed|=AvailableCargoProtectionChecks();
    failed|=FollowerPriorityChecks();
    failed|=PendingClaimChecks();
    free(runtime.pickupQuery);runtime.pickupQuery=NULL;
    return failed;
}
static int WildResourceLimitChecks(void) {
    Reset();
    /* Three current ground Wild actors. The first two share the same Player
     * Interest; neither has Cargo, a claim, held ownership or accepted motion.
     * A wall at x32 separates Wild0 from Cargo1 but leaves Wild2 beside it.
     * Search exhausts real fixed storage; no status or capacity is forced. */
    blockedX=32;
    objects[1].xCurr=60;objects[1].yCurr=28;
    conditions.frame.world.actors[1].x=60;conditions.frame.world.actors[1].y=28;
    objects[2]=(LocalMapObject){.flags=1,.id=102,.xCurr=59,.yCurr=27,
        .xrange=-1,.yrange=-1,.posVec={0,64,0}};
    actors.slots[2].snapshot.active=1;
    actors.slots[2].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
    actors.slots[2].snapshot.subjectIdentity=1002;
    actors.slots[2].snapshot.handle=(OverworldActorHandle){2,4,3,4,7,0};
    spawns.spawns[2]=(OverworldWildSpawn){&objects[2],1002,7,1};
    conditions.frame.world.actors[2]=(OverworldBehaviorConditionActorObservation){
        actors.slots[2].snapshot.handle,59,27,1,0,3,0};
    conditions.frame.world.actorCount=3;
    conditions.bindings[2].subject=actors.slots[2].snapshot.handle;
    conditions.bindings[2].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=
        conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    profile.owner.hopAllowNonCardinal=0; /* Actual cardinal one-tile Walk. */
    NativeQuery *q=NULL;u32 limitFrame=0,limitCalls=0,limitWork=0;u16 nodes=0,edges=0;
    for(u16 n=0;n<1800;n++) {
        ++conditions.frame.world.frame;
        u32 before=nativeCalls;
        OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
        u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
        q=runtime.pickupQuery;
        CHECK(q);
        CHECK(!(observation&(1023u<<8)) && !conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags);
        CHECK(!runtime.throwState.targetMask && !runtime.throwState.carrierMask && !runtime.throwState.recoveringMask);
        CHECK(q->state.lastWork.routeUnits<=OVERWORLD_CARGO_QUERY_INTERNAL_WORK);
        CHECK(q->state.lastWork.edgeQueries+q->state.lastWork.goalQueries<=1);
        CHECK(nativeCalls-before<=1);
        if(observedRoute.status==LIMIT) {
            CHECK(abort && observation==0);
            limitFrame=conditions.frame.world.frame;limitCalls=nativeCalls;
            limitWork=nativeCalls-before;
            nodes=q->state.route.nodeCount;edges=q->state.route.cachedEdgeCount;
            break;
        }
        CHECK(!abort && (observation&OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID));
        CHECK(observedRoute.status==PENDING);
    }
    CHECK(limitFrame && allocations==1 && forcedRouteStatus==-1);
    printf("Wild resource exhaustion: frame%u nodes%u edges%u owner%u valid%u Interest%u Cargo%u nativeCalls%u frameNativeWork%u stateFrame%u frameValid%u\n",
        limitFrame,nodes,edges,q->owner.slot,q->valid,
        conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags,
        conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags,
        nativeCalls,limitWork,q->state.frame,q->state.frameValid);
    /* The same owner cannot restart a full search in the used frame. */
    OverworldCargoReadWildObservationCall repeat=ReadCall();BOOL repeatAbort=FALSE;
    CHECK(!OverworldCargoReadWild_Observe(&repeat,&repeatAbort) && repeatAbort);
    CHECK(nativeCalls==limitCalls && q->owner.slot==0 && q->cached.status==LIMIT);
    world.slot=2;world.subjectObject=world.heightObject=&objects[2];expectedSubjectSlot=2;
    conditions.frame.world.subject=actors.slots[2].snapshot.handle;
    conditions.frame.world.subjectX=59;conditions.frame.world.subjectY=27;
    conditions.frame.world.bindings=&conditions.bindings[2];
    /* A full workspace does not revoke an existing Cargo/motion owner. */
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO]=
        (OverworldTargetBinding){0};
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags=1;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.kind=
        OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor=
        actors.slots[1].snapshot.handle;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING && q->owner.slot==0);
    conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags=0;
    actors.slots[0].snapshot.reservationId=1;
    CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING && q->owner.slot==0);
    actors.slots[0].snapshot.reservationId=0;
    OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
    u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
    printf("Second grounded Wild: frame%u owner%u valid%u nativeCalls%u stateFrame%u frameValid%u eligible%u abort%u\n",
        conditions.frame.world.frame,q->owner.slot,q->valid,nativeCalls,
        q->state.frame,q->state.frameValid,(observation>>8)&1023,(unsigned)abort);
    /* Handoff/reset keeps the already used queue budget. It grants no Cargo
     * or move until a later current route receipt has actually completed. */
    CHECK(!abort && !(observation&(1023u<<8)) && nativeCalls==limitCalls);
    CHECK(q->state.frame==limitFrame && q->state.frameValid);
    CHECK(q->valid && Same(&q->owner,&actors.slots[2].snapshot.handle,12));
    for(u8 n=0;n<32 && !((observation>>8)&2);n++) {
        ++conditions.frame.world.frame;u32 before=nativeCalls;
        observation=OverworldCargoReadWild_Observe(&read,&abort);
        CHECK(!abort && nativeCalls-before<=1);
    }
    CHECK((observation>>8)&2);
    CHECK(q->cached.status==OVERWORLD_PICKUP_ROUTE_REACHABLE && q->cached.route.cargo.slot==1);
    CHECK(!conditions.bindings[2].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
        && !runtime.throwState.targetMask && !runtime.throwState.carrierMask && allocations==1);
    puts("Wild resource-limit owner releases shared workspace; same-frame budget survives and next Wild proves current Cargo");
    free(runtime.pickupQuery);runtime.pickupQuery=NULL;
    return 0;
}
/* An enclosed Wild can end UNREACHABLE with a real reachable Cargo still
 * available to another Wild. This is not an empty candidate mask or a forced
 * reducer status. Keep Cargo first in the compact World so losing the old
 * frame stamp during handoff would immediately spend a second native call. */
static int WildUnreachableChecks(void) {
    Reset();profile.owner.hopAllowNonCardinal=0;
    const s16 enclosure[4][2]={{3,4},{5,4},{4,3},{4,5}};
    for(u8 n=0;n<4;n++) objects[3+n]=(LocalMapObject){.flags=1,.id=20+n,
        .xCurr=enclosure[n][0],.yCurr=enclosure[n][1],.posVec={0,64,0}};
    objects[2]=(LocalMapObject){.flags=1,.id=102,.xCurr=11,.yCurr=4,
        .xrange=-1,.yrange=-1,.posVec={0,64,0}};
    actors.slots[2].snapshot.active=1;actors.slots[2].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
    actors.slots[2].snapshot.subjectIdentity=1002;
    actors.slots[2].snapshot.handle=(OverworldActorHandle){2,4,3,4,7,0};
    spawns.spawns[2]=(OverworldWildSpawn){&objects[2],1002,7,1};
    OverworldBehaviorConditionActorObservation first=conditions.frame.world.actors[0];
    conditions.frame.world.actors[0]=conditions.frame.world.actors[1];
    conditions.frame.world.actors[1]=first;
    conditions.frame.world.actors[2]=(OverworldBehaviorConditionActorObservation){
        actors.slots[2].snapshot.handle,11,4,1,0,3,0};
    conditions.frame.world.actorCount=3;
    conditions.bindings[2].subject=actors.slots[2].snapshot.handle;
    conditions.bindings[2].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=
        conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    NativeQuery *q=NULL;u32 terminalFrame=0,terminalCalls=0;
    for(u16 n=0;n<256;n++) {
        ++conditions.frame.world.frame;u32 before=nativeCalls;
        OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;
        u32 observation=OverworldCargoReadWild_Observe(&read,&abort);q=runtime.pickupQuery;
        if(!q || nativeCalls-before>1)
            fprintf(stderr,"Wild enclosure frame%u query%p nativeCalls%u/%u observation%u abort%u\n",
                conditions.frame.world.frame,(void *)q,nativeCalls,before,observation,(unsigned)abort);
        CHECK(q && nativeCalls-before<=1);
        CHECK(!(observation&(1023u<<8)) && !conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags);
        CHECK(q->state.lastWork.routeUnits<=OVERWORLD_CARGO_QUERY_INTERNAL_WORK
            && q->state.lastWork.edgeQueries+q->state.lastWork.goalQueries<=1);
        if(observedRoute.status==UNREACHABLE) {
            printf("Wild enclosure: frame%u nodes%u edges%u owner%u Interest%u Cargo%u abort%u\n",
                conditions.frame.world.frame,q->state.route.nodeCount,q->state.route.cachedEdgeCount,
                q->owner.slot,conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags,
                conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags,(unsigned)abort);
            CHECK(abort && !observation);
            terminalFrame=conditions.frame.world.frame;terminalCalls=nativeCalls;break;
        }
        CHECK(observedRoute.status==PENDING && !abort
            && (observation&OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID));
    }
    CHECK(terminalFrame && allocations==1 && forcedRouteStatus==-1);
    CHECK(q->state.route.nodeCount==1 && q->state.route.cachedEdgeCount==4);
    /* An unchanged same-owner read in the used frame stays terminal. */
    OverworldCargoReadWildObservationCall repeat=ReadCall();BOOL abort=FALSE;
    CHECK(!OverworldCargoReadWild_Observe(&repeat,&abort) && abort);
    CHECK(q->cached.status==UNREACHABLE && q->owner.slot==0 && nativeCalls==terminalCalls);
    world.slot=2;world.subjectObject=world.heightObject=&objects[2];expectedSubjectSlot=2;
    conditions.frame.world.subject=actors.slots[2].snapshot.handle;
    conditions.frame.world.subjectX=11;conditions.frame.world.subjectY=4;
    conditions.frame.world.bindings=&conditions.bindings[2];
    /* Neither terminal status revokes either actor's existing Cargo or
     * accepted destination reservation. Protected calls leave search intact. */
    for(u8 fault=0;fault<4;fault++) {
        u8 slot=fault<2?0:2;
        OverworldTargetBinding *cargo=&conditions.bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO];
        if(!(fault&1)) *cargo=(OverworldTargetBinding){.flags=OVERWORLD_TARGET_BINDING_BOUND,
            .target={.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,
                .actor=actors.slots[1].snapshot.handle}};
        else actors.slots[slot].snapshot.reservationId=1;
        OverworldCargoQueryState before=q->state;
        CHECK(OverworldCargoQueryWild_Tick(&call,&output)==PENDING);
        CHECK(q->owner.slot==0 && nativeCalls==terminalCalls && !output.eligibleActorMask
            && !output.route.hasNextStep && !memcmp(&before,&q->state,sizeof(before)));
        *cargo=(OverworldTargetBinding){0};actors.slots[slot].snapshot.reservationId=0;
    }
    OverworldTargetBindingsState bindingsBefore[10];memcpy(bindingsBefore,conditions.bindings,sizeof(bindingsBefore));
    OverworldCargoReadWildObservationCall read=ReadCall();abort=FALSE;
    u32 observation=OverworldCargoReadWild_Observe(&read,&abort);
    CHECK(nativeCalls==terminalCalls);
    CHECK(!abort && !(observation&(1023u<<8)));
    CHECK(q->valid && Same(&q->owner,&actors.slots[2].snapshot.handle,12));
    CHECK(q->state.frameValid && q->state.frame==terminalFrame);
    /* Current Cargo is adjacent to this peer. It now gets the real route,
     * with one native call per frame and no new binding or held claim. */
    u8 frames=0;
    for(;frames<8 && !(observation>>8&2);frames++) {
        ++conditions.frame.world.frame;u32 before=nativeCalls;
        observation=OverworldCargoReadWild_Observe(&read,&abort);
        CHECK(!abort && nativeCalls-before<=1);
    }
    CHECK((observation>>8&2) && q->cached.status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
    CHECK(Same(&q->cached.route.subject,&actors.slots[2].snapshot.handle,12)
        && Same(&q->cached.route.cargo,&actors.slots[1].snapshot.handle,12));
    CHECK(q->cached.route.origin.x==11 && q->cached.route.origin.y==4
        && q->cached.route.cargoPosition.x==12 && q->cached.route.cargoPosition.y==4);
    CHECK(!memcmp(bindingsBefore,conditions.bindings,sizeof(bindingsBefore)) && allocations==1
        && !runtime.throwState.targetMask && !runtime.throwState.carrierMask && !runtime.throwState.recoveringMask);
    printf("Wild unreachable owner releases to current peer/Cargo in%u later frames; same-frame budget and Cargo/reservation claims preserved\n",frames);
    free(runtime.pickupQuery);runtime.pickupQuery=NULL;return 0;
}
static int WildRetargetChecks(void) {
    Reset();expectedCargoSlot=255;
    profile.owner.continueWhenArrived=(12u<<2)|(1u<<6);
    CHECK(!Finish());CHECK(output.route.cargo.slot==1);
    NativeQuery *q=runtime.pickupQuery;
    OverworldTargetBinding *cargo=&conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO];
    cargo->flags=1;cargo->target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    cargo->target.actor=actors.slots[1].snapshot.handle;
    conditions.actors[0].subject=actors.slots[0].snapshot.handle;
    OverworldBehaviorConditionEntryState rows[2]={{.flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE},
        {.flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE}};
    conditions.actors[0].count=2;conditions.actors[0].states=rows;
    conditions.actors[0].catalogEntryIndexes[1]=1;
    OverworldWildBehaviorDataBlob blob={.header={2},.conditionOptions={{.captureBinding=2},{.usesBinding=1}}};
    world.behaviorData=&blob;
    runtime.throwState.targets[0]=2;runtime.throwState.carrierMask=1;runtime.throwState.targetMask=2;
    actors.slots[0].snapshot.reservationId=33;
    actors.slots[0].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
    actorPolicy.pendingStep=OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED;
    actorPolicy.motionPhase=OVERWORLD_MOTION_PHASE_MOVING;
    objects[0].xPrev=objects[0].xInit=objects[0].xCurr;
    objects[0].yPrev=objects[0].yInit=objects[0].yCurr;
    OverworldActorStateSnapshot motion=actors.slots[0].snapshot;
    LocalMapObject pose=objects[0];
    OverworldTargetBinding interest=conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    objects[2]=objects[1];objects[2].id=102;objects[2].xCurr=7;
    actors.slots[2]=actors.slots[1];actors.slots[2].snapshot.handle=(OverworldActorHandle){2,4,3,4,7,0};
    actors.slots[2].snapshot.subjectIdentity=1002;
    spawns.spawns[2]=(OverworldWildSpawn){objects+2,1002,7,1};
    conditions.frame.world.actorCount=3;
    conditions.frame.world.actors[2]=(OverworldBehaviorConditionActorObservation){actors.slots[2].snapshot.handle,7,4,1,0,3,0};
    call.eligibleActorMask=6;
    OverworldCargoReadWildObservationCall read=ReadCall();BOOL abort=FALSE;u32 observation=0;
    u32 completed=q->targetCheckFrame;
    for(u8 n=1;n<12;n++) {
        conditions.frame.world.frame=completed+n;
        u32 before=nativeCalls;
        observation=OverworldCargoReadWild_Observe(&read,&abort);
        CHECK(!abort && nativeCalls-before<=1 && !q->checkingTargets && cargo->flags);
    }
    for(u16 n=0;n<1000 && cargo->flags;n++) {
        ++conditions.frame.world.frame;u32 before=nativeCalls;
        observation=OverworldCargoReadWild_Observe(&read,&abort);
        CHECK(!abort && nativeCalls-before<=1);
        CHECK(!memcmp(&motion,&actors.slots[0].snapshot,sizeof(motion))
            && !memcmp(&pose,&objects[0],sizeof(pose)));
    }
    CHECK(!cargo->flags && ((observation>>8)&1023)==4 && q->cached.route.cargo.slot==2);
    CHECK(!runtime.throwState.targets[0] && !runtime.throwState.carrierMask && !runtime.throwState.targetMask);
    CHECK(!memcmp(&interest,&conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST],sizeof(interest)));
    CHECK(!(rows[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)
        && (rows[1].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
    /* A second pursuer keeps the shared old target bit; HELD refuses release. */
    cargo->flags=1;cargo->target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    cargo->target.actor=actors.slots[1].snapshot.handle;
    runtime.throwState.targets[0]=2;runtime.throwState.targets[3]=2;
    runtime.throwState.carrierMask=9;runtime.throwState.targetMask=2;
    CHECK(OverworldThrowHeldWild_ReleaseCargo(&world));
    CHECK(runtime.throwState.targets[3]==2 && runtime.throwState.carrierMask==8 && runtime.throwState.targetMask==2);
    runtime.throwState.targets[0]=0x82;cargo->flags=1;
    CHECK(!OverworldThrowHeldWild_ReleaseCargo(&world) && cargo->flags && runtime.throwState.targets[0]==0x82);
    puts("Wild retarget: authored12-frame interval, fresh nearer proof, Cargo-only release, unchanged Interest/accepted move and shared/HELD ownership");
    return 0;
}
int main(int argc,char **argv) {
    if(argc==2 && !strcmp(argv[1],"--wild-retarget-regression"))return WildRetargetChecks();
    if(argc==2 && !strcmp(argv[1],"--claimed-route-regression"))
        return ClaimedRouteCompetitionChecks() || ClaimedRouteRoundRobinChecks();
    if(argc==2 && !strcmp(argv[1],"--slot-mask-regression"))return SlotMaskRegression();
    if(argc==2 && !strcmp(argv[1],"--follower-priority-regression"))return FollowerPriorityChecks();
    if(argc==2 && !strcmp(argv[1],"--wild-resource-limit-regression"))return WildResourceLimitChecks();
    if(argc==2 && !strcmp(argv[1],"--wild-unreachable-regression"))return WildUnreachableChecks();
    if(argc==2 && !strcmp(argv[1],"--unavailable-cargo-regression"))return UnavailableCargoRegression();
    CHECK(argc==1);
    CHECK(!ClaimedRouteCompetitionChecks());
    CHECK(!ClaimedRouteRoundRobinChecks());
    CHECK(!WildUnreachableChecks());
    CHECK(!WildResourceLimitChecks());
    CHECK(!UnavailableCargoRegression());
    CHECK(!PolicyChecks());CHECK(!HopOnlyPolicyChecks());CHECK(!UnlimitedHopAnchorChecks());CHECK(!MovingAnchorChecks());CHECK(!FootprintChecks());CHECK(!OwnDependencyChecks());CHECK(!SetupChecks());CHECK(!CacheChecks());
    CHECK(!SlotMaskRegression());
    free(runtime.pickupQuery);runtime.pickupQuery=NULL;
    printf("Cargo Wild production checks passed; host NativeQuery bytes%zu (not ARM layout)\n",sizeof(NativeQuery));return 0;
}
