#ifndef OVERWORLD_ACTOR_SYSTEM_H
#define OVERWORLD_ACTOR_SYSTEM_H

#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
#include <stddef.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int16_t s16;
typedef int32_t s32;
#else
#include "types.h"
#endif

#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_ID 158
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_LOAD_ADDR 0x023B6500
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE 0x023B6B00
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_END 0x023BAB00
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_SIZE 0x4600
#define OVERWORLD_ACTOR_SYSTEM_ENTRY_ADDR OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x18)
#define OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT_ADDR \
    (OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x38)

#define OVERWORLD_ACTOR_SYSTEM_MAGIC 0x5341574F /* OWAS */
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_MAGIC 0x4341574F /* OWAC */
#define OVERWORLD_ACTOR_SYSTEM_DEBUG_MAGIC 0x4C44574F /* OWDL */
#define OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC 0x5353574F /* OWSS */
#define OVERWORLD_ACTOR_TRACE_MAGIC 0x5254574F /* OWTR */
#define OVERWORLD_ACTOR_SYSTEM_ABI_VERSION 1
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_VERSION 3
#define OVERWORLD_ACTOR_SYSTEM_DEBUG_VERSION 1
#define OVERWORLD_ACTOR_TRANSITION_CALL_VERSION 2
#define OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS 10
#define OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT 7
#define OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY 2
#define OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY 2
#define OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY 16
#define OVERWORLD_ACTOR_INVALID_SLOT 0xFFFF
#define OVERWORLD_ACTOR_TRACE_ALL_SLOTS 0xFFFF

typedef enum OverworldActorResult {
    OVERWORLD_ACTOR_RESULT_OK = 0,
    OVERWORLD_ACTOR_RESULT_RETRY = 1,
    OVERWORLD_ACTOR_RESULT_REJECTED = 2,
    OVERWORLD_ACTOR_RESULT_ERROR = 3,
} OverworldActorResult;

typedef enum OverworldActorFrameResult {
    OVERWORLD_ACTOR_FRAME_OK = 0,
    OVERWORLD_ACTOR_FRAME_PENDING = 1,
    OVERWORLD_ACTOR_FRAME_CONTEXT_LOST = 2,
    OVERWORLD_ACTOR_FRAME_INVALID = 3,
} OverworldActorFrameResult;

typedef enum OverworldActorReason {
    OVERWORLD_ACTOR_REASON_OK = 0,
    OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY = 1,
    OVERWORLD_ACTOR_REASON_REJECTED_BLOCKED = 2,
    OVERWORLD_ACTOR_REASON_REJECTED_SIDE_TILE = 3,
    OVERWORLD_ACTOR_REASON_REJECTED_TERRAIN = 4,
    OVERWORLD_ACTOR_REASON_REJECTED_OCCUPIED = 5,
    OVERWORLD_ACTOR_REASON_REJECTED_RESERVED = 6,
    OVERWORLD_ACTOR_REASON_REJECTED_DIRECTION = 7,
    OVERWORLD_ACTOR_REASON_REJECTED_PROFILE = 8,
    OVERWORLD_ACTOR_REASON_UNSUPPORTED_LOCOMOTION = 9,
    OVERWORLD_ACTOR_REASON_MOTION_ALREADY_ACTIVE = 10,
    OVERWORLD_ACTOR_REASON_STALE_ACTOR = 11,
    OVERWORLD_ACTOR_REASON_STALE_FIELD = 12,
    OVERWORLD_ACTOR_REASON_PRESENTATION_MISSING = 13,
    OVERWORLD_ACTOR_REASON_DATA_UNAVAILABLE = 14,
    OVERWORLD_ACTOR_REASON_NO_MEMORY = 15,
    OVERWORLD_ACTOR_REASON_CONTEXT_LOST = 16,
    OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT = 17,
    OVERWORLD_ACTOR_REASON_QUEUE_FULL = 18,
    OVERWORLD_ACTOR_REASON_UNSUPPORTED_COMMAND = 19,
    OVERWORLD_ACTOR_REASON_STALE_SEQUENCE = 20,
} OverworldActorReason;

