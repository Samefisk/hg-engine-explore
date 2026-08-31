#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/map_events_internal.h"

#define ARRAY_COUNT(array) (sizeof(array) / sizeof((array)[0]))
#define TRACE_INDEX_MASK (OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY - 1)
#define ACTOR_WILD_SPIN_SPEED_MASK 0x0F
#define ACTOR_WILD_SWAY_WIDTH_SHIFT 4
OverworldActorSystemState gOverworldActorSystemState
    __attribute__((section(".overworld_actor_system_state"), used));

typedef struct OverworldActorWildMotionPrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} OverworldActorWildMotionPrefix;

#define ACTOR_WILD_RUNTIME(state) \
    ((OverworldActorWildMotionPrefix *)((state)->movementRuntimeState))

OverworldActorFrameResult OverworldActorSystem_TickImpl(
    const OverworldActorFrame *frame);

static void ActorSystem_Zero(void *destination, u32 size)
{
    u8 *bytes = destination;

    while (size != 0) {
        *bytes++ = 0;
        size--;
    }
}

static void ActorSystem_ResetTraceRecords(void)
{
    OverworldActorTraceHeader *trace = &gOverworldActorSystemState.trace;

    ActorSystem_Zero(gOverworldActorSystemState.events,
        sizeof(gOverworldActorSystemState.events));
    trace->oldestSequence = 1;
    trace->nextSequence = 1;
    trace->overwrittenEvents = 0;
    trace->writeIndex = 0;
    trace->count = 0;
}

static void ActorSystem_EnsureInitialized(void)
{
    OverworldActorSystemState *state = &gOverworldActorSystemState;

    if (state->magic == OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        && state->version == OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        && state->size == sizeof(*state)) {
        return;
    }

    ActorSystem_Zero(state, sizeof(*state));
    state->magic = OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC;
    state->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    state->size = sizeof(*state);
    state->fieldEpoch = 1;
    state->lastReason = OVERWORLD_ACTOR_REASON_OK;
    state->trace.magic = OVERWORLD_ACTOR_TRACE_MAGIC;
    state->trace.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    state->trace.size = sizeof(state->trace);
    state->trace.fieldEpoch = state->fieldEpoch;
    state->trace.filterActorSlot = OVERWORLD_ACTOR_TRACE_ALL_SLOTS;
    ActorSystem_ResetTraceRecords();
}

static BOOL ActorSystem_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    return left->slot == right->slot
        && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

static OverworldActorStateSnapshot *ActorSystem_FindActor(
    const OverworldActorHandle *handle)
{
    OverworldActorStateSnapshot *actor;

    if (handle == NULL || handle->slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        return NULL;
    }

    actor = &gOverworldActorSystemState.slots[handle->slot].snapshot;
    if (actor->active == 0 || !ActorSystem_HandleEquals(&actor->handle, handle)) {
        return NULL;
    }
    return actor;
}

static BOOL ActorSystem_TraceAccepts(
    const OverworldActorHandle *handle,
    u16 event)
{
    OverworldActorTraceHeader *trace = &gOverworldActorSystemState.trace;

    if (trace->armed == 0) {
        return FALSE;
    }
    if (event < 32 && event != 0 && trace->filterEventMask != 0
        && (trace->filterEventMask & (1u << event)) == 0) {
        return FALSE;
    }
    if (trace->filterActorSlot == OVERWORLD_ACTOR_TRACE_ALL_SLOTS) {
        return TRUE;
    }
    return handle != NULL
        && handle->slot == trace->filterActorSlot
        && handle->generation == trace->filterActorGeneration;
}

static void ActorSystem_WriteTrace(
    const OverworldActorHandle *handle,
    u16 event,
    u16 reason,
    u32 valueA,
    u32 valueB)
{
    OverworldActorTraceHeader *trace = &gOverworldActorSystemState.trace;
    OverworldActorTraceEvent *record;

    if (!ActorSystem_TraceAccepts(handle, event)) {
        return;
    }

    record = &gOverworldActorSystemState.events[trace->writeIndex];
    ActorSystem_Zero(record, sizeof(*record));
    record->sequence = trace->nextSequence++;
    if (trace->nextSequence == 0) {
        trace->nextSequence = 1;
    }
    record->frame = gOverworldActorSystemState.frame;
    if (handle != NULL) {
        record->actor = *handle;
    } else {
        record->actor.slot = OVERWORLD_ACTOR_INVALID_SLOT;
        record->actor.fieldEpoch = gOverworldActorSystemState.fieldEpoch;
    }
    record->event = event;
    record->reason = reason;
    record->valueA = valueA;
    record->valueB = valueB;

    trace->writeIndex = (trace->writeIndex + 1) & TRACE_INDEX_MASK;
    if (trace->count < OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY) {
        trace->count++;
    } else {
        trace->overwrittenEvents++;
        trace->oldestSequence++;
    }
}

static void ActorSystem_WriteTerminalTrace(
    OverworldActorStateSnapshot *actor,
    u16 event,
    u16 reason,
    u32 valueA,
    u32 valueB)
{
    ActorSystem_WriteTrace(&actor->handle, event, reason, valueA, valueB);
    ActorSystem_WriteTrace(&actor->handle,
        OVERWORLD_ACTOR_EVENT_CONTROL_RETURNED, reason,
        actor->inputOwnership, actor->commitSequence);
}

static void ActorSystem_CancelActor(
    OverworldActorStateSnapshot *actor,
    u16 reason)
{
    OverworldActorRuntimeSlot *slot =
        &gOverworldActorSystemState.slots[actor->handle.slot];

    if (slot->motion.phase == OVERWORLD_MOTION_PHASE_IDLE
        || slot->motion.phase == OVERWORLD_MOTION_PHASE_CANCELED) {
        return;
    }
    OverworldMotion_Cancel(&slot->motion, (u8)reason);
    slot->pendingFirstPathAdvance = 0;
    slot->pendingLastPathAdvance = 0;
    actor->motionPhase = OVERWORLD_ACTOR_PHASE_CANCELED;
    actor->inputOwnership = 0;
    actor->reservationId = 0;
    actor->lastCancelReason = (u8)reason;
    ActorSystem_WriteTerminalTrace(actor,
        OVERWORLD_ACTOR_EVENT_MOTION_CANCELED, reason,
        actor->motionKind, actor->commitSequence);
}

static void ActorSystem_FillReply(
    OverworldActorReply *reply,
    const OverworldActorCommand *command,
    u16 result,
    u16 reason)
{
    ActorSystem_Zero(reply, sizeof(*reply));
    reply->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    reply->size = sizeof(*reply);
    if (command != NULL) {
        reply->sequence = command->sequence;
        reply->actor = command->actor;
    }
    reply->result = result;
    reply->reason = reason;
}

static BOOL ActorSystem_SequenceIsNewer(u32 sequence, u32 reference)
{
    return reference == 0 || (s32)(sequence - reference) > 0;
}

static void ActorSystem_RememberReply(const OverworldActorReply *reply)
{
    OverworldActorSystemState *state = &gOverworldActorSystemState;

    state->acknowledgements[state->ackWriteIndex] = *reply;
    state->ackWriteIndex = (state->ackWriteIndex + 1)
        % OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY;
    if (ActorSystem_SequenceIsNewer(
            reply->sequence, state->lastAcknowledgedSequence)) {
        state->lastAcknowledgedSequence = reply->sequence;
    }
}

static const OverworldActorReply *ActorSystem_FindReply(u32 sequence)
{
    u32 index;

    for (index = 0; index < ARRAY_COUNT(gOverworldActorSystemState.acknowledgements);
         index++) {
        if (gOverworldActorSystemState.acknowledgements[index].sequence
            == sequence) {
            return &gOverworldActorSystemState.acknowledgements[index];
        }
    }
    return NULL;
}

