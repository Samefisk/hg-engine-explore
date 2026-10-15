#ifndef OVERWORLD_WILD_RUNTIME_STATE_INTERNAL_H
#define OVERWORLD_WILD_RUNTIME_STATE_INTERNAL_H

/* The wild owner and the resident Throw observer share this runtime layout. */
#include "overworld_wild_spawns_internal.h"
#include "overworld_behavior_condition_adapter.h"
#include "overworld_wild_helper.h"
#include "overworld_spawn_guard.h"
#include "overworld_motion_model.h"
#include "overworld_entry_route.h"
#include "overworld_water_sink.h"
#include <stddef.h>

enum {
    OW_WILD_RETURN_NONE = 0,
    OW_WILD_RETURN_OUTWARD,
    OW_WILD_RETURN_PENDING,
    OW_WILD_RETURN_RETURNING,
};

/* One controller decision may own an ordinary outward and return leg. The
 * shared Actor still owns each accepted plan and its terminal boundary. */
typedef struct OverworldWildReturnMove {
    OverworldActorHandle subject;
    OverworldMotionPlan plan;
    OverworldWildBehaviorProfileData lane;
    FieldSystem *fieldSystem;
    u16 originSurfaceId;
    u8 laneState;
    u8 phase;
    u8 deferredPause;
    u8 retryFrames;
    __extension__ union {
        u16 returnMotionIdentity;
        u16 retryFrame; /* Only while PENDING; the return owns it after START. */
    };
} OverworldWildReturnMove;

typedef struct OverworldWildBehaviorSlotCache {
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u16 species;
    u16 mapId;
    u8 form;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 behaviorClass;
    u8 valid;
} OverworldWildBehaviorSlotCache;

typedef struct OverworldWildSpawnDestinationScan {
    s16 playerX;
    s16 playerY;
    s16 nextX;
    s16 nextY;
    u16 destinationMask;
    u8 candidateCount;
} OverworldWildSpawnDestinationScan;

#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
#define OW_WILD_SPAWN_STARTUP_PENDING 0xFE
#define OW_WILD_SPAWN_MOVE_DESTINATION_PENDING 0xFB
#define OW_WILD_SPAWN_ROUTE_READY 0xFC
#define OW_WILD_SPAWN_ROUTE_PENDING 0xFD
#define OW_WILD_PROFILE_DESTINATION_CHECKS_PER_UPDATE 4