typedef enum OverworldActorTransitionDisposition {
    OVERWORLD_ACTOR_TRANSITION_DISPOSITION_NONE = 0,
    OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE = 1,
    OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD = 2,
} OverworldActorTransitionDisposition;

typedef enum OverworldActorTransitionWork {
    OVERWORLD_ACTOR_TRANSITION_WORK_NONE = 0,
    OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE = 1,
    OVERWORLD_ACTOR_TRANSITION_WORK_REBIND = 2,
    OVERWORLD_ACTOR_TRANSITION_WORK_RESUME = 3,
    OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD = 4,
    OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE = 5,
} OverworldActorTransitionWork;

#define OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED (1u << 0)
#define OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND (1u << 1)
#define OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED             (1u << 2)
#define OVERWORLD_ACTOR_TRANSITION_ACK_ALL                   \
    (OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED     \
        | OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND \
        | OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED)

typedef enum OverworldActorRole {
    OVERWORLD_ACTOR_ROLE_NONE = 0,
    OVERWORLD_ACTOR_ROLE_WILD = 1,
    OVERWORLD_ACTOR_ROLE_FOLLOWER = 2,
    OVERWORLD_ACTOR_ROLE_MOUNTED = 3,
    OVERWORLD_ACTOR_ROLE_SCRIPTED = 4,
} OverworldActorRole;

typedef enum OverworldActorMotionKind {
    OVERWORLD_ACTOR_MOTION_NONE = 0,
    OVERWORLD_ACTOR_MOTION_WALK = 1,
    OVERWORLD_ACTOR_MOTION_HOP = 2,
    OVERWORLD_ACTOR_MOTION_TELEPORT = 3,
    OVERWORLD_ACTOR_MOTION_SKID = 4,
    OVERWORLD_ACTOR_MOTION_REPOSITION = 5,
} OverworldActorMotionKind;

typedef enum OverworldActorMotionPhase {
    OVERWORLD_ACTOR_PHASE_IDLE = 0,
    OVERWORLD_ACTOR_PHASE_PLANNED = 1,
    OVERWORLD_ACTOR_PHASE_MOVING = 2,
    OVERWORLD_ACTOR_PHASE_COMMIT_PENDING = 3,
    OVERWORLD_ACTOR_PHASE_SETTLING = 4,
    OVERWORLD_ACTOR_PHASE_SUSPENDED = 5,
    OVERWORLD_ACTOR_PHASE_CANCELED = 6,
} OverworldActorMotionPhase;

typedef enum OverworldActorStreamState {
    OVERWORLD_ACTOR_STREAM_IDLE = 0,
    OVERWORLD_ACTOR_STREAM_WAITING = 1,
    OVERWORLD_ACTOR_STREAM_ADVANCED = 2,
} OverworldActorStreamState;

typedef enum OverworldActorWorldEffect {
    OVERWORLD_ACTOR_WORLD_EFFECT_NONE = 0,
    OVERWORLD_ACTOR_WORLD_EFFECT_STOMP = 1,
    OVERWORLD_ACTOR_WORLD_EFFECT_SKID_DUST = 2,
    OVERWORLD_ACTOR_WORLD_EFFECT_CRASH = 3,
} OverworldActorWorldEffect;

typedef enum OverworldActorWorldGate {
    OVERWORLD_ACTOR_WORLD_GATE_WARP = 0,
    OVERWORLD_ACTOR_WORLD_GATE_BATTLE = 1,
} OverworldActorWorldGate;

