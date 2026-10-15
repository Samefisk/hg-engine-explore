#ifndef OVERWORLD_QUERY_CODE_ADDON_H
#define OVERWORLD_QUERY_CODE_ADDON_H

#include "overworld_target_bindings.h"
#include "overworld_pickup_route_native.h"
#include "overworld_behavior_condition_runtime.h"
#include "overworld_cargo_query.h"
#include "overworld_pickup_route_wild.h"
#include "overworld_cargo_query_wild.h"
#include "overworld_pickup_landing_wild.h"

struct OverworldCargoReadWildObservationCall;
struct OverworldCargoReadWildTargetCall;
struct OverworldCargoReadWildTarget;
struct OverworldThrowAwayWildCall;
struct OverworldThrowHeldWildCall;
struct PlayerHealthContactSegment;
struct OverworldWildSpawn;
struct LocalMapObject;
struct FieldSystem;
struct OverworldReturnMoveWildContext;
struct OverworldReturnMoveWildRequest;
struct OverworldMotionPlan;
struct OverworldWildSpawnState;
struct OverworldWildBehaviorConditionRuntime;
struct OverworldActorSystemEntry;
struct OverworldActorSystemDebugLayout;
struct OverworldActorSystemState;
struct OverworldConditionNativeCall;
struct OverworldActorHopPlanCall;
struct OverworldHopClearanceNativeOps;

#define OVERWORLD_QUERY_CODE_ADDON_MAGIC 0x51444F57 /* WODQ */
#define OVERWORLD_QUERY_CODE_ADDON_MEMBER_ID 21
#define OVERWORLD_QUERY_CODE_ADDON_VERSION 9
#define OVERWORLD_QUERY_CODE_ADDON_HEADER_BYTES 64
#define OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES 196
#define OVERWORLD_QUERY_CODE_ADDON_CALLBACKS 39
#define OVERWORLD_QUERY_CODE_ADDON_CONDITION_WORLD_BYTES 248
#define OVERWORLD_QUERY_CODE_ADDON_LINK_BASE 0x02080000
/* Includes the shared query and return adapters. Allocate the exact package,
 * retaining the existing 32KiB free-heap reserve; no static RAM is added. */
/* Current target-access and mounted landing code use the bounded tail. The
 * Cargo Tick prefix and its read budget do not grow. */
/* Exact complete ARM image and package. Compared with published3573,
 * compact witnesses and removal of the unused follower Entry path save5264
 * workspace bytes; this package adds1976. Combined payload is3288 bytes
 * smaller. The32KiB reserve stays. Bounds match the full measured package. */
#define OVERWORLD_QUERY_CODE_ADDON_MAX_IMAGE 0x10C38
#define OVERWORLD_QUERY_CODE_ADDON_MAX_BLOB 0x11200
#define OVERWORLD_QUERY_CODE_ADDON_MAX_RELOCATIONS 256

/* Serialized little-endian file. Image begins at byte64. Only local ABS32
 * words listed by the packer are rebased; fixed resident imports stay fixed.
 * The packer also proves every retained Thumb branch is local to this image.
 * No BSS, mutable globals, constructors, ARM code or external direct branches. */
typedef struct OverworldQueryCodeAddonHeader {
    u32 magic;
    u16 version, headerSize;
    u32 blobSize, imageSize, linkBase, entryOffset, imageOffset;
    u32 relocationOffset, relocationCount, importOffset, importCount;
    u32 checksum;
    u16 entryVersion, entrySize;
    u32 flags, reserved[2];
} OverworldQueryCodeAddonHeader;
typedef struct OverworldQueryCodeAddonImport { u32 offset, target; } OverworldQueryCodeAddonImport;

/* One typed query-code interface, with caller-owned values/workspace.
 * No entry function may retain a draw callback or allocate a second search. */