typedef struct OverworldWildOverlayRuntimeState {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
    s16 playerBallShadowTileX;
    s16 playerBallShadowTileY;
    u16 playerBallShadowGfxId;
    u8 playerBallShadowTrackingValid;
    u8 movementMankeyTreeTopCacheValid[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyTreeTopCacheResult[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopCacheX[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopCacheY[OW_WILD_MAX_SPAWNS];
    u16 movementMankeyTreeTopCacheMapId[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyTreeTopLandingExpected[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyTreeTopSettled[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopSettledX[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopSettledY[OW_WILD_MAX_SPAWNS];
    u8 movementEmotePlayHopSound[OW_WILD_MAX_SPAWNS];
    u8 movementHopStartSoundSuppressFrames[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorLimitKeys[OW_WILD_MAX_SPAWNS];
    u8 playerBallCatchValues[OW_WILD_MAX_SPAWNS];
    u8 movementHelpSpawnParentSlotPlusOne;
    u8 movementHelpSpawnRemaining;
    u8 movementHelpSpawnPositionChecksRemaining;
    OverworldWildThrowState throwState;
    union {
        struct {
            u16 movementFrameDrivenOwnerMask;
            u16 movementFrameDrivenTiredMask;
            u16 movementOwnerTeleportMask;
            u16 movementTiredTeleportMask;
        };
        u16 movementRoutingMasks[4];
    };
    OverworldWildBehaviorSlotCache *movementBehaviorSlotCaches;
    OverworldWildPresentationState spawnPresentations;
    OverworldWildDespawnTelemetry despawnTelemetry;
    OverworldWildResidentData *residentData;
    u16 movementNativeHeldMask;
    u8 movementIdleAiCursor;
    u8 movementNativeShadowRestorePending;
    u8 movementCustomJumpArcHeightsQ4[OW_WILD_MAX_SPAWNS];
    u8 movementCustomMotionModes[OW_WILD_MAX_SPAWNS];
    /* One ordinary refill, owned by the existing maintenance schedule. No
     * engine object exists until the next usable frame validates this value. */
    OverworldWildPreparedSpawn queuedSpawn;
    OverworldWildQueuedSpawnGuard queuedSpawnGuard;
    OverworldWildSpawnDestinationScan spawnDestinationScan;
    OverworldWildBehaviorConditionRuntime *conditions;
    /* Sole Field-owned, read-only cargo route workspace. */
    void *pickupQuery;
    /* Append only: all existing native reader and Cargo offsets stay fixed.
     * NONE is unowned; RETURNING suppresses recursive return admission. */
    OverworldWildReturnMove returnMoves[OW_WILD_MAX_SPAWNS];
    /* Appended private queue receipt; old native offsets stay unchanged. */
    u32 queuedSpawnSerial;
    OverworldEntryRouteReceipt entryRouteReceipt;
    u32 entryRouteSerial[OW_WILD_MAX_SPAWNS];
    /* Appended water sink presentation. The terrain reconcile sets the
     * target; motion eases the current depth toward it in whole pixels. */
    u8 waterSinkTargetPx[OW_WILD_MAX_SPAWNS];
    u8 waterSinkPx[OW_WILD_MAX_SPAWNS];
    /* Encounter generation of the body each depth belongs to, high bit set;
     * zero (a fresh runtime) marks every body new. The cropped quads live on
     * the Field heap: draws keep them while a menu frees this runtime. */
    u8 waterSinkBodyTag[OW_WILD_MAX_SPAWNS];
} OverworldWildOverlayRuntimeState;

#if defined(__arm__)
_Static_assert(sizeof(OverworldWildReturnMove) == 144,
    "private return move layout changed");
_Static_assert(offsetof(OverworldWildOverlayRuntimeState, conditions) == 0x514,
    "return storage moved the native conditions pointer");
_Static_assert(offsetof(OverworldWildOverlayRuntimeState, pickupQuery) == 0x518,
    "return storage moved the native Cargo query pointer");
_Static_assert(offsetof(OverworldWildOverlayRuntimeState, returnMoves) == 0x51C,
    "return storage must follow the old runtime extent");
#endif

/* The role that adopts a real world effect owns this delivery. It is separate
 * from optional trace capture and does not add state to the Actor facade. */
static inline void OverworldWildConditions_NotifyWorldEffectInline(
    const OverworldWildSpawnState *state,
    const OverworldActorHandle *subject,
    u32 effect)
{
    OverworldWildOverlayRuntimeState *runtime;
    const OverworldBehaviorConditionServiceEntry *service;

    if (state == NULL || subject == NULL
        || subject->slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || state->movementRuntimeState == NULL
        || state->mapGeneration != subject->mapGeneration
        || !state->spawns[subject->slot].active
        || state->spawns[subject->slot].encounterGeneration
            != subject->encounterGeneration) {
        return;
    }
    runtime = state->movementRuntimeState;
    if (runtime->conditions == NULL) {
        return;
    }
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
    service = OverworldBehaviorConditionService_Get();
#else
    service = OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE();
#endif
    if (service != NULL && service->magic == OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC
        && service->version == OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        && service->size == sizeof(*service) && service->notifyWorldEffect != NULL) {
        service->notifyWorldEffect(
            &runtime->conditions->actors[subject->slot], subject, effect);
    }
}

#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
/* Host checks keep the production guard and delivery body. */
#define OverworldWildConditions_NotifyWorldEffect \
    OverworldWildConditions_NotifyWorldEffectInline
#else
/* Real effects are adopted only by current field actors while stock overlay
 * 1 is loaded. One private bridge shares these guards between all roles. */
void OverworldWildConditions_NotifyWorldEffect(
    const OverworldWildSpawnState *state,
    const OverworldActorHandle *subject,
    u32 effect);
#if !defined(OVERWORLD_FIELD_CAPSULE_IMPLEMENTATION)
__asm__(
    ".thumb\n"
    ".global OverworldWildConditions_NotifyWorldEffect\n"
    ".thumb_func\n"
    ".thumb_set OverworldWildConditions_NotifyWorldEffect, 0x02208900\n");
#endif
#endif

#endif // OVERWORLD_WILD_RUNTIME_STATE_INTERNAL_H
