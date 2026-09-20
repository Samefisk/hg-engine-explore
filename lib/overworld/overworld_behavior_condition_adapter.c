#include "../../include/overworld_behavior_condition_adapter.h"

#include "../../include/map_events_internal.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_spawns_internal.h"

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <stdlib.h>
#endif

static void OverworldBehaviorConditionAdapter_Free(void *memory)
{
#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
    free(memory);
#else
    sys_FreeMemoryEz(memory);
#endif
}

static const OverworldBehaviorConditionServiceEntry *
OverworldBehaviorConditionAdapter_GetService(void)
{
#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
    return OverworldBehaviorConditionService_Get();
#else
    /* Calling the absolute Thumb gate as a linked symbol creates an ARM
     * veneer that loses bit 0.  Keep the typed indirect call so the CPU
     * enters the selector overlay in Thumb state. */
    return OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE();
#endif
}

static void OverworldBehaviorConditionAdapter_ClearResolution(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot)
{
    runtime->activeApplicationMasks[slot] = 0;
    runtime->timedWinningApplicationMasks[slot] = 0;
    /* The validity bit owns the target cache. Coordinates are ignored while
     * it is clear and are replaced before it is set again. */
    runtime->targetValidMask &= (u16)~(1u << slot);
    runtime->frame.valid = FALSE;
}

static void OverworldBehaviorConditionAdapter_ClearActor(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot)
{
    OverworldBehaviorConditionPreparedActor *prepared =
        &runtime->actors[slot];

    if (prepared->states != NULL) {
        OverworldBehaviorConditionAdapter_Free(prepared->states);
    }
    memset(prepared, 0, sizeof(*prepared));
    OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
}

_Static_assert(OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS == 10,
    "condition adapter clear loop must match the actor slot count");

static void __attribute__((naked, noinline))
OverworldBehaviorConditionAdapter_ClearAll(
    OverworldWildBehaviorConditionRuntime *runtime)
{
    (void)runtime;
    __asm__(
        "push {r4, r5, r6, lr}\n"
        "mov r5, r0\n"
        "movs r4, #9\n"
        "1:\n"
        "mov r1, r4\n"
        "mov r0, r5\n"
        "bl OverworldBehaviorConditionAdapter_ClearActor\n"
        "sub r4, #1\n"
        "bcs 1b\n"
        "pop {r4, r5, r6, pc}\n");
}

