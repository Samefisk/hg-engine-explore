#ifndef OVERWORLD_ACTOR_SYSTEM_INTERNAL_H
#define OVERWORLD_ACTOR_SYSTEM_INTERNAL_H

#include "overworld_actor_system.h"
#include "overworld_actor_transition_model.h"
#include "overworld_behavior_resolver.h"
#include "overworld_motion_model.h"
#include "overworld_population_model.h"
#include "overworld_wild_movement.h"

void OverworldActor_PlayStompSound(u8 walkOptions);
BOOL OverworldActorPolicy_MountCommand(u8 operation, void *payload);

#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x78)
#define OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x88)
#define OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x98)
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0xA8)
#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY_ADDR 0x023BC834
#define OVERWORLD_ACTOR_SYSTEM_STATE_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x3670)
/* Supplemental debug metadata; checked against the compiled state layout. */
#define OVERWORLD_ACTOR_DEBUG_MAP_GENERATION_OFFSET 46
#define OVERWORLD_ACTOR_SYSTEM_RESOLVER_MAGIC 0x5250574F /* OWPR */
#define OVERWORLD_ACTOR_SYSTEM_MOTION_MAGIC 0x534D574F /* OWMS */
#define OVERWORLD_ACTOR_SYSTEM_POPULATION_MAGIC 0x5450574F /* OWPT */
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC 0x504D574F /* OWMP */
#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_MAGIC 0x5057574F /* OWWP */
#define OVERWORLD_ACTOR_SYSTEM_SERVICE_COUNT 4
#define OVERWORLD_ACTOR_RESOLVER_SERVICE_VERSION 2
#define OVERWORLD_ACTOR_MOTION_SERVICE_VERSION 6
#define OVERWORLD_ACTOR_POPULATION_SERVICE_VERSION 3
#define OVERWORLD_ACTOR_POPULATION_FRAME_CALL_VERSION 1
#define OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION 5
#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_VERSION 1
#define OVERWORLD_ACTOR_MOTION_CALL_VERSION 5

typedef enum OverworldActorLookPhase {
    OVERWORLD_ACTOR_LOOK_FIRST = 0,
    OVERWORLD_ACTOR_LOOK_SECOND,
    OVERWORLD_ACTOR_LOOK_RETURN,
} OverworldActorLookPhase;

struct FieldSystem;
struct LocalMapObject;
struct OverworldWildBehaviorProfile;
struct OverworldWildBehaviorProfileData;
struct OverworldWildSurfaceCatalog;
struct OverworldWildBehaviorPrimitives;
struct OverworldMountRuntimeState;

u8 OverworldActorSystem_SelectMovementLocomotion(
    const struct OverworldWildBehaviorPrimitives *primitives,
    u8 laneState);
u8 OverworldActorSystem_SelectMovementTarget(
    const struct OverworldWildBehaviorPrimitives *primitives,
    u8 laneState);

typedef OverworldActorResult (*OverworldActorCompatibilityBindFunc)(
    const OverworldActorStateSnapshot *initial,
    OverworldActorHandle *handle);
typedef OverworldActorResult (*OverworldActorCompatibilityUpdateFunc)(
    const OverworldActorHandle *handle,
    const OverworldActorStateSnapshot *state);
typedef OverworldActorResult (*OverworldActorCompatibilityUnbindFunc)(
    const OverworldActorHandle *handle,
    u16 reason);
typedef OverworldActorResult (*OverworldActorCompatibilityTransitionFunc)(
    OverworldActorTransitionCall *call);
typedef OverworldActorResult (*OverworldActorCompatibilityRecordTraceFunc)(
    const OverworldActorHandle *handle,
    u16 event,
    u16 reason,
    u32 valueA,
    u32 valueB);
/* One pointer-free context read. The low half is the field epoch and the high
 * half is the Actor-owned map generation. */
typedef u32 OverworldActorFieldContext;
#define OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(value) ((u16)(value))
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(value) \
    ((u16)((value) >> 16))
typedef OverworldActorFieldContext (*OverworldActorCompatibilityGetContextFunc)(
    void);

typedef struct OverworldActorCompatibilityEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorCompatibilityBindFunc bind;
    OverworldActorCompatibilityUpdateFunc update;
    OverworldActorCompatibilityUnbindFunc unbind;
    OverworldActorCompatibilityTransitionFunc transition;
    OverworldActorCompatibilityRecordTraceFunc recordTrace;
    OverworldActorCompatibilityGetContextFunc getContext;
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
    OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST = 9,
    OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY = 10,
    OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP = 11,
    OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT = 12,
} OverworldActorMotionServiceOperation;

typedef enum OverworldActorHopPlanOperation {
    OVERWORLD_ACTOR_HOP_PLAN_VECTOR = 0,
    OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY = 1,
    OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY = 2,
} OverworldActorHopPlanOperation;

#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY (1u << 0)

/*
 * One caller-owned planning value crosses the Actor Motion request seam.
 * Engine adapters provide the resolved profile and read-only world-query
 * context; Actor Motion alone interprets Hop direction, range, duration, arc,
 * and clearance.
 */
typedef struct OverworldActorHopPlanCall {
    const struct OverworldWildBehaviorProfile *profile;
    const struct OverworldWildBehaviorProfileData *lane;
    struct FieldSystem *fieldSystem;
    const struct OverworldWildSurfaceCatalog *surfaceCatalog;
    struct LocalMapObject *object;
    s32 startBaseY;
    s32 targetBaseY;
    s16 startX;
    s16 startY;
    s16 targetX;
    s16 targetY;
    s16 deltaX;
    s16 deltaY;
    /* Output: arc height in the high half, duration in the low half.
     * FLAT_TRAJECTORY also takes its authored duration in the low half on
     * input. Flat clearance uses geometric edge fractions, not Hop timing;
     * it never adds an arc or lifts over an intervening raised surface. */
    u32 trajectory;
    u8 operation;
    /* VECTOR stores the spot state here. Trajectory planning stores the
     * OVERWORLD_ACTOR_HOP_PLAN_FLAG_* bits instead. The name remains stable
     * for the fixed 48-byte service ABI. */
    u8 spotState;
    u8 direction;
    u8 distance;
} OverworldActorHopPlanCall;

OverworldMotionDecision OverworldActorHopPlanner_Plan(
    OverworldActorHopPlanCall *call);

typedef enum OverworldActorTeleportTargetMode {
    OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT = 0,
    OVERWORLD_ACTOR_TELEPORT_TARGET_DIRECTIONAL = 1,
    OVERWORLD_ACTOR_TELEPORT_TARGET_CHILL = 2,
} OverworldActorTeleportTargetMode;

#define OVERWORLD_ACTOR_TELEPORT_FLAG_RESERVED_STOPS_SEARCH (1u << 0)

typedef struct OverworldActorTeleportCandidate {
    s16 targetX;
    s16 targetY;
    s32 targetBaseY;
    u16 rejectionFlags;
    u8 direction;
    u8 distance;
    u8 targetFacing;
    u16 targetSurfaceId;
} OverworldActorTeleportCandidate;

typedef void (*OverworldActorTeleportClassifyFunc)(
    void *world,
    OverworldActorTeleportCandidate *candidate);

/*
 * Teleport candidate order, timing, and immutable-plan construction are
 * deterministic Motion policy. The adapter supplies one read-only world
 * classifier; it does not enumerate or accept candidates itself.
 */
typedef struct OverworldActorTeleportPlanCall {
    const struct OverworldWildBehaviorProfileData *lane;
    const u8 *directions;
    OverworldActorTeleportClassifyFunc classify;
    void *world;
    u32 directionRandom;
    u32 distanceRandom;
    s16 desiredX;
    s16 desiredY;
    u8 targetMode;
    u8 directionCount;
    u8 pathAdvancePolicy;
    u8 flags;
} OverworldActorTeleportPlanCall;

/*
 * Engine adapters acknowledge work at this seam. Path advances remain pending
 * until the adapter confirms both the engine update and terrain streaming.
 * A terminal commit additionally requires the final presentation sample and
 * the real engine movement-END boundary.
 */
#define OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED        (1u << 0)
#define OVERWORLD_ACTOR_BOUNDARY_STREAM_READY        (1u << 1)
#define OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED (1u << 2)
#define OVERWORLD_ACTOR_BOUNDARY_ENGINE_END          (1u << 3)
#define OVERWORLD_ACTOR_BOUNDARY_SUSPEND              (1u << 4)
#define OVERWORLD_ACTOR_BOUNDARY_REBIND_FIELD         (1u << 5)
#define OVERWORLD_ACTOR_BOUNDARY_CANCEL               (1u << 6)
#define OVERWORLD_ACTOR_BOUNDARY_RESUME               (1u << 7)

