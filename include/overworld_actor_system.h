#ifndef OVERWORLD_ACTOR_SYSTEM_H
#define OVERWORLD_ACTOR_SYSTEM_H

#include "types.h"

#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_ID 158
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE 0x023B6B00
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_END 0x023BAB00
#define OVERWORLD_ACTOR_SYSTEM_OVERLAY_SIZE 0x4000
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
#define OVERWORLD_ACTOR_SYSTEM_DEBUG_VERSION 1
#define OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS 12
#define OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY 8
#define OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY 8
#define OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY 32
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
} OverworldActorReason;

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
} OverworldActorEvent;

typedef enum OverworldActorCommandKind {
    OVERWORLD_ACTOR_COMMAND_NONE = 0,
    OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION = 1,
    OVERWORLD_ACTOR_COMMAND_DETACH = 2,
    OVERWORLD_ACTOR_COMMAND_REBIND_ROLE = 3,
    OVERWORLD_ACTOR_COMMAND_TRACE_CONFIGURE = 4,
    OVERWORLD_ACTOR_COMMAND_TRACE_CLEAR = 5,
    OVERWORLD_ACTOR_COMMAND_FIELD_EPOCH_ADVANCE = 6,
} OverworldActorCommandKind;

typedef enum OverworldActorInspectKind {
    OVERWORLD_ACTOR_INSPECT_SYSTEM = 0,
    OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE = 1,
    OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX = 2,
    OVERWORLD_ACTOR_INSPECT_TRACE_HEADER = 3,
    OVERWORLD_ACTOR_INSPECT_TRACE_EVENT = 4,
} OverworldActorInspectKind;

typedef struct OverworldActorHandle {
    u16 slot;
    u16 generation;
    u16 fieldEpoch;
    u16 mapGeneration;
    u16 encounterGeneration;
    u16 reserved;
} OverworldActorHandle;

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
    u8 reserved0;
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
    u8 reserved;
    u32 frame;
    u16 fieldEpoch;
    u16 actorCount;
    u16 queueDepth;
    u16 lastReason;
    OverworldActorStateSnapshot actor;
    OverworldActorTraceHeader trace;
    OverworldActorTraceEvent traceEvent;
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
typedef char OverworldActorCommandSizeMustRemain32Bytes[
    sizeof(OverworldActorCommand) == 32 ? 1 : -1];
typedef char OverworldActorReplySizeMustRemain24Bytes[
    sizeof(OverworldActorReply) == 24 ? 1 : -1];
typedef char OverworldActorFrameSizeMustRemain12Bytes[
    sizeof(OverworldActorFrame) == 12 ? 1 : -1];
typedef char OverworldActorStateSnapshotSizeMustRemain88Bytes[
    sizeof(OverworldActorStateSnapshot) == 88 ? 1 : -1];
typedef char OverworldActorTraceHeaderSizeMustRemain36Bytes[
    sizeof(OverworldActorTraceHeader) == 36 ? 1 : -1];
typedef char OverworldActorTraceEventSizeMustRemain32Bytes[
    sizeof(OverworldActorTraceEvent) == 32 ? 1 : -1];
typedef char OverworldActorQuerySizeMustRemain24Bytes[
    sizeof(OverworldActorQuery) == 24 ? 1 : -1];
typedef char OverworldActorSnapshotSizeMustRemain176Bytes[
    sizeof(OverworldActorSnapshot) == 176 ? 1 : -1];
typedef char OverworldActorSystemEntrySizeMustRemain24Bytes[
    sizeof(OverworldActorSystemEntry) == 24 ? 1 : -1];

#endif // OVERWORLD_ACTOR_SYSTEM_H