OverworldActorResult OverworldActorSystem_CompatibilityBindImpl(
    const OverworldActorStateSnapshot *initial,
    OverworldActorHandle *handle)
{
    OverworldActorSystemState *system;
    OverworldActorRuntimeSlot *runtimeSlot;
    OverworldActorStateSnapshot *actor;
    u16 slot;
    u16 generation;
    BOOL resetPolicy;

    ActorSystem_EnsureInitialized();
    system = &gOverworldActorSystemState;
    if (initial == NULL || handle == NULL
        || initial->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || initial->size != sizeof(*initial)) {
        system->lastReason = OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    slot = initial->handle.slot;
    if (slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        && system->slots[slot].snapshot.active != 0) {
        system->lastReason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }
    if (slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        for (slot = 0; slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; slot++) {
            if (system->slots[slot].snapshot.active == 0) {
                break;
            }
        }
    }
    if (slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        system->lastReason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }

    generation = ++system->actorGenerations[slot];
    if (generation == 0) {
        generation = ++system->actorGenerations[slot];
    }
    runtimeSlot = &system->slots[slot];
    actor = &runtimeSlot->snapshot;
    resetPolicy = slot != OW_WILD_FOLLOWER_SLOT
        || actor->subjectIdentity != initial->subjectIdentity;
    if (resetPolicy) {
        ActorSystem_Zero(&runtimeSlot->motion, sizeof(runtimeSlot->motion));
        ActorSystem_Zero(
            &system->policies[slot],
            sizeof(system->policies[slot]));
        runtimeSlot->pendingFirstPathAdvance = 0;
        runtimeSlot->pendingLastPathAdvance = 0;
        runtimeSlot->lastWorldEffectSequence = 0;
    }
    *actor = *initial;
    if (resetPolicy) {
        actor->behaviorFingerprint = 0;
        actor->matchedLayerMask = 0;
        actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
    }
    actor->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    actor->size = sizeof(*actor);
    actor->handle.slot = slot;
    actor->handle.generation = generation;
    actor->handle.fieldEpoch = system->fieldEpoch;
    actor->authorityGeneration = generation;
    actor->engineAnchorGeneration = generation;
    actor->presentationGeneration = actor->presentationAttached
        ? generation
        : 0;
    actor->active = 1;
    *handle = actor->handle;
    system->actorCount++;
    system->lastReason = OVERWORLD_ACTOR_REASON_OK;
    ActorSystem_WriteTrace(handle, OVERWORLD_ACTOR_EVENT_ACTOR_ATTACHED,
        OVERWORLD_ACTOR_REASON_OK, actor->role, actor->subjectIdentity);
    if (actor->behaviorFingerprint != 0) {
        ActorSystem_WriteTrace(handle,
            OVERWORLD_ACTOR_EVENT_PROFILE_RESOLVED,
            OVERWORLD_ACTOR_REASON_OK,
            actor->behaviorFingerprint,
            actor->matchedLayerMask);
    }
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldActorResult OverworldActorSystem_CompatibilityUpdateImpl(
    const OverworldActorHandle *handle,
    const OverworldActorStateSnapshot *state)
{
    OverworldActorStateSnapshot *actor;
    OverworldActorHandle assigned;

    ActorSystem_EnsureInitialized();
    actor = ActorSystem_FindActor(handle);
    if (actor == NULL) {
        gOverworldActorSystemState.lastReason = OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (state == NULL || state->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || state->size != sizeof(*state)) {
        gOverworldActorSystemState.lastReason =
            OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    assigned = actor->handle;
    *actor = *state;
    actor->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    actor->size = sizeof(*actor);
    actor->handle = assigned;
    actor->active = 1;
    gOverworldActorSystemState.lastReason = OVERWORLD_ACTOR_REASON_OK;
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldActorResult OverworldActorSystem_CompatibilityUnbindImpl(
    const OverworldActorHandle *handle,
    u16 reason)
{
    OverworldActorRuntimeSlot *runtimeSlot;
    OverworldActorStateSnapshot *actor;

    ActorSystem_EnsureInitialized();
    actor = ActorSystem_FindActor(handle);
    if (actor == NULL) {
        gOverworldActorSystemState.lastReason = OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    runtimeSlot = &gOverworldActorSystemState.slots[handle->slot];
    OverworldMotion_Reset(&runtimeSlot->motion);
    runtimeSlot->pendingFirstPathAdvance = 0;
    runtimeSlot->pendingLastPathAdvance = 0;
    ActorSystem_WriteTrace(handle, OVERWORLD_ACTOR_EVENT_ACTOR_DETACHED,
        reason, actor->role, actor->subjectIdentity);
    actor->active = 0;
    actor->inputOwnership = 0;
    actor->reservationId = 0;
    actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
    actor->motionPhase = OVERWORLD_ACTOR_PHASE_IDLE;
    gOverworldActorSystemState.actorCount--;
    gOverworldActorSystemState.lastReason = reason;
    return OVERWORLD_ACTOR_RESULT_OK;
}

u16 OverworldActorSystem_CompatibilityAdvanceFieldEpochImpl(u16 reason)
{
    OverworldActorSystemState *state;
    u32 index;

    ActorSystem_EnsureInitialized();
    state = &gOverworldActorSystemState;
    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        if (state->slots[index].snapshot.active != 0) {
            ActorSystem_WriteTrace(&state->slots[index].snapshot.handle,
                OVERWORLD_ACTOR_EVENT_CONTEXT_CHANGED, reason,
                state->fieldEpoch, state->fieldEpoch + 1);
            state->slots[index].snapshot.active = 0;
        }
        OverworldMotion_Suspend(&state->slots[index].motion);
    }
    state->fieldEpoch++;
    if (state->fieldEpoch == 0) {
        state->fieldEpoch++;
    }
    state->actorCount = 0;
    state->trace.fieldEpoch = state->fieldEpoch;
    state->lastReason = reason;
    return state->fieldEpoch;
}

OverworldActorResult OverworldActorSystem_CompatibilityRecordTraceImpl(
    const OverworldActorHandle *handle,
    u16 event,
    u16 reason,
    u32 valueA,
    u32 valueB)
{
    ActorSystem_EnsureInitialized();
    if (event == OVERWORLD_ACTOR_EVENT_NONE
        || event > OVERWORLD_ACTOR_EVENT_CONTROL_RETURNED) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (handle != NULL && ActorSystem_FindActor(handle) == NULL) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    ActorSystem_WriteTrace(handle, event, reason, valueA, valueB);
    return OVERWORLD_ACTOR_RESULT_OK;
}

u16 OverworldActorSystem_CompatibilityGetFieldEpochImpl(void)
{
    ActorSystem_EnsureInitialized();
    return gOverworldActorSystemState.fieldEpoch;
}

OverworldActorResult OverworldActorSystem_MotionDispatchImpl(
    OverworldActorMotionServiceCall *call)
{
    OverworldActorRuntimeSlot *runtimeSlot = NULL;
    OverworldActorStateSnapshot *actor = NULL;
    OverworldMotionState *motionState;
    OverworldMotionPlan localPlan;
    OverworldMotionPlan *plan;
    u8 phaseBefore;

    if (call == NULL
        || call->version != OVERWORLD_ACTOR_MOTION_CALL_VERSION
        || call->size != sizeof(*call)
        || call->operation > OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    motionState = call->state;
    if (motionState == NULL
        && call->actorSlot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        ActorSystem_EnsureInitialized();
        runtimeSlot = &gOverworldActorSystemState.slots[call->actorSlot];
        motionState = &runtimeSlot->motion;
        actor = &runtimeSlot->snapshot;
    }

    call->selectedIndex = 0xFF;
    call->decision = OVERWORLD_MOTION_DECISION_PROFILE;
    call->tickFlags = 0;
    switch (call->operation) {
    case OVERWORLD_ACTOR_MOTION_SERVICE_RESET:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        OverworldMotion_Reset(motionState);
        if (runtimeSlot != NULL) {
            runtimeSlot->pendingFirstPathAdvance = 0;
            runtimeSlot->pendingLastPathAdvance = 0;
            runtimeSlot->snapshot.motionKind = OVERWORLD_ACTOR_MOTION_NONE;
            runtimeSlot->snapshot.motionPhase = OVERWORLD_ACTOR_PHASE_IDLE;
            runtimeSlot->snapshot.motionElapsed = 0;
            runtimeSlot->snapshot.motionDuration = 0;
            runtimeSlot->snapshot.reservationId = 0;
        }
        call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_SELECT_PLAN:
        call->decision = OverworldMotion_SelectPlan(
            call->intent,
            call->startX,
            call->startY,
            call->startBaseY,
            call->candidates,
            call->candidateCount,
            call->plan,
            &call->selectedIndex);
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_BEGIN:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        call->decision = OverworldMotion_Begin(motionState, call->plan);
        if (call->decision == OVERWORLD_MOTION_DECISION_ACCEPTED
            && actor != NULL && actor->active) {
            ActorSystem_WriteTrace(&actor->handle,
                OVERWORLD_ACTOR_EVENT_MOTION_STARTED,
                OVERWORLD_ACTOR_REASON_OK,
                motionState->plan.kind,
                motionState->plan.duration);
        }
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_READ_SAMPLE:
        if (motionState == NULL || call->sample == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        call->decision = OverworldMotion_Read(
            motionState,
            call->fieldEpoch,
            call->sample);
        if (call->decision == OVERWORLD_MOTION_DECISION_ACCEPTED
            && runtimeSlot != NULL
            && runtimeSlot->pendingFirstPathAdvance != 0) {
            call->sample->firstPathAdvance =
                runtimeSlot->pendingFirstPathAdvance;
            call->sample->lastPathAdvance =
                runtimeSlot->pendingLastPathAdvance;
            call->sample->flags |= OVERWORLD_MOTION_TICK_PATH_ADVANCED;
            call->tickFlags |= OVERWORLD_MOTION_TICK_PATH_ADVANCED;
            runtimeSlot->pendingFirstPathAdvance = 0;
            runtimeSlot->pendingLastPathAdvance = 0;
        }
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_ACKNOWLEDGE_COMMIT:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        phaseBefore = motionState->phase;
        call->decision = OverworldMotion_AcknowledgeCommit(
            motionState,
            call->fieldEpoch);
        if (call->decision == OVERWORLD_MOTION_DECISION_ACCEPTED
            && phaseBefore == OVERWORLD_MOTION_PHASE_COMMIT_PENDING
            && actor != NULL && actor->active) {
            actor->commitSequence = motionState->commitSequence;
            ActorSystem_WriteTrace(&actor->handle,
                OVERWORLD_ACTOR_EVENT_LOGICAL_COMMIT,
                OVERWORLD_ACTOR_REASON_OK,
                actor->commitSequence,
                motionState->plan.kind);
            if (motionState->phase == OVERWORLD_MOTION_PHASE_IDLE) {
                actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
                actor->motionPhase = OVERWORLD_ACTOR_PHASE_IDLE;
                actor->reservationId = 0;
                ActorSystem_WriteTerminalTrace(actor,
                    OVERWORLD_ACTOR_EVENT_MOTION_FINISHED,
                    OVERWORLD_ACTOR_REASON_OK,
                    actor->commitSequence,
                    motionState->plan.kind);
            }
        }
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_SUSPEND:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        OverworldMotion_Suspend(motionState);
        call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_RESUME:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        call->decision = OverworldMotion_Resume(
            motionState,
            call->fieldEpoch);
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_CANCEL:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        if (motionState->phase == OVERWORLD_MOTION_PHASE_IDLE
            || motionState->phase == OVERWORLD_MOTION_PHASE_CANCELED) {
            call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
            break;
        }
        if (actor != NULL && actor->active) {
            ActorSystem_CancelActor(actor, call->cancelReason);
        } else {
            OverworldMotion_Cancel(motionState, call->cancelReason);
        }
        call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_REBIND_FIELD:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        call->decision = OverworldMotion_RebindField(
            motionState,
            motionState->plan.fieldEpoch,
            call->fieldEpoch);
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST:
        if (motionState == NULL || call->intent == NULL
            || call->candidates == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        if (motionState->phase == OVERWORLD_MOTION_PHASE_SUSPENDED
            && motionState->plan.fieldEpoch != call->intent->fieldEpoch) {
            if (actor != NULL && actor->active) {
                ActorSystem_CancelActor(
                    actor,
                    OVERWORLD_ACTOR_REASON_STALE_FIELD);
            } else {
                OverworldMotion_Cancel(
                    motionState,
                    OVERWORLD_ACTOR_REASON_STALE_FIELD);
            }
        }
        if (actor != NULL && actor->active) {
            actor->lastIntent = call->intent->kind;
            ActorSystem_WriteTrace(&actor->handle,
                OVERWORLD_ACTOR_EVENT_INTENT_CREATED,
                OVERWORLD_ACTOR_REASON_OK,
                call->intent->kind,
                call->candidateCount);
        }
        plan = call->plan != NULL ? call->plan : &localPlan;
        call->decision = OverworldMotion_SelectPlan(
            call->intent,
            call->startX,
            call->startY,
            call->startBaseY,
            call->candidates,
            call->candidateCount,
            plan,
            &call->selectedIndex);
        if (call->decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            if (actor != NULL && actor->active) {
                actor->lastDecision = (u8)call->decision;
                ActorSystem_WriteTrace(&actor->handle,
                    OVERWORLD_ACTOR_EVENT_CANDIDATE_REJECTED,
                    call->decision,
                    call->selectedIndex,
                    call->candidateCount);
            }
            break;
        }
        if (actor != NULL && actor->active) {
            if (plan->behaviorFingerprint == 0) {
                plan->behaviorFingerprint = (u16)actor->behaviorFingerprint;
            }
            if (plan->reservationId == 0) {
                gOverworldActorSystemState.nextReservationId++;
                if (gOverworldActorSystemState.nextReservationId == 0) {
                    gOverworldActorSystemState.nextReservationId++;
                }
                plan->reservationId =
                    gOverworldActorSystemState.nextReservationId;
            }
        }
        call->decision = OverworldMotion_Begin(motionState, plan);
        if (actor != NULL && actor->active) {
            actor->lastDecision = (u8)call->decision;
        }
        if (call->decision == OVERWORLD_MOTION_DECISION_ACCEPTED
            && actor != NULL && actor->active) {
            actor->originX = plan->startX;
            actor->originY = plan->startY;
            actor->targetX = plan->targetX;
            actor->targetY = plan->targetY;
            actor->motionKind = plan->kind;
            actor->motionPhase = OVERWORLD_ACTOR_PHASE_MOVING;
            actor->motionElapsed = 0;
            actor->motionDuration = plan->duration;
            actor->reservationId = plan->reservationId;
            ActorSystem_WriteTrace(&actor->handle,
                OVERWORLD_ACTOR_EVENT_PLAN_ACCEPTED,
                OVERWORLD_ACTOR_REASON_OK,
                ((u32)(u16)plan->targetX << 16) | (u16)plan->targetY,
                plan->duration);
            ActorSystem_WriteTrace(&actor->handle,
                OVERWORLD_ACTOR_EVENT_MOTION_STARTED,
                OVERWORLD_ACTOR_REASON_OK,
                plan->kind,
                plan->duration);
        }
        break;
    default:
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldMotionDecision OverworldActorSystem_RequestWildMotion(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfileData *lane,
    u8 kind,
    u8 visibilityPolicy,
    u8 arcHeightQ4,
    u8 facing)
{
    OverworldActorWildMotionPrefix *runtime;
    OverworldActorMotionServiceCall call;
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;

    if (state == NULL || state->movementRuntimeState == NULL || lane == NULL
        || (u32)slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        || kind < OVERWORLD_MOTION_KIND_WALK
        || kind > OVERWORLD_MOTION_KIND_REPOSITION) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    ActorSystem_EnsureInitialized();
    runtime = ACTOR_WILD_RUNTIME(state);
    ActorSystem_Zero(&intent, sizeof(intent));
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = kind;
    intent.facing = facing;
    intent.fieldEpoch = gOverworldActorSystemState.fieldEpoch;
    intent.duration = runtime->movementCustomJumpFrameCounts[slot];
    intent.arcHeightQ4 = arcHeightQ4;
    intent.spinSpeed = runtime->movementCustomJumpSpinSpeeds[slot]
        & ACTOR_WILD_SPIN_SPEED_MASK;
    intent.swayWidth = runtime->movementCustomJumpSpinSpeeds[slot]
        >> ACTOR_WILD_SWAY_WIDTH_SHIFT;
    intent.visibilityPolicy = visibilityPolicy;
    intent.pauseFrames = kind == OVERWORLD_MOTION_KIND_WALK
        ? lane->walkPause
        : kind == OVERWORLD_MOTION_KIND_TELEPORT
            ? lane->teleportPause
            : lane->hopPause;
    intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    intent.commitPolicy = kind == OVERWORLD_MOTION_KIND_REPOSITION
        ? OVERWORLD_MOTION_COMMIT_NO_CHAIN
        : OVERWORLD_MOTION_COMMIT_NORMAL;

    ActorSystem_Zero(&candidate, sizeof(candidate));
    candidate.targetX = runtime->movementCustomJumpTargetX[slot];
    candidate.targetY = runtime->movementCustomJumpTargetY[slot];
    candidate.targetBaseY = runtime->movementCustomJumpTargetBaseY[slot];
    candidate.direction = state->movementPendingDirections[slot];
    candidate.distance = state->movementPendingDistances[slot];

    ActorSystem_Zero(&call, sizeof(call));
    call.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    call.size = sizeof(call);
    call.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;
    call.actorSlot = (u8)slot;
    call.candidateCount = 1;
    call.startX = runtime->movementCustomJumpStartX[slot];
    call.startY = runtime->movementCustomJumpStartY[slot];
    call.startBaseY = runtime->movementCustomJumpStartBaseY[slot];
    call.intent = &intent;
    call.candidates = &candidate;
    if (OverworldActorSystem_MotionDispatchImpl(&call)
        != OVERWORLD_ACTOR_RESULT_OK) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    return (OverworldMotionDecision)call.decision;
}

static void ActorSystem_FillLegacyActorView(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    OverworldActorStateSnapshot *view)
{
    OverworldActorRuntimeSlot *actorSlot =
        &gOverworldActorSystemState.slots[slot];
    const OverworldMotionState *motion = &actorSlot->motion;
    OverworldWildSpawn *spawn = &state->spawns[slot];
    LocalMapObject *object = spawn->object;
    BOOL mounted = slot == OW_WILD_FOLLOWER_SLOT
        && OVERWORLD_MOUNT_OVERLAY_ENTRY->isActive();

    ActorSystem_Zero(view, sizeof(*view));
    view->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    view->size = sizeof(*view);
    view->handle.slot = (u16)slot;
    view->handle.mapGeneration = state->mapGeneration;
    view->handle.encounterGeneration = spawn->encounterGeneration;
    view->subjectIdentity = spawn->personality;
    view->species = spawn->species;
    view->form = spawn->form;
    view->level = spawn->level;
    view->role = mounted
        ? OVERWORLD_ACTOR_ROLE_MOUNTED
        : slot == OW_WILD_FOLLOWER_SLOT
            ? OVERWORLD_ACTOR_ROLE_FOLLOWER
            : OVERWORLD_ACTOR_ROLE_WILD;
    view->lane = state->movementSpotStates[slot];
    view->controllerState = state->movementSpotStates[slot];
    view->behaviorFingerprint =
        gOverworldActorSystemState.policies[slot].behaviorFingerprint;
    view->matchedLayerMask =
        gOverworldActorSystemState.policies[slot].matchedLayerMask;
    view->streamState =
        gOverworldActorSystemState.policies[slot].streamState;
    view->presentationAttached = object != NULL
        && spawn->mapId == fieldSystem->location->mapId;
    view->active = TRUE;

    if (mounted && fieldSystem->playerAvatar != NULL) {
        object = fieldSystem->playerAvatar->mapObject;
        view->inputOwnership = TRUE;
    }
    if (object == NULL) {
        return;
    }
    if (actorSlot->snapshot.active
        && motion->phase != OVERWORLD_MOTION_PHASE_IDLE
        && motion->phase != OVERWORLD_MOTION_PHASE_CANCELED) {
        /* The actor model owns logical position until the engine reaches its
         * real movement boundary. Do not let an older engine tile undo a
         * shared path advance while the motion is active. */
        view->logicalX = actorSlot->snapshot.logicalX;
        view->logicalY = actorSlot->snapshot.logicalY;
    } else {
        view->logicalX = (s16)object->xCurr;
        view->logicalY = (s16)object->yCurr;
    }
    view->renderX = (s16)((s32)object->posVec[0] >> 16);
    view->renderY = (s16)((s32)object->posVec[2] >> 16);
    view->motionPhase = motion->phase;
    if (motion->phase != OVERWORLD_MOTION_PHASE_IDLE
        && motion->phase != OVERWORLD_MOTION_PHASE_CANCELED) {
        view->motionKind = motion->plan.kind;
        view->originX = motion->plan.startX;
        view->originY = motion->plan.startY;
        view->targetX = motion->plan.targetX;
        view->targetY = motion->plan.targetY;
        view->motionElapsed = motion->elapsed;
        view->motionDuration = motion->plan.duration;
        view->reservationId = motion->plan.reservationId;
    }
}

static void ActorSystem_SyncLegacyActor(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldActorStateSnapshot view;
    OverworldActorStateSnapshot previous;
    OverworldActorStateSnapshot *current =
        &gOverworldActorSystemState.slots[slot].snapshot;
    OverworldActorHandle handle;

    if (!state->spawns[slot].active) {
        if (current->active) {
            handle = current->handle;
            (void)OverworldActorSystem_CompatibilityUnbindImpl(
                &handle,
                OVERWORLD_ACTOR_REASON_OK);
        }
        return;
    }
    ActorSystem_FillLegacyActorView(fieldSystem, state, slot, &view);
    if (!current->active
        || current->handle.mapGeneration != state->mapGeneration
        || current->handle.encounterGeneration
            != state->spawns[slot].encounterGeneration
        || current->subjectIdentity != state->spawns[slot].personality) {
        if (current->active) {
            handle = current->handle;
            (void)OverworldActorSystem_CompatibilityUnbindImpl(
                &handle,
                OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
        }
        (void)OverworldActorSystem_CompatibilityBindImpl(&view, &handle);
        return;
    }

    previous = *current;
    view.handle = current->handle;
    if (view.behaviorFingerprint == 0) {
        view.behaviorFingerprint = current->behaviorFingerprint;
        view.matchedLayerMask = current->matchedLayerMask;
    }
    view.commitSequence = current->commitSequence;
    view.lastCommandSequence = current->lastCommandSequence;
    view.authorityGeneration = current->authorityGeneration;
    view.engineAnchorGeneration = current->engineAnchorGeneration;
    view.presentationGeneration = current->presentationGeneration;
    if (previous.role != view.role) {
        view.authorityGeneration++;
        view.engineAnchorGeneration++;
    }
    if (previous.presentationAttached != view.presentationAttached) {
        view.presentationGeneration++;
    }
    view.lastIntent = current->lastIntent;
    view.lastDecision = current->lastDecision;
    view.lastCancelReason = current->lastCancelReason;
    (void)OverworldActorSystem_CompatibilityUpdateImpl(
        &current->handle,
        &view);
    if (previous.lane != view.lane) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_LANE_CHANGED,
            OVERWORLD_ACTOR_REASON_OK,
            previous.lane,
            view.lane);
    }
    if (previous.behaviorFingerprint != view.behaviorFingerprint
        || previous.matchedLayerMask != view.matchedLayerMask) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_PROFILE_RESOLVED,
            OVERWORLD_ACTOR_REASON_OK,
            view.behaviorFingerprint,
            view.matchedLayerMask);
    }
    if (previous.streamState != view.streamState) {
        ActorSystem_WriteTrace(&view.handle,
            view.streamState == OVERWORLD_ACTOR_STREAM_WAITING
                ? OVERWORLD_ACTOR_EVENT_STREAM_WAITING
                : OVERWORLD_ACTOR_EVENT_STREAM_ADVANCED,
            OVERWORLD_ACTOR_REASON_OK,
            previous.streamState,
            view.streamState);
    }
    if (gOverworldActorSystemState.slots[slot].lastWorldEffectSequence
        != gOverworldActorSystemState.policies[slot].worldEffectSequence) {
        gOverworldActorSystemState.slots[slot].lastWorldEffectSequence =
            gOverworldActorSystemState.policies[slot].worldEffectSequence;
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_WORLD_EFFECT,
            OVERWORLD_ACTOR_REASON_OK,
            gOverworldActorSystemState.policies[slot].worldEffectId,
            gOverworldActorSystemState.policies[slot].worldEffectSequence);
    }
    if (previous.role != view.role) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_ACTOR_REBOUND,
            OVERWORLD_ACTOR_REASON_OK,
            previous.role,
            view.role);
    }
    if (previous.inputOwnership != view.inputOwnership) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_CONTROL_REBOUND,
            OVERWORLD_ACTOR_REASON_OK,
            previous.inputOwnership,
            view.inputOwnership);
    }
    if (previous.presentationAttached != view.presentationAttached
        || (view.presentationAttached
            && previous.motionPhase != view.motionPhase)) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_PRESENTATION_SYNCED,
            OVERWORLD_ACTOR_REASON_OK,
            ((u32)(u16)view.renderX << 16) | (u16)view.renderY,
            view.motionKind);
    }
}

