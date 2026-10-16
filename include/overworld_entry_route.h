#ifndef OVERWORLD_ENTRY_ROUTE_H
#define OVERWORLD_ENTRY_ROUTE_H
#include "overworld_pickup_route_wild.h"
#include "overworld_cargo_query.h"
#include "overworld_actor_hop_clearance.h"
#include "overworld_prepared_movement.h"
#include "overworld_wild_helper.h"

#define OVERWORLD_ENTRY_ROUTE_VERSION 1
#define OVERWORLD_ENTRY_ROUTE_MAX_READS 8
#define OVERWORLD_ENTRY_ROUTE_MAX_STEPS 96
#define OVERWORLD_ENTRY_ROUTE_MAX_UPDATES 240
#define OVERWORLD_ENTRY_ROUTE_STALL_FRAMES 120
/* Existing Cargo callback slot, explicit private call operation; op0 keeps
 * all Cargo reserved-byte checks. Unknown operations are rejected. */
#define OVERWORLD_FIELD_ROUTE_CARGO 0
#define OVERWORLD_FIELD_ROUTE_ENTRY 1
#define OVERWORLD_ENTRY_ROUTE_PREPARE 0
#define OVERWORLD_ENTRY_ROUTE_ADOPT 1
#define OVERWORLD_ENTRY_ROUTE_GUIDE 2
#define OVERWORLD_ENTRY_ROUTE_RETIRE 3

/* A prepared physical subject is a value, never a fabricated MapObject or
 * Actor handle. The caller supplies the exact constructor flags/ranges and
 * checks the created object before adopting its full current handle. */
typedef struct OverworldEntryRoutePhysical {
    u32 flags, flags2;
    s16 rangeX, rangeY;
    s16 targetX, targetY;
} OverworldEntryRoutePhysical;
typedef struct OverworldEntryRouteRequest {
    u16 version, size;
    u32 serial, fieldEpoch, mapGeneration;
    OverworldActorHandle actor; /* Zero before ADOPT, full handle afterwards. */
    OverworldPickupRoutePosition destination, origin;
    OverworldEntryRoutePhysical physical;
    u16 expectedSlotGeneration;
    u8 slot, operation;
} OverworldEntryRouteRequest;
struct OverworldEntryRouteNativeControl;
typedef struct OverworldEntryRouteCommand {
    OverworldEntryRouteRequest request;
    struct OverworldEntryRouteReceipt *receipt;
    /* Sampled before the real START: zero-duration Teleport may publish END
     * before its successful START call returns to the GUIDE caller. */
    u32 startCommitSequence;
    u8 accepted, usableIdle, safelyOffscreen, reserved;
    struct OverworldEntryRouteNativeControl *nativeControl;
} OverworldEntryRouteCommand;
/* Native exact queue and public command receipt. Pending is not a created
 * Actor. The serial binds READY and a later created full handle to one owned
 * prepared packet. No setup work is credited as a successful finalizer. */
typedef struct OverworldEntryRouteReceipt {
    u16 version, size;
    u32 serial;
    OverworldActorHandle actor;
    OverworldPickupRoutePosition origin, target, nextStep;
    u16 edgeTag, stepsRemaining;
    u8 status, readsUsed, queued, hasNextStep;
} OverworldEntryRouteReceipt;
/* Per-edge replay only. It resumes the existing native classifier; it does
 * not choose a lane or run another clearance model. A cached completed read
 * is valid only for the exact edge/binding/static policy and a complete
 * dynamic ledger that excludes every physical cell in that edge. */