typedef enum OverworldActorEvent {
    OVERWORLD_ACTOR_EVENT_NONE = 0,
    OVERWORLD_ACTOR_EVENT_ACTOR_ATTACHED = 1,
    OVERWORLD_ACTOR_EVENT_ACTOR_DETACHED = 2,
    OVERWORLD_ACTOR_EVENT_CONTROL_REBOUND = 3,
    OVERWORLD_ACTOR_EVENT_PROFILE_RESOLVED = 4,
    OVERWORLD_ACTOR_EVENT_LANE_CHANGED = 5,
    OVERWORLD_ACTOR_EVENT_INTENT_CREATED = 6,
    OVERWORLD_ACTOR_EVENT_CANDIDATE_REJECTED = 7,
    OVERWORLD_ACTOR_EVENT_PLAN_ACCEPTED = 8,
    OVERWORLD_ACTOR_EVENT_MOTION_STARTED = 9,
    OVERWORLD_ACTOR_EVENT_STREAM_WAITING = 10,
    OVERWORLD_ACTOR_EVENT_STREAM_ADVANCED = 11,
    OVERWORLD_ACTOR_EVENT_PATH_ADVANCED = 12,
    OVERWORLD_ACTOR_EVENT_LOGICAL_COMMIT = 13,
    OVERWORLD_ACTOR_EVENT_WORLD_EFFECT = 14,
    OVERWORLD_ACTOR_EVENT_PRESENTATION_SYNCED = 15,
    OVERWORLD_ACTOR_EVENT_MOTION_FINISHED = 16,
    OVERWORLD_ACTOR_EVENT_MOTION_CANCELED = 17,
    OVERWORLD_ACTOR_EVENT_CONTEXT_CHANGED = 18,
    OVERWORLD_ACTOR_EVENT_ACTOR_REBOUND = 19,
    OVERWORLD_ACTOR_EVENT_CONTROL_RETURNED = 20,
    OVERWORLD_ACTOR_EVENT_MOUNT_PRESENTATION_POSITION = 21,
    OVERWORLD_ACTOR_EVENT_MOUNT_PRESENTATION_STATE = 22,
    OVERWORLD_ACTOR_EVENT_CONDITION_EVALUATED = 23,
    OVERWORLD_ACTOR_EVENT_CONDITION_TIMERS = 24,
    OVERWORLD_ACTOR_EVENT_CONDITION_TARGET = 25,
    OVERWORLD_ACTOR_EVENT_CONDITIONAL_RESOLVED = 26,
} OverworldActorEvent;

typedef enum OverworldActorCommandKind {
    OVERWORLD_ACTOR_COMMAND_NONE = 0,
    OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION = 1,
    OVERWORLD_ACTOR_COMMAND_DETACH = 2,
    OVERWORLD_ACTOR_COMMAND_REBIND_ROLE = 3,
    OVERWORLD_ACTOR_COMMAND_TRACE_CONFIGURE = 4,
    OVERWORLD_ACTOR_COMMAND_TRACE_CLEAR = 5,
} OverworldActorCommandKind;

typedef enum OverworldActorInspectKind {
    OVERWORLD_ACTOR_INSPECT_SYSTEM = 0,
    OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE = 1,
    OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX = 2,
    OVERWORLD_ACTOR_INSPECT_TRACE_HEADER = 3,
    OVERWORLD_ACTOR_INSPECT_TRACE_EVENT = 4,
    OVERWORLD_ACTOR_INSPECT_POPULATION = 5,
    OVERWORLD_ACTOR_INSPECT_WORLD_GATE = 6,
} OverworldActorInspectKind;

typedef struct OverworldActorHandle {
    u16 slot;
    u16 generation;
    u16 fieldEpoch;
    u16 mapGeneration;
    u16 encounterGeneration;
    u16 reserved;
} OverworldActorHandle;

/* Agent-facing binary layouts. The debug descriptor generator reads these
 * exact formats from the public ABI header instead of owning a second copy. */
#define OVERWORLD_ACTOR_DEBUG_HANDLE_FORMAT "<6H"
#define OVERWORLD_ACTOR_DEBUG_STATE_FORMAT "<HH6H8I8h4H16B"

/*
 * One idempotent field-transition exchange. Callers begin with no
 * acknowledgements, execute the returned work, then repeat the same sequence
 * with cumulative acknowledgement bits. The actor system is the only owner of
 * field-epoch and map-generation advancement.
 */