typedef struct OverworldQueryCodeAddonEntry {
    u32 magic;
    u16 version, size;
    u16 bindingStateSize, routeStateSize, workspaceSize, resultSize;
    u16 nativeContextSize, nativeVersion;
    OverworldTargetBindingStatus (*bindingInit)(OverworldTargetBindingsState *, const OverworldActorHandle *);
    OverworldTargetBindingStatus (*bindingCapture)(OverworldTargetBindingsState *, const OverworldBehaviorConditionWorldView *, const OverworldActorHandle *, const OverworldBehaviorConditionEntryResult *, u8, u8, u16);
    OverworldTargetBindingStatus (*bindingResolve)(OverworldTargetBindingsState *, const OverworldBehaviorConditionWorldView *, u8, OverworldTargetBindingPosition *);
    OverworldTargetBindingStatus (*bindingClear)(OverworldTargetBindingsState *, const OverworldActorHandle *, u8, u8);
    OverworldTargetBindingStatus (*bindingClearAll)(OverworldTargetBindingsState *, const OverworldActorHandle *, u8);
    OverworldPickupRouteStatus (*routeBegin)(OverworldPickupRouteState *, const OverworldPickupRouteQuery *, OverworldPickupRouteWorkspace *);
    OverworldPickupRouteStatus (*routeResume)(OverworldPickupRouteState *, const OverworldPickupRouteQuery *, u32, OverworldPickupRouteResult *);
    OverworldPickupRouteEdgeResult (*classify)(void *, const OverworldPickupRoutePosition *, const OverworldPickupRouteEdge *, OverworldPickupRoutePosition *);
    OverworldPickupRouteEdgeResult (*pickupGoal)(OverworldPickupRouteNativeContext *, s16, s16, OverworldPickupRoutePosition *);
    OverworldPickupRouteEdgeResult (*landing)(const OverworldPickupRouteNativeLandingCall *);
    OverworldBehaviorConditionPrepareActorFunc conditionPrepare;
    OverworldBehaviorConditionEvaluatePreparedFunc conditionEvaluate;
    OverworldBehaviorResolverCallFunc resolverCall;
    OverworldBehaviorConditionNotifyWorldEffectFunc conditionNotify;
    u16 conditionVersion, conditionWorldSize, conditionPreparedSize, conditionResultSize;
    void (*cargoInit)(OverworldCargoQueryState *, OverworldCargoQueryStorage *);
    void (*cargoClear)(OverworldCargoQueryState *);
    OverworldPickupRouteStatus (*cargoTick)(OverworldCargoQueryState *, const OverworldCargoQueryInput *, OverworldCargoQueryResult *);
    OverworldPickupRouteEdgeResult (*atomicPickup)(void *, const OverworldActorHandle *, const OverworldActorHandle *);
    u16 cargoVersion, cargoStateSize, cargoInputSize, cargoResultSize, cargoStorageSize, reservedCargo;
    OverworldPickupRouteStatus (*cargoWildTick)(const OverworldCargoQueryWildCall *, OverworldCargoQueryResult *);
    enum OverworldMotionDecision (*landingWild)(const OverworldPickupRouteWildLandingCall *);
    OverworldPickupRouteStatus (*cargoReadRoute)(const OverworldCargoQueryWildCall *, OverworldCargoQueryResult *);
    u32 (*cargoReadObserve)(const struct OverworldCargoReadWildObservationCall *, BOOL *);
    OverworldPickupRouteEdgeResult (*cargoReadReach)(void *, const OverworldPickupRoutePosition *, const OverworldPickupRoutePosition *);
    const struct OverworldActorSystemState *(*cargoReadActorState)(const struct OverworldActorSystemEntry *, const struct OverworldActorSystemDebugLayout *, const struct OverworldActorSystemState *);
    const OverworldWildBehaviorConditionOptions *(*cargoReadOptions)(const OverworldPickupRouteWildWorld *);
    u8 (*cargoReadTarget)(const struct OverworldCargoReadWildTargetCall *, struct OverworldCargoReadWildTarget *);
    BOOL (*throwAwayRead)(const struct OverworldThrowAwayWildCall *);
    void (*playerDamageRead)(struct OverworldWildBehaviorConditionRuntime *,
        struct OverworldWildSpawnState *, struct FieldSystem *, u8,
        const OverworldWildBehaviorDataBlob *);
    OverworldBehaviorConditionStatus (*conditionNative)(struct OverworldConditionNativeCall *);
    u32 (*throwObserve)(struct OverworldWildSpawnState *, int,
        const OverworldWildBehaviorProfile *, const OverworldWildBehaviorDataBlob *,
        const struct OverworldWildBehaviorConditionRuntime *,
        BOOL (*)(struct FieldSystem *, const struct OverworldWildSpawn *),
        BOOL (*)(struct OverworldWildSpawnState *, int, int, u8, u32),
        BOOL (*)(struct OverworldWildSpawnState *, u8, u8, OverworldTargetBindingPosition *));
    BOOL (*throwHeld)(const struct OverworldThrowHeldWildCall *);
    void (*playerDamagePublish)(const struct OverworldWildSpawnState *, u8,
        BOOL (*)(const struct OverworldWildSpawnState *, u8));
    BOOL (*contactIntersects)(const struct PlayerHealthContactSegment *);
    enum OverworldMotionDecision (*returnRequest)(const struct OverworldReturnMoveWildRequest *);
    BOOL (*returnCurrent)(const struct OverworldReturnMoveWildContext *);
    void (*returnStart)(const struct OverworldReturnMoveWildContext *);
    BOOL (*returnFinish)(const struct OverworldReturnMoveWildContext *,
        OverworldWildBehaviorProfile *, OverworldWildBehaviorPrimitives *, u8);
    u8 (*returnCombatWork)(const struct OverworldReturnMoveWildContext *,
        struct OverworldMotionPlan *);
    /* Append only: all original192-byte metadata/callback offsets stay fixed. */
    enum OverworldMotionDecision (*hopTrajectory)(struct OverworldActorHopPlanCall *,
        const struct OverworldHopClearanceNativeOps *);
} OverworldQueryCodeAddonEntry;