#define OVERWORLD_ENTRY_ROUTE_MEMO_READS 40
typedef struct OverworldEntryRouteMemoRead {
    OverworldPickupRouteNativeTile tile;
    OverworldWildSurfaceHit hit;
    s32 height;
    u8 operation, result, hitValid, reserved;
} OverworldEntryRouteMemoRead;
typedef struct OverworldEntryRouteTerrainCursor {
    OverworldPickupRouteNativeTile tile;
    OverworldWildSurfaceHit hit;
    s16 x, y;
    u16 wanted;
    u8 phase, hitValid;
} OverworldEntryRouteTerrainCursor;
typedef struct OverworldEntryRouteMemo {
    OverworldPickupRoutePosition from;
    OverworldPickupRouteEdge edge;
    OverworldEntryRouteMemoRead reads[OVERWORLD_ENTRY_ROUTE_MEMO_READS];
    OverworldEntryRouteTerrainCursor terrain;
    OverworldActorHopPlanCall hopInput;
    OverworldActorHopClearanceCursor hop;
    OverworldPreparedMovementInput movementInput;
    OverworldPreparedMovementCursor movement;
    const OverworldPickupRouteNativeSeams *native;
    u32 scope, policy, dynamic;
    u16 physicalPlayerMask;
    u8 valid, count, cursor, budget, used, hopStarted, terminal, reserved;
    u8 movementStarted, guideReady, reserved2[2];
} OverworldEntryRouteMemo;
typedef struct OverworldEntryRoutePath {
    OverworldActorHandle actor;
    OverworldPickupRoutePosition origin, target, expected;
    /* Full endpoints own displacement; retain every native forward tag. */
    u16 edgeTags[OVERWORLD_ENTRY_ROUTE_MAX_STEPS];
    OverworldPickupRoutePosition endpoints[OVERWORLD_ENTRY_ROUTE_MAX_STEPS];
    u32 serial, policy, scope, acceptedSequence, lastIdleFrame;
    u16 count, next, noProgress;
    u8 valid, accepted;
    u8 stepRead, reserved;
} OverworldEntryRoutePath;
typedef struct OverworldEntryRouteSearch {
    OverworldCargoQueryState *ledger; /* Sole existing Field workspace/state. */
    OverworldPickupRouteQuery query;
    OverworldPickupRouteExtension extension;
    OverworldPickupRouteNativeContext native;
    OverworldPickupRouteNativePolicy policy;
    OverworldPickupRouteWildWorld world;
    OverworldEntryRoutePhysical physical;
    OverworldEntryRouteMemo memo;
    OverworldEntryRouteRequest receipt;
    OverworldPickupRoutePosition goal;
    u16 updates;
    u8 active, reverse;
    /* Only this owned Field receipt callback checks the current queue/full
     * handle. It must not borrow a public spawn caller's prepared packet. */
    u8 (*current)(void *, const OverworldEntryRouteRequest *);
    void *owner;
} OverworldEntryRouteSearch;
/* A read-through native seam table. Only a World with an owned entry memo
 * may use it. The ordinary Cargo/bare START table remains unchanged. */
const OverworldPickupRouteNativeSeams *OverworldEntryRoute_MemoSeams(void);
void OverworldEntryRoute_ResetMemo(OverworldEntryRouteSearch *);
OverworldPickupRouteStatus OverworldEntryRoute_Begin(
    OverworldEntryRouteSearch *, const OverworldEntryRouteRequest *,
    const OverworldPickupRouteWildWorld *, const OverworldPickupRouteNativePolicy *,
    OverworldCargoQueryState *, const OverworldPickupRouteEdge *, u16,
    const OverworldPickupRouteBounds *, u32 scope, u32 policyRevision, u32 dynamic,
    u8 (*current)(void *, const OverworldEntryRouteRequest *), void *owner);
OverworldPickupRouteStatus OverworldEntryRoute_Resume(
    OverworldEntryRouteSearch *, u32 dynamic, const OverworldCargoQueryChangedTile *,
    u16 changeCount, u8 changesComplete,
    OverworldEntryRoutePath *, OverworldEntryRouteReceipt *);
OverworldPickupRouteStatus OverworldEntryRoute_ValidateStep(
    OverworldEntryRouteSearch *, const OverworldEntryRoutePath *, u32 dynamic,
    const OverworldCargoQueryChangedTile *, u16, u8, OverworldEntryRouteReceipt *);
/* Guide never advances on REQUEST. Confirm advances only after actual END at
 * the proved endpoint; chains and blocked starts must re-root the same core. */
u8 OverworldEntryRoute_Guide(const OverworldEntryRoutePath *,
    const OverworldActorHandle *, const OverworldPickupRoutePosition *, u32 policy,
    OverworldEntryRouteReceipt *);
u8 OverworldEntryRoute_Confirm(OverworldEntryRoutePath *,
    const OverworldActorHandle *, const OverworldPickupRoutePosition *,
    const OverworldActorRuntimeSlot *);
u8 OverworldEntryRoute_IdleStall(OverworldEntryRoutePath *,
    const OverworldActorHandle *, u8 usableIdle, u8 safelyOffscreen);

/* Native glue borrows the already leased Entry callback and current native
 * owners synchronously. No callback/control pointer is saved in the graph. */
#define OVERWORLD_ENTRY_NATIVE_MAGIC 0x4E454F57 /* WOEN */
#define OVERWORLD_ENTRY_NATIVE_VERSION 1
#define OVERWORLD_ENTRY_NATIVE_ARM 0
#define OVERWORLD_ENTRY_NATIVE_QUERY 1
#define OVERWORLD_ENTRY_NATIVE_FINALIZE 2
#define OVERWORLD_ENTRY_NATIVE_GUIDE 3
#define OVERWORLD_ENTRY_NATIVE_UPDATE 4
#define OVERWORLD_ENTRY_NATIVE_READY 5
#define OVERWORLD_ENTRY_NATIVE_RETIRE 6
#define OVERWORLD_ENTRY_NATIVE_COMMIT 7
#define OVERWORLD_ENTRY_NATIVE_SPAWN 8
/* SPAWN subtypes share the existing synchronous control and native owner.
 * Direct keeps its slot/terrain input. Ordinary refill owns no such input;
 * its Runtime selects one ordered terrain attempt and returns result|delay<<8. */
