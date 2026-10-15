#ifndef OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_H
#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_H

#include "overworld_behavior_condition_runtime.h"
#include "overworld_target_bindings.h"

#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_MAGIC 0x4143574F /* OWCA */
#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION 12
#define OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD_ADDR 0x023BF408

#define OVERWORLD_BEHAVIOR_CONDITION_TARGET_ROLE_MOUNTED (1u << 2)

/* Private evaluateActor operation: current reachable Cargo capture only.
 * Resolver, published masks and motion stay with the later idle boundary. */
#define OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO (-2)
/* Evaluate all conditions and publish metadata during an ordinary move.
 * The accepted move keeps control; presentation waits for legal intent.
 * The owner calls once per actor frame and clears pending state at teardown. */
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT (-3)
#define OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT

typedef struct FieldSystem FieldSystem;
typedef struct OverworldWildSpawn OverworldWildSpawn;
typedef struct OverworldWildSpawnState OverworldWildSpawnState;

/* Private event tag for the existing authenticated damage publisher. */
#define OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE 0x80u

typedef struct OverworldWildBehaviorConditionFrame {
    OverworldBehaviorConditionWorldView world;
    OverworldBehaviorConditionCandidate
        candidates[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    u16 actorSlotMask;
    u8 traceArmed;
    u8 valid;
} OverworldWildBehaviorConditionFrame;

/* One accepted player hit. Pending bits belong to the prepared generations
 * present at that hit; consumption is per subject, independent of actor role.
 * A later accepted hit replaces this value. Field cleanup clears it. */
typedef struct OverworldPlayerDamageSource {
    FieldSystem *fieldSystem;
    u32 frame;
    OverworldActorHandle source;
    u16 recipientGenerations[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    u16 pendingMask;
    u16 reserved;
} OverworldPlayerDamageSource;

typedef struct OverworldWildBehaviorConditionRuntime {
    OverworldBehaviorConditionPreparedActor
        actors[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    BehaviorResolveRequest request;
    BehaviorResolveResult resolution;
    OverworldWildBehaviorContext context;
    OverworldWildBehaviorConditionFrame frame;
    /* Stable Vision is resolved once without conditional applications and
     * reused by every condition at later intent boundaries. */
    OverworldVisionSpec currentVisions[
        OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
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
    OverworldTargetBindingsState bindings[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    OverworldPlayerDamageSource playerDamage;
} OverworldWildBehaviorConditionRuntime;

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldPlayerDamageSourceMustRemain44Bytes[
    sizeof(OverworldPlayerDamageSource) == 44 ? 1 : -1];
typedef char OverworldPlayerDamageSourceOffsetMustRemain3056[
    offsetof(OverworldWildBehaviorConditionRuntime, playerDamage) == 3056 ? 1 : -1];
typedef char OverworldWildBehaviorConditionRuntimeBudgetMustRemain3100Bytes[
    sizeof(OverworldWildBehaviorConditionRuntime) == 3100 ? 1 : -1];
typedef char OverworldWildBehaviorConditionScratchOffsetMustRemain880[
    offsetof(OverworldWildBehaviorConditionRuntime, scratch) == 880 ? 1 : -1];
typedef char OverworldWildBehaviorConditionResultOffsetMustRemain912[
    offsetof(OverworldWildBehaviorConditionRuntime, result) == 912 ? 1 : -1];
typedef char OverworldWildBehaviorConditionResolutionOffsetMustRemain1496[
    offsetof(OverworldWildBehaviorConditionRuntime, resolution) == 1496
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionActorSnapshotOffsetMustRemain2156[
    offsetof(OverworldWildBehaviorConditionRuntime, actorSnapshot) == 2156
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionActiveMasksOffsetMustRemain2332[
    offsetof(OverworldWildBehaviorConditionRuntime, activeApplicationMasks)
            == 2332
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionTimedMasksOffsetMustRemain2372[
    offsetof(
        OverworldWildBehaviorConditionRuntime,
        timedWinningApplicationMasks) == 2372
        ? 1
        : -1];
typedef char OverworldWildBehaviorConditionTargetValidOffsetMustRemain2452[
    offsetof(OverworldWildBehaviorConditionRuntime, targetValidMask) == 2452
        ? 1
        : -1];
#endif

#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED   (1u << 0)
#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED (1u << 1)
#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED (1u << 2)
/* Full Moving evaluation, including publication and current target resolve.
 * A skipped or failed Moving call leaves this bit clear for Warm fallback. */
#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED (1u << 3)
#define OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED (1u << 4)

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
 * valueA: winning condition [0:15], actor-target slot [16:30], Until Crash [31].
 * valueB: activeUntil [0:15], cooldownUntil [16:31].
 * The fixed trace event has no room for a second complete 12-byte handle;
 * target generation fields are therefore recovered from the current actor
 * snapshot selected by the recorded slot. Runtime Crash delivery is independent
 * of whether trace capture is armed. */

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

typedef void (*OverworldBehaviorConditionPopulateVisibilityFunc)(
    FieldSystem *fieldSystem,
    OverworldBehaviorConditionWorldView *world);

typedef OverworldBehaviorConditionStatus
(*OverworldBehaviorConditionPrepareActorAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldWildSpawnState *state,
    const void *blobBytes,
    u32 blobSize,
    const OverworldActorHandle *subject,
    const OverworldWildBehaviorProfile *stableProfile,
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

typedef u32 (*OverworldBehaviorConditionObserveFunc)(
    OverworldWildSpawnState *, int, const OverworldWildBehaviorProfile *,
    const OverworldWildBehaviorDataBlob *, OverworldWildBehaviorConditionRuntime *);

typedef OverworldBehaviorConditionStatus
(*OverworldBehaviorConditionEvaluateActorAdapterFunc)(
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const void *blobBytes,
    u32 blobSize,
    u8 slot,
    u8 subjectMovementSpeed,
    /* Observe only after the current frame and full subject are populated. */
    const OverworldWildBehaviorProfile *observedProfile,
    OverworldBehaviorConditionObserveFunc observe,
    int forcedOverrideProfileIndex,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    OverworldBehaviorConditionIsCurrentSpawnFunc isCurrentSpawn,
    OverworldBehaviorConditionTerrainFunc terrainAt,
    OverworldBehaviorConditionPopulateVisibilityFunc populateVisibility,
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