static OverworldBehaviorConditionStatus
OverworldBehaviorConditionAdapter_PrepareActor(
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldWildSpawnState *state,
    const void *blobBytes,
    u32 blobSize,
    const OverworldActorHandle *subject,
    u8 slot,
    OverworldBehaviorConditionBuildContextFunc buildContext)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OverworldBehaviorConditionAdapter_GetService();
    OverworldBehaviorConditionStatus status;

    if (runtime == NULL || state == NULL || blobBytes == NULL
        || subject == NULL || buildContext == NULL
        || slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || service == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    OverworldBehaviorConditionAdapter_ClearActor(runtime, slot);
    buildContext(
        &runtime->context,
        &state->spawns[slot],
        0,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    runtime->context.behaviorClass = state->movementBehaviorClasses[slot];
    status = service->prepareActor(
        blobBytes,
        blobSize,
        &runtime->context,
        subject,
        &runtime->actors[slot]);
    if (status != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        OverworldBehaviorConditionAdapter_ClearActor(runtime, slot);
        return status;
    }
    runtime->frame.valid = FALSE;
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

static BOOL OverworldBehaviorConditionAdapter_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    return left->slot == right->slot
        && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldBehaviorConditionAdapter_BuildFrame(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    OverworldBehaviorConditionIsCurrentSpawnFunc isCurrentSpawn)
{
    OverworldActorQuery query;
    OverworldActorSnapshot *systemSnapshot = &runtime->actorSnapshot;
    OverworldWildBehaviorConditionFrame *frame = &runtime->frame;
    int slot;

    memset(&query, 0, sizeof(query));
    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_SYSTEM;
    if (OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(
            &query, systemSnapshot)
            != OVERWORLD_ACTOR_RESULT_OK) {
        return FALSE;
    }
    if (frame->valid
        && frame->world.frame == systemSnapshot->frame) {
        return TRUE;
    }
    memset(frame, 0, sizeof(*frame));
    frame->world.frame = systemSnapshot->frame;
    frame->traceArmed = systemSnapshot->trace.armed;
    if (fieldSystem->playerAvatar != NULL) {
        frame->world.playerValid = TRUE;
        frame->world.playerX =
            (s16)GetPlayerXCoord(fieldSystem->playerAvatar);
        frame->world.playerY =
            (s16)GetPlayerYCoord(fieldSystem->playerAvatar);
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        OverworldBehaviorConditionPreparedActor *prepared =
            &runtime->actors[slot];
        OverworldWildSpawn *spawn = &state->spawns[slot];
        OverworldBehaviorConditionActorObservation *observation;
        OverworldBehaviorConditionCandidate *candidate;
        u8 actorRole;
        u8 index;

        if (!spawn->active || spawn->object == NULL || !prepared->valid
            || prepared->subject.slot != slot
            || prepared->subject.encounterGeneration
                != spawn->encounterGeneration
            || !isCurrentSpawn(fieldSystem, spawn)) {
            continue;
        }
        index = frame->world.actorCount;
        observation = &frame->world.actors[index];
        observation->actor = prepared->subject;
        observation->x = (s16)spawn->object->xCurr;
        observation->y = (s16)spawn->object->yCurr;
        observation->valid = TRUE;
        candidate = &frame->candidates[index];
        buildContext(
            &candidate->context,
            spawn,
            0,
            0,
            OW_WILD_SPAWN_TERRAIN_LAND,
            FALSE);
        candidate->context.behaviorClass =
            state->movementBehaviorClasses[slot];
        candidate->roleMask =
            OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
        if (slot == OW_WILD_FOLLOWER_SLOT) {
            query.kind = OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX;
            query.index = (u8)slot;
            if (OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(
                    &query, systemSnapshot)
                    != OVERWORLD_ACTOR_RESULT_OK
                || !systemSnapshot->hasActor
                || !OverworldBehaviorConditionAdapter_HandleEquals(
                    &systemSnapshot->actor.handle, &prepared->subject)) {
                continue;
            }
            actorRole = systemSnapshot->actor.role;
            candidate->roleMask =
                actorRole == OVERWORLD_ACTOR_ROLE_MOUNTED
                    ? OVERWORLD_BEHAVIOR_CONDITION_TARGET_ROLE_MOUNTED
                    : OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER;
        }
        frame->actorSlotMask |= 1u << slot;
        frame->world.actorCount++;
    }
    frame->valid = TRUE;
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldBehaviorConditionAdapter_ResolveTarget(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot,
    OverworldBehaviorConditionAdapterOutcome *outcome)
{
    const OverworldBehaviorConditionTargetReference *target =
        &runtime->result.resolvedTarget;
    OverworldWildBehaviorConditionFrame *frame = &runtime->frame;
    u8 index;

    runtime->targetValidMask &= (u16)~(1u << slot);
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
        return TRUE;
    }
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
        if (!frame->world.playerValid) {
            return FALSE;
        }
        runtime->targetX[slot] = frame->world.playerX;
        runtime->targetY[slot] = frame->world.playerY;
        outcome->targetDx = frame->world.playerX - frame->world.subjectX;
        outcome->targetDy = frame->world.playerY - frame->world.subjectY;
        runtime->targetValidMask |= 1u << slot;
        return TRUE;
    }
    if (target->kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        return FALSE;
    }
    for (index = 0; index < frame->world.actorCount; index++) {
        const OverworldBehaviorConditionActorObservation *actor =
            &frame->world.actors[index];

        if (actor->valid
            && OverworldBehaviorConditionAdapter_HandleEquals(
                &target->actor, &actor->actor)) {
            runtime->targetX[slot] = actor->x;
            runtime->targetY[slot] = actor->y;
            outcome->targetDx = actor->x - frame->world.subjectX;
            outcome->targetDy = actor->y - frame->world.subjectY;
            runtime->targetValidMask |= 1u << slot;
            return TRUE;
        }
    }
    return FALSE;
}

static OverworldBehaviorConditionStatus
OverworldBehaviorConditionAdapter_EvaluateActor(
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
    OverworldBehaviorConditionAdapterOutcome *outcome)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OverworldBehaviorConditionAdapter_GetService();
    OverworldBehaviorConditionPreparedActor *prepared;
    OverworldWildSpawn *spawn;
    LocalMapObject *object;
    OverworldBehaviorConditionStatus status;
    u32 timedWinningApplicationMask = 0;
    u32 timedWinningApplicationMaskBefore;
    u32 endedTimedApplicationMask;
    u16 winningTraceState = 0;
    u8 winningEntryIndex = OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
    u8 index;

    if (runtime == NULL || state == NULL || fieldSystem == NULL
        || blobBytes == NULL || outcome == NULL
        || slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || service == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    memset(outcome, 0, sizeof(*outcome));
    prepared = &runtime->actors[slot];
    spawn = &state->spawns[slot];
    object = spawn->object;
    if (!OverworldBehaviorConditionAdapter_BuildFrame(
            state, fieldSystem, runtime, buildContext, isCurrentSpawn)
        || !prepared->valid || object == NULL
        || (runtime->frame.actorSlotMask & (1u << slot)) == 0) {
        OverworldBehaviorConditionAdapter_ClearActor(runtime, slot);
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    }

    buildContext(
        &runtime->context,
        spawn,
        0,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    runtime->context.behaviorClass = state->movementBehaviorClasses[slot];
    runtime->frame.world.subjectTerrainMask =
        terrainAt(fieldSystem, object->xCurr, object->yCurr);
    runtime->frame.world.subject = prepared->subject;
    runtime->frame.world.subjectX = (s16)object->xCurr;
    runtime->frame.world.subjectY = (s16)object->yCurr;
    runtime->frame.world.subjectFacing = object->curFacing;
    runtime->frame.world.subjectMovementSpeed = subjectMovementSpeed;
    status = service->evaluatePrepared(
        blobBytes,
        blobSize,
        prepared,
        &runtime->frame.world,
        runtime->frame.candidates,
        runtime->frame.world.actorCount,
        runtime->frame.world.frame,
        &runtime->scratch,
        &runtime->result);
    if (status != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
        return status;
    }

    if (runtime->result.activeApplicationMask
            != runtime->activeApplicationMasks[slot]) {
        memset(&runtime->request, 0, sizeof(runtime->request));
        runtime->request.context = runtime->context;
        runtime->request.behaviorClass = runtime->context.behaviorClass;
        runtime->request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
        runtime->request.activeConditionalMask =
            runtime->result.activeApplicationMask;
        runtime->request.winningConditionId = runtime->result.winningConditionId;
        runtime->request.targetSourceApplication =
            runtime->result.resolvedTargetSourceApplication;
        runtime->request.resolvedTargetConditionId =
            runtime->result.resolvedTargetConditionId;
        if (forcedOverrideProfileIndex >= 0) {
            runtime->request.forcedOverrideMask =
                1u << forcedOverrideProfileIndex;
        }
        memcpy(
            &runtime->request.resolvedTarget,
            &runtime->result.resolvedTarget,
            sizeof(runtime->request.resolvedTarget));
        if (OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->resolve(
                blobBytes,
                blobSize,
                &runtime->request,
                &runtime->resolution,
                NULL) != BEHAVIOR_RESOLVE_OK) {
            OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
        outcome->flags =
            OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED;
        if (runtime->result.triggeredApplicationMask != 0) {
            outcome->flags |=
                OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED;
        }
    }

    for (index = 0; index < prepared->count; index++) {
        const OverworldWildBehaviorConditionEntry *entry;
        u8 entryFlags = runtime->scratch.entryFlags[index];

        if (prepared->catalogEntryIndexes[index]
                >= ((const OverworldWildBehaviorDataBlob *)blobBytes)
                    ->header.conditionEntryCount) {
            OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
        entry = &((const OverworldWildBehaviorDataBlob *)blobBytes)
            ->conditionEntries[prepared->catalogEntryIndexes[index]];

        if ((entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_ACTIVE) != 0
            && runtime->result.winningConditionIds[
                    entry->applicationIndex]
                == entry->conditionId) {
            if (entry->activationMode
                    == OVERWORLD_BEHAVIOR_CONDITION_TIMED) {
                timedWinningApplicationMask |=
                    1u << entry->applicationIndex;
            }
            if (entry->applicationIndex
                    == runtime->result.winningConditionSourceApplication) {
                winningEntryIndex = index;
                if (runtime->frame.traceArmed) {
                    winningTraceState =
                        ((entryFlags
                            & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED)
                                != 0
                            ? 1u << 12
                            : 0)
                        | ((entryFlags
                            & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE)
                                != 0
                            ? 1u << 13
                            : 0)
                        | (1u << 14)
                        | ((u16)entry->activationMode << 15);
                }
            }
        }
    }
    if (!OverworldBehaviorConditionAdapter_ResolveTarget(
            runtime, slot, outcome)) {
        OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    }

    timedWinningApplicationMaskBefore =
        runtime->timedWinningApplicationMasks[slot];
    runtime->timedWinningApplicationMasks[slot] =
        timedWinningApplicationMask;
    endedTimedApplicationMask =
        timedWinningApplicationMaskBefore
        & ~timedWinningApplicationMask;
    runtime->activeApplicationMasks[slot] =
        runtime->result.activeApplicationMask;
    if (endedTimedApplicationMask != 0) {
        outcome->flags |= OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED;
    }
    if (runtime->frame.traceArmed
        && winningEntryIndex
            != OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION) {
        OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD(
            &prepared->subject,
            &runtime->result,
            &prepared->states[winningEntryIndex],
            winningTraceState);
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

const OverworldBehaviorConditionAdapterEntry
    gOverworldBehaviorConditionAdapterEntry = {
        OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_MAGIC,
        OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION,
        sizeof(OverworldBehaviorConditionAdapterEntry),
        OverworldBehaviorConditionAdapter_PrepareActor,
        OverworldBehaviorConditionAdapter_ClearActor,
        OverworldBehaviorConditionAdapter_ClearAll,
        OverworldBehaviorConditionAdapter_ClearResolution,
        OverworldBehaviorConditionAdapter_EvaluateActor,
    };
