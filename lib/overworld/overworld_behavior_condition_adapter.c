#include "../../include/overworld_behavior_condition_adapter.h"
#include "../../include/overworld_condition_moving_notice_native.h"
#include "../../include/overworld_condition_subject_native.h"
#include "../../include/overworld_condition_publication_native.h"

#include "../../include/map_events_internal.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_query_code_addon_service.h"
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include "../../include/overworld_wild_runtime_state_internal.h"
#endif

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <stdlib.h>
#endif

#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
__asm__(".thumb\n.thumb_func\n.thumb_set OverworldConditionPublication_ChangedMask, 0x023C2FCC\n");
#endif

typedef u16 OverworldBehaviorConditionVisionWord
    __attribute__((may_alias));
typedef u16 OverworldBehaviorConditionHandleHalfword
    __attribute__((may_alias));
_Static_assert((offsetof(OverworldBehaviorConditionWorldView, reserved) + 1) % 2 == 0,
    "reachable Cargo mask must have halfword alignment");

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

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
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
#else
/* Boot-loaded overlay 161 has the same body at a fixed Thumb entry. The
 * actor adapter calls it directly, within the Thumb BL range. */
extern void OverworldBehaviorConditionAdapter_ClearResolution(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot);
__asm__(
    ".global OverworldBehaviorConditionAdapter_ClearResolution\n"
    ".thumb_func\n"
    ".thumb_set OverworldBehaviorConditionAdapter_ClearResolution, "
    "0x01FFBD01\n");
#endif

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
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
    memset(&runtime->bindings[slot], 0, sizeof(runtime->bindings[slot]));
    runtime->currentVisions[slot].range = 0;
    runtime->currentVisions[slot].options = 0;
    OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
}

#else
__asm__(
    ".global OverworldConditionSubject_ClearActor\n"
    ".thumb_func\n"
    ".thumb_set OverworldConditionSubject_ClearActor, 0x022082C0\n");
