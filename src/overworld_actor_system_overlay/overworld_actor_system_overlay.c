#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_behavior_condition_adapter.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/constants/sndseq.h"
#include "../../include/map_events_internal.h"
#include "../../include/sound.h"

#define OW_ACTOR_STEP_PARTICLE_SET_BITS 0x00010004
#define OW_ACTOR_STEP_PARTICLE_CLEAR_BITS 0x00100000

void __attribute__((noinline, used, optimize("Os"),
        section(".overworld_mount_one_frame_walk")))
OverworldMount_FinishOneFrameWalk(FIELD_PLAYER_AVATAR *avatar)
{
    LocalMapObject *player = avatar->mapObject;

    avatar->unk10 = 1; /* AVATAR_MOVE_STATE_MOVING */
    avatar->unk14 = 2; /* PLAYER_MOVE_STATE_MOVING */
    /* The actor has reached its target. Stock command 0x3C can lag behind
     * a one-frame Walk, so complete that shell now. Longer Walks already have
     * this bit set. Vanilla emits the real END on the next field frame. */
    if (player->movementCmd == 0x3C) {
        player->flags |= MAPOBJECTFLAG_UNK5;
    }
}

void __attribute__((noinline, used,
        section(".overworld_actor_stomp_sound")))
OverworldActor_PlayStompSound(u8 walkOptions)
{
    /* Ram locks its direction. Ordinary Heavy Stomp uses the hop landing sound. */
    if ((walkOptions & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0) {
        PlaySE(SEQ_SE_GS_IWAOTOSHI02);
    } else {
        PlaySE(SEQ_SE_DP_SUTYA2);
    }
}

void __attribute__((noinline, optimize("Os"), used,
        section(".overworld_actor_step_particle")))
OverworldWildRuntime_PlayStepDirtParticle(LocalMapObject *object)
{
    if (object == NULL) {
        return;
    }
    MapObject_SetBits(object, OW_ACTOR_STEP_PARTICLE_SET_BITS);
    ov01_022000DC(object);
    MapObject_ClearBits(object, OW_ACTOR_STEP_PARTICLE_CLEAR_BITS);
}

/* Preserve Thumb metadata for the direct resident helper import. */
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set ActorSystem_ClampWalkTimeWide, 0x023BF488\n"
    ".thumb_func\n.thumb_set OverworldWalk_SkidTiles, 0x023BF4D6\n"
    ".thumb_func\n.thumb_set OverworldActorHopPlanner_Plan, 0x023BD4F0\n"
    ".thumb_func\n.thumb_set OverworldActorTeleportPlanner_Plan, 0x023BD4F8\n");

/* Compiler helpers live in the resident core as Thumb functions. An untyped
 * import makes the linker switch to ARM before entering that Thumb code. */
__asm__(
    ".thumb\n"
    ".global memcpy\n.thumb_func\n.thumb_set memcpy, 0x023DEEBE\n"
    ".global memset\n.thumb_func\n.thumb_set memset, 0x023DEEA2\n"
    ".global __aeabi_uidivmod\n.thumb_func\n.thumb_set __aeabi_uidivmod, 0x023DEE4C\n"
    ".global __aeabi_lmul\n.thumb_func\n.thumb_set __aeabi_lmul, 0x023DEEC6\n"
    ".global __aeabi_idiv\n.thumb_func\n.thumb_set __aeabi_idiv, 0x023DEE44\n"
    ".global __aeabi_uidiv\n.thumb_func\n.thumb_set __aeabi_uidiv, 0x023DEE4C\n"
    ".global __gnu_thumb1_case_uqi\n.thumb_func\n.thumb_set __gnu_thumb1_case_uqi, 0x023DEE54\n"
    ".global __gnu_thumb1_case_sqi\n.thumb_func\n.thumb_set __gnu_thumb1_case_sqi, 0x023DED9A\n"
    ".global __aeabi_idivmod\n.thumb_func\n.thumb_set __aeabi_idivmod, 0x023DEE44\n");

#pragma GCC optimize("Os,no-tree-sra,no-defer-pop,no-tree-forwprop,no-tree-dominator-opts,rename-registers")

u8 ActorSystem_ClampWalkTimeWide(u32 time);
typedef void (*OverworldWalkSelectDisplayedTimeFunc)(
    OverworldActorWalkPolicyCall *call,
    const OverworldActorStateSnapshot *snapshot,
    const OverworldActorPolicyState *policy);
#define OVERWORLD_WALK_SELECT_DISPLAYED_TIME \
    ((OverworldWalkSelectDisplayedTimeFunc)0x01FF9C8D)

#define ARRAY_COUNT(array) (sizeof(array) / sizeof((array)[0]))
#define TRACE_INDEX_MASK (OVERWORLD_ACTOR_SYSTEM_TRACE_CAPACITY - 1)
_Static_assert(__builtin_offsetof(OverworldActorSystemState, mapGeneration)
    == OVERWORLD_ACTOR_DEBUG_MAP_GENERATION_OFFSET,
    "actor map-generation debug offset differs from native layout");
OverworldActorSystemState gOverworldActorSystemState
    __attribute__((section(".overworld_actor_system_state"), used));

OverworldActorFrameResult OverworldActorSystem_TickImpl(
    const OverworldActorFrame *frame);
static u8 OverworldActorSystem_PopulationControlImpl(
    u8 operation,
    u16 refillDelay);

static void __attribute__((section(".overworld_condition_adapter_zero")))
ActorSystem_Zero(void *destination, u32 size)
{
    u8 *bytes = destination;

    while (size != 0) {
        *bytes++ = 0;
        size--;
    }
}

u8 __attribute__((noinline, optimize("Os"),
    section(".overworld_actor_locomotion_policy")))
OverworldActorSystem_SelectMovementLocomotion(
    const OverworldWildBehaviorPrimitives *primitives,
    u8 laneState)
{
    return laneState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? primitives->tiredLocomotion
        : primitives->chillLocomotion;
}

u8 __attribute__((noinline, optimize("Os"),
    section(".overworld_actor_target_policy")))
OverworldActorSystem_SelectMovementTarget(
    const OverworldWildBehaviorPrimitives *primitives,
    u8 laneState)
{
    return laneState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? primitives->tiredTarget
        : primitives->chillTarget;
}

static void __attribute__((noinline, section(".overworld_actor_population_adapter")))
ActorSystem_InitPopulationInput(
    OverworldPopulationInput *input,
    u8 kind,
    u16 fieldEpoch)
{
    u32 eventSequence;

    ActorSystem_Zero(input, sizeof(*input));
    input->version = OVERWORLD_POPULATION_INPUT_VERSION;
    input->size = sizeof(*input);
    input->kind = kind;
    input->fieldEpoch = fieldEpoch;
    eventSequence =
        gOverworldActorSystemState.population.lastWorldEventSequence;
    eventSequence++;
    if (eventSequence == 0) {
        eventSequence++;
    }
    input->eventSequence = eventSequence;
}