#define OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS        \
    (OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED             \
        | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY        \
        | OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED \
        | OVERWORLD_ACTOR_BOUNDARY_ENGINE_END)

typedef char OverworldActorRequiredBoundaryAcksMustRemainExact[
    OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS
            == (OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY
                | OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_ENGINE_END)
        ? 1
        : -1];

typedef struct OverworldActorMotionBoundaryCall {
    u16 version;
    u16 size;
    u8 operation;
    u8 acknowledgements;
    u8 cancelReason;
    u8 phase;
    u8 actorSlot;
    u8 reserved;
    u16 fieldEpoch;
    u16 acknowledgedPathAdvance;
    /* Reservation returned by the accepted start. A delayed engine receipt
     * must carry this exact per-motion identity. */
    u16 motionIdentity;
    u16 pendingLastPathAdvance;
    u16 decision;
    u16 tickFlags;
    OverworldMotionSample *sample;
    /* Walk supplies its terminal policy transaction at the same engine
     * boundary that publishes the logical commit. Other motion kinds leave
     * this null. The result is returned in the caller-owned value object. */
    OverworldActorWalkPolicyCall *walkPolicy;
} OverworldActorMotionBoundaryCall;

typedef struct OverworldActorMotionRequestCall {
    u16 version;
    u16 size;
    u8 operation;
    u8 candidateCount;
    u8 reservedReason;
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
    union {
        OverworldActorHopPlanCall *hopPlan;
        OverworldActorTeleportPlanCall *teleportPlan;
    };
    u16 targetSurfaceId;
    /* Output only: zero until Begin accepts, then the plan reservation ID. */
    u16 motionIdentity;
    u16 decision;
    u16 tickFlags;
} OverworldActorMotionRequestCall;

OverworldMotionDecision OverworldActorTeleportPlanner_Plan(
    OverworldActorMotionRequestCall *call);

typedef OverworldActorResult (*OverworldActorMotionRequestFunc)(
    OverworldActorMotionRequestCall *call);
typedef OverworldActorResult (*OverworldActorMotionBoundaryFunc)(
    OverworldActorMotionBoundaryCall *call);

typedef struct OverworldActorMotionServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorMotionRequestFunc request;
    OverworldActorMotionBoundaryFunc boundary;
} OverworldActorMotionServiceEntry;

typedef enum OverworldActorPopulationFrameFlags {
    OVERWORLD_ACTOR_POPULATION_FRAME_TIMER_ELIGIBLE = 1 << 0,
} OverworldActorPopulationFrameFlags;

typedef enum OverworldActorPopulationFrameResultFlags {
    OVERWORLD_ACTOR_POPULATION_FRAME_REFILL_DUE = 1 << 0,
} OverworldActorPopulationFrameResultFlags;

/* Wild owns the opaque source and resident refill flags. Actor consumes only
 * the timer decision and returns only the resulting refill decision. */
typedef struct OverworldActorPopulationFrameCall {
    u16 version;
    u16 size;
    struct FieldSystem *fieldSystem;
    void *actorSource;
    u16 flags;
    u16 resultFlags;
} OverworldActorPopulationFrameCall;

typedef OverworldActorFrameResult (*OverworldActorPopulationFrameFunc)(
    OverworldActorPopulationFrameCall *call);

typedef enum OverworldActorPopulationControlOperation {
    OVERWORLD_ACTOR_POPULATION_CONTROL_RESET = 0,
    OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL,
    OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE,
    OVERWORLD_ACTOR_POPULATION_CONTROL_CANCEL_MAINTENANCE,
    OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE,
    OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE,
} OverworldActorPopulationControlOperation;

typedef enum OverworldActorPopulationWork {
    OVERWORLD_ACTOR_POPULATION_WORK_NONE = 0,
    OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN,
    OVERWORLD_ACTOR_POPULATION_WORK_REFILL,
    OVERWORLD_ACTOR_POPULATION_WORK_REVEAL,
} OverworldActorPopulationWork;

typedef u8 (*OverworldActorPopulationControlFunc)(
    u8 operation,
    u16 refillDelay);

