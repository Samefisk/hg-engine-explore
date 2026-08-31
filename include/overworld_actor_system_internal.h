#ifndef OVERWORLD_ACTOR_SYSTEM_INTERNAL_H
#define OVERWORLD_ACTOR_SYSTEM_INTERNAL_H

#include "overworld_actor_system.h"
#include "overworld_behavior_resolver.h"
#include "overworld_motion_model.h"
#include "overworld_wild_movement.h"

#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x78)
#define OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x88)
#define OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x98)
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0xA8)
#define OVERWORLD_ACTOR_SYSTEM_STATE_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x3100)
#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_MAGIC 0x5250574F /* OWPR */
#define OVERWORLD_ACTOR_SYSTEM_MOTION_MAGIC 0x534D574F /* OWMS */
#define OVERWORLD_ACTOR_SYSTEM_POPULATION_MAGIC 0x5450574F /* OWPT */
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC 0x504D574F /* OWMP */
#define OVERWORLD_ACTOR_SYSTEM_SERVICE_COUNT 4
#define OVERWORLD_ACTOR_RESOLVER_SERVICE_VERSION 1
#define OVERWORLD_ACTOR_MOTION_SERVICE_VERSION 2
#define OVERWORLD_ACTOR_POPULATION_SERVICE_VERSION 1
#define OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION 1
#define OVERWORLD_ACTOR_MOTION_CALL_VERSION 2

struct FieldSystem;
struct OverworldWildSpawnState;

typedef OverworldActorResult (*OverworldActorCompatibilityBindFunc)(
    const OverworldActorStateSnapshot *initial,
    OverworldActorHandle *handle);
typedef OverworldActorResult (*OverworldActorCompatibilityUpdateFunc)(
    const OverworldActorHandle *handle,
    const OverworldActorStateSnapshot *state);
typedef OverworldActorResult (*OverworldActorCompatibilityUnbindFunc)(
    const OverworldActorHandle *handle,
    u16 reason);
typedef u16 (*OverworldActorCompatibilityAdvanceFieldEpochFunc)(u16 reason);
typedef OverworldActorResult (*OverworldActorCompatibilityRecordTraceFunc)(
    const OverworldActorHandle *handle,
    u16 event,
    u16 reason,
    u32 valueA,
    u32 valueB);
typedef u16 (*OverworldActorCompatibilityGetFieldEpochFunc)(void);

typedef struct OverworldActorCompatibilityEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorCompatibilityBindFunc bind;
    OverworldActorCompatibilityUpdateFunc update;
    OverworldActorCompatibilityUnbindFunc unbind;
    OverworldActorCompatibilityAdvanceFieldEpochFunc advanceFieldEpoch;
    OverworldActorCompatibilityRecordTraceFunc recordTrace;
    OverworldActorCompatibilityGetFieldEpochFunc getFieldEpoch;
} OverworldActorCompatibilityEntry;

/*
 * Stable code-home slots for resolver, motion, population timer, and movement
 * policy modules. Version zero means reserved and unavailable. Activating a
 * slot does not move the public facade, compatibility entry, or debug layout.
 */
typedef struct OverworldActorReservedServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    u32 apply;
    u32 inspect;
} OverworldActorReservedServiceEntry;

typedef BehaviorResolveStatus (*OverworldActorResolverResolveFunc)(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request,
    BehaviorResolveResult *result,
    BehaviorResolutionTrace *trace);
typedef BehaviorResolveStatus (*OverworldActorResolverInspectClassFunc)(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request,
    BehaviorClassSelection *selection,
    BehaviorResolutionTrace *trace);

typedef struct OverworldActorResolverServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorResolverResolveFunc resolve;
    OverworldActorResolverInspectClassFunc inspectClass;
} OverworldActorResolverServiceEntry;

typedef enum OverworldActorMotionServiceOperation {
    OVERWORLD_ACTOR_MOTION_SERVICE_RESET = 0,
    OVERWORLD_ACTOR_MOTION_SERVICE_SELECT_PLAN = 1,
    OVERWORLD_ACTOR_MOTION_SERVICE_BEGIN = 2,
    OVERWORLD_ACTOR_MOTION_SERVICE_READ_SAMPLE = 3,
    OVERWORLD_ACTOR_MOTION_SERVICE_ACKNOWLEDGE_COMMIT = 4,
    OVERWORLD_ACTOR_MOTION_SERVICE_SUSPEND = 5,
    OVERWORLD_ACTOR_MOTION_SERVICE_RESUME = 6,
    OVERWORLD_ACTOR_MOTION_SERVICE_CANCEL = 7,
    OVERWORLD_ACTOR_MOTION_SERVICE_REBIND_FIELD = 8,
    OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST = 9,
} OverworldActorMotionServiceOperation;

