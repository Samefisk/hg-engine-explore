#include "../../include/overworld_behavior_condition_shadow.h"

#include "../../include/map_events_internal.h"
#include "../../include/overworld_actor_system_internal.h"

static u8 OverworldBehaviorConditionShadow_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    return left->slot == right->slot
        && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

static const OverworldBehaviorConditionServiceEntry *
OverworldBehaviorConditionShadow_GetService(void)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY;

    if (service->magic != OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC
        || service->version != OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        || service->size != sizeof(*service)) {
        return NULL;
    }
    return service;
}

static void OverworldBehaviorConditionShadow_ClearSlot(
    OverworldBehaviorConditionShadowRuntime *runtime,
    u8 slot)
{
    if (runtime != NULL && slot < OW_WILD_MAX_SPAWNS) {
        memset(&runtime->actors[slot], 0, sizeof(runtime->actors[slot]));
        runtime->frame.valid = FALSE;
    }
}

static void OverworldBehaviorConditionShadow_ClearAll(
    OverworldBehaviorConditionShadowRuntime *runtime)
{
    if (runtime != NULL) {
        memset(runtime, 0, sizeof(*runtime));
    }
}

static BOOL OverworldBehaviorConditionShadow_Prepare(
    OverworldWildSpawnState *state,
    const OverworldWildBehaviorDataBlob *behaviorData,
    OverworldBehaviorConditionShadowRuntime *runtime,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    const OverworldActorHandle *handle,
    u8 slot)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OverworldBehaviorConditionShadow_GetService();
    OverworldWildBehaviorContext context;

    if (state == NULL || behaviorData == NULL || runtime == NULL
        || buildContext == NULL || handle == NULL
        || slot >= OW_WILD_MAX_SPAWNS || !state->spawns[slot].active
        || service == NULL) {
        return FALSE;
    }
    context = buildContext(
        &state->spawns[slot],
        0,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    context.behaviorClass = state->movementBehaviorClasses[slot];
    if (service->prepareActor(
            behaviorData,
            sizeof(*behaviorData),
            &context,
            handle,
            &runtime->actors[slot])
            != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        OverworldBehaviorConditionShadow_ClearSlot(runtime, slot);
        return FALSE;
    }
    if (runtime->actors[slot].count > runtime->maxPreparedCount) {
        runtime->maxPreparedCount = runtime->actors[slot].count;
    }
    runtime->frame.valid = FALSE;
    return TRUE;
}

static BOOL OverworldBehaviorConditionShadow_BuildFrame(
    const OverworldBehaviorConditionShadowCall *call)
{
    OverworldBehaviorConditionShadowRuntime *runtime = call->runtime;
    OverworldActorQuery query;
    OverworldActorSnapshot systemSnapshot;
    int slot;

    memset(&query, 0, sizeof(query));
    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_SYSTEM;
    if (OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(&query, &systemSnapshot)
            != OVERWORLD_ACTOR_RESULT_OK) {
        return FALSE;
    }
    if (runtime->frame.valid
        && runtime->frame.world.frame == systemSnapshot.frame) {
        return TRUE;
    }
    memset(&runtime->frame, 0, sizeof(runtime->frame));
    runtime->frame.world.frame = systemSnapshot.frame;
    runtime->frame.traceArmed = systemSnapshot.trace.armed;
    if (call->fieldSystem->playerAvatar != NULL) {
        runtime->frame.world.playerValid = TRUE;
        runtime->frame.world.playerX =
            (s16)GetPlayerXCoord(call->fieldSystem->playerAvatar);
        runtime->frame.world.playerY =
            (s16)GetPlayerYCoord(call->fieldSystem->playerAvatar);
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        OverworldBehaviorConditionPreparedActor *prepared =
            &runtime->actors[slot];
        OverworldWildSpawn *spawn = &call->state->spawns[slot];
        OverworldBehaviorConditionActorObservation *observation;
        OverworldBehaviorConditionCandidate *candidate;
        u8 index;

        if (!spawn->active || spawn->object == NULL || !prepared->valid
            || prepared->subject.slot != slot
            || prepared->subject.encounterGeneration
                != spawn->encounterGeneration
            || !call->isCurrentSpawn(call->fieldSystem, spawn)) {
            continue;
        }
        index = runtime->frame.world.actorCount;
        if (index >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS) {
            return FALSE;
        }
        observation = &runtime->frame.world.actors[index];
        observation->actor = prepared->subject;
        observation->x = (s16)spawn->object->xCurr;
        observation->y = (s16)spawn->object->yCurr;
        observation->valid = TRUE;
        candidate = &runtime->frame.candidates[index];
        candidate->context = call->buildContext(
            spawn,
            0,
            0,
            OW_WILD_SPAWN_TERRAIN_LAND,
            FALSE);
        candidate->context.behaviorClass =
            call->state->movementBehaviorClasses[slot];
        candidate->roleMask = slot == OW_WILD_FOLLOWER_SLOT
            ? OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER
            : OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
        runtime->frame.world.actorCount++;
    }
    runtime->frame.valid = TRUE;
    return TRUE;
}