static OverworldActorFrameResult OverworldActorSystem_PopulationFrameImpl(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    OverworldActorFrame frame;
    int slot;

    ActorSystem_EnsureInitialized();
    if (fieldSystem == NULL || state == NULL || fieldSystem->location == NULL) {
        return OVERWORLD_ACTOR_FRAME_INVALID;
    }
    if (gOverworldActorSystemState.compatibilityMapGeneration != 0
        && gOverworldActorSystemState.compatibilityMapGeneration
            != state->mapGeneration) {
        (void)OverworldActorSystem_CompatibilityAdvanceFieldEpochImpl(
            OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
    }
    gOverworldActorSystemState.compatibilityMapGeneration =
        state->mapGeneration;

    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        ActorSystem_SyncLegacyActor(fieldSystem, state, slot);
    }

    if (state->movementRuntimeState != NULL
        && gOverworldWildFieldIdleRearmPending == 0
        && state->spawnCooldown != OW_WILD_REFILL_TIMER_PENDING) {
        if (state->spawnCooldown != 0) {
            state->spawnCooldown--;
        } else {
            state->spawnCooldown = OW_WILD_REFILL_TIMER_PENDING;
            gOverworldWildFieldIdleRearmPending |=
                OW_WILD_FIELD_IDLE_REARM_PENDING;
        }
    }

    ActorSystem_Zero(&frame, sizeof(frame));
    frame.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    frame.size = sizeof(frame);
    frame.frame = gOverworldActorSystemState.frame + 1;
    frame.expectedFieldEpoch = gOverworldActorSystemState.fieldEpoch;
    return OverworldActorSystem_TickImpl(&frame);
}