static OverworldPopulationDecision
__attribute__((section(".overworld_actor_population_adapter")))
ActorSystem_ApplyPopulationInput(
    const OverworldPopulationInput *input,
    OverworldPopulationResult *result)
{
    return OverworldPopulation_Apply(
        &gOverworldActorSystemState.population,
        input,
        result);
}

static void __attribute__((noinline, section(".overworld_actor_population_adapter")))
ActorSystem_PublishPopulationFieldEvent(u8 event)
{
    typedef u32 ActorSystemLogicalTile __attribute__((may_alias));
    OverworldActorSystemState *state = &gOverworldActorSystemState;
    OverworldPopulationInput input;
    OverworldPopulationResult result;

    ActorSystem_InitPopulationInput(
        &input,
        OVERWORLD_POPULATION_INPUT_FIELD_EVENT,
        state->fieldEpoch);
    input.event = event;
    *(ActorSystemLogicalTile *)&input.logicalX =
        *(const ActorSystemLogicalTile *)&state->population.centerX;
    (void)ActorSystem_ApplyPopulationInput(&input, &result);
}

static void __attribute__((section(".overworld_actor_population_adapter")))
ActorSystem_PublishNativePlayerPathAdvance(FieldSystem *fieldSystem)
{
    typedef u32 ActorSystemLogicalTile __attribute__((may_alias));
    OverworldActorSystemState *state = &gOverworldActorSystemState;
    OverworldPopulationInput input;
    OverworldPopulationResult result;
    ActorSystemLogicalTile logicalTile =
        (u16)GetPlayerXCoord(fieldSystem->playerAvatar)
        | ((u32)(u16)GetPlayerYCoord(fieldSystem->playerAvatar) << 16);

    if (logicalTile
        == *(ActorSystemLogicalTile *)&state->population.centerX) {
        return;
    }
    ActorSystem_InitPopulationInput(
        &input,
        OVERWORLD_POPULATION_INPUT_PATH_ADVANCE,
        state->fieldEpoch);
    *(ActorSystemLogicalTile *)&input.logicalX = logicalTile;
    input.flags = OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED
        | OVERWORLD_POPULATION_INPUT_NATIVE_PLAYER;
    (void)ActorSystem_ApplyPopulationInput(&input, &result);
}

static void __attribute__((section(".overworld_actor_population_adapter")))
ActorSystem_PublishPopulationCommit(void)
{
    OverworldPopulationInput input;
    OverworldPopulationResult result;

    ActorSystem_InitPopulationInput(
        &input,
        OVERWORLD_POPULATION_INPUT_COMMIT,
        gOverworldActorSystemState.fieldEpoch);
    (void)ActorSystem_ApplyPopulationInput(&input, &result);
}

static void __attribute__((section(".overworld_actor_population_adapter")))
ActorSystem_FillPopulationSnapshot(OverworldActorPopulationSnapshot *output)
{
    typedef u32 ActorSystemPopulationWord __attribute__((may_alias));
    const OverworldPopulationState *state =
        &gOverworldActorSystemState.population;

    *(ActorSystemPopulationWord *)&output->version =
        OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        | ((u32)sizeof(*output) << 16);
    output->lastWorldEventSequence = state->lastWorldEventSequence;
    *(ActorSystemPopulationWord *)&output->centerX =
        *(const ActorSystemPopulationWord *)&state->centerX;
    *(ActorSystemPopulationWord *)&output->fieldEpoch =
        *(const ActorSystemPopulationWord *)&state->fieldEpoch;
    *(ActorSystemPopulationWord *)&output->refillArmed =
        *(const ActorSystemPopulationWord *)&state->refillArmed;
    output->workPending = state->maintenanceState != 0;
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
    state->mapGeneration = 1;
    state->lastReason = OVERWORLD_ACTOR_REASON_OK;
    state->trace.magic = OVERWORLD_ACTOR_TRACE_MAGIC;
    state->trace.version = OVERWORLD_ACTOR_TRACE_VERSION;
    state->trace.size = sizeof(state->trace);
    state->trace.fieldEpoch = state->fieldEpoch;
    state->trace.filterActorSlot = OVERWORLD_ACTOR_TRACE_ALL_SLOTS;
    {
        OverworldPopulationInput input;
        OverworldPopulationResult result;

        ActorSystem_InitPopulationInput(
            &input,
            OVERWORLD_POPULATION_INPUT_RESET,
            state->fieldEpoch);
        (void)ActorSystem_ApplyPopulationInput(&input, &result);
    }
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

static inline void __attribute__((always_inline))
ActorSystem_ReleaseTarget(OverworldActorStateSnapshot *actor)
{
    actor->reservationId = 0;
}

static void ActorSystem_CancelActor(
    OverworldActorStateSnapshot *actor,
    u16 reason)
{
    OverworldActorRuntimeSlot *slot =
        &gOverworldActorSystemState.slots[actor->handle.slot];
    OverworldActorPolicyState *policy = &slot->policy;

    if (slot->motion.phase == OVERWORLD_MOTION_PHASE_IDLE
        || slot->motion.phase == OVERWORLD_MOTION_PHASE_CANCELED) {
        ActorSystem_ReleaseTarget(actor);
        return;
    }
    OverworldMotion_Cancel(&slot->motion, (u8)reason);
    policy->pendingFirstPathAdvance = 0;
    policy->pendingLastPathAdvance = 0;
    slot->snapshot.reserved1 = 0;
    actor->motionPhase = OVERWORLD_ACTOR_PHASE_CANCELED;
    actor->inputOwnership = 0;
    ActorSystem_ReleaseTarget(actor);
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

static BOOL ActorSystem_TransitionIsActive(void)
{
    return (u8)(gOverworldActorSystemState.transition.phase
            - OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE)
        < (OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE
            - OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE);
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
    if (ActorSystem_TransitionIsActive()) {
        system->lastReason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }
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

    runtimeSlot = &system->slots[slot];
    actor = &runtimeSlot->snapshot;
    generation = actor->handle.generation + 1;
    if (generation == 0) {
        generation = 1;
    }
    resetPolicy = slot != OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT
        || actor->subjectIdentity != initial->subjectIdentity;
    if (resetPolicy) {
        ActorSystem_Zero(&runtimeSlot->motion, sizeof(runtimeSlot->motion));
        ActorSystem_Zero(&runtimeSlot->policy, sizeof(runtimeSlot->policy));
        runtimeSlot->snapshot.presentationState = 0;
        runtimeSlot->snapshot.reserved1 = 0;
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

OverworldActorResult OverworldActorSystem_CompatibilityUnbindImpl(
    const OverworldActorHandle *handle,
    u16 reason)
{
    OverworldActorRuntimeSlot *runtimeSlot;
    OverworldActorStateSnapshot *actor;

    ActorSystem_EnsureInitialized();
    if (ActorSystem_TransitionIsActive()) {
        gOverworldActorSystemState.lastReason =
            OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }
    actor = ActorSystem_FindActor(handle);
    if (actor == NULL) {
        gOverworldActorSystemState.lastReason = OVERWORLD_ACTOR_REASON_STALE_ACTOR;
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }

    runtimeSlot = &gOverworldActorSystemState.slots[handle->slot];
    OverworldMotion_Reset(&runtimeSlot->motion);
    runtimeSlot->policy.pendingFirstPathAdvance = 0;
    runtimeSlot->policy.pendingLastPathAdvance = 0;
    runtimeSlot->snapshot.reserved1 = 0;
    ActorSystem_WriteTrace(handle, OVERWORLD_ACTOR_EVENT_ACTOR_DETACHED,
        reason, actor->role, actor->subjectIdentity);
    actor->active = 0;
    actor->inputOwnership = 0;
    ActorSystem_ReleaseTarget(actor);
    actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
    actor->motionPhase = OVERWORLD_ACTOR_PHASE_IDLE;
    gOverworldActorSystemState.actorCount--;
    gOverworldActorSystemState.lastReason = reason;
    return OVERWORLD_ACTOR_RESULT_OK;
}

static u32 __attribute__((optimize("Os")))
ActorSystem_ActorMasks(void)
{
    u32 actorMasks = 0;
    u32 index;

    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        OverworldActorRuntimeSlot *slot =
            &gOverworldActorSystemState.slots[index];

        if (slot->snapshot.active != 0) {
            actorMasks |= 1u << index;
        }
        if (OverworldMotion_BlocksWorldGate(
                slot->snapshot.active,
                slot->snapshot.inputOwnership,
                slot->motion.phase,
                slot->snapshot.reservationId)) {
            actorMasks |= 1u << (index + 16);
        }
    }
    return actorMasks;
}

static void ActorSystem_SuspendTransitionActors(u16 actorMask)
{
    u32 index;

    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        OverworldActorRuntimeSlot *slot =
            &gOverworldActorSystemState.slots[index];

        if ((actorMask & (1u << index)) == 0 || !slot->snapshot.active) {
            continue;
        }
        OverworldMotion_Suspend(&slot->motion);
        slot->snapshot.reserved1 = 0;
        slot->snapshot.motionPhase = slot->motion.phase;
    }
}

static void ActorSystem_AdvanceTransitionField(
    OverworldActorTransitionCall *call)
{
    OverworldActorSystemState *state = &gOverworldActorSystemState;
    u16 previousFieldEpoch = state->fieldEpoch;
    u32 index;

    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        OverworldActorStateSnapshot *actor = &state->slots[index].snapshot;

        if ((state->transition.actorMask & (1u << index)) != 0
            && actor->active) {
            ActorSystem_WriteTrace(&actor->handle,
                OVERWORLD_ACTOR_EVENT_CONTEXT_CHANGED,
                OVERWORLD_ACTOR_REASON_CONTEXT_LOST,
                previousFieldEpoch,
                call->nextFieldEpoch);
        }
    }
    state->fieldEpoch = call->nextFieldEpoch;
    state->mapGeneration = call->nextMapGeneration;
    state->trace.fieldEpoch = state->fieldEpoch;
    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        OverworldActorRuntimeSlot *slot = &state->slots[index];
        OverworldActorStateSnapshot *actor = &state->slots[index].snapshot;

        if ((call->retainedActorMask & (1u << index)) == 0
            || !actor->active) {
            continue;
        }
        actor->handle.fieldEpoch = call->nextFieldEpoch;
        actor->handle.mapGeneration = call->nextMapGeneration;
        if ((call->resumeMotionMask & (1u << index)) != 0) {
            if (slot->motion.phase != OVERWORLD_MOTION_PHASE_SUSPENDED
                || slot->motion.plan.fieldEpoch != previousFieldEpoch) {
                state->transition.resumeMotionMask &= ~(1u << index);
                call->resumeMotionMask &= ~(1u << index);
            } else {
                slot->motion.plan.fieldEpoch = call->nextFieldEpoch;
            }
        }
        ActorSystem_WriteTrace(&actor->handle,
            OVERWORLD_ACTOR_EVENT_ACTOR_REBOUND,
            OVERWORLD_ACTOR_REASON_OK,
            call->previousMapId,
            call->currentMapId);
    }
}