typedef struct OverworldActorMotionServiceCall {
    u16 version;
    u16 size;
    u8 operation;
    u8 candidateCount;
    u8 cancelReason;
    u8 selectedIndex;
    u8 actorSlot;
    u8 reserved;
    u16 fieldEpoch;
    s16 startX;
    s16 startY;
    s32 startBaseY;
    const OverworldMotionIntent *intent;
    const OverworldMotionCandidate *candidates;
    OverworldMotionPlan *plan;
    OverworldMotionState *state;
    OverworldMotionSample *sample;
    u16 decision;
    u16 tickFlags;
} OverworldActorMotionServiceCall;

typedef OverworldActorResult (*OverworldActorMotionDispatchFunc)(
    OverworldActorMotionServiceCall *call);
typedef OverworldMotionDecision (*OverworldActorMotionRequestWildFunc)(
    struct OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfileData *lane,
    u8 kind,
    u8 visibilityPolicy,
    u8 arcHeightQ4,
    u8 facing);

typedef struct OverworldActorMotionServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorMotionDispatchFunc dispatch;
    OverworldActorMotionRequestWildFunc requestWild;
} OverworldActorMotionServiceEntry;

typedef OverworldActorFrameResult (*OverworldActorPopulationFrameFunc)(
    struct FieldSystem *fieldSystem,
    struct OverworldWildSpawnState *state);
typedef void (*OverworldActorPopulationResetFunc)(void);

typedef struct OverworldActorPopulationServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorPopulationFrameFunc frame;
    OverworldActorPopulationResetFunc reset;
} OverworldActorPopulationServiceEntry;

struct OverworldWildMovementPolicyEntry;
typedef BOOL (*OverworldActorMovementPolicyValidateFunc)(void);

typedef struct OverworldActorPolicyState {
    OverworldWildWalkMomentumState walkMomentum;
    u32 behaviorFingerprint;
    u32 matchedLayerMask;
    u8 chainStepsRemaining;
    u8 deferredChainPauseTicks;
    u8 deferredChainPauseAction;
    u8 variancePhase;
    u8 bufferedDirection;
    u8 stopPending;
    u8 pendingStep;
    u8 pendingSkid;
    u8 streamState;
    u16 worldEffectSequence;
    u16 worldEffectId;
} OverworldActorPolicyState;

typedef struct OverworldActorMovementPolicyServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    const struct OverworldWildMovementPolicyEntry *policy;
    OverworldActorPolicyState *states;
} OverworldActorMovementPolicyServiceEntry;

#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY \
    ((const OverworldActorResolverServiceEntry *) \
        OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY_ADDR)
#define OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY \
    ((const OverworldActorMotionServiceEntry *) \
        OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY_ADDR)
#define OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY \
    ((const OverworldActorPopulationServiceEntry *) \
        OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY_ADDR)
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY \
    ((const OverworldActorMovementPolicyServiceEntry *) \
        OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY_ADDR)

#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY \
    ((const OverworldActorCompatibilityEntry *) \
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY_ADDR)

typedef struct OverworldActorSystemDebugLayout {
    u32 magic;
    u16 version;
    u16 size;
    u32 overlayBase;
    u32 overlayEnd;
    u32 stateAddress;
    u16 actorCapacity;
    u16 commandCapacity;
    u16 traceCapacity;
    u16 handleSize;
    u16 commandSize;
    u16 replySize;
    u16 querySize;
    u16 snapshotSize;
    u16 actorStateSize;
    u16 traceHeaderSize;
    u16 traceEventSize;
    u16 stateSize;
    u16 fieldEpochOffset;
    u16 actorsOffset;
    u16 traceHeaderOffset;
    u16 traceEventsOffset;
    u16 queueOffset;
    u16 serviceDirectoryOffset;
    u16 serviceEntrySize;
    u16 serviceEntryCount;
    u16 stateCapacity;
    u16 reserved;
} OverworldActorSystemDebugLayout;

#define OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT \
    ((const OverworldActorSystemDebugLayout *) \
        OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT_ADDR)