typedef struct OverworldActorTransitionCall {
    u16 version;
    u16 size;
    u32 sequence;
    __extension__ union {
        __extension__ struct {
            u16 previousMapId;
            u16 currentMapId;
        };
        u32 mapIdentity;
    };
    __extension__ union {
        __extension__ struct {
            u16 expectedFieldEpoch;
            u16 previousMapGeneration;
        };
        u32 previousFieldContext;
    };
    u8 disposition;
    u8 acknowledgements;
    u8 work;
    u8 reserved;
    u16 nextFieldEpoch;
    u16 nextMapGeneration;
    u16 retainedActorMask;
    u16 resumeMotionMask;
    u16 discardActorMask;
    u16 reason;
} OverworldActorTransitionCall;

typedef struct OverworldActorCommand {
    u16 version;
    u16 size;
    u32 sequence;
    /* TRACE_CONFIGURE uses INVALID_SLOT to trace all actors. */
    OverworldActorHandle actor;
    u16 expectedFieldEpoch;
    u8 kind;
    u8 role;
    u32 valueA;
    u32 valueB;
} OverworldActorCommand;

typedef struct OverworldActorReply {
    u16 version;
    u16 size;
    u32 sequence;
    u16 result;
    u16 reason;
    OverworldActorHandle actor;
} OverworldActorReply;

typedef struct OverworldActorFrame {
    u16 version;
    u16 size;
    u32 frame;
    u16 expectedFieldEpoch;
    u16 flags;
} OverworldActorFrame;

enum {
    OVERWORLD_ACTOR_PRESENTATION_ACTIVE = 1 << 0,
    OVERWORLD_ACTOR_PRESENTATION_VISIBLE = 1 << 1,
    OVERWORLD_ACTOR_PRESENTATION_CURRENT_MANAGER = 1 << 2,
    OVERWORLD_ACTOR_PRESENTATION_READY =
        OVERWORLD_ACTOR_PRESENTATION_ACTIVE
        | OVERWORLD_ACTOR_PRESENTATION_VISIBLE
        | OVERWORLD_ACTOR_PRESENTATION_CURRENT_MANAGER,
};

typedef struct OverworldActorStateSnapshot {
    u16 version;
    u16 size;
    OverworldActorHandle handle;
    u32 subjectIdentity;
    u32 behaviorFingerprint;
    u32 matchedLayerMask;
    u32 lastCommandSequence;
    u32 commitSequence;
    u32 authorityGeneration;
    u32 engineAnchorGeneration;
    u32 presentationGeneration;
    s16 logicalX;
    s16 logicalY;
    s16 renderX;
    s16 renderY;
    s16 originX;
    s16 originY;
    s16 targetX;
    s16 targetY;
    u16 motionElapsed;
    u16 motionDuration;
    u16 reservationId;
    u16 species;
    u8 form;
    u8 level;
    u8 role;
    u8 lane;
    u8 motionKind;
    u8 motionPhase;
    u8 inputOwnership;
    u8 streamState;
    u8 controllerState;
    u8 lastIntent;
    u8 lastDecision;
    u8 lastCancelReason;
    u8 active;
    u8 presentationAttached;
    u8 presentationState;
    u8 reserved1;
} OverworldActorStateSnapshot;

typedef struct OverworldActorTraceHeader {
    u32 magic;
    u16 version;
    u16 size;
    u32 oldestSequence;
    u32 nextSequence;
    u32 overwrittenEvents;
    u32 filterEventMask;
    u16 fieldEpoch;
    u16 filterActorSlot;
    u16 filterActorGeneration;
    u16 filterFramesRemaining;
    u8 writeIndex;
    u8 count;
    u8 armed;
    u8 reserved;
} OverworldActorTraceHeader;

typedef struct OverworldActorTraceEvent {
    u32 sequence;
    u32 frame;
    OverworldActorHandle actor;
    u16 event;
    u16 reason;
    u32 valueA;
    u32 valueB;
} OverworldActorTraceEvent;

typedef struct OverworldActorPopulationSnapshot {
    u16 version;
    u16 size;
    u32 lastWorldEventSequence;
    s16 centerX;
    s16 centerY;
    u16 fieldEpoch;
    u16 refillTimer;
    u8 refillArmed;
    u8 workPending;
    u8 fieldActive;
    u8 reserved0;
    u32 reserved1[3];
} OverworldActorPopulationSnapshot;