static void OverworldBehaviorConditionAdapter_ClearActor(
    OverworldWildBehaviorConditionRuntime *runtime, u8 slot)
{
    OverworldConditionSubject_ClearActor(runtime, slot);
}
#endif

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
    const OverworldWildBehaviorProfile *stableProfile,
    u8 slot,
    OverworldBehaviorConditionBuildContextFunc buildContext)
{
    const OverworldBehaviorConditionServiceEntry *service;
    OverworldBehaviorConditionStatus status;
    u16 vision;

    if (runtime == NULL || state == NULL || blobBytes == NULL
        || subject == NULL || stableProfile == NULL || buildContext == NULL
        || slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    service = OverworldBehaviorConditionAdapter_GetService();
    if (service == NULL) {
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
    vision = stableProfile->owner.visionRange
        | ((u16)((stableProfile->owner.visionCone
                      & OVERWORLD_VISION_CONE_MASK)
                     | (stableProfile->owner.visionAdjacentAwareness
                           ? OVERWORLD_VISION_ADJACENT_AWARENESS
                           : 0))
            << 8);
    *(OverworldBehaviorConditionVisionWord *)&runtime->currentVisions[slot] =
        vision;
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
    runtime->bindings[slot].subject = *subject;
    for (u8 name = 0; name < OVERWORLD_TARGET_BINDING_COUNT; name++) {
        runtime->bindings[slot].bindings[name].sourceConditionId =
            OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
        runtime->bindings[slot].bindings[name].sourceApplication =
            OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
        runtime->bindings[slot].bindings[name].reason = OVERWORLD_TARGET_BINDING_EMPTY;
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
static BOOL __attribute__((noinline, optimize("Os")))
OverworldBehaviorConditionAdapter_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    const OverworldBehaviorConditionHandleHalfword *leftValues =
        (const OverworldBehaviorConditionHandleHalfword *)left;
    const OverworldBehaviorConditionHandleHalfword *rightValues =
        (const OverworldBehaviorConditionHandleHalfword *)right;
    u8 index;

    /* World observations are only halfword aligned. ARM9 unaligned word
     * loads rotate data, so compare the native halfword fields. */
    for (index = 0; index < 5; index++) {
        if (leftValues[index] != rightValues[index]) {
            return FALSE;
        }
    }
    return TRUE;
}

#else
__asm__(
    ".global OverworldConditionSubject_HandleEquals\n"
    ".thumb_func\n"
    ".thumb_set OverworldConditionSubject_HandleEquals, 0x02208320\n");
#define OverworldBehaviorConditionAdapter_HandleEquals \
    OverworldConditionSubject_HandleEquals
#endif

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
static inline void __attribute__((always_inline))
OverworldBehaviorConditionAdapter_PopulateSubject(
    OverworldWildBehaviorConditionRuntime *runtime,
    FieldSystem *fieldSystem,
    const OverworldBehaviorConditionPreparedActor *prepared,
    const LocalMapObject *object,
    u8 slot,
    u8 subjectMovementSpeed,
    OverworldBehaviorConditionTerrainFunc terrainAt)
{
    OverworldBehaviorConditionWorldView *world = &runtime->frame.world;

    world->subjectTerrainMask = terrainAt(
        fieldSystem, object->xCurr, object->yCurr);
    world->subject = prepared->subject;
    world->subjectX = (s16)object->xCurr;
    world->subjectY = (s16)object->yCurr;
    world->subjectFacing = object->curFacing;
    world->subjectMovementSpeed = subjectMovementSpeed;
    world->subjectVisionRange = runtime->currentVisions[slot].range;
    world->subjectVisionOptions = runtime->currentVisions[slot].options;
    world->bindings = &runtime->bindings[slot];
    world->subjectRoleMask = 0;
    world->reservedBinding = 0;
    for (u8 index = 0; index < world->actorCount; index++) {
        if (world->actors[index].actor.slot == slot) {
            world->subjectRoleMask = runtime->frame.candidates[index].roleMask;
            break;
        }
    }
}

#else
/* Private Field leaf is resident. The explicit Thumb symbol avoids an ARM
 * veneer while keeping the original synchronous PopulateSubject call. */
__asm__(
    ".global OverworldConditionSubject_Populate\n"
    ".thumb_func\n"
    ".thumb_set OverworldConditionSubject_Populate, 0x02208200\n");
#define OverworldBehaviorConditionAdapter_PopulateSubject \
    OverworldConditionSubject_Populate
#endif

BOOL __attribute__((noinline, optimize("Os")))
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
    /* The actor list is compact. Every field read below actorCount is
     * replaced in this pass. Visibility replaces all player fields later. */
    frame->world.actorCount = 0;
    frame->actorSlotMask = 0;
    frame->world.frame = systemSnapshot->frame;
    frame->traceArmed = systemSnapshot->trace.armed;
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
        observation->facingAndOcclusion = spawn->object->curFacing;
        observation->visionRange = runtime->currentVisions[slot].range;
        observation->visionOptions = runtime->currentVisions[slot].options;
        candidate = &frame->candidates[index];
        candidate->reserved[0] = OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE;
        if (buildContext != NULL) {
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
        }
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
            if (buildContext != NULL) {
                candidate->roleMask =
                    actorRole == OVERWORLD_ACTOR_ROLE_MOUNTED
                        ? OVERWORLD_BEHAVIOR_CONDITION_TARGET_ROLE_MOUNTED
                        : OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER;
            }
        }
        frame->actorSlotMask |= 1u << slot;
        frame->world.actorCount++;
    }
    /* A binding read needs current positions, without resolving profiles.
     * The next condition evaluation must still populate candidate contexts. */
    frame->valid = buildContext != NULL;
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
    s16 targetX;
    s16 targetY;
    u16 targetBit = (u16)(1u << slot);
    u8 index;

    runtime->targetValidMask &= (u16)~targetBit;
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
        return TRUE;
    }
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
        if (!frame->world.playerValid) {
            return FALSE;
        }
        targetX = frame->world.playerX;
        targetY = frame->world.playerY;
    } else {
        if (target->kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
            return FALSE;
        }
        for (index = 0; index < frame->world.actorCount; index++) {
            const OverworldBehaviorConditionActorObservation *actor =
                &frame->world.actors[index];

            if (OverworldBehaviorConditionAdapter_HandleEquals(
                    &target->actor, &actor->actor)) {
                targetX = actor->x;
                targetY = actor->y;
                goto resolved;
            }
        }
        return FALSE;
    }