typedef struct OverworldActorPopulationServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorPopulationFrameFunc frame;
    OverworldActorPopulationControlFunc control;
} OverworldActorPopulationServiceEntry;

typedef BOOL (*OverworldActorMovementPolicyValidateFunc)(void);
typedef struct OverworldActorPolicyState OverworldActorPolicyState;
typedef BOOL (*OverworldActorMountedWalkFinishFunc)(
    const struct OverworldMountRuntimeState *state,
    BOOL started,
    BOOL crashOnBlocked,
    OverworldActorWalkPolicyCall *output);
typedef BOOL (*OverworldActorWalkTerminalBoundaryFunc)(
    OverworldActorWalkPolicyCall *walkPolicy,
    u8 acknowledgements,
    u16 acknowledgedPathAdvance,
    u16 motionIdentity);

typedef struct OverworldActorWalkPolicyOwnerEntry {
    u32 magic;
    u16 version;
    u16 size;
    BOOL (*reduceWalk)(
        OverworldActorPolicyState *policy,
        OverworldActorStateSnapshot *actor,
        OverworldActorWalkPolicyCall *call);
} OverworldActorWalkPolicyOwnerEntry;

typedef char OverworldActorWalkPolicyOwnerEntrySizeMustRemain12Bytes[
    sizeof(OverworldActorWalkPolicyOwnerEntry) == 12 ? 1 : -1];

#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY \
    ((const OverworldActorWalkPolicyOwnerEntry *) \
        OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY_ADDR)

#define OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX 3

/* The first four fields retain the legacy policy-entry ABI. Fixed-address
 * thunks can continue to load reduceWalk at byte offset 12. The actor-only
 * terminal Walk and mounted START_RESULT callbacks follow that prefix. The
 * terminal callback is a compact adapter into the motion boundary; it does
 * not reduce or commit Walk outside ActorSystem_EngineBoundary. */
typedef struct OverworldActorMovementPolicyEntry {
    OverworldWildMovementPolicyBuildLookPlanFunc buildLookPlan;
    OverworldWildMovementPolicyResolveLookFunc resolveLook;
    OverworldWildMovementPolicyChooseWanderDirectionFunc chooseWanderDirection;
    OverworldActorWalkPolicyReduceFunc reduceWalk;
    OverworldActorWalkTerminalBoundaryFunc terminalWalk;
    OverworldActorMountedWalkFinishFunc finishMountedWalk;
} OverworldActorMovementPolicyEntry;

typedef char OverworldActorMovementPolicyEntrySizeMustRemain24Bytes[
    sizeof(OverworldActorMovementPolicyEntry) == 24 ? 1 : -1];

struct OverworldActorPolicyState {
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
    u8 lastWalkTime;
    u16 pendingFirstPathAdvance;
    u16 pendingLastPathAdvance;
    u16 targetSurfaceId;
};

typedef char OverworldActorPolicyStateSizeMustRemain32[
    sizeof(OverworldActorPolicyState) == 32 ? 1 : -1];
typedef char OverworldActorPolicyWalkOffsetMustRemain0[
    offsetof(OverworldActorPolicyState, walkMomentum) == 0 ? 1 : -1];
typedef char OverworldActorPolicyDirectionOffsetMustRemain0[
    offsetof(OverworldActorPolicyState, walkMomentum)
            + offsetof(OverworldWildWalkMomentumState, direction)
        == 0 ? 1 : -1];
typedef char OverworldActorPolicySpeedOffsetMustRemain2[
    offsetof(OverworldActorPolicyState, walkMomentum)
            + offsetof(OverworldWildWalkMomentumState, speed)
        == 2 ? 1 : -1];
typedef char OverworldActorPolicyBaseOffsetMustRemain3[
    offsetof(OverworldActorPolicyState, walkMomentum)
            + offsetof(OverworldWildWalkMomentumState, baseSpeed)
        == 3 ? 1 : -1];
typedef char OverworldActorPolicyBufferedOffsetMustRemain20[
    offsetof(OverworldActorPolicyState, bufferedDirection) == 20 ? 1 : -1];
typedef char OverworldActorPolicyPendingOffsetMustRemain22[
    offsetof(OverworldActorPolicyState, pendingStep) == 22 ? 1 : -1];
typedef char OverworldActorPolicyPendingSkidOffsetMustRemain23[
    offsetof(OverworldActorPolicyState, pendingSkid) == 23 ? 1 : -1];