typedef struct OverworldActorQuery {
    u16 version;
    u16 size;
    u8 kind;
    u8 index;
    u16 reserved;
    OverworldActorHandle actor;
    u32 sequence;
} OverworldActorQuery;

typedef struct OverworldActorSnapshot {
    u16 version;
    u16 size;
    u8 kind;
    u8 hasActor;
    u8 hasTraceEvent;
    u8 hasPopulation;
    u32 frame;
    u16 fieldEpoch;
    u16 actorCount;
    u16 queueDepth;
    u16 lastReason;
    OverworldActorStateSnapshot actor;
    OverworldActorTraceHeader trace;
    __extension__ union {
        OverworldActorTraceEvent traceEvent;
        OverworldActorPopulationSnapshot population;
    };
} OverworldActorSnapshot;

typedef OverworldActorResult (*OverworldActorSystemValidateFunc)(void);
typedef OverworldActorResult (*OverworldActorSystemApplyFunc)(
    const OverworldActorCommand *command,
    OverworldActorReply *reply);
typedef OverworldActorFrameResult (*OverworldActorSystemTickFunc)(
    const OverworldActorFrame *frame);
typedef OverworldActorResult (*OverworldActorSystemInspectFunc)(
    const OverworldActorQuery *query,
    OverworldActorSnapshot *snapshot);

typedef struct OverworldActorSystemEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldActorSystemValidateFunc validate;
    OverworldActorSystemApplyFunc apply;
    OverworldActorSystemTickFunc tick;
    OverworldActorSystemInspectFunc inspect;
} OverworldActorSystemEntry;

#define OVERWORLD_ACTOR_SYSTEM_ENTRY \
    ((const OverworldActorSystemEntry *)OVERWORLD_ACTOR_SYSTEM_ENTRY_ADDR)

typedef char OverworldActorHandleSizeMustRemain12Bytes[
    sizeof(OverworldActorHandle) == 12 ? 1 : -1];
typedef char OverworldActorTransitionCallSizeMustRemain32Bytes[
    sizeof(OverworldActorTransitionCall) == 32 ? 1 : -1];
typedef char OverworldActorTransitionMapIdentityOffsetMustRemain8[
    offsetof(OverworldActorTransitionCall, mapIdentity) == 8 ? 1 : -1];
typedef char OverworldActorTransitionFieldContextOffsetMustRemain12[
    offsetof(OverworldActorTransitionCall, previousFieldContext) == 12
        ? 1
        : -1];
typedef char OverworldActorCommandSizeMustRemain32Bytes[
    sizeof(OverworldActorCommand) == 32 ? 1 : -1];
typedef char OverworldActorReplySizeMustRemain24Bytes[
    sizeof(OverworldActorReply) == 24 ? 1 : -1];
typedef char OverworldActorFrameSizeMustRemain12Bytes[
    sizeof(OverworldActorFrame) == 12 ? 1 : -1];
typedef char OverworldActorStateSnapshotSizeMustRemain88Bytes[
    sizeof(OverworldActorStateSnapshot) == 88 ? 1 : -1];
/* The host probe decodes this public value object from raw emulator memory.
 * Lock every decoded field boundary, not only the total size, so a same-size
 * C reorder cannot silently turn valid bytes into false semantic evidence. */
#define OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(name, field, expected) \
    typedef char name[offsetof(OverworldActorStateSnapshot, field) \
        == (expected) ? 1 : -1]
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateVersionOffsetMustRemain0, version, 0);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateHandleOffsetMustRemain4, handle, 4);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateSubjectOffsetMustRemain16, subjectIdentity, 16);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateFingerprintOffsetMustRemain20, behaviorFingerprint, 20);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateMatchedMaskOffsetMustRemain24, matchedLayerMask, 24);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateLastCommandOffsetMustRemain28, lastCommandSequence, 28);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateCommitOffsetMustRemain32, commitSequence, 32);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateAuthorityOffsetMustRemain36, authorityGeneration, 36);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateAnchorOffsetMustRemain40, engineAnchorGeneration, 40);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStatePresentationOffsetMustRemain44, presentationGeneration, 44);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateLogicalXOffsetMustRemain48, logicalX, 48);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateRenderXOffsetMustRemain52, renderX, 52);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateOriginXOffsetMustRemain56, originX, 56);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateTargetXOffsetMustRemain60, targetX, 60);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateMotionElapsedOffsetMustRemain64, motionElapsed, 64);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStatePresentationStateOffsetMustRemain86,
    presentationState, 86);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateReservationOffsetMustRemain68, reservationId, 68);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateSpeciesOffsetMustRemain70, species, 70);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateFormOffsetMustRemain72, form, 72);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateRoleOffsetMustRemain74, role, 74);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateMotionKindOffsetMustRemain76, motionKind, 76);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateInputOwnerOffsetMustRemain78, inputOwnership, 78);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateControllerOffsetMustRemain80, controllerState, 80);