typedef struct OverworldActorRuntimeSlot {
    OverworldActorStateSnapshot snapshot;
    OverworldMotionState motion;
    u16 pendingFirstPathAdvance;
    u16 pendingLastPathAdvance;
    u16 lastWorldEffectSequence;
    u16 reserved;
} OverworldActorRuntimeSlot;

typedef struct OverworldActorSystemState {
    u32 magic;
    u16 version;
    u16 size;
    u32 frame;
    u16 fieldEpoch;
    u16 actorCount;
    u16 queueHead;
    u16 queueCount;
    u16 ackWriteIndex;
    u16 lastReason;
    u32 lastAcknowledgedSequence;
    u16 compatibilityMapGeneration;
    u16 nextReservationId;
    u16 actorGenerations[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS];
    OverworldActorRuntimeSlot slots[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS];
    OverworldActorPolicyState policies[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS];
    OverworldActorCommand commands[OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY];
    OverworldActorReply acknowledgements[OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY];
    OverworldActorTraceHeader trace;
    OverworldActorTraceEvent events[OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY];
} OverworldActorSystemState;

extern OverworldActorSystemState gOverworldActorSystemState;
extern const OverworldActorSystemDebugLayout gOverworldActorSystemDebugLayout;
extern const OverworldActorResolverServiceEntry
    gOverworldActorSystemResolverServiceEntry;
extern const OverworldActorMotionServiceEntry
    gOverworldActorSystemMotionServiceEntry;
extern const OverworldActorPopulationServiceEntry
    gOverworldActorSystemPopulationServiceEntry;
extern const OverworldActorMovementPolicyServiceEntry
    gOverworldActorSystemMovementPolicyServiceEntry;

typedef char OverworldActorCompatibilityEntrySizeMustRemain32Bytes[
    sizeof(OverworldActorCompatibilityEntry) == 32 ? 1 : -1];
typedef char OverworldActorSystemDebugLayoutSizeMustRemain64Bytes[
    sizeof(OverworldActorSystemDebugLayout) == 64 ? 1 : -1];
typedef char OverworldActorReservedServiceEntrySizeMustRemain16Bytes[
    sizeof(OverworldActorReservedServiceEntry) == 16 ? 1 : -1];
typedef char OverworldActorResolverServiceEntrySizeMustRemain16Bytes[
    sizeof(OverworldActorResolverServiceEntry) == 16 ? 1 : -1];
typedef char OverworldActorMotionServiceEntrySizeMustRemain16Bytes[
    sizeof(OverworldActorMotionServiceEntry) == 16 ? 1 : -1];
typedef char OverworldActorPopulationServiceEntrySizeMustRemain16Bytes[
    sizeof(OverworldActorPopulationServiceEntry) == 16 ? 1 : -1];
typedef char OverworldActorMovementPolicyServiceEntrySizeMustRemain16Bytes[
    sizeof(OverworldActorMovementPolicyServiceEntry) == 16 ? 1 : -1];
typedef char OverworldActorMotionServiceCallSizeMustRemain44Bytes[
    sizeof(OverworldActorMotionServiceCall) == 44 ? 1 : -1];
typedef char OverworldActorBehaviorClassSelectionSizeMustRemain8Bytes[
    sizeof(BehaviorClassSelection) == 8 ? 1 : -1];
typedef char OverworldActorMotionIntentSizeMustRemain18Bytes[
    sizeof(OverworldMotionIntent) == 18 ? 1 : -1];
typedef char OverworldActorMotionCandidateSizeMustRemain16Bytes[
    sizeof(OverworldMotionCandidate) == 16 ? 1 : -1];
typedef char OverworldActorMotionPlanSizeMustRemain40Bytes[
    sizeof(OverworldMotionPlan) == 40 ? 1 : -1];
typedef char OverworldActorMotionStateSizeMustRemain52Bytes[
    sizeof(OverworldMotionState) == 52 ? 1 : -1];
typedef char OverworldActorMotionSampleSizeMustRemain36Bytes[
    sizeof(OverworldMotionSample) == 36 ? 1 : -1];
typedef char OverworldActorPolicyStateSizeMustRemain32Bytes[
    sizeof(OverworldActorPolicyState) == 32 ? 1 : -1];
typedef char OverworldActorRuntimeSlotSizeMustRemain148Bytes[
    sizeof(OverworldActorRuntimeSlot) == 148 ? 1 : -1];
typedef char OverworldActorSystemStateMustFitResidentBlock[
    sizeof(OverworldActorSystemState) <= 0xF00 ? 1 : -1];

#endif // OVERWORLD_ACTOR_SYSTEM_INTERNAL_H
