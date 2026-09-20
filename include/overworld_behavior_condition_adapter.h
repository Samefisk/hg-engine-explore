#ifndef OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_H
#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_H

#include "overworld_behavior_condition_runtime.h"

#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_MAGIC 0x4143574F /* OWCA */
#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION 10
#define OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD_ADDR 0x023BF408

#define OVERWORLD_BEHAVIOR_CONDITION_TARGET_ROLE_MOUNTED (1u << 2)

typedef struct FieldSystem FieldSystem;
typedef struct OverworldWildSpawn OverworldWildSpawn;
typedef struct OverworldWildSpawnState OverworldWildSpawnState;

typedef struct OverworldWildBehaviorConditionFrame {
    OverworldBehaviorConditionWorldView world;
    OverworldBehaviorConditionCandidate
        candidates[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    u16 actorSlotMask;
    u8 traceArmed;
    u8 valid;
} OverworldWildBehaviorConditionFrame;

typedef struct OverworldWildBehaviorConditionRuntime {
    OverworldBehaviorConditionPreparedActor
        actors[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    BehaviorResolveRequest request;
    BehaviorResolveResult resolution;
    OverworldWildBehaviorContext context;
    OverworldWildBehaviorConditionFrame frame;
    /* Inspection is condition-workspace data, not call-stack data.  A wild
     * intent boundary already has a deep field-task call chain. */
    OverworldActorSnapshot actorSnapshot;
    u32 activeApplicationMasks[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    /* One bit per conditional-profile application whose current winner is
     * timed. Keeping the bits separate lets one stacked profile end while
     * another remains active. */
    u32 timedWinningApplicationMasks[
        OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    s16 targetX[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    s16 targetY[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    u16 targetValidMask;
} OverworldWildBehaviorConditionRuntime;

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldWildBehaviorConditionRuntimeBudgetMustRemain2044Bytes[
    sizeof(OverworldWildBehaviorConditionRuntime) == 2044 ? 1 : -1];
typedef char OverworldWildBehaviorConditionScratchOffsetMustRemain520[
    offsetof(OverworldWildBehaviorConditionRuntime, scratch) == 520 ? 1 : -1];
typedef char OverworldWildBehaviorConditionResultOffsetMustRemain552[
    offsetof(OverworldWildBehaviorConditionRuntime, result) == 552 ? 1 : -1];
typedef char OverworldWildBehaviorConditionResolutionOffsetMustRemain1136[
    offsetof(OverworldWildBehaviorConditionRuntime, resolution) == 1136
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionActorSnapshotOffsetMustRemain1744[
    offsetof(OverworldWildBehaviorConditionRuntime, actorSnapshot) == 1744
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionActiveMasksOffsetMustRemain1920[
    offsetof(OverworldWildBehaviorConditionRuntime, activeApplicationMasks)
            == 1920
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionTimedMasksOffsetMustRemain1960[
    offsetof(
        OverworldWildBehaviorConditionRuntime,
        timedWinningApplicationMasks) == 1960
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionTargetValidOffsetMustRemain2040[
    offsetof(OverworldWildBehaviorConditionRuntime, targetValidMask) == 2040
        ? 1
        : -1];
#endif

#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED   (1u << 0)
#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED (1u << 1)
#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED (1u << 2)

typedef struct OverworldBehaviorConditionAdapterOutcome {
    u8 flags;
    u8 reserved;
    s16 targetDx;
    s16 targetDy;
} OverworldBehaviorConditionAdapterOutcome;

/* TRIGGERED requests presentation only when a trigger changes the resolved
 * conditional behavior. Timed refreshes still restart duration and report in
 * OverworldBehaviorConditionResult, but do not trap the actor in alerts. */

/* CONDITIONAL_RESOLVED traces remain bound to the full subject handle.
 * reason: winning application [0:4], target source [5:9], target kind
 * [10:11], triggered [12], truth [13], active [14], timed [15].
 * valueA: winning condition [0:15], actor-target slot [16:31].
 * valueB: activeUntil [0:15], cooldownUntil [16:31].
 * The fixed trace event has no room for a second complete 12-byte handle;
 * target generation fields are therefore recovered from the current actor
 * snapshot selected by the recorded slot. */

typedef void (*OverworldBehaviorConditionBuildContextFunc)(
    OverworldWildBehaviorContext *context,
    const OverworldWildSpawn *spawn,
    u16 species,
    u8 level,
    u8 terrain,
    u8 shiny);

typedef BOOL (*OverworldBehaviorConditionIsCurrentSpawnFunc)(
    FieldSystem *fieldSystem,
    const OverworldWildSpawn *spawn);

typedef u16 (*OverworldBehaviorConditionTerrainFunc)(
    FieldSystem *fieldSystem,
    int x,
    int y);

typedef OverworldBehaviorConditionStatus
(*OverworldBehaviorConditionPrepareActorAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldWildSpawnState *state,
    const void *blobBytes,
    u32 blobSize,
    const OverworldActorHandle *subject,
    u8 slot,
    OverworldBehaviorConditionBuildContextFunc buildContext);

typedef void (*OverworldBehaviorConditionClearActorAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot);

typedef void (*OverworldBehaviorConditionClearAllAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime);

typedef void (*OverworldBehaviorConditionClearResolutionAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot);

typedef OverworldBehaviorConditionStatus
(*OverworldBehaviorConditionEvaluateActorAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const void *blobBytes,
    u32 blobSize,
    u8 slot,
    u8 subjectMovementSpeed,
    int forcedOverrideProfileIndex,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    OverworldBehaviorConditionIsCurrentSpawnFunc isCurrentSpawn,
    OverworldBehaviorConditionTerrainFunc terrainAt,
    OverworldBehaviorConditionAdapterOutcome *outcome);

typedef struct OverworldBehaviorConditionAdapterEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldBehaviorConditionPrepareActorAdapterFunc prepareActor;
    OverworldBehaviorConditionClearActorAdapterFunc clearActor;
    OverworldBehaviorConditionClearAllAdapterFunc clearAll;
    OverworldBehaviorConditionClearResolutionAdapterFunc clearResolution;
    OverworldBehaviorConditionEvaluateActorAdapterFunc evaluateActor;
} OverworldBehaviorConditionAdapterEntry;

void OverworldBehaviorConditionTrace_Record(
    const OverworldActorHandle *subject,
    const OverworldBehaviorConditionResult *result,
    const OverworldBehaviorConditionEntryState *entryState,
    u16 entryStateBits);

typedef void (*OverworldBehaviorConditionTraceRecordFunc)(
    const OverworldActorHandle *subject,
    const OverworldBehaviorConditionResult *result,
    const OverworldBehaviorConditionEntryState *entryState,
    u16 entryStateBits);

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#define OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD \
    ((OverworldBehaviorConditionTraceRecordFunc) \
        (OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD_ADDR | 1u))
#else
#define OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD \
    OverworldBehaviorConditionTrace_Record
#endif

extern const OverworldBehaviorConditionAdapterEntry
    gOverworldBehaviorConditionAdapterEntry;

typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[
    sizeof(OverworldBehaviorConditionAdapterEntry) == 28 ? 1 : -1];

#endif // OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_H