static void OverworldActorSystem_PopulationResetImpl(void)
{
    ActorSystem_EnsureInitialized();
    gOverworldActorSystemState.compatibilityMapGeneration = 0;
}

#define OW_ACTOR_LOOK_PLAN_BASE_MASK 0x03
#define OW_ACTOR_LOOK_PLAN_FIRST_SHIFT 2
#define OW_ACTOR_LOOK_PLAN_SECOND_SHIFT 4
#define OW_ACTOR_LOOK_PLAN_TWO_GLANCES (1u << 6)

static u8 ActorSystem_BuildLookPlan(u8 baseDirection)
{
    u8 firstDirection;
    u8 secondDirection = baseDirection;
    BOOL twoGlances = (gf_rand() & 1u) != 0;

    do {
        firstDirection = gf_rand() & OW_ACTOR_LOOK_PLAN_BASE_MASK;
    } while (firstDirection == baseDirection);
    if (twoGlances) {
        secondDirection = baseDirection ^ 1u;
        if (secondDirection == firstDirection) {
            secondDirection = baseDirection ^ 2u;
        }
    }
    return baseDirection
        | (firstDirection << OW_ACTOR_LOOK_PLAN_FIRST_SHIFT)
        | (secondDirection << OW_ACTOR_LOOK_PLAN_SECOND_SHIFT)
        | (twoGlances ? OW_ACTOR_LOOK_PLAN_TWO_GLANCES : 0);
}