typedef char OverworldActorPolicyStreamOffsetMustRemain24[
    offsetof(OverworldActorPolicyState, streamState) == 24 ? 1 : -1];
typedef char OverworldActorPolicyLastWalkTimeOffsetMustRemain25[
    offsetof(OverworldActorPolicyState, lastWalkTime) == 25 ? 1 : -1];
typedef char OverworldActorPolicyPendingFirstPathOffsetMustRemain26[
    offsetof(OverworldActorPolicyState, pendingFirstPathAdvance) == 26 ? 1 : -1];
typedef char OverworldActorPolicyPendingLastPathOffsetMustRemain28[
    offsetof(OverworldActorPolicyState, pendingLastPathAdvance) == 28 ? 1 : -1];

typedef struct OverworldActorMovementPolicyServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    const OverworldActorMovementPolicyEntry *policy;
    const struct OverworldBehaviorConditionAdapterEntry *conditionAdapter;
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

static inline BOOL OverworldActorPolicy_Inspect(
    u8 actorSlot,
    OverworldActorPolicyView *view)
{
    OverworldActorWalkPolicyCall call;

    call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call.size = sizeof(call);
    call.policyView = view;
    call.actorSlot = actorSlot;
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_INSPECT;
    return OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
        ->reduceWalk(&call);
}

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
    u16 actorStride;
} OverworldActorSystemDebugLayout;

#define OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT \
    ((const OverworldActorSystemDebugLayout *) \
        OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT_ADDR)

typedef struct OverworldActorRuntimeSlot {
    OverworldActorStateSnapshot snapshot;
    OverworldMotionState motion;
    OverworldActorPolicyState policy;
} OverworldActorRuntimeSlot;

typedef struct OverworldActorSystemState {
    u32 magic;
    u16 version;
    u16 size;
    u32 frame;
    u16 fieldEpoch;
    u8 actorCount;
    u8 queueHead;
    u8 queueCount;
    u8 ackWriteIndex;
    u16 lastReason;
    u32 lastAcknowledgedSequence;
    OverworldActorTransitionState transition;
    u16 nextReservationId;
    /* This occupies the former alignment pad; state size and later offsets do
     * not move. Actor alone advances it with the field transition. */
    u16 mapGeneration;
    OverworldPopulationState population;
    OverworldActorRuntimeSlot slots[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS];
    OverworldActorCommand commands[OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY];
    OverworldActorReply acknowledgements[OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY];
    OverworldActorTraceHeader trace;
    OverworldActorTraceEvent events[OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY];
} OverworldActorSystemState;

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
typedef char OverworldActorMotionRequestCallSizeMustRemain44Bytes[
    sizeof(OverworldActorMotionRequestCall) == 44 ? 1 : -1];
typedef char OverworldActorMotionRequestTargetSurfaceOffsetMustRemain36[
    offsetof(OverworldActorMotionRequestCall, targetSurfaceId) == 36 ? 1 : -1];
typedef char OverworldActorHopPlanCallSizeMustRemain48Bytes[
    sizeof(OverworldActorHopPlanCall) == 48 ? 1 : -1];
typedef char OverworldActorTeleportCandidateSizeMustRemain16Bytes[
    sizeof(OverworldActorTeleportCandidate) == 16 ? 1 : -1];
typedef char OverworldActorTeleportPlanCallSizeMustRemain32Bytes[
    sizeof(OverworldActorTeleportPlanCall) == 32 ? 1 : -1];
typedef char OverworldActorMotionBoundaryCallSizeMustRemain32Bytes[
    sizeof(OverworldActorMotionBoundaryCall) == 32 ? 1 : -1];
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
typedef char OverworldActorPolicyTargetSurfaceOffsetMustRemain30[
    offsetof(OverworldActorPolicyState, targetSurfaceId) == 30 ? 1 : -1];
typedef char OverworldActorRuntimeSlotSizeMustRemain172Bytes[
    sizeof(OverworldActorRuntimeSlot) == 172 ? 1 : -1];
typedef char OverworldActorSystemStateMustFitResidentBlock[
    sizeof(OverworldActorSystemState) <= 0xF00 ? 1 : -1];

#endif // OVERWORLD_ACTOR_SYSTEM_INTERNAL_H