static void ActorSystem_CanonicalizeRetainedMotion(
    OverworldActorRuntimeSlot *slot)
{
    OverworldActorStateSnapshot *actor = &slot->snapshot;
    OverworldActorPolicyState *policy = &slot->policy;

    if (slot->motion.phase != OVERWORLD_MOTION_PHASE_SUSPENDED) {
        return;
    }
    ActorSystem_CancelActor(actor, OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
    OverworldMotion_Reset(&slot->motion);
    policy->pendingFirstPathAdvance = 0;
    policy->pendingLastPathAdvance = 0;
    slot->snapshot.reserved1 = 0;
    actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
    actor->motionPhase = OVERWORLD_ACTOR_PHASE_IDLE;
    actor->motionElapsed = 0;
    actor->motionDuration = 0;
    actor->reservationId = 0;
    actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
}

static void ActorSystem_FinalizeTransition(
    const OverworldActorTransitionCall *call)
{
    OverworldActorSystemState *state = &gOverworldActorSystemState;
    u32 index;

    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; index++) {
        OverworldActorRuntimeSlot *slot = &state->slots[index];
        OverworldActorHandle handle;

        if ((call->discardActorMask & (1u << index)) != 0
            && slot->snapshot.active) {
            handle = slot->snapshot.handle;
            (void)OverworldActorSystem_CompatibilityUnbindImpl(
                &handle,
                OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
            continue;
        }
        if ((call->retainedActorMask & (1u << index)) == 0
            || !slot->snapshot.active) {
            continue;
        }
        if ((call->resumeMotionMask & (1u << index)) != 0) {
            if (OverworldMotion_Resume(&slot->motion, state->fieldEpoch)
                != OVERWORLD_MOTION_DECISION_ACCEPTED) {
                ActorSystem_CancelActor(
                    &slot->snapshot,
                    OVERWORLD_ACTOR_REASON_STALE_FIELD);
            }
            slot->snapshot.motionPhase = slot->motion.phase;
        } else {
            ActorSystem_CanonicalizeRetainedMotion(slot);
        }
    }
}

OverworldActorResult __attribute__((optimize("Os")))
OverworldActorSystem_CompatibilityTransitionImpl(
    OverworldActorTransitionCall *call)
{
    OverworldActorSystemState *state;
    OverworldActorResult result;
    u32 actorMasks;
    u8 effects = OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE;

    ActorSystem_EnsureInitialized();
    state = &gOverworldActorSystemState;
    actorMasks = ActorSystem_ActorMasks();
    result = OverworldActorTransition_Apply(
        &state->transition,
        call,
        state->fieldEpoch | ((u32)state->mapGeneration << 16),
        (u16)actorMasks,
        (u16)(actorMasks >> 16),
        &effects);
    if (result != OVERWORLD_ACTOR_RESULT_OK) {
        state->lastReason = call != NULL
                && call->version == OVERWORLD_ACTOR_TRANSITION_CALL_VERSION
                && call->size == sizeof(*call)
            ? call->reason
            : OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT;
        return result;
    }
    if ((effects & OVERWORLD_ACTOR_TRANSITION_EFFECT_SUSPEND) != 0) {
        ActorSystem_SuspendTransitionActors(state->transition.actorMask);
        ActorSystem_PublishPopulationFieldEvent(
            OVERWORLD_POPULATION_FIELD_SUSPEND);
    }
    if ((effects & OVERWORLD_ACTOR_TRANSITION_EFFECT_ADVANCE_FIELD) != 0) {
        ActorSystem_AdvanceTransitionField(call);
        ActorSystem_PublishPopulationFieldEvent(
            OVERWORLD_POPULATION_FIELD_REBIND);
    }
    if ((effects & OVERWORLD_ACTOR_TRANSITION_EFFECT_FINALIZE) != 0) {
        ActorSystem_FinalizeTransition(call);
        ActorSystem_PublishPopulationFieldEvent(
            call->disposition == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE
                ? OVERWORLD_POPULATION_FIELD_RESUME
                : OVERWORLD_POPULATION_FIELD_DISCARD);
    }
    state->lastReason = call->reason;
    return result;
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
        || event > OVERWORLD_ACTOR_EVENT_CONDITIONAL_RESOLVED) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    if (handle != NULL && ActorSystem_FindActor(handle) == NULL) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    ActorSystem_WriteTrace(handle, event, reason, valueA, valueB);
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldActorFieldContext OverworldActorSystem_CompatibilityGetContextImpl(void)
{
    ActorSystem_EnsureInitialized();
    return gOverworldActorSystemState.fieldEpoch
        | ((u32)gOverworldActorSystemState.mapGeneration << 16);
}

static void __attribute__((noinline, optimize("Os")))
ActorSystem_RecordPathAdvances(
    OverworldActorRuntimeSlot *runtimeSlot,
    const OverworldMotionSample *sample)
{
    OverworldActorStateSnapshot *actor = &runtimeSlot->snapshot;
    OverworldActorPolicyState *policy = &runtimeSlot->policy;
    s16 logicalX;
    s16 logicalY;

    if (policy->pendingFirstPathAdvance == 0) {
        policy->pendingFirstPathAdvance = sample->firstPathAdvance;
    }
    policy->pendingLastPathAdvance = sample->lastPathAdvance;
    actor->reserved1 &= ~(OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
        | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY);
    actor->streamState = OVERWORLD_ACTOR_STREAM_WAITING;
    if (!actor->active) {
        return;
    }
    if (OverworldMotion_GetPathAdvanceTile(
            &runtimeSlot->motion.plan,
            sample->lastPathAdvance,
            &logicalX,
            &logicalY)) {
        actor->logicalX = logicalX;
        actor->logicalY = logicalY;
    }
    ActorSystem_WriteTrace(&actor->handle,
        OVERWORLD_ACTOR_EVENT_PATH_ADVANCED,
        OVERWORLD_ACTOR_REASON_OK,
        ((u32)sample->firstPathAdvance << 16) | sample->lastPathAdvance,
        runtimeSlot->motion.plan.kind);
}

static void __attribute__((noinline, optimize("Os")))
ActorSystem_RecordMotionStart(
    OverworldActorStateSnapshot *actor,
    const OverworldActorRuntimeSlot *runtimeSlot,
    const OverworldMotionPlan *plan)
{
    actor->originX = plan->startX;
    actor->originY = plan->startY;
    actor->targetX = plan->targetX;
    actor->targetY = plan->targetY;
    actor->motionKind = plan->kind;
    actor->motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
    actor->motionElapsed = runtimeSlot->motion.elapsed;
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

typedef u32 ActorSystemTargetPair __attribute__((may_alias));

static BOOL __attribute__((optimize("Os")))
ActorSystem_IsTargetReservedByOtherActor(
    u8 actorSlot,
    const OverworldMotionPlan *plan,
    u16 targetSurfaceId)
{
    const OverworldActorRuntimeSlot *slot =
        &gOverworldActorSystemState.slots[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS];
    u32 index = OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS;

    while (index-- != 0) {
        const OverworldActorStateSnapshot *other = &(--slot)->snapshot;

        if (index != actorSlot
            && other->reservationId != 0
            && other->handle.fieldEpoch == plan->fieldEpoch
            && *(const ActorSystemTargetPair *)&other->targetX
                == *(const ActorSystemTargetPair *)&plan->targetX
            && gOverworldActorSystemState.slots[index].policy.targetSurfaceId
                == targetSurfaceId) {
            return TRUE;
        }
    }
    return FALSE;
}

static OverworldActorResult __attribute__((optimize("Os")))
ActorSystem_RequestMotion(
    OverworldActorMotionRequestCall *call)
{
    OverworldActorRuntimeSlot *runtimeSlot;
    OverworldActorStateSnapshot *actor;
    OverworldMotionPlan localPlan;
    OverworldMotionPlan *plan;
    OverworldMotionSample immediateSample;
    u16 immediateFlags;
    u16 expectedFieldEpoch;

    if (call == NULL
        || call->version != OVERWORLD_ACTOR_MOTION_CALL_VERSION
        || call->size != sizeof(*call)) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    call->motionIdentity = 0;
    call->decision = OVERWORLD_MOTION_DECISION_PROFILE;
    if (call->operation == OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP) {
        if (call->hopPlan == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        call->decision = OverworldActorHopPlanner_Plan(call->hopPlan);
        return OVERWORLD_ACTOR_RESULT_OK;
    }
    if ((call->operation != OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST
            && call->operation
                != OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT)
        || call->actorSlot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    ActorSystem_EnsureInitialized();
    runtimeSlot = &gOverworldActorSystemState.slots[call->actorSlot];
    actor = &runtimeSlot->snapshot;
    if (!actor->active) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    call->selectedIndex = 0xFF;
    plan = call->plan != NULL ? call->plan : &localPlan;
    if (call->operation == OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT) {
        if (call->teleportPlan == NULL
            || call->plan == NULL) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        expectedFieldEpoch = call->fieldEpoch;
    } else {
        if (call->intent == NULL
            || call->candidates == NULL
            || call->candidateCount == 0) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        expectedFieldEpoch = call->intent->fieldEpoch;
    }
    if (ActorSystem_TransitionIsActive()) {
        call->decision = OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
        goto motion_rejected;
    }
    if (expectedFieldEpoch != gOverworldActorSystemState.fieldEpoch) {
        call->decision = OVERWORLD_MOTION_DECISION_STALE_FIELD;
        goto motion_rejected;
    }
    actor->lastIntent = call->operation
            == OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT
        ? OVERWORLD_MOTION_KIND_TELEPORT
        : call->intent->kind;
    ActorSystem_WriteTrace(&actor->handle,
        OVERWORLD_ACTOR_EVENT_INTENT_CREATED,
        OVERWORLD_ACTOR_REASON_OK,
        actor->lastIntent,
        call->candidateCount);
    if (call->operation == OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT) {
        call->decision = OverworldActorTeleportPlanner_Plan(call);
        if (call->decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            goto motion_rejected;
        }
        goto plan_accepted;
    }
    if (runtimeSlot->motion.phase == OVERWORLD_MOTION_PHASE_SUSPENDED
        && runtimeSlot->motion.plan.fieldEpoch != expectedFieldEpoch) {
        ActorSystem_CancelActor(actor, OVERWORLD_ACTOR_REASON_STALE_FIELD);
    }
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
motion_rejected:
        actor->lastDecision = (u8)call->decision;
        ActorSystem_WriteTrace(&actor->handle,
            OVERWORLD_ACTOR_EVENT_CANDIDATE_REJECTED,
            call->decision,
            call->selectedIndex,
            call->candidateCount);
        return OVERWORLD_ACTOR_RESULT_OK;
    }
plan_accepted:
    if (ActorSystem_IsTargetReservedByOtherActor(
            call->actorSlot,
            plan,
            call->targetSurfaceId)) {
        call->decision = OVERWORLD_MOTION_DECISION_RESERVED;
        goto motion_rejected;
    }
    if (plan->behaviorFingerprint == 0) {
        plan->behaviorFingerprint = (u16)actor->behaviorFingerprint;
    }
    gOverworldActorSystemState.nextReservationId++;
    if (gOverworldActorSystemState.nextReservationId == 0) {
        gOverworldActorSystemState.nextReservationId++;
    }
    plan->reservationId = gOverworldActorSystemState.nextReservationId;
    call->decision = OverworldMotion_Begin(&runtimeSlot->motion, plan);
    actor->lastDecision = (u8)call->decision;
    if (call->decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return OVERWORLD_ACTOR_RESULT_OK;
    }
    call->motionIdentity = plan->reservationId;
    if (call->reserved != 0 && plan->duration > 1) {
        /* A mounted continuation is requested after this field frame's
         * shared tick, while the old Walk snapshot still records its terminal
         * boundary. Consume that missed first tick here. Fresh starts and
         * one-frame Walks keep their normal complete duration. */
        runtimeSlot->motion.elapsed = 1;
    }
    runtimeSlot->policy.pendingFirstPathAdvance = 0;
    runtimeSlot->policy.pendingLastPathAdvance = 0;
    runtimeSlot->snapshot.reserved1 = 0;
    runtimeSlot->policy.targetSurfaceId = call->targetSurfaceId;
    ActorSystem_RecordMotionStart(actor, runtimeSlot, plan);
    if (plan->kind == OVERWORLD_MOTION_KIND_TELEPORT
        && plan->duration == 0) {
        immediateFlags = OverworldMotion_Tick(
            &runtimeSlot->motion,
            gOverworldActorSystemState.fieldEpoch,
            &immediateSample);
        if ((immediateFlags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
            ActorSystem_RecordPathAdvances(runtimeSlot, &immediateSample);
        }
        actor->motionPhase = runtimeSlot->motion.phase;
    }
    return OVERWORLD_ACTOR_RESULT_OK;
}

static OverworldMotionDecision __attribute__((noinline, optimize("Os"),
    section(".overworld_actor_population_adapter")))
ActorSystem_TryAcknowledgeMotionCommit(
    OverworldActorRuntimeSlot *runtimeSlot,
    u16 fieldEpoch,
    OverworldActorWalkPolicyCall *walkPolicy)
{
    OverworldActorStateSnapshot *actor = &runtimeSlot->snapshot;
    OverworldMotionState *motion = &runtimeSlot->motion;
    OverworldActorPolicyState *policy = &runtimeSlot->policy;
    OverworldMotionDecision decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
    u16 worldEffect = OVERWORLD_ACTOR_WORLD_EFFECT_NONE;

    if (motion->phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING
        || policy->pendingFirstPathAdvance != 0
        || (runtimeSlot->snapshot.reserved1
            & OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS)
            != OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS) {
        return decision;
    }
    if (!actor->active) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (motion->plan.kind == OVERWORLD_MOTION_KIND_WALK
        || motion->plan.kind == OVERWORLD_MOTION_KIND_SKID) {
        if (walkPolicy == NULL
            || walkPolicy->version != OVERWORLD_ACTOR_WALK_POLICY_VERSION
            || walkPolicy->size != sizeof(*walkPolicy)
            || walkPolicy->actorSlot != actor->handle.slot
            || walkPolicy->operation != OVERWORLD_ACTOR_WALK_POLICY_COMMIT
            || walkPolicy->lane == NULL) {
            /* All engine seams can arrive before the adapter has prepared the
             * terminal Walk value. Keep COMMIT_PENDING without mutating the
             * reducer or publishing a logical commit. */
            return decision;
        }
        if (motion->plan.fieldEpoch != fieldEpoch) {
            return OVERWORLD_MOTION_DECISION_STALE_FIELD;
        }
        if (!gOverworldActorSystemMovementPolicyServiceEntry.policy
                ->reduceWalk(walkPolicy)) {
            return OVERWORLD_MOTION_DECISION_PROFILE;
        }
        if (walkPolicy->decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
            && walkPolicy->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
            return OVERWORLD_MOTION_DECISION_PROFILE;
        }
        worldEffect = walkPolicy->effect;
    } else if (walkPolicy != NULL) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    decision = OverworldMotion_AcknowledgeCommit(motion, fieldEpoch);
    if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return decision;
    }
    /* Engine acknowledgements can follow Tick in this same field frame.
     * Publish the new phase before policy readers decide whether to wait. */
    actor->motionPhase = motion->phase;
    if (motion->plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NORMAL
        && policy->pendingStep == OVERWORLD_ACTOR_WALK_PENDING_NONE
        && (walkPolicy == NULL
            || (walkPolicy->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) == 0)) {
        policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;
    }
    /* This counter belongs to the actor lifetime, not the current plan. */
    actor->commitSequence++;
    ActorSystem_ReleaseTarget(actor);
    ActorSystem_PublishPopulationCommit();
    ActorSystem_WriteTrace(&actor->handle,
        OVERWORLD_ACTOR_EVENT_LOGICAL_COMMIT,
        OVERWORLD_ACTOR_REASON_OK,
        actor->commitSequence,
        motion->plan.kind);
    if (worldEffect != OVERWORLD_ACTOR_WORLD_EFFECT_NONE) {
        ActorSystem_WriteTrace(&actor->handle,
            OVERWORLD_ACTOR_EVENT_WORLD_EFFECT,
            OVERWORLD_ACTOR_REASON_OK,
            worldEffect,
            actor->commitSequence);
    }
    if (motion->phase == OVERWORLD_MOTION_PHASE_IDLE) {
        actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
        actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
        ActorSystem_WriteTerminalTrace(actor,
            OVERWORLD_ACTOR_EVENT_MOTION_FINISHED,
            OVERWORLD_ACTOR_REASON_OK,
            actor->commitSequence,
            motion->plan.kind);
    }
    runtimeSlot->snapshot.reserved1 = 0;
    return decision;
}

static OverworldActorResult __attribute__((optimize("Os")))
ActorSystem_EngineBoundary(
    OverworldActorMotionBoundaryCall *call)
{
    OverworldActorRuntimeSlot *runtimeSlot;
    OverworldActorStateSnapshot *actor;
    OverworldMotionState *motion;
    OverworldActorPolicyState *policy;
    u8 acknowledgements;

    if (call == NULL
        || call->version != OVERWORLD_ACTOR_MOTION_CALL_VERSION
        || call->size != sizeof(*call)
        || call->operation != OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY
        || call->actorSlot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    ActorSystem_EnsureInitialized();
    runtimeSlot = &gOverworldActorSystemState.slots[call->actorSlot];
    policy = &runtimeSlot->policy;
    actor = &runtimeSlot->snapshot;
    motion = &runtimeSlot->motion;
    call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
    acknowledgements = call->acknowledgements;
    if (call->motionIdentity == 0
        || call->motionIdentity != actor->reservationId) {
        call->decision = OVERWORLD_MOTION_DECISION_CONTEXT_LOST;
        goto boundary_done;
    }
    if ((acknowledgements & OVERWORLD_ACTOR_BOUNDARY_CANCEL) != 0) {
        ActorSystem_CancelActor(actor, call->cancelReason);
        goto boundary_done;
    }
    if ((acknowledgements & OVERWORLD_ACTOR_BOUNDARY_SUSPEND) != 0) {
        OverworldMotion_Suspend(motion);
        runtimeSlot->snapshot.reserved1 = 0;
        goto boundary_done;
    }
    if ((acknowledgements & OVERWORLD_ACTOR_BOUNDARY_RESUME) != 0) {
        call->decision = OverworldMotion_Resume(motion, call->fieldEpoch);
        goto boundary_done;
    }

    if (call->sample != NULL) {
        call->decision = OverworldMotion_Read(
            motion,
            call->fieldEpoch,
            call->sample);
        if (call->decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
            if (policy->pendingFirstPathAdvance != 0) {
                call->sample->firstPathAdvance =
                    policy->pendingFirstPathAdvance;
                call->sample->lastPathAdvance =
                    policy->pendingLastPathAdvance;
                call->sample->flags |= OVERWORLD_MOTION_TICK_PATH_ADVANCED;
            }
        }
    }
    if (policy->pendingFirstPathAdvance != 0) {
        if ((acknowledgements
                    & (OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                        | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY)) != 0
            && call->acknowledgedPathAdvance
                < policy->pendingLastPathAdvance) {
            acknowledgements &=
                ~(OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                    | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY);
        }
    }
    runtimeSlot->snapshot.reserved1 |= acknowledgements;
    if (policy->pendingFirstPathAdvance != 0
        && (runtimeSlot->snapshot.reserved1
                & (OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                    | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY))
            == (OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY)) {
        policy->pendingFirstPathAdvance = 0;
        policy->pendingLastPathAdvance = 0;
        actor->streamState = OVERWORLD_ACTOR_STREAM_ADVANCED;
    }
    call->decision = ActorSystem_TryAcknowledgeMotionCommit(
        runtimeSlot,
        call->fieldEpoch,
        call->walkPolicy);

boundary_done:
    call->phase = motion->phase;
    return OVERWORLD_ACTOR_RESULT_OK;
}

static void ActorSystem_SyncLegacyActor(
    FieldSystem *fieldSystem,
    void *actorSource,
    int slot)
{
    OverworldActorStateSnapshot view;
    OverworldActorStateSnapshot previous;
    OverworldActorStateSnapshot *current =
        &gOverworldActorSystemState.slots[slot].snapshot;
    OverworldActorHandle handle;

    /* Wild fills a public value snapshot. Seed Actor-owned motion fields so
     * an identity refresh cannot overwrite an in-flight actor command. */
    view = *current;
    OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->fillActorView(
        fieldSystem, actorSource, slot, &view);
    if (!view.active) {
        if (current->active) {
            handle = current->handle;
            (void)OverworldActorSystem_CompatibilityUnbindImpl(
                &handle,
                OVERWORLD_ACTOR_REASON_OK);
        }
        return;
    }
    if (!current->active
        || current->handle.mapGeneration != view.handle.mapGeneration
        || current->handle.encounterGeneration
            != view.handle.encounterGeneration
        || current->subjectIdentity != view.subjectIdentity) {
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
    if (previous.role != view.role) {
        view.authorityGeneration++;
        view.engineAnchorGeneration++;
    }
    if (previous.presentationAttached != view.presentationAttached) {
        view.presentationGeneration++;
    }
    *current = view;
    if (previous.lane != view.lane) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_LANE_CHANGED,
            OVERWORLD_ACTOR_REASON_OK,
            previous.lane,
            view.lane);
    }
    /* FillActorView preserves profile and stream policy. Comparing those
     * seeded fields here cannot detect a change made by their owners. */
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
    if (previous.presentationAttached != view.presentationAttached) {
        ActorSystem_WriteTrace(&view.handle,
            OVERWORLD_ACTOR_EVENT_PRESENTATION_SYNCED,
            OVERWORLD_ACTOR_REASON_OK,
            ((u32)(u16)view.renderX << 16) | (u16)view.renderY,
            view.motionKind);
    }
}

static OverworldActorFrameResult __attribute__((optimize("Os")))
OverworldActorSystem_PopulationFrameImpl(
    OverworldActorPopulationFrameCall *call)
{
    FieldSystem *fieldSystem;
    OverworldActorFrame frame;
    OverworldPopulationInput input;
    OverworldPopulationResult populationResult;
    int slot;

    ActorSystem_EnsureInitialized();
    if (call == NULL
        || call->version != OVERWORLD_ACTOR_POPULATION_FRAME_CALL_VERSION
        || call->size != sizeof(*call)
        || call->fieldSystem == NULL
        || call->actorSource == NULL
        || call->fieldSystem->location == NULL) {
        return OVERWORLD_ACTOR_FRAME_INVALID;
    }
    fieldSystem = call->fieldSystem;
    call->resultFlags = 0;
    if (gOverworldActorSystemState.transition.phase
            == OVERWORLD_ACTOR_TRANSITION_PHASE_NONE
        || gOverworldActorSystemState.transition.phase
            == OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE) {
        for (slot = 0; slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS; slot++) {
            ActorSystem_SyncLegacyActor(
                fieldSystem,
                call->actorSource,
                slot);
        }

        ActorSystem_PublishNativePlayerPathAdvance(fieldSystem);
        ActorSystem_InitPopulationInput(
            &input,
            OVERWORLD_POPULATION_INPUT_FRAME,
            gOverworldActorSystemState.fieldEpoch);
        if ((call->flags
                & OVERWORLD_ACTOR_POPULATION_FRAME_TIMER_ELIGIBLE) != 0) {
            input.flags = OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE;
        }
        (void)ActorSystem_ApplyPopulationInput(&input, &populationResult);
        if ((populationResult.flags
                & OVERWORLD_POPULATION_RESULT_REFILL_DUE) != 0) {
            call->resultFlags |=
                OVERWORLD_ACTOR_POPULATION_FRAME_REFILL_DUE;
        }
    }

    ActorSystem_Zero(&frame, sizeof(frame));
    frame.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    frame.size = sizeof(frame);
    frame.frame = gOverworldActorSystemState.frame + 1;
    frame.expectedFieldEpoch = gOverworldActorSystemState.fieldEpoch;
    return OverworldActorSystem_TickImpl(&frame);
}

static u8 __attribute__((noinline, section(".overworld_actor_population_adapter")))
OverworldActorSystem_PopulationControlImpl(
    u8 operation,
    u16 refillDelay)
{
    OverworldPopulationInput input;
    OverworldPopulationResult result;
    u8 kind;

    ActorSystem_EnsureInitialized();
    if (operation == OVERWORLD_ACTOR_POPULATION_CONTROL_RESET
        && ActorSystem_TransitionIsActive()) {
        /* FIELD_REBIND already queued the destination reconciliation. A
         * legacy Wild clear during DISCARD must not erase actor-owned work. */
        return OVERWORLD_ACTOR_POPULATION_WORK_NONE;
    }
    switch (operation) {
    case OVERWORLD_ACTOR_POPULATION_CONTROL_RESET:
        kind = OVERWORLD_POPULATION_INPUT_RESET;
        break;
    case OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL:
        kind = OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL;
        break;
    case OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE:
        kind = OVERWORLD_POPULATION_INPUT_REQUEST_MAINTENANCE;
        break;
    case OVERWORLD_ACTOR_POPULATION_CONTROL_CANCEL_MAINTENANCE:
        kind = OVERWORLD_POPULATION_INPUT_CANCEL_MAINTENANCE;
        break;
    case OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE:
        kind = OVERWORLD_POPULATION_INPUT_TAKE_WORK;
        break;
    case OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE:
        kind = OVERWORLD_POPULATION_INPUT_QUERY;
        break;
    default:
        return OVERWORLD_ACTOR_POPULATION_WORK_NONE;
    }
    ActorSystem_InitPopulationInput(
        &input,
        kind,
        gOverworldActorSystemState.fieldEpoch);
    input.logicalX = gOverworldActorSystemState.population.centerX;
    input.logicalY = gOverworldActorSystemState.population.centerY;
    input.value = refillDelay;
    (void)ActorSystem_ApplyPopulationInput(&input, &result);
    if (operation
            == OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE) {
        return result.pending;
    }
    return result.work;
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
        if (phase == OVERWORLD_ACTOR_LOOK_SECOND
            && remainingFrames > (twoGlances
                    ? (totalFrames * 2) / 3
                    : totalFrames / 2)) {
            return -1;
        }
        if (phase == OVERWORLD_ACTOR_LOOK_RETURN
            && remainingFrames > (twoGlances
                    ? totalFrames / 3
                    : totalFrames / 2)) {
            return -1;
        }
    }
    if (phase == OVERWORLD_ACTOR_LOOK_FIRST) {
        shift = OW_ACTOR_LOOK_PLAN_FIRST_SHIFT;
    } else if (phase == OVERWORLD_ACTOR_LOOK_SECOND) {
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

static BOOL ActorSystem_ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    OverworldActorRuntimeSlot *slot;

    if (call == NULL
        || call->actorSlot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        return FALSE;
    }
    slot = &gOverworldActorSystemState.slots[call->actorSlot];
    if (!OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY->reduceWalk(
            &slot->policy,
            &slot->snapshot,
            call)) {
        return FALSE;
    }
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_INPUT) {
        OVERWORLD_WALK_SELECT_DISPLAYED_TIME(
            call, &slot->snapshot, &slot->policy);
    }
    return TRUE;
}

BOOL __attribute__((noinline, used,
    section(".overworld_actor_mount_profile_command")))
OverworldActorPolicy_MountCommand(u8 operation, void *payload)
{
    OverworldActorWalkPolicyCall call;

    if (operation == OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE
        && (payload == NULL
            || ((OverworldActorPolicyProfileTransaction *)payload)
                    ->next.behaviorFingerprint == 0)) {
        return FALSE;
    }

    call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call.size = sizeof(call);
    call.policyView = payload;
    call.actorSlot = OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT;
    call.operation = operation;
    call.direction = (u8)(u32)payload;
    call.effect = (u8)(u32)payload;
    return ActorSystem_ReduceWalk(&call);
}

static BOOL __attribute__((noinline, optimize("Os"),
    section(".overworld_actor_mount_policy")))
ActorSystem_FinishMountedWalk(
    const OverworldMountRuntimeState *state,
    BOOL started,
    BOOL crashOnBlocked,
    OverworldActorWalkPolicyCall *output)
{
    OverworldActorPolicyState *policy =
        &gOverworldActorSystemState
            .slots[OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT].policy;

    ActorSystem_Zero(output, sizeof(*output));
    output->version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    output->size = sizeof(*output);
    output->lane = &state->snapshot.profile;
    output->actorSlot = OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT;
    output->operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
    output->laneState = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    output->startResult = started
        ? OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED
        : OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
    output->stepFlags = state->reservedPolicyState[
        OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX];
    output->stepDirection = state->reservedPolicyState[
        OVERWORLD_MOUNT_WALK_STEP_DIRECTION_INDEX];
    output->facingDirection = state->reservedPolicyState[
        OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX];
    output->travelTime = state->reservedPolicyState[
        OVERWORLD_MOUNT_WALK_TRAVEL_TIME_INDEX];
    /* A new skid follows a displayed Walk tile. Continuation distance is
     * ignored by START_RESULT, so its cleared lastWalkTime is harmless. */
    output->distance = (output->stepFlags
            & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0
        ? OverworldWalk_SkidTiles(policy->lastWalkTime)
        : 0;
    output->reserved[0] = state->reservedPolicyProfile[
        OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX];
    if (crashOnBlocked) {
        output->flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED;
    }
    return ActorSystem_ReduceWalk(output);
}

static BOOL __attribute__((noinline, optimize("Os"),
    section(".overworld_actor_population_adapter")))
ActorSystem_TerminalWalkBoundary(
    OverworldActorWalkPolicyCall *walkPolicy,
    u8 acknowledgements,
    u16 acknowledgedPathAdvance,
    u16 motionIdentity)
{
    OverworldActorMotionBoundaryCall boundary;

    if (walkPolicy == NULL) {
        return FALSE;
    }
    boundary.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    boundary.size = sizeof(boundary);
    boundary.operation = OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY;
    boundary.acknowledgements = acknowledgements;
    boundary.actorSlot = walkPolicy->actorSlot;
    boundary.fieldEpoch = gOverworldActorSystemState.fieldEpoch;
    boundary.acknowledgedPathAdvance = acknowledgedPathAdvance;
    boundary.motionIdentity = motionIdentity;
    boundary.sample = NULL;
    boundary.walkPolicy = walkPolicy;
    if (ActorSystem_EngineBoundary(&boundary) != OVERWORLD_ACTOR_RESULT_OK) {
        return FALSE;
    }
    walkPolicy->reserved[OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX] =
        boundary.phase;
    return boundary.decision == OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static const OverworldActorMovementPolicyEntry sActorMovementPolicy = {
    ActorSystem_BuildLookPlan,
    ActorSystem_ResolveLook,
    ActorSystem_ChooseWanderDirection,
    ActorSystem_ReduceWalk,
    ActorSystem_TerminalWalkBoundary,
    ActorSystem_FinishMountedWalk,
};

OverworldActorResult __attribute__((optimize("Os")))
OverworldActorSystem_ValidateImpl(void)
{
    const OverworldActorReservedServiceEntry *service =
        (const OverworldActorReservedServiceEntry *)
            OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY_ADDR;
    u32 index;

    ActorSystem_EnsureInitialized();
    if (OVERWORLD_ACTOR_SYSTEM_ENTRY->magic != OVERWORLD_ACTOR_SYSTEM_MAGIC
        || OVERWORLD_ACTOR_SYSTEM_ENTRY->version
            != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || OVERWORLD_ACTOR_SYSTEM_ENTRY->size
            != sizeof(OverworldActorSystemEntry)
        || gOverworldActorSystemState.magic
            != OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        || gOverworldActorSystemState.size != sizeof(gOverworldActorSystemState)) {
        return OVERWORLD_ACTOR_RESULT_ERROR;
    }
    for (index = 0; index < OVERWORLD_ACTOR_SYSTEM_SERVICE_COUNT; index++) {
        if (service[index].magic == 0
            || service[index].version == 0
            || service[index].size != sizeof(*service)
            || service[index].apply == 0
            || service[index].inspect == 0) {
            return OVERWORLD_ACTOR_RESULT_ERROR;
        }
    }
    if (gOverworldBehaviorConditionAdapterEntry.magic
            != OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_MAGIC
        || gOverworldBehaviorConditionAdapterEntry.version
            != OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION
        || gOverworldBehaviorConditionAdapterEntry.size
            != sizeof(gOverworldBehaviorConditionAdapterEntry)
        || gOverworldBehaviorConditionAdapterEntry.prepareActor == NULL
        || gOverworldBehaviorConditionAdapterEntry.clearActor == NULL
        || gOverworldBehaviorConditionAdapterEntry.clearAll == NULL
        || gOverworldBehaviorConditionAdapterEntry.clearResolution == NULL
        || gOverworldBehaviorConditionAdapterEntry.evaluateActor == NULL
        || gOverworldActorSystemMovementPolicyServiceEntry.magic
            != OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC
        || gOverworldActorSystemMovementPolicyServiceEntry.version
            != OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION
        || gOverworldActorSystemMovementPolicyServiceEntry.size
            != sizeof(gOverworldActorSystemMovementPolicyServiceEntry)
        || gOverworldActorSystemMovementPolicyServiceEntry.conditionAdapter
            != &gOverworldBehaviorConditionAdapterEntry) {
        return OVERWORLD_ACTOR_RESULT_ERROR;
    }
    return OVERWORLD_ACTOR_RESULT_OK;
}

OverworldActorResult __attribute__((optimize("Os")))
OverworldActorSystem_ApplyImpl(
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
    if (ActorSystem_TransitionIsActive()
        && (command->kind == OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION
            || command->kind == OVERWORLD_ACTOR_COMMAND_DETACH
            || command->kind == OVERWORLD_ACTOR_COMMAND_REBIND_ROLE)) {
        ActorSystem_FillReply(reply, command, OVERWORLD_ACTOR_RESULT_RETRY,
            OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY);
        state->lastReason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
        return OVERWORLD_ACTOR_RESULT_RETRY;
    }
    if (command->kind > OVERWORLD_ACTOR_COMMAND_TRACE_CLEAR) {
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

    if (command->expectedFieldEpoch != 0
        && command->expectedFieldEpoch
            != gOverworldActorSystemState.fieldEpoch) {
        return OVERWORLD_ACTOR_REASON_STALE_FIELD;
    }
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
    default:
        return OVERWORLD_ACTOR_REASON_UNSUPPORTED_COMMAND;
    }
    return reason;
}

OverworldActorFrameResult __attribute__((optimize("Os")))
OverworldActorSystem_TickImpl(
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
            if ((tickFlags & (OVERWORLD_MOTION_TICK_MOVED
                    | OVERWORLD_MOTION_TICK_VISIBILITY)) != 0) {
                slot->snapshot.reserved1 &=
                    ~OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED;
            }
            if ((tickFlags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
                ActorSystem_RecordPathAdvances(slot, &sample);
            }
            if (slot->motion.phase
                    == OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
                (void)ActorSystem_TryAcknowledgeMotionCommit(
                    slot,
                    state->fieldEpoch,
                    NULL);
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
        } else {
            actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
            actor->reservationId = 0;
            actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
            slot->snapshot.reserved1 = 0;
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

static BOOL ActorSystem_WorldGateOpen(void)
{
    return !ActorSystem_TransitionIsActive()
        && (ActorSystem_ActorMasks() >> 16) == 0;
}

OverworldActorResult __attribute__((optimize("Os")))
OverworldActorSystem_InspectImpl(
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
    case OVERWORLD_ACTOR_INSPECT_POPULATION:
        ActorSystem_FillPopulationSnapshot(&snapshot->population);
        snapshot->hasPopulation = 1;
        return OVERWORLD_ACTOR_RESULT_OK;
    case OVERWORLD_ACTOR_INSPECT_WORLD_GATE:
        if (query->index > OVERWORLD_ACTOR_WORLD_GATE_BATTLE) {
            return OVERWORLD_ACTOR_RESULT_REJECTED;
        }
        if (!ActorSystem_WorldGateOpen()) {
            snapshot->lastReason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
            return OVERWORLD_ACTOR_RESULT_RETRY;
        }
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
        OVERWORLD_ACTOR_SYSTEM_COMPAT_VERSION,
        sizeof(OverworldActorCompatibilityEntry),
        OverworldActorSystem_CompatibilityBindImpl,
        0,
        OverworldActorSystem_CompatibilityUnbindImpl,
        OverworldActorSystem_CompatibilityTransitionImpl,
        OverworldActorSystem_CompatibilityRecordTraceImpl,
        OverworldActorSystem_CompatibilityGetContextImpl,
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
        0x990,
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
        ActorSystem_RequestMotion,
        ActorSystem_EngineBoundary,
    };

const OverworldActorPopulationServiceEntry
    gOverworldActorSystemPopulationServiceEntry
    __attribute__((section(".overworld_actor_system_population_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_POPULATION_MAGIC,
        OVERWORLD_ACTOR_POPULATION_SERVICE_VERSION,
        sizeof(OverworldActorPopulationServiceEntry),
        OverworldActorSystem_PopulationFrameImpl,
        OverworldActorSystem_PopulationControlImpl,
    };

const OverworldActorMovementPolicyServiceEntry
    gOverworldActorSystemMovementPolicyServiceEntry
    __attribute__((section(".overworld_actor_system_movement_policy_entry"), used)) = {
        OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC,
        OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION,
        sizeof(OverworldActorMovementPolicyServiceEntry),
        &sActorMovementPolicy,
        &gOverworldBehaviorConditionAdapterEntry,
    };