static int ActorSystem_ResolveLook(
    u8 lookPlan,
    u8 phase,
    u8 totalFrames,
    u8 remainingFrames)
{
    BOOL twoGlances = (lookPlan & OW_ACTOR_LOOK_PLAN_TWO_GLANCES) != 0;
    u8 shift = 0;

    if (totalFrames != 0) {
        if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_SECOND
            && remainingFrames > (twoGlances
                    ? (totalFrames * 2) / 3
                    : totalFrames / 2)) {
            return -1;
        }
        if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_RETURN
            && remainingFrames > (twoGlances
                    ? totalFrames / 3
                    : totalFrames / 2)) {
            return -1;
        }
    }
    if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_FIRST) {
        shift = OW_ACTOR_LOOK_PLAN_FIRST_SHIFT;
    } else if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_SECOND) {
        shift = OW_ACTOR_LOOK_PLAN_SECOND_SHIFT;
    }
    return (lookPlan >> shift) & OW_ACTOR_LOOK_PLAN_BASE_MASK;
}

static int ActorSystem_ChooseWanderDirection(
    const u8 *directions,
    int directionCount,
    u8 previousDirection,
    u8 chance)
{
    int index;

    if (chance == 100 || (chance != 0 && (gf_rand() % 100) < chance)) {
        for (index = 0; index < directionCount; index++) {
            if (directions[index] == previousDirection) {
                return index;
            }
        }
    }
    return -2;
}