#define OVERWORLD_ENTRY_SPAWN_DIRECT 0
#define OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL 1

#define OVERWORLD_ENTRY_NATIVE_FINISH_REFILL 9
/* Private FinishRefill input subtype. Success is admitted only by the actual
 * COMMIT constructor, never by a caller's boolean or a READY queue reply. */
#define OVERWORLD_ENTRY_REFILL_BACKOFF 0
#define OVERWORLD_ENTRY_REFILL_FAILED 1
#define OVERWORLD_ENTRY_REFILL_BASE_FRAMES 60
#define OVERWORLD_ENTRY_REFILL_RETRY_FRAMES 15
#define OVERWORLD_ENTRY_REFILL_SHORT_LIMIT 3
/* This high bit shares the new private failure-count byte, not another timer.
 * Begin once in TryRefill; consume once only after all series work ends. */
#define OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE 0x80
#define OVERWORLD_ENTRY_REFILL_FAILURE_COUNT 0x03
/* COMMIT output: exact native outcome in bits0..7; optional delay in bits8..23.
 * Input value must be0. Delay0 means no natural schedule: manual, stale,
 * rebound, pending or empty. FINISH_REFILL returns a delay only. */
#define OVERWORLD_ENTRY_COMMIT_NONE 0
#define OVERWORLD_ENTRY_COMMIT_PENDING 1
#define OVERWORLD_ENTRY_COMMIT_FAILED 2
#define OVERWORLD_ENTRY_COMMIT_SUCCESS 3
#define OVERWORLD_ENTRY_COMMIT_OUTCOME(value) ((u8)(value))
#define OVERWORLD_ENTRY_COMMIT_REFILL_DELAY(value) ((u16)((value) >> 8))

struct OverworldWildQueuedSpawnGuard;
typedef struct OverworldEntryRouteNativeOps {
    u32 magic;
    u16 version, size;
    const OverworldActorSystemState *(*actors)(void);
    void (*initWorld)(OverworldWildSpawnState *, u8, OverworldPickupRouteWildWorld *);
    u16 (*allowed)(const OverworldWildBehaviorProfile *, u8);
    BOOL (*start)(OverworldWildSpawnState *, int, struct LocalMapObject *,
        const OverworldWildBehaviorProfile *, const OverworldWildBehaviorPrimitives *,
        const OverworldEntryRouteReceipt *, u32 *);
    void (*finish)(OverworldWildSpawnState *, FieldSystem *, int, struct LocalMapObject *, int, int, u8);
    void (*remove)(OverworldWildSpawnState *, FieldSystem *, int);
    BOOL (*occupied)(FieldSystem *, int, int);
    void (*resolve)(OverworldWildPreparedSpawn *, OverworldWildSpawnTerrain, int);
    BOOL (*limit)(OverworldWildSpawnState *, u8, const OverworldWildBehaviorProfile *);
    BOOL (*destination)(OverworldWildSpawnState *, FieldSystem *, OverworldWildSpawnTerrain,
        const OverworldWildBehaviorProfile *, OverworldWildSpawnPosition *);
    s32 (*groundHeight)(FieldSystem *, struct LocalMapObject *, int, int);
    BOOL (*personality)(FieldSystem *, OverworldWildPreparedSpawn *);
    OverworldWildHelperPrepareResult (*prepare)(OverworldWildSpawnState *, FieldSystem *, OverworldWildSpawnTerrain, int, OverworldWildPreparedSpawn *);
    BOOL (*guard)(OverworldWildSpawnState *, FieldSystem *, const OverworldWildPreparedSpawn *, int, struct OverworldWildQueuedSpawnGuard *);
    BOOL (*placementBlocked)(OverworldWildSpawnState *, FieldSystem *, int, int);
    BOOL (*spawn)(OverworldWildSpawnState *, FieldSystem *, OverworldWildSpawnTerrain, int, const OverworldWildPreparedSpawn *);
} OverworldEntryRouteNativeOps;
typedef struct OverworldEntryRouteNativeControl {
    u16 version, size;
    const OverworldEntryRouteNativeOps *ops;
    OverworldWildSpawnState *state;
    FieldSystem *field;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    OverworldWildPreparedSpawn *prepared;
    struct LocalMapObject *object;
    OverworldEntryRouteReceipt *receipt;
    u32 startCommitSequence;
    u32 value;
    u8 operation, slot, terrain, queryOperation;
    u8 accepted, usableIdle, reserved[2];
} OverworldEntryRouteNativeControl;
struct OverworldCargoQueryWildCall;
OverworldPickupRouteStatus OverworldEntryRoute_NativeControl(
    const struct OverworldCargoQueryWildCall *, OverworldCargoQueryResult *);
#endif
