#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/map_events_internal.h"

#define ARRAY_COUNT(array) (sizeof(array) / sizeof((array)[0]))
#define TRACE_INDEX_MASK (OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY - 1)
#define ACTOR_LEGACY_SPIN_SPEED_MASK 0x0F
#define ACTOR_LEGACY_SWAY_WIDTH_SHIFT 4

OverworldActorSystemState gOverworldActorSystemState
    __attribute__((section(".overworld_actor_system_state"), used));

typedef struct OverworldActorLegacyMotionPrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} OverworldActorLegacyMotionPrefix;

#define ACTOR_LEGACY_RUNTIME(state) \
    ((OverworldActorLegacyMotionPrefix *)((state)->movementRuntimeState))

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

    actor = &gOverworldActorSystemState.actors[handle->slot];
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

static void ActorSystem_RememberReply(const OverworldActorReply *reply)
{
    OverworldActorSystemState *state = &gOverworldActorSystemState;

    state->acknowledgements[state->ackWriteIndex] = *reply;
    state->ackWriteIndex = (state->ackWriteIndex + 1)
        % OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY;
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
    OverworldActorStateSnapshot *actor;
    u16 slot;
    u16 generation;

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
        && system->actors[slot].active != 0) {
        system->lastReason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }
    if (slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        for (slot = 0; slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; slot++) {
            if (system->actors[slot].active == 0) {
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
    actor = &system->actors[slot];
    *actor = *initial;
    actor->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    actor->size = sizeof(*actor);
    actor->handle.slot = slot;
    actor->handle.generation = generation;
    actor->handle.fieldEpoch = system->fieldEpoch;
    actor->active = 1;
    *handle = actor->handle;
    system->actorCount++;
    system->lastReason = OVERWORLD_ACTOR_REASON_OK;
    ActorSystem_WriteTrace(handle, OVERWORLD_ACTOR_EVENT_ACTOR_ATTACHED,
        OVERWORLD_ACTOR_REASON_OK, actor->role, actor->subjectIdentity);
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
    OverworldActorStateSnapshot *actor;

    ActorSystem_EnsureInitialized();
    actor = ActorSystem_FindActor(handle);
    if (actor == NULL) {
        gOverworldActorSystemState.lastReason = OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    ActorSystem_WriteTrace(handle, OVERWORLD_ACTOR_EVENT_ACTOR_DETACHED,
        reason, actor->role, actor->subjectIdentity);
    actor->active = 0;
    actor->inputOwnership = 0;
    actor->reservationId = 0;
    actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
    actor->motionPhase = OVERWORLD_ACTOR_PHASE_IDLE;
    if (gOverworldActorSystemState.actorCount != 0) {
        gOverworldActorSystemState.actorCount--;
    }
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
        if (state->actors[index].active != 0) {
            ActorSystem_WriteTrace(&state->actors[index].handle,
                OVERWORLD_ACTOR_EVENT_CONTEXT_CHANGED, reason,
                state->fieldEpoch, state->fieldEpoch + 1);
            state->actors[index].active = 0;
        }
        OverworldMotion_Suspend(&state->motions[index]);
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
    OverworldMotionState *motionState;

    if (call == NULL
        || call->version != OVERWORLD_ACTOR_MOTION_CALL_VERSION
        || call->size != sizeof(*call)
        || call->operation > OVERWORLD_ACTOR_MOTION_SERVICE_REBIND_FIELD) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    motionState = call->state;
    if (motionState == NULL
        && call->actorSlot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        ActorSystem_EnsureInitialized();
        motionState = &gOverworldActorSystemState.motions[call->actorSlot];
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
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_TICK:
    {
        u8 phaseBeforeTick;

        if (motionState == NULL || call->sample == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        phaseBeforeTick = motionState->phase;
        call->tickFlags = OverworldMotion_Tick(
            motionState,
            call->fieldEpoch,
            call->sample);
        call->decision = phaseBeforeTick == OVERWORLD_MOTION_PHASE_IDLE
                || phaseBeforeTick == OVERWORLD_MOTION_PHASE_CANCELED
            ? OVERWORLD_MOTION_DECISION_NO_CANDIDATE
            : motionState->plan.fieldEpoch != call->fieldEpoch
            ? OVERWORLD_MOTION_DECISION_STALE_FIELD
            : OVERWORLD_MOTION_DECISION_ACCEPTED;
        break;
    }
    case OVERWORLD_ACTOR_MOTION_SERVICE_ACKNOWLEDGE_COMMIT:
        call->decision = OverworldMotion_AcknowledgeCommit(
            motionState,
            call->fieldEpoch);
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_SUSPEND:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        OverworldMotion_Suspend(motionState);
        call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_RESUME:
        call->decision = OverworldMotion_Resume(
            motionState,
            call->fieldEpoch);
        break;
    case OVERWORLD_ACTOR_MOTION_SERVICE_CANCEL:
        if (motionState == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        OverworldMotion_Cancel(motionState, call->cancelReason);
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
    default:
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldMotionDecision OverworldActorSystem_BeginLegacyMotion(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfileData *lane,
    u8 kind,
    u8 visibilityPolicy,
    u8 arcHeightQ4,
    u8 facing)
{
    OverworldActorLegacyMotionPrefix *runtime;
    OverworldMotionPlan plan;

    if (state == NULL || state->movementRuntimeState == NULL || lane == NULL
        || (u32)slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        || kind < OVERWORLD_MOTION_KIND_WALK
        || kind > OVERWORLD_MOTION_KIND_REPOSITION) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    ActorSystem_EnsureInitialized();
    runtime = ACTOR_LEGACY_RUNTIME(state);
    ActorSystem_Zero(&plan, sizeof(plan));
    plan.version = OVERWORLD_MOTION_MODEL_VERSION;
    plan.kind = kind;
    plan.facing = facing;
    plan.fieldEpoch = gOverworldActorSystemState.fieldEpoch;
    plan.startX = runtime->movementCustomJumpStartX[slot];
    plan.startY = runtime->movementCustomJumpStartY[slot];
    plan.targetX = runtime->movementCustomJumpTargetX[slot];
    plan.targetY = runtime->movementCustomJumpTargetY[slot];
    plan.startBaseY = runtime->movementCustomJumpStartBaseY[slot];
    plan.targetBaseY = runtime->movementCustomJumpTargetBaseY[slot];
    plan.duration = runtime->movementCustomJumpFrameCounts[slot];
    plan.direction = state->movementPendingDirections[slot];
    plan.distance = state->movementPendingDistances[slot];
    plan.arcHeightQ4 = arcHeightQ4;
    plan.spinSpeed = runtime->movementCustomJumpSpinSpeeds[slot]
        & ACTOR_LEGACY_SPIN_SPEED_MASK;
    plan.swayWidth = runtime->movementCustomJumpSpinSpeeds[slot]
        >> ACTOR_LEGACY_SWAY_WIDTH_SHIFT;
    plan.visibilityPolicy = visibilityPolicy;
    plan.pauseFrames = kind == OVERWORLD_MOTION_KIND_WALK
        ? lane->walkPause
        : kind == OVERWORLD_MOTION_KIND_TELEPORT
            ? lane->teleportPause
            : lane->hopPause;
    plan.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    plan.commitPolicy = kind == OVERWORLD_MOTION_KIND_REPOSITION
        ? OVERWORLD_MOTION_COMMIT_NO_CHAIN
        : OVERWORLD_MOTION_COMMIT_NORMAL;
    if (gOverworldActorSystemState.motions[slot].phase
            == OVERWORLD_MOTION_PHASE_SUSPENDED
        && gOverworldActorSystemState.motions[slot].plan.fieldEpoch
            != gOverworldActorSystemState.fieldEpoch) {
        OverworldMotion_Cancel(
            &gOverworldActorSystemState.motions[slot],
            OVERWORLD_ACTOR_REASON_STALE_FIELD);
    }
    return OverworldMotion_Begin(
        &gOverworldActorSystemState.motions[slot],
        &plan);
}

static u8 ActorSystem_LegacyMotionKind(
    const OverworldWildSpawnState *state,
    int slot)
{
    const OverworldActorLegacyMotionPrefix *runtime;

    if (state->movementRuntimeState == NULL) {
        return OVERWORLD_ACTOR_MOTION_NONE;
    }
    runtime = ACTOR_LEGACY_RUNTIME(state);
    if (runtime->movementCustomJumpActive[slot]
        || runtime->movementCustomJumpPrepActive[slot]) {
        return state->movementTeleportHidden[slot]
                || state->movementTeleportFlickerObjects[slot] != NULL
            ? OVERWORLD_ACTOR_MOTION_TELEPORT
            : OVERWORLD_ACTOR_MOTION_HOP;
    }
    return (state->movementInProgressMask & (1u << slot)) != 0
        ? OVERWORLD_ACTOR_MOTION_WALK
        : OVERWORLD_ACTOR_MOTION_NONE;
}

static void ActorSystem_FillLegacyActorView(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    OverworldActorStateSnapshot *view)
{
    OverworldWildSpawn *spawn = &state->spawns[slot];
    LocalMapObject *object = spawn->object;
    BOOL mounted = slot == OW_WILD_FOLLOWER_SLOT
        && OVERWORLD_MOUNT_OVERLAY_ENTRY->isActive();
    u8 motionKind;

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
    view->logicalX = (s16)object->xCurr;
    view->logicalY = (s16)object->yCurr;
    view->renderX = (s16)((s32)object->posVec[0] >> 16);
    view->renderY = (s16)((s32)object->posVec[2] >> 16);
    motionKind = ActorSystem_LegacyMotionKind(state, slot);
    view->motionKind = motionKind;
    view->motionPhase = motionKind == OVERWORLD_ACTOR_MOTION_NONE
        ? OVERWORLD_ACTOR_PHASE_IDLE
        : OVERWORLD_ACTOR_PHASE_MOVING;
    if (state->movementRuntimeState != NULL
        && ACTOR_LEGACY_RUNTIME(state)->movementCustomJumpActive[slot]) {
        const OverworldActorLegacyMotionPrefix *runtime =
            ACTOR_LEGACY_RUNTIME(state);

        view->originX = runtime->movementCustomJumpStartX[slot];
        view->originY = runtime->movementCustomJumpStartY[slot];
        view->targetX = runtime->movementCustomJumpTargetX[slot];
        view->targetY = runtime->movementCustomJumpTargetY[slot];
        view->motionElapsed = runtime->movementCustomJumpElapsedFrames[slot];
        view->motionDuration = runtime->movementCustomJumpFrameCounts[slot];
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
        &gOverworldActorSystemState.actors[slot];
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
    view.commitSequence = current->commitSequence;
    view.lastCommandSequence = current->lastCommandSequence;
    (void)OverworldActorSystem_CompatibilityUpdateImpl(
        &current->handle,
        &view);
    if (previous.motionPhase == OVERWORLD_ACTOR_PHASE_IDLE
        && view.motionPhase == OVERWORLD_ACTOR_PHASE_MOVING) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_MOTION_STARTED,
            OVERWORLD_ACTOR_REASON_OK,
            view.motionKind,
            view.motionDuration);
    }
    if (previous.logicalX != view.logicalX
        || previous.logicalY != view.logicalY) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_PATH_ADVANCED,
            OVERWORLD_ACTOR_REASON_OK,
            ((u32)(u16)view.logicalX << 16) | (u16)view.logicalY,
            view.motionKind);
    }
    if (previous.motionPhase == OVERWORLD_ACTOR_PHASE_MOVING
        && view.motionPhase == OVERWORLD_ACTOR_PHASE_IDLE) {
        current->commitSequence++;
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_LOGICAL_COMMIT,
            OVERWORLD_ACTOR_REASON_OK,
            current->commitSequence,
            previous.motionKind);
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_MOTION_FINISHED,
            OVERWORLD_ACTOR_REASON_OK,
            current->commitSequence,
            previous.motionKind);
    }
    if (previous.renderX != view.renderX
        || previous.renderY != view.renderY) {
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

static BOOL ActorSystem_ValidateMovementPolicy(void)
{
    return sActorMovementPolicy.buildLookPlan != NULL
        && sActorMovementPolicy.resolveLook != NULL
        && sActorMovementPolicy.chooseWanderDirection != NULL
        && sActorMovementPolicy.prepareChainPause != NULL;
}

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
        actor->motionPhase = OVERWORLD_ACTOR_PHASE_CANCELED;
        actor->inputOwnership = 0;
        actor->reservationId = 0;
        actor->lastCancelReason = (u8)reason;
        actor->lastDecision = (u8)reason;
        ActorSystem_WriteTrace(&actor->handle,
            OVERWORLD_ACTOR_EVENT_MOTION_CANCELED, reason,
            actor->motionKind, actor->commitSequence);
        ActorSystem_WriteTrace(&actor->handle,
            OVERWORLD_ACTOR_EVENT_CONTROL_RETURNED, reason, 0, 0);
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
    OverworldActorCommand command;
    BOOL traceWasArmed;
    u16 reason;
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
        if (state->actors[index].active != 0
            && state->actors[index].motionPhase != OVERWORLD_ACTOR_PHASE_IDLE
            && state->actors[index].motionPhase
                != OVERWORLD_ACTOR_PHASE_CANCELED) {
            return OVERWORLD_ACTOR_FRAME_PENDING;
        }
    }
    return state->queueCount != 0
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
            && gOverworldActorSystemState.actors[query->index].active != 0) {
            actor = &gOverworldActorSystemState.actors[query->index];
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
        __builtin_offsetof(OverworldActorSystemState, actors),
        __builtin_offsetof(OverworldActorSystemState, trace),
        __builtin_offsetof(OverworldActorSystemState, events),
        __builtin_offsetof(OverworldActorSystemState, commands),
        OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY_ADDR
            - OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE,
        sizeof(OverworldActorReservedServiceEntry),
        OVERWORLD_ACTOR_SYSTEM_SERVICE_COUNT,
        0x1000,
        0,
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
        OverworldActorSystem_BeginLegacyMotion,
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
        ActorSystem_ValidateMovementPolicy,
    };