static BOOL OverworldBehaviorConditionShadow_Resolve(
    const OverworldBehaviorConditionShadowCall *call,
    const OverworldWildBehaviorContext *context)
{
    OverworldBehaviorConditionShadowRuntime *runtime = call->runtime;
    const OverworldBehaviorConditionTargetReference *target =
        &runtime->result.resolvedTarget;
    BehaviorResolveRequest request;

    memset(&request, 0, sizeof(request));
    request.context = *context;
    request.behaviorClass = context->behaviorClass;
    request.conditionInputMode = BEHAVIOR_RESOLVE_CONDITIONS_EXPLICIT;
    request.activeConditionalMask = runtime->result.activeApplicationMask;
    request.winningConditionId = runtime->result.winningConditionId;
    request.targetSourceApplication =
        runtime->result.resolvedTargetSourceApplication;
    request.resolvedTargetConditionId =
        runtime->result.resolvedTargetConditionId;
    if (call->forcedOverrideProfileIndex >= 0) {
        request.forcedOverrideMask =
            1u << call->forcedOverrideProfileIndex;
    }
    request.resolvedTarget.kind = target->kind;
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        request.resolvedTarget.actorSlot = target->actor.slot;
        request.resolvedTarget.actorGeneration = target->actor.generation;
        request.resolvedTarget.fieldEpoch = target->actor.fieldEpoch;
        request.resolvedTarget.mapGeneration = target->actor.mapGeneration;
        request.resolvedTarget.encounterGeneration =
            target->actor.encounterGeneration;
        request.resolvedTarget.actorReserved = target->actor.reserved;
    }
    return OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->resolve(
            call->behaviorData,
            sizeof(*call->behaviorData),
            &request,
            &runtime->resolution,
            NULL) == BEHAVIOR_RESOLVE_OK;
}

static void OverworldBehaviorConditionShadow_RecordTrace(
    const OverworldBehaviorConditionShadowCall *call,
    const OverworldBehaviorConditionPreparedActor *prepared)
{
    const OverworldBehaviorConditionShadowRuntime *runtime = call->runtime;
    u16 i;

    if (!runtime->frame.traceArmed) {
        return;
    }
    for (i = 0; i < prepared->count; i++) {
        const OverworldBehaviorConditionEntryResult *entry =
            &runtime->scratch.entryResults[i];
        const OverworldBehaviorConditionEntryState *entryState =
            &prepared->states[i];
        u16 flags = entry->conditionTrue
            | (entry->active << 1)
            | (entry->triggered << 2)
            | (entry->target.kind << 4);

        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace(
            &prepared->subject,
            OVERWORLD_ACTOR_EVENT_CONDITION_EVALUATED,
            flags,
            entry->conditionId
                | ((u32)entry->applicationIndex << 16)
                | ((u32)i << 24),
            runtime->result.activeApplicationMask);
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace(
            &prepared->subject,
            OVERWORLD_ACTOR_EVENT_CONDITION_TIMERS,
            entry->conditionId,
            entryState->activeUntil,
            entryState->cooldownUntil);
        if (entry->target.kind
                == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
            OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace(
                &prepared->subject,
                OVERWORLD_ACTOR_EVENT_CONDITION_TARGET,
                entry->target.actor.slot,
                entry->target.actor.generation
                    | ((u32)entry->target.actor.fieldEpoch << 16),
                entry->target.actor.mapGeneration
                    | ((u32)entry->target.actor.encounterGeneration << 16));
        }
    }
    OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace(
        &prepared->subject,
        OVERWORLD_ACTOR_EVENT_CONDITIONAL_RESOLVED,
        runtime->result.resolvedTargetSourceApplication
            | ((u16)prepared->count << 8),
        runtime->result.activeApplicationMask,
        runtime->result.winningConditionId
            | ((u32)runtime->result.resolvedTargetConditionId << 16));
}