resolved:
    runtime->targetX[slot] = targetX;
    runtime->targetY[slot] = targetY;
    outcome->targetDx = targetX - frame->world.subjectX;
    outcome->targetDy = targetY - frame->world.subjectY;
    runtime->targetValidMask |= targetBit;
    return TRUE;
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
    const OverworldWildBehaviorProfile *observedProfile,
    OverworldBehaviorConditionObserveFunc observe,
    int forcedOverrideProfileIndex,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    OverworldBehaviorConditionIsCurrentSpawnFunc isCurrentSpawn,
    OverworldBehaviorConditionTerrainFunc terrainAt,
    OverworldBehaviorConditionPopulateVisibilityFunc populateVisibility,
    OverworldBehaviorConditionAdapterOutcome *outcome)
{
    const OverworldBehaviorConditionServiceEntry *service;
    const OverworldQueryCodeAddonEntry *addon;
    OverworldQueryCodeAddonOwner addonOwner;
    OverworldConditionNativeCall nativeCall;
    OverworldBehaviorConditionPreparedActor *prepared;
    OverworldWildSpawn *spawn;
    LocalMapObject *object;
    OverworldBehaviorConditionStatus status;
    u32 interactionObservation;
    u32 timedWinningApplicationMask = 0;
    u32 timedWinningApplicationMaskBefore;
    u32 endedTimedApplicationMask;
    u16 winningTraceState = 0;
    u8 winningEntryIndex = OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;

    if (runtime == NULL || state == NULL || fieldSystem == NULL
        || blobBytes == NULL || buildContext == NULL
        || isCurrentSpawn == NULL || terrainAt == NULL
        || populateVisibility == NULL || outcome == NULL
        || slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    service = OverworldBehaviorConditionAdapter_GetService();
    if (service == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    memset(outcome, 0, sizeof(*outcome));
    prepared = &runtime->actors[slot];
    spawn = &state->spawns[slot];
    object = spawn->object;
    if (!OverworldBehaviorConditionAdapter_BuildFrame(
            state, fieldSystem, runtime, buildContext, isCurrentSpawn)
        || (runtime->frame.actorSlotMask & (1u << slot)) == 0) {
        OverworldBehaviorConditionAdapter_ClearActor(runtime, slot);
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    }

    /* The public gate proves this compiled private table's lifetime. Acquire
     * then checks the exact Field, epoch, map and loaded package before use. */
    addonOwner = (OverworldQueryCodeAddonOwner){(u32)(uintptr_t)fieldSystem,
        runtime->actors[slot].subject.fieldEpoch, runtime->actors[slot].subject.mapGeneration};
    addon = ((const OverworldQueryCodeAddonServiceEntry *)OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR)->acquire(&addonOwner);
    if (addon == NULL) return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    nativeCall=(OverworldConditionNativeCall){
        .runtime=runtime,.state=state,.field=fieldSystem,.blob=blobBytes,.blobSize=blobSize,
        .observedProfile=observedProfile,.observe=observe,.buildContext=buildContext,.terrainAt=terrainAt,
        .forcedProfileIndex=forcedOverrideProfileIndex,.version=OVERWORLD_CONDITION_NATIVE_CALL_VERSION,
        .size=sizeof(nativeCall),.slot=slot,.movementSpeed=subjectMovementSpeed,
    };
    if (forcedOverrideProfileIndex == OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE) {
        nativeCall.operation=OVERWORLD_CONDITION_NATIVE_MOVING;
        status=addon->conditionNative(&nativeCall);
        if (status!=OVERWORLD_BEHAVIOR_CONDITION_OK || !nativeCall.reservedOutput) return status;
    } else {
    buildContext(
        &runtime->context,
        spawn,
        0,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    runtime->context.behaviorClass = state->movementBehaviorClasses[slot];
    OverworldBehaviorConditionAdapter_PopulateSubject(
        runtime,
        fieldSystem,
        prepared,
        object,
        slot,
        subjectMovementSpeed,
        terrainAt);
    populateVisibility(fieldSystem, &runtime->frame.world);
    addon->playerDamageRead(runtime, state, fieldSystem, slot, NULL);
    /* Observation borrows the validated current Frame. Warm Cargo route
     * work retains accepted motion and its authored pause; restore this same
     * synchronous mode before evaluating prepared entries. */
    if (forcedOverrideProfileIndex == OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO) {
        runtime->frame.world.reservedBinding =
            OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;
    }
    interactionObservation = observe != NULL
        ? observe(state, slot, observedProfile, blobBytes, runtime) : 0;
    runtime->frame.world.reserved[0] = (u8)interactionObservation;
    *(OverworldBehaviorConditionVisionWord *)&runtime->frame.world.reserved[1] =
        (u16)(interactionObservation >> 8);
    runtime->frame.world.incomingClaimMask = (u16)(interactionObservation >> 18);
    if (forcedOverrideProfileIndex == OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO) {
        runtime->frame.world.reservedBinding = 1;
    }
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
    if (runtime->frame.world.reservedBinding) {
        runtime->frame.world.reservedBinding = 0;
        return status;
    }
    if (status != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
        return status;
    }
    }

    status=addon->conditionNative(&nativeCall);
    if(status!=OVERWORLD_BEHAVIOR_CONDITION_OK) {
        OverworldBehaviorConditionAdapter_ClearResolution(runtime,slot);
        return status;
    }
    if (OverworldConditionPublication_ChangedMask(runtime, slot)) {
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
    }
    if (runtime->result.triggeredApplicationMask != 0)
        outcome->flags |= OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED;
    outcome->flags |= ((nativeCall.reservedOutput & 2) << 3)
        | ((nativeCall.reservedOutput & 4) >> 1);

    addon->playerDamageRead(runtime, state, fieldSystem, slot, blobBytes);
    if (!OverworldBehaviorConditionAdapter_ResolveTarget(
            runtime, slot, outcome)) {
        OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    }
    timedWinningApplicationMask=nativeCall.timedWinningApplicationMask;
    winningEntryIndex=nativeCall.winningEntryIndex;
    winningTraceState=nativeCall.winningTraceState;

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
    if (forcedOverrideProfileIndex == OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE)
        outcome->flags |= OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_MOVING_EVALUATED;
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