static BOOL ActorSystem_PrepareChainPause(
    u8 *stepsRemaining,
    u8 *deferredPauseTicks,
    u8 *deferredPauseAction,
    u8 *variancePhase,
    OverworldWildWalkMomentumState *walkMomentum,
    const OverworldWildBehaviorProfileData *lane,
    u8 locomotion)
{
    u8 pauseAction = lane->chainPauseAction;
    u8 pauseTicks;
    u32 pauseFrames;

    if (locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK) {
        if (lane->walkPause != 0) {
            walkMomentum->turnDirection = 0;
        } else if (walkMomentum->turnDirection != 0xFE) {
            walkMomentum->turnDirection++;
        }
    }
    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE) {
        *deferredPauseTicks = 0;
        goto disabled;
    }
    if ((locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK
            && !OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(lane->walkOptions))
        || lane->ramAccelerationSteps == 0
        || !((locomotion >= OW_WILD_BEHAVIOR_LOCOMOTION_WALK
                && locomotion <= OW_WILD_BEHAVIOR_LOCOMOTION_HOP)
            || locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT)) {
disabled:
        *stepsRemaining = 0;
        *deferredPauseAction = 0;
        return FALSE;
    }
    if (*stepsRemaining == 0) {
        *stepsRemaining = lane->ramAccelerationSteps;
        if (lane->chainMovementVariance != 0) {
            *variancePhase = (u8)(*variancePhase * 73u + 41u);
            *stepsRemaining += (u8)(((u16)*variancePhase
                * (lane->chainMovementVariance + 1u)) >> 8);
        }
    }
    (*stepsRemaining)--;
    if (*stepsRemaining != 0) {
        return FALSE;
    }
    if (lane->chainPauseActionChance != 0
        && lane->chainPauseActionChance < 100
        && (gf_rand() % 100) >= lane->chainPauseActionChance) {
        return FALSE;
    }
    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) {
        pauseTicks = 0;
    } else if (pauseAction
        >= OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS) {
        pauseTicks = lane->chainRepositionSpeed;
    } else {
        pauseFrames = lane->ramMaxSpeed;
        if (pauseFrames == 0
            && pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
            pauseFrames = 60;
        }
        *variancePhase = (u8)(*variancePhase * 73u + 41u);
        pauseFrames += (u8)(((u16)*variancePhase
            * (lane->chainPauseVariance + 1u)) >> 8);
        pauseTicks = (u8)((pauseFrames + 1u) / 2u);
        if (pauseAction
            == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS) {
            pauseTicks /= lane->chainRepositionJumpCount;
            if (pauseTicks == 0) {
                pauseTicks = 1;
            }
            pauseTicks += pauseTicks;
        }
    }
    *deferredPauseTicks = pauseTicks;
    *deferredPauseAction = pauseAction | 0x80;
    return TRUE;
}

static const OverworldWildMovementPolicyEntry sActorMovementPolicy = {
    ActorSystem_BuildLookPlan,
    ActorSystem_ResolveLook,
    ActorSystem_ChooseWanderDirection,
    ActorSystem_PrepareChainPause,
};

