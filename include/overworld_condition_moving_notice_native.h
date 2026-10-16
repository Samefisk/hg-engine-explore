#ifndef OVERWORLD_CONDITION_MOVING_NOTICE_NATIVE_H
#define OVERWORLD_CONDITION_MOVING_NOTICE_NATIVE_H
#include "overworld_behavior_condition_adapter.h"

#define OVERWORLD_CONDITION_NATIVE_CALL_VERSION 2
#define OVERWORLD_CONDITION_NATIVE_NORMAL 0
#define OVERWORLD_CONDITION_NATIVE_MOVING 1
#define OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS 2
/* Private read-only lookup in the existing 56-byte conditionNative packet. */
#define OVERWORLD_CONDITION_NATIVE_HOP_ARC_LOOKUP 7

struct OverworldPickupRouteWildWorld;
struct OverworldMountRuntimeState;
struct OverworldHopPresentationOps;

/* Synchronous borrowed packet. Actor owns frame admission and publication;
 * this physical heap-code host uses the same Field condition workspace. */
typedef struct OverworldConditionNativeCall {
    union {
        OverworldWildBehaviorConditionRuntime *runtime;
        struct OverworldMountRuntimeState *hopMount;
    };
    OverworldWildSpawnState *state;
    FieldSystem *field;
    union {
        const OverworldWildBehaviorDataBlob *blob;
        struct LocalMapObject *hopObject;
    };
    union {
        u32 blobSize;
        struct { u8 hopRequiredState, hopDirection, hopCount, hopOptions; };
    };
    union {
        const OverworldWildBehaviorProfile *observedProfile;
        const struct OverworldHopPresentationOps *hopOps;
        /* HOP_ARC_LOOKUP: authenticated current species-local map from the
         * capacity owner. Ordered global IDs; synchronous, never retained. */
        const u16 *hopArcApplicationIds;
    };
    OverworldBehaviorConditionObserveFunc observe;
    OverworldBehaviorConditionBuildContextFunc buildContext;
    OverworldBehaviorConditionTerrainFunc terrainAt;
    union {
        int forcedProfileIndex;
        u32 allowedTerrainMask; /* TARGET_ACCESS only: current resolved lane. */
        u32 hopArcAppliedMask; /* HOP_ARC_LOOKUP: resolved LOCAL mask. */
    };
    u16 version, size;
    u8 slot;
    union { u8 movementSpeed, hopArcApplicationCount; };
    u8 operation, reserved;
    union {
        u32 timedWinningApplicationMask;
        u32 hopArcPacked; /* HOP_ARC_LOOKUP output: rise, hang, drop, peak. */
        /* TARGET_ACCESS only, synchronously borrowed; never retained. */
        struct OverworldPickupRouteWildWorld *targetAccessWorld;
    };
    union {
        u16 winningTraceState;
        u16 hopArcApplicationId; /* global ID; FFFF when no group matched. */
    };
    /* HOP_ARC_LOOKUP winningEntryIndex is the LOCAL bit index, not a global ID. */
    u8 winningEntryIndex, reservedOutput;
} OverworldConditionNativeCall;

OverworldBehaviorConditionStatus OverworldConditionNative_Run(OverworldConditionNativeCall *);
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldConditionNativeCallMustRemain56[sizeof(OverworldConditionNativeCall)==56?1:-1];
_Static_assert(__builtin_offsetof(OverworldConditionNativeCall, version) == 40
    && __builtin_offsetof(OverworldConditionNativeCall, operation) == 46
    && __builtin_offsetof(OverworldConditionNativeCall, hopObject) == 12
    && __builtin_offsetof(OverworldConditionNativeCall, hopRequiredState) == 16
    && __builtin_offsetof(OverworldConditionNativeCall, hopOps) == 20
    && __builtin_offsetof(OverworldConditionNativeCall, hopArcApplicationIds) == 20
    && __builtin_offsetof(OverworldConditionNativeCall, hopArcApplicationCount) == 45
    && __builtin_offsetof(OverworldConditionNativeCall, hopArcApplicationId) == 52
    && __builtin_offsetof(OverworldConditionNativeCall, winningEntryIndex) == 54,
    "borrowed Hop packet moved existing native fields");
#endif
#endif