static void OverworldBehaviorConditionShadow_Run(
    const OverworldBehaviorConditionShadowCall *call)
{
    OverworldBehaviorConditionShadowRuntime *runtime;
    OverworldBehaviorConditionPreparedActor *prepared;
    const OverworldBehaviorConditionServiceEntry *service;
    OverworldWildBehaviorContext context;
    LocalMapObject *object;
    int rosterIndex = -1;
    u8 index;

    if (call == NULL || call->state == NULL || call->fieldSystem == NULL
        || call->behaviorData == NULL
        || call->runtime == NULL || call->buildContext == NULL
        || call->isCurrentSpawn == NULL
        || call->slot >= OW_WILD_MAX_SPAWNS
        || !call->state->spawns[call->slot].active
        || !OverworldBehaviorConditionShadow_BuildFrame(call)) {
        return;
    }
    runtime = call->runtime;
    service = OverworldBehaviorConditionShadow_GetService();
    if (service == NULL) {
        return;
    }
    prepared = &runtime->actors[call->slot];
    for (index = 0; index < runtime->frame.world.actorCount; index++) {
        if (OverworldBehaviorConditionShadow_HandleEquals(
                &prepared->subject,
                &runtime->frame.world.actors[index].actor)) {
            rosterIndex = index;
            break;
        }
    }
    if (!prepared->valid || rosterIndex < 0) {
        memset(prepared, 0, sizeof(*prepared));
        return;
    }
    object = call->state->spawns[call->slot].object;
    context = call->buildContext(
        &call->state->spawns[call->slot],
        0,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    context.behaviorClass = call->state->movementBehaviorClasses[call->slot];
    context.conditionTerrainMask = call->subjectTerrainMask;
    runtime->frame.world.subject = prepared->subject;
    runtime->frame.world.subjectX = (s16)object->xCurr;
    runtime->frame.world.subjectY = (s16)object->yCurr;
    runtime->frame.world.subjectFacing = object->curFacing;
    runtime->frame.world.subjectTerrainMask = call->subjectTerrainMask;
    runtime->frame.world.subjectMovementSpeed = call->subjectMovementSpeed;
    if (service->evaluatePrepared(
            call->behaviorData,
            sizeof(*call->behaviorData),
            prepared,
            &runtime->frame.world,
            runtime->frame.candidates,
            runtime->frame.world.actorCount,
            runtime->frame.world.frame,
            &runtime->scratch,
            &runtime->result) != OVERWORLD_BEHAVIOR_CONDITION_OK
        || !OverworldBehaviorConditionShadow_Resolve(call, &context)) {
        return;
    }
    OverworldBehaviorConditionShadow_RecordTrace(call, prepared);
}

const OverworldBehaviorConditionShadowEntry
    gOverworldBehaviorConditionShadowEntry
    __attribute__((section(".overworld_condition_shadow_entry"), used)) = {
        OVERWORLD_BEHAVIOR_CONDITION_SHADOW_MAGIC,
        OVERWORLD_BEHAVIOR_CONDITION_SHADOW_VERSION,
        sizeof(OverworldBehaviorConditionShadowEntry),
        OverworldBehaviorConditionShadow_Prepare,
        OverworldBehaviorConditionShadow_ClearSlot,
        OverworldBehaviorConditionShadow_ClearAll,
        OverworldBehaviorConditionShadow_Run,
    };