OverworldActorResult OverworldActorSystem_ValidateImpl(void)
{
    ActorSystem_EnsureInitialized();
    if (OVERWORLD_ACTOR_SYSTEM_ENTRY->magic != OVERWORLD_ACTOR_SYSTEM_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_ENTRY->version
            != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || OVERWORLD_ACTOR_SYSTEM_ENTRY->size
            != sizeof(OverworldActorSystemEntry)
        || OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->magic
            != OVERWORLD_ACTOR_SYSTEM_COMPAT_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->version
            != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->size
            != sizeof(OverworldActorCompatibilityEntry)
        || OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT->magic
            != OVERWORLD_ACTOR_SYSTEM_DEBUG_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_DEBUG_LAYOUT->size
            != sizeof(OverworldActorSystemDebugLayout)
        || OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->magic
            != OVERWORLD_ACTOR_SYSTEM_RESOLVER_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->size
            != sizeof(OverworldActorResolverServiceEntry)
        || OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->version
            != OVERWORLD_ACTOR_RESOLVER_SERVICE_VERSION
        || OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->magic
            != OVERWORLD_ACTOR_SYSTEM_MOTION_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->size
            != sizeof(OverworldActorMotionServiceEntry)
        || OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->version
            != OVERWORLD_ACTOR_MOTION_SERVICE_VERSION
        || OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY->magic
            != OVERWORLD_ACTOR_SYSTEM_POPULATION_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY->size
            != sizeof(OverworldActorPopulationServiceEntry)
        || OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY->version
            != OVERWORLD_ACTOR_POPULATION_SERVICE_VERSION
        || OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->magic
            != OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->size
            != sizeof(OverworldActorMovementPolicyServiceEntry)
        || OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->version
            != OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION
        || OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->states
            != gOverworldActorSystemState.policies
        || sActorMovementPolicy.buildLookPlan == NULL
        || sActorMovementPolicy.resolveLook == NULL
        || sActorMovementPolicy.chooseWanderDirection == NULL
        || sActorMovementPolicy.prepareChainPause == NULL
        || gOverworldActorSystemState.magic
            != OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        || gOverworldActorSystemState.size != sizeof(gOverworldActorSystemState)
        || gOverworldActorSystemDebugLayout.stateAddress
            != (u32)&gOverworldActorSystemState) {
        return OVERWORLD_ACTOR_RESULT_ERROR;
    }
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldActorResult OverworldActorSystem_ApplyImpl(
    const OverworldActorCommand *command,
    OverworldActorReply *reply)
{
    OverworldActorSystemState *state;
    const OverworldActorReply *prior;
    u16 reason;

    ActorSystem_EnsureInitialized();
    state = &gOverworldActorSystemState;
    if (reply == NULL) {
        state->lastReason = OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (command == NULL || command->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || command->size != sizeof(*command) || command->sequence == 0) {
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_REJECTED,
            OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        state->lastReason = OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    prior = ActorSystem_FindReply(command->sequence);
    if (prior != NULL) {
        *reply = *prior;
        return (OverworldActorResult)reply->result;
    }
    if (!ActorSystem_SequenceIsNewer(
            command->sequence, state->lastAcknowledgedSequence)) {
        reason = OVERWORLD_ACTOR_REASON_STALE_SEQUENCE;
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_REJECTED,
            reason);
        ActorSystem_RememberReply(reply);
        state->lastReason = reason;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (command->expectedFieldEpoch != 0
        && command->expectedFieldEpoch != state->fieldEpoch) {
        reason = OVERWORLD_ACTOR_REASON_STALE_FIELD;
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_REJECTED,
            reason);
        ActorSystem_RememberReply(reply);
        state->lastReason = reason;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (command->kind > OVERWORLD_ACTOR_COMMAND_FIELD_EPOCH_ADVANCE) {
        reason = OVERWORLD_ACTOR_REASON_UNSUPPORTED_COMMAND;
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_REJECTED,
            reason);
        ActorSystem_RememberReply(reply);
        state->lastReason = reason;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if ((command->kind == OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION
            || command->kind == OVERWORLD_ACTOR_COMMAND_DETACH
            || command->kind == OVERWORLD_ACTOR_COMMAND_REBIND_ROLE)
        && ActorSystem_FindActor(&command->actor) == NULL) {
        reason = OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_REJECTED,
            reason);
        ActorSystem_RememberReply(reply);
        state->lastReason = reason;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (state->queueCount >= OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY) {
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_RETRY,
            OVERWORLD_ACTOR_REASON_QUEUE_FULL);
        state->lastReason = OVERWORLD_ACTOR_REASON_QUEUE_FULL;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }

    state->commands[(state->queueHead + state->queueCount)
        % OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY] = *command;
    state->queueCount++;
    ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_OK,
        OVERWORLD_ACTOR_REASON_OK);
    ActorSystem_RememberReply(reply);
    state->lastReason = OVERWORLD_ACTOR_REASON_OK;
    return OVERWORLD_ACTOR_RESULT_OK;
}

static u16 ActorSystem_RunCommand(const OverworldActorCommand *command)
{
    OverworldActorStateSnapshot *actor;
    OverworldActorTraceHeader *trace = &gOverworldActorSystemState.trace;
    u16 reason = OVERWORLD_ACTOR_REASON_OK;
    u8 oldRole;

    switch (command->kind) {
    case OVERWORLD_ACTOR_COMMAND_NONE:
        break;
    case OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION:
        actor = ActorSystem_FindActor(&command->actor);
        if (actor == NULL) {
            return OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        }
        reason = (u16)command->valueA;
        actor->lastCommandSequence = command->sequence;
        actor->lastDecision = (u8)reason;
        ActorSystem_CancelActor(actor, reason);
        break;
    case OVERWORLD_ACTOR_COMMAND_DETACH:
        actor = ActorSystem_FindActor(&command->actor);
        if (actor == NULL) {
            return OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        }
        reason = (u16)command->valueA;
        OverworldActorSystem_CompatibilityUnbindImpl(&command->actor, reason);
        break;
    case OVERWORLD_ACTOR_COMMAND_REBIND_ROLE:
        actor = ActorSystem_FindActor(&command->actor);
        if (actor == NULL) {
            return OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        }
        if (command->role > OVERWORLD_ACTOR_ROLE_SCRIPTED) {
            return OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        }
        oldRole = actor->role;
        actor->role = command->role;
        actor->lastCommandSequence = command->sequence;
        ActorSystem_WriteTrace(&actor->handle,
            OVERWORLD_ACTOR_EVENT_CONTROL_REBOUND,
            OVERWORLD_ACTOR_REASON_OK, oldRole, actor->role);
        break;
    case OVERWORLD_ACTOR_COMMAND_TRACE_CONFIGURE:
        trace->filterEventMask = command->valueA;
        trace->filterFramesRemaining = (u16)command->valueB;
        trace->filterActorSlot = OVERWORLD_ACTOR_TRACE_ALL_SLOTS;
        trace->filterActorGeneration = 0;
        if (command->actor.slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
            actor = ActorSystem_FindActor(&command->actor);
            if (actor == NULL) {
                return OVERWORLD_ACTOR_REASON_STALE_ACTOR;
            }
            trace->filterActorSlot = actor->handle.slot;
            trace->filterActorGeneration = actor->handle.generation;
        }
        trace->armed = 1;
        break;
    case OVERWORLD_ACTOR_COMMAND_TRACE_CLEAR:
        ActorSystem_ResetTraceRecords();
        break;
    case OVERWORLD_ACTOR_COMMAND_FIELD_EPOCH_ADVANCE:
        reason = (u16)command->valueA;
        OverworldActorSystem_CompatibilityAdvanceFieldEpochImpl(reason);
        break;
    default:
        return OVERWORLD_ACTOR_REASON_UNSUPPORTED_COMMAND;
    }
    return reason;
}

OverworldActorFrameResult OverworldActorSystem_TickImpl(
    const OverworldActorFrame *frame)
{
    OverworldActorSystemState *state;
    OverworldActorRuntimeSlot *slot;
    OverworldActorStateSnapshot *actor;
    OverworldMotionSample sample;
    OverworldActorCommand command;
    BOOL traceWasArmed;
    BOOL advanceMotion;
    BOOL motionPending = FALSE;
    u16 reason;
    u16 tickFlags;
    u8 phaseBefore;
    s16 logicalX;
    s16 logicalY;
    u32 index;

    ActorSystem_EnsureInitialized();
    state = &gOverworldActorSystemState;
    if (frame == NULL || frame->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || frame->size != sizeof(*frame)) {
        state->lastReason = OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return OVERWORLD_ACTOR_FRAME_INVALID;
    }
    if (frame->expectedFieldEpoch != 0
        && frame->expectedFieldEpoch != state->fieldEpoch) {
        state->lastReason = OVERWORLD_ACTOR_REASON_CONTEXT_LOST;
        return OVERWORLD_ACTOR_FRAME_CONTEXT_LOST;
    }
    if (frame->frame < state->frame) {
        state->lastReason = OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return OVERWORLD_ACTOR_FRAME_INVALID;
    }

    advanceMotion = frame->frame != state->frame;
    state->frame = frame->frame;
    traceWasArmed = state->trace.armed != 0;
    while (state->queueCount != 0) {
        command = state->commands[state->queueHead];
        state->queueHead = (state->queueHead + 1)
            % OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY;
        state->queueCount--;
        reason = ActorSystem_RunCommand(&command);
        state->lastReason = reason;
    }
    if (traceWasArmed && state->trace.filterFramesRemaining != 0) {
        state->trace.filterFramesRemaining--;
        if (state->trace.filterFramesRemaining == 0) {
            state->trace.armed = 0;
        }
    }

    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        slot = &state->slots[index];
        actor = &slot->snapshot;
        phaseBefore = slot->motion.phase;
        tickFlags = 0;
        if (advanceMotion) {
            tickFlags = OverworldMotion_Tick(
                &slot->motion,
                state->fieldEpoch,
                &sample);
            if ((tickFlags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
                if (slot->pendingFirstPathAdvance == 0) {
                    slot->pendingFirstPathAdvance = sample.firstPathAdvance;
                }
                slot->pendingLastPathAdvance = sample.lastPathAdvance;
                if (actor->active) {
                    if (OverworldMotion_GetPathAdvanceTile(
                            &slot->motion.plan,
                            sample.lastPathAdvance,
                            &logicalX,
                            &logicalY)) {
                        actor->logicalX = logicalX;
                        actor->logicalY = logicalY;
                    }
                    ActorSystem_WriteTrace(&actor->handle,
                        OVERWORLD_ACTOR_EVENT_PATH_ADVANCED,
                        OVERWORLD_ACTOR_REASON_OK,
                        ((u32)sample.firstPathAdvance << 16)
                            | sample.lastPathAdvance,
                        slot->motion.plan.kind);
                }
            }
        }
        actor->motionPhase = slot->motion.phase;
        actor->motionElapsed = slot->motion.elapsed;
        actor->motionDuration = slot->motion.plan.duration;
        if (slot->motion.phase != OVERWORLD_MOTION_PHASE_IDLE
            && slot->motion.phase != OVERWORLD_MOTION_PHASE_CANCELED) {
            actor->motionKind = slot->motion.plan.kind;
            actor->originX = slot->motion.plan.startX;
            actor->originY = slot->motion.plan.startY;
            actor->targetX = slot->motion.plan.targetX;
            actor->targetY = slot->motion.plan.targetY;
            actor->reservationId = slot->motion.plan.reservationId;
        } else {
            actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
            actor->reservationId = 0;
            actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
            state->policies[index].streamState = OVERWORLD_ACTOR_STREAM_IDLE;
        }
        if (advanceMotion
            && phaseBefore == OVERWORLD_MOTION_PHASE_SETTLING
            && slot->motion.phase == OVERWORLD_MOTION_PHASE_IDLE
            && actor->active) {
            ActorSystem_WriteTerminalTrace(actor,
                OVERWORLD_ACTOR_EVENT_MOTION_FINISHED,
                OVERWORLD_ACTOR_REASON_OK,
                actor->commitSequence,
                slot->motion.plan.kind);
        }
        if (actor->active != 0
            && actor->motionPhase != OVERWORLD_ACTOR_PHASE_IDLE
            && actor->motionPhase != OVERWORLD_ACTOR_PHASE_CANCELED) {
            motionPending = TRUE;
        }
    }
    return motionPending || state->queueCount != 0
        ? OVERWORLD_ACTOR_FRAME_PENDING
        : OVERWORLD_ACTOR_FRAME_OK;
}

static const OverworldActorTraceEvent *ActorSystem_FindTraceEvent(
    const OverworldActorQuery *query)
{
    OverworldActorTraceHeader *trace = &gOverworldActorSystemState.trace;
    u32 logicalIndex;
    u32 physicalIndex;

    if (query->sequence != 0) {
        for (logicalIndex = 0; logicalIndex < trace->count; logicalIndex++) {
            physicalIndex = (trace->writeIndex
                + OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY - trace->count
                + logicalIndex) & TRACE_INDEX_MASK;
            if (gOverworldActorSystemState.events[physicalIndex].sequence
                == query->sequence) {
                return &gOverworldActorSystemState.events[physicalIndex];
            }
        }
        return NULL;
    }
    if (query->index >= trace->count) {
        return NULL;
    }
    physicalIndex = (trace->writeIndex
        + OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY - trace->count
        + query->index) & TRACE_INDEX_MASK;
    return &gOverworldActorSystemState.events[physicalIndex];
}

OverworldActorResult OverworldActorSystem_InspectImpl(
    const OverworldActorQuery *query,
    OverworldActorSnapshot *snapshot)
{
    OverworldActorStateSnapshot *actor = NULL;
    const OverworldActorTraceEvent *record;

    ActorSystem_EnsureInitialized();
    if (query == NULL || snapshot == NULL
        || query->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || query->size != sizeof(*query)) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    ActorSystem_Zero(snapshot, sizeof(*snapshot));
    snapshot->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    snapshot->size = sizeof(*snapshot);
    snapshot->kind = query->kind;
    snapshot->frame = gOverworldActorSystemState.frame;
    snapshot->fieldEpoch = gOverworldActorSystemState.fieldEpoch;
    snapshot->actorCount = gOverworldActorSystemState.actorCount;
    snapshot->queueDepth = gOverworldActorSystemState.queueCount;
    snapshot->lastReason = gOverworldActorSystemState.lastReason;
    snapshot->trace = gOverworldActorSystemState.trace;

    switch (query->kind) {
    case OVERWORLD_ACTOR_INSPECT_SYSTEM:
    case OVERWORLD_ACTOR_INSPECT_TRACE_HEADER:
        return OVERWORLD_ACTOR_RESULT_OK;
    case OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE:
        actor = ActorSystem_FindActor(&query->actor);
        break;
    case OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX:
        if (query->index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
            && gOverworldActorSystemState.slots[query->index]
                .snapshot.active != 0) {
            actor = &gOverworldActorSystemState.slots[query->index].snapshot;
        }
        break;
    case OVERWORLD_ACTOR_INSPECT_TRACE_EVENT:
        record = ActorSystem_FindTraceEvent(query);
        if (record == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        snapshot->traceEvent = *record;
        snapshot->hasTraceEvent = 1;
        return OVERWORLD_ACTOR_RESULT_OK;
    default:
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    if (actor == NULL) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    snapshot->actor = *actor;
    snapshot->hasActor = 1;
    return OVERWORLD_ACTOR_RESULT_OK;
}

const OverworldActorSystemEntry gOverworldActorSystemEntry
    __attribute__((section(".overworld_actor_system_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_MAGIC,
        OVERWORLD_ACTOR_SYSTEM_ABI_VERSION,
        sizeof(OverworldActorSystemEntry),
        OverworldActorSystem_ValidateImpl,
        OverworldActorSystem_ApplyImpl,
        OverworldActorSystem_TickImpl,
        OverworldActorSystem_InspectImpl,
    };

const OverworldActorCompatibilityEntry gOverworldActorCompatibilityEntry
    __attribute__((section(".overworld_actor_system_compat_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_COMPAT_MAGIC,
        OVERWORLD_ACTOR_SYSTEM_ABI_VERSION,
        sizeof(OverworldActorCompatibilityEntry),
        OverworldActorSystem_CompatibilityBindImpl,
        OverworldActorSystem_CompatibilityUpdateImpl,
        OverworldActorSystem_CompatibilityUnbindImpl,
        OverworldActorSystem_CompatibilityAdvanceFieldEpochImpl,
        OverworldActorSystem_CompatibilityRecordTraceImpl,
        OverworldActorSystem_CompatibilityGetFieldEpochImpl,
    };

const OverworldActorSystemDebugLayout gOverworldActorSystemDebugLayout
    __attribute__((section(".overworld_actor_system_debug_layout"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_DEBUG_MAGIC,
        OVERWORLD_ACTOR_SYSTEM_DEBUG_VERSION,
        sizeof(OverworldActorSystemDebugLayout),
        OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE,
        OVERWORLD_ACTOR_SYSTEM_OVERLAY_END,
        (u32)&gOverworldActorSystemState,
        OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS,
        OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY,
        OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY,
        sizeof(OverworldActorHandle),
        sizeof(OverworldActorCommand),
        sizeof(OverworldActorReply),
        sizeof(OverworldActorQuery),
        sizeof(OverworldActorSnapshot),
        sizeof(OverworldActorStateSnapshot),
        sizeof(OverworldActorTraceHeader),
        sizeof(OverworldActorTraceEvent),
        sizeof(OverworldActorSystemState),
        __builtin_offsetof(OverworldActorSystemState, fieldEpoch),
        __builtin_offsetof(OverworldActorSystemState, slots),
        __builtin_offsetof(OverworldActorSystemState, trace),
        __builtin_offsetof(OverworldActorSystemState, events),
        __builtin_offsetof(OverworldActorSystemState, commands),
        OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY_ADDR
            - OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE,
        sizeof(OverworldActorReservedServiceEntry),
        OVERWORLD_ACTOR_SYSTEM_SERVICE_COUNT,
        0xF00,
        sizeof(OverworldActorRuntimeSlot),
    };

const OverworldActorResolverServiceEntry
    gOverworldActorSystemResolverServiceEntry
    __attribute__((section(".overworld_actor_system_resolver_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_RESOLVER_MAGIC,
        OVERWORLD_ACTOR_RESOLVER_SERVICE_VERSION,
        sizeof(OverworldActorResolverServiceEntry),
        BehaviorResolver_Resolve,
        BehaviorResolver_InspectClass,
    };

const OverworldActorMotionServiceEntry gOverworldActorSystemMotionServiceEntry
    __attribute__((section(".overworld_actor_system_motion_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_MOTION_MAGIC,
        OVERWORLD_ACTOR_MOTION_SERVICE_VERSION,
        sizeof(OverworldActorMotionServiceEntry),
        OverworldActorSystem_MotionDispatchImpl,
        OverworldActorSystem_RequestWildMotion,
    };

const OverworldActorPopulationServiceEntry
    gOverworldActorSystemPopulationServiceEntry
    __attribute__((section(".overworld_actor_system_population_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_POPULATION_MAGIC,
        OVERWORLD_ACTOR_POPULATION_SERVICE_VERSION,
        sizeof(OverworldActorPopulationServiceEntry),
        OverworldActorSystem_PopulationFrameImpl,
        OverworldActorSystem_PopulationResetImpl,
    };

const OverworldActorMovementPolicyServiceEntry
    gOverworldActorSystemMovementPolicyServiceEntry
    __attribute__((section(".overworld_actor_system_movement_policy_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC,
        OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION,
        sizeof(OverworldActorMovementPolicyServiceEntry),
        &sActorMovementPolicy,
        gOverworldActorSystemState.policies,
    };