OVERWORLD_ACTOR_STATE_OFFSET_ASSERT(
    OverworldActorStateActiveOffsetMustRemain84, active, 84);
#undef OVERWORLD_ACTOR_STATE_OFFSET_ASSERT
typedef char OverworldActorTraceHeaderSizeMustRemain36Bytes[
    sizeof(OverworldActorTraceHeader) == 36 ? 1 : -1];
typedef char OverworldActorTraceEventSizeMustRemain32Bytes[
    sizeof(OverworldActorTraceEvent) == 32 ? 1 : -1];
typedef char OverworldActorPopulationSnapshotSizeMustRemain32Bytes[
    sizeof(OverworldActorPopulationSnapshot) == 32 ? 1 : -1];
typedef char OverworldActorQuerySizeMustRemain24Bytes[
    sizeof(OverworldActorQuery) == 24 ? 1 : -1];
typedef char OverworldActorSnapshotSizeMustRemain176Bytes[
    sizeof(OverworldActorSnapshot) == 176 ? 1 : -1];
/* Native Inspect probes encode queries and decode snapshots independently.
 * Keep each decoded boundary fixed even if a reorder preserves total size. */
#define OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(name, field, expected) \
    typedef char name[offsetof(OverworldActorQuery, field) \
        == (expected) ? 1 : -1]
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQueryVersionOffsetMustRemain0, version, 0);
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQuerySizeOffsetMustRemain2, size, 2);
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQueryKindOffsetMustRemain4, kind, 4);
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQueryIndexOffsetMustRemain5, index, 5);
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQueryReservedOffsetMustRemain6, reserved, 6);
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQueryActorOffsetMustRemain8, actor, 8);
OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT(
    OverworldActorQuerySequenceOffsetMustRemain20, sequence, 20);
#undef OVERWORLD_ACTOR_QUERY_OFFSET_ASSERT
#define OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(name, field, expected) \
    typedef char name[offsetof(OverworldActorSnapshot, field) \
        == (expected) ? 1 : -1]
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectVersionOffsetMustRemain0, version, 0);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectSizeOffsetMustRemain2, size, 2);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectKindOffsetMustRemain4, kind, 4);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectHasActorOffsetMustRemain5, hasActor, 5);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectHasTraceEventOffsetMustRemain6, hasTraceEvent, 6);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectHasPopulationOffsetMustRemain7, hasPopulation, 7);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectFrameOffsetMustRemain8, frame, 8);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectFieldEpochOffsetMustRemain12, fieldEpoch, 12);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectActorCountOffsetMustRemain14, actorCount, 14);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectQueueDepthOffsetMustRemain16, queueDepth, 16);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectLastReasonOffsetMustRemain18, lastReason, 18);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectActorOffsetMustRemain20, actor, 20);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectTraceOffsetMustRemain108, trace, 108);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectTraceEventOffsetMustRemain144, traceEvent, 144);
OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT(
    OverworldActorInspectPopulationOffsetMustRemain144, population, 144);
#undef OVERWORLD_ACTOR_INSPECT_OFFSET_ASSERT
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char OverworldActorSystemEntrySizeMustRemain24Bytes[
    sizeof(OverworldActorSystemEntry) == 24 ? 1 : -1];
#endif

#endif // OVERWORLD_ACTOR_SYSTEM_H