typedef struct OverworldQueryCodeAddonOwner { u32 fieldIdentity; u16 fieldEpoch, mapGeneration; } OverworldQueryCodeAddonOwner;
typedef struct OverworldQueryCodeAddonState {
    void *blob;
    u32 blobSize;
    const OverworldQueryCodeAddonEntry *entry;
    OverworldQueryCodeAddonOwner owner;
    u32 memberId;
    u8 phase, reserved[3];
} OverworldQueryCodeAddonState;
typedef enum OverworldQueryCodeAddonStatus {
    OVERWORLD_QUERY_ADDON_OK = 0, OVERWORLD_QUERY_ADDON_INVALID,
    OVERWORLD_QUERY_ADDON_LOAD_FAILED, OVERWORLD_QUERY_ADDON_BAD_PACKAGE,
    OVERWORLD_QUERY_ADDON_BUSY, OVERWORLD_QUERY_ADDON_DRAIN_PENDING,
} OverworldQueryCodeAddonStatus;

/* loadBlob has the existing WildLoadCodeAddonBlob signature. It allocates
 * once from the stock Field resource heap. This module does not allocate workspace.
 * Stock cache order: DC_FlushRange, DC_WaitWriteBufferEmpty, IC_InvalidateRange.
 * drain cancels the sole query/borrowed callbacks; FALSE retains the code and
 * blocks new entry access until a later cleanup retry. It must clear every
 * stored addon function pointer before TRUE. Keep this owner/ops code alive. */
typedef struct OverworldQueryCodeAddonOps {
    BOOL (*loadBlob)(u32, u32, void **, u32 *);
    void (*freeBlob)(void *);
    void (*flushData)(const void *, u32);
    void (*waitWriteBuffer)(void);
    void (*invalidateCode)(void *, u32);
    BOOL (*drain)(void *);
} OverworldQueryCodeAddonOps;

/* State starts zeroed. expectedSize is the exact generated package size,
 * never zero. Call only from a current loaded Field. No automatic retry loop. */
OverworldQueryCodeAddonStatus OverworldQueryCodeAddon_Load(OverworldQueryCodeAddonState *, const OverworldQueryCodeAddonOwner *, const OverworldQueryCodeAddonOps *, u32 memberId, u32 expectedSize);
/* Borrow only for the current synchronous call. The field owner serializes
 * the one workspace; do not retain this pointer in Actor or scheduled work. */
const OverworldQueryCodeAddonEntry *OverworldQueryCodeAddon_Acquire(const OverworldQueryCodeAddonState *, const OverworldQueryCodeAddonOwner *);
/* Same loaded Field only: retain same-epoch map rebinds, or accept the exact
 * next paired nonzero epoch/map generation (FFFF wraps to 1). Block access,
 * drain the query and bindings, then publish without another allocation. */
OverworldQueryCodeAddonStatus OverworldQueryCodeAddon_Rebind(OverworldQueryCodeAddonState *, const OverworldQueryCodeAddonOwner *, const OverworldQueryCodeAddonOps *, void *queryOwner);
/* Call BEFORE runtime/workspace/Field resource heap teardown, while drain is callable.
 * Publication is blocked before drain and cleared before freeing code. */
OverworldQueryCodeAddonStatus OverworldQueryCodeAddon_Unload(OverworldQueryCodeAddonState *, const OverworldQueryCodeAddonOps *, void *queryOwner);

/* Typed native cache wrappers for Ops. Their ARM imports are authenticated by
 * the package proof; do not add a Thumb bit to these stock ARM functions. */
void OverworldQueryCodeAddon_FlushData(const void *, u32);
void OverworldQueryCodeAddon_WaitWriteBuffer(void);
void OverworldQueryCodeAddon_InvalidateCode(void *, u32);

typedef char QueryAddonHeaderMustRemain64[sizeof(OverworldQueryCodeAddonHeader)==64?1:-1];
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char QueryAddonEntryMustRemain196[sizeof(OverworldQueryCodeAddonEntry)==196?1:-1];
typedef char QueryAddonConditionNativeCallbackMustRemain152[
    __builtin_offsetof(OverworldQueryCodeAddonEntry, conditionNative)==152?1:-1];
typedef char QueryAddonCombatCallbackMustRemain188[
    __builtin_offsetof(OverworldQueryCodeAddonEntry, returnCombatWork)==188?1:-1];
typedef char QueryAddonHopCallbackMustRemain192[
    __builtin_offsetof(OverworldQueryCodeAddonEntry, hopTrajectory)==192?1:-1];
typedef char QueryAddonStateMustRemain28[sizeof(OverworldQueryCodeAddonState)==28?1:-1];
typedef char QueryAddonConditionWorldMustRemain248[sizeof(OverworldBehaviorConditionWorldView)==248?1:-1];
#endif
#endif
