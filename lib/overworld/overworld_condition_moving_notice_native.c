#include "../../include/overworld_condition_moving_notice_native.h"
#include "../../include/overworld_vision.h"
#include "../../include/overworld_pickup_route_wild.h"
#include "../../include/overworld_hop_presentation_native.h"
#include "../../include/overworld_application_bank.h"
#include "../../include/overworld_condition_publication_native.h"
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/pokemon.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_wild_movement.h"
#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)((state)->movementRuntimeState))
#endif

extern BOOL OverworldBehaviorCondition_BuildRequest(OverworldWildBehaviorConditionRuntime *, int, const OverworldWildBehaviorDataBlob *);
extern void OverworldPlayerDamageCondition_Read(OverworldWildBehaviorConditionRuntime *,
    OverworldWildSpawnState *, FieldSystem *, u8, const OverworldWildBehaviorDataBlob *);
extern void OverworldConditionSubject_Populate(OverworldWildBehaviorConditionRuntime *, FieldSystem *,
    const OverworldBehaviorConditionPreparedActor *, const LocalMapObject *, u8, u8,
    OverworldBehaviorConditionTerrainFunc);
extern int OverworldConditionVisibility_PlayerX(FIELD_PLAYER_AVATAR *);
extern int OverworldConditionVisibility_PlayerY(FIELD_PLAYER_AVATAR *);
extern BOOL OverworldConditionVisibility_TraceBlocked(FieldSystem *,
    const OverworldBehaviorConditionWorldView *, s16, s16);

typedef u16 NativeHandleHalfword __attribute__((may_alias));
typedef u16 NativeVisionWord __attribute__((may_alias));
static BOOL Native_HandleEquals(const OverworldActorHandle *a,const OverworldActorHandle *b)
{
    const NativeHandleHalfword *x=(const NativeHandleHalfword *)a,*y=(const NativeHandleHalfword *)b;
    for(u8 i=0;i<5;i++)if(x[i]!=y[i])return FALSE;
    return TRUE;
}

/* Target access is a current physical fact, not a Vision rule or path search.
 * These reads share the native route's terrain/support callbacks; they never
 * inspect occupancy, reserve a tile, or replace an accepted movement plan. */
static LocalMapObject *Native_AccessObject(
    const OverworldConditionNativeCall *call,
    const OverworldActorSystemState *system,
    const OverworldActorHandle *handle)
{
    if (handle->slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || handle->reserved || !handle->generation
        || handle->fieldEpoch != system->fieldEpoch
        || handle->mapGeneration != system->mapGeneration) return NULL;
    const OverworldWildSpawn *spawn = &call->state->spawns[handle->slot];
    const OverworldActorStateSnapshot *actor = &system->slots[handle->slot].snapshot;
    const OverworldBehaviorConditionPreparedActor *prepared = &call->runtime->actors[handle->slot];
    LocalMapObject *object = spawn->object;
    if (!prepared->valid || prepared->subject.reserved
        || !Native_HandleEquals(handle, &prepared->subject)
        || !spawn->active || spawn->encounterGeneration != handle->encounterGeneration
        || !actor->active || actor->handle.reserved
        || !Native_HandleEquals(handle, &actor->handle)
        || actor->subjectIdentity != spawn->personality
        || object == NULL || !(object->flags & 1u)
        || !call->targetAccessWorld->ops->currentObject(call->field, object)) return NULL;
    return object;
}

/* One immediate support call may be reused only with its original input.
 * Terrain and both current identities are still read on every invocation. */
typedef struct NativeSupportQueryKey {
    s32 baseY;
    u32 flags;
} NativeSupportQueryKey;

static BOOL Native_AccessPose(OverworldPickupRouteWildWorld *world,
    const OverworldPickupRouteNativeSeams *seams,
    const OverworldActorRuntimeSlot *actor, LocalMapObject *object,
    OverworldPickupRoutePosition *pose, OverworldPickupRouteNativeTile *tile,
    NativeSupportQueryKey *supportInput)
{
    s32 anchor = (s32)object->posVec[1];
    BOOL exactAnchor = TRUE;
    const OverworldMotionState *motion = &actor->motion;
    if (motion->phase != OVERWORLD_MOTION_PHASE_IDLE) {
        const OverworldMotionPlan *plan = &motion->plan;
        if (plan->version != OVERWORLD_MOTION_MODEL_VERSION
            || plan->fieldEpoch != actor->snapshot.handle.fieldEpoch
            || !plan->reservationId
            || (plan->reservationId != actor->snapshot.reservationId
                && !(motion->phase == OVERWORLD_MOTION_PHASE_SETTLING
                    && motion->commitPublished
                    && actor->snapshot.reservationId == 0
                    && object->xCurr == plan->targetX
                    && object->yCurr == plan->targetY))) return FALSE;
        /* Logical endpoints retain their accepted physical support while a
         * Hop adds render height. At an intermediate committed Walk tile the
         * canonical height read determines support from the accepted origin. */
        anchor = plan->startBaseY;
        if (object->xCurr == plan->targetX && object->yCurr == plan->targetY
            && (motion->commitPublished || object->xCurr != plan->startX
                || object->yCurr != plan->startY)) anchor = plan->targetBaseY;
        else if (object->xCurr != plan->startX || object->yCurr != plan->startY)
            exactAnchor = FALSE;
    }
    *pose = (OverworldPickupRoutePosition){object->xCurr, object->yCurr, anchor, 0, 0};
    world->heightObject = object;
    world->routeRead = 1; /* Missing support must not use START's old-height fallback. */
    if (seams->terrain(world, pose->x, pose->y, 0xFFFF, tile)
            != OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
        || tile->reserved || (tile->flags & ~7u)) return FALSE;
    /* Capture before support can replace baseY at an intermediate Walk tile. */
    if (supportInput != NULL) {
        supportInput->baseY = pose->baseY;
        supportInput->flags = object->flags & OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK;
    }
    if (seams->support(world, pose, pose->x, pose->y, tile, &pose->baseY)
            != OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
        || (exactAnchor && pose->baseY != anchor)) return FALSE;
    pose->surfaceId = tile->surfaceId;
    return TRUE;
}

static OverworldBehaviorConditionStatus Native_TargetAccess(OverworldConditionNativeCall *call)
{
    OverworldWildBehaviorConditionFrame *frame = &call->runtime->frame;
    OverworldPickupRouteWildWorld *borrowed = call->targetAccessWorld;
    const OverworldPickupRouteNativeSeams *seams;
    const OverworldActorSystemState *system;
    OverworldPickupRouteWildWorld world;
    OverworldPickupRoutePosition origin, target;
    OverworldPickupRouteNativeTile tile;
    LocalMapObject *subject;
    const OverworldBehaviorConditionPreparedActor *prepared = &call->runtime->actors[call->slot];
    BOOL needsActorTarget = FALSE;

    if (frame->world.actorCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    for (u8 i = 0; i < frame->world.actorCount; i++)
        frame->candidates[i].reserved[0] |= OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE;
    if (call->blobSize != sizeof(*call->blob)
        || !prepared->valid || prepared->count > prepared->stateCapacity
        || prepared->count > OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        || (prepared->count && prepared->states == NULL))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    if (borrowed == NULL || call->state == NULL || call->field == NULL
        || call->state->movementFieldSystem != call->field
        || borrowed->state != call->state || borrowed->field != call->field
        || borrowed->slot != call->slot || borrowed->landingPolicy
        || call->allowedTerrainMask > OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_POLICY_ALL)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    /* Player-only and disabled inactive rows need no target-world work.
     * The shared reducer still owns truth, chance, lifetime and selection. */
    for (u8 i = 0; i < prepared->count; i++) {
        u16 index = prepared->catalogEntryIndexes[i];
        if (index >= call->blob->header.conditionEntryCount)
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        /* Warm evaluation uses only reachable Cargo ActorFacts rows. Other
         * conditions still receive fresh physical access in normal modes. */
        if (frame->world.reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO
            && (call->blob->conditionEntries[index].kind != OW_WILD_BEHAVIOR_CONDITION_ACTOR_FACTS
                || call->blob->conditionOptions[index].captureBinding != OVERWORLD_TARGET_BINDING_CARGO+1
                || !call->blob->conditionOptions[index].mustBeReachableForPickup)) continue;
        if (call->blob->conditionEntries[index].targetKind == OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR
            && OverworldBehaviorCondition_RoleApplies(call->blob->conditionOptions[index].subjectRoleMask,
                frame->world.subjectRoleMask)
            && (call->blob->conditionEntries[index].chancePercent
                || (prepared->states[i].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)))
            needsActorTarget = TRUE;
    }
    if (!needsActorTarget) return OVERWORLD_BEHAVIOR_CONDITION_OK;
    if ((seams = OverworldPickupRouteWild_GetSeams(borrowed)) == NULL)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    system = borrowed->ops->actorState();
    if (system == NULL || system->magic != OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        || system->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || system->size != sizeof(*system) || system->frame != frame->world.frame)
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    subject = Native_AccessObject(call, system, &frame->world.subject);
    if (subject == NULL || subject != borrowed->subjectObject
        || frame->world.subject.slot != call->slot)
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    world = *borrowed;
    if (!Native_AccessPose(&world, seams, &system->slots[call->slot], subject,
            &origin, &tile, NULL)) return OVERWORLD_BEHAVIOR_CONDITION_OK;
    for (u8 i = 0; i < frame->world.actorCount; i++) {
        const OverworldBehaviorConditionActorObservation *observation = &frame->world.actors[i];
        LocalMapObject *object;
        s32 subjectSupport;
        NativeSupportQueryKey targetInput;
        u16 mask = (u16)call->allowedTerrainMask;
        if (!observation->valid
            || (object = Native_AccessObject(call, system, &observation->actor)) == NULL
            || observation->actor.slot == frame->world.subject.slot
            || object->xCurr != observation->x || object->yCurr != observation->y
            || !Native_AccessPose(&world, seams, &system->slots[observation->actor.slot],
                object, &target, &tile, &targetInput)) continue;
        /* An authored surface always needs its real surface permission.
         * Positional Interest admits supported native ground only. It cannot
         * turn Signpost/Rooftop/Canopy into an allowed destination. */
        if (!(tile.terrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL)
            && tile.surfaceId == OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND
            && (mask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST))
            mask |= OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
        mask &= ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST;
        u16 physicalMask = tile.terrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL;
        if (!(mask & (physicalMask ? physicalMask : tile.terrainMask))) continue;
        world.heightObject = subject;
        /* Same Field, XY, current terrain/support hit, routeRead and native
         * callback; only the input anchor and height flags can differ here. */
        if (targetInput.baseY == origin.baseY
            && targetInput.flags == (subject->flags & OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK))
            subjectSupport = target.baseY;
        else if (seams->support(&world, &origin, target.x, target.y, &tile, &subjectSupport)
                != OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL) continue;
        if (subjectSupport != target.baseY) continue;
        frame->candidates[i].reserved[0] &= ~OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE;
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

/* Fresh positions first; native solid traces only after the shared authored
 * condition core has selected the eligible geometric candidate mask. */
static void Native_Visibility(FieldSystem *field,OverworldBehaviorConditionWorldView *world)
{
    FIELD_PLAYER_AVATAR *avatar=field->playerAvatar;
    u16 mask=world->reservedBinding==OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING_NOTICE
        ? (u16)world->reserved[1]|((u16)world->reserved[2]<<8) : 0;
    world->playerValid=avatar!=NULL;
    world->playerFacingAndOcclusion=0;
    world->playerVisionRange=OVERWORLD_VISION_DEFAULT_RANGE;
    world->playerVisionOptions=OVERWORLD_VISION_DEFAULT_OPTIONS;
    if(avatar!=NULL){
        world->playerX=(s16)OverworldConditionVisibility_PlayerX(avatar);
        world->playerY=(s16)OverworldConditionVisibility_PlayerY(avatar);
        world->playerFacingAndOcclusion=avatar->mapObject!=NULL?avatar->mapObject->curFacing:OVERWORLD_VISION_FACING_SOUTH;
        if((mask&OVERWORLD_BEHAVIOR_CONDITION_NOTICE_PLAYER_MASK)
            && OverworldConditionVisibility_TraceBlocked(field,world,world->playerX,world->playerY))
            world->playerFacingAndOcclusion|=OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT
                |OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT;
    }
    for(u8 i=0;i<world->actorCount;i++){
        OverworldBehaviorConditionActorObservation *actor=&world->actors[i];
        actor->facingAndOcclusion&=~(OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT
            | OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT);
        if(actor->valid && actor->actor.slot<OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
            && (mask&(1u<<actor->actor.slot))
            && OverworldConditionVisibility_TraceBlocked(field,world,actor->x,actor->y))
            actor->facingAndOcclusion|=OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT
                |OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT;
    }
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldBehaviorConditionAdapter_MovingAllowed(
    const OverworldWildBehaviorConditionRuntime *runtime,
    const OverworldWildSpawnState *state, u8 slot)
{
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
    /* Host integration supplies the native current-motion admission seam. */
    (void)runtime; (void)state; (void)slot;
    return TRUE;
#else
    const OverworldActorSystemState *system =
        (const OverworldActorSystemState *)OVERWORLD_ACTOR_SYSTEM_STATE_ADDR;
    const OverworldActorRuntimeSlot *actor = &system->slots[slot];
    const OverworldWildOverlayRuntimeState *movement = state->movementRuntimeState;
    const OverworldMotionPlan *plan = &actor->motion.plan;
    const OverworldActorHandle *subject = &runtime->actors[slot].subject;
    return movement != NULL && system->magic == OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        && system->version == OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        && system->size == sizeof(*system)
        && system->fieldEpoch == subject->fieldEpoch
        && system->mapGeneration == subject->mapGeneration
        && system->frame == runtime->frame.world.frame
        && actor->snapshot.active && !actor->snapshot.inputOwnership
        && actor->snapshot.subjectIdentity == state->spawns[slot].personality
        && !subject->reserved && !actor->snapshot.handle.reserved
        && Native_HandleEquals(subject, &actor->snapshot.handle)
        && (actor->motion.phase == OVERWORLD_MOTION_PHASE_MOVING
            || actor->motion.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING
            || actor->motion.phase == OVERWORLD_MOTION_PHASE_SETTLING)
        && plan->kind > OVERWORLD_MOTION_KIND_NONE && plan->kind < OVERWORLD_MOTION_KIND_FLY_IN
        && plan->fieldEpoch == subject->fieldEpoch && plan->reservationId != 0
        && plan->reservationId == movement->movementMotionIdentities[slot]
        && !(plan->flags & OVERWORLD_MOTION_FLAG_FORCED);
#endif
}

static OverworldBehaviorConditionStatus __attribute__((noinline, optimize("Os")))
OverworldBehaviorConditionAdapter_EvaluateMovingNotice(
    OverworldWildBehaviorConditionRuntime *runtime, OverworldWildSpawnState *state,
    FieldSystem *fieldSystem, const void *blobBytes, u32 blobSize, u8 slot,
    u8 subjectMovementSpeed, const OverworldWildBehaviorProfile *observedProfile,
    OverworldBehaviorConditionObserveFunc observe,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    OverworldBehaviorConditionTerrainFunc terrainAt,
    OverworldBehaviorConditionPopulateVisibilityFunc populateVisibility,
    u8 *evaluated)
{
    OverworldBehaviorConditionPreparedActor *prepared = &runtime->actors[slot];
    OverworldWildSpawn *spawn = &state->spawns[slot];
    LocalMapObject *object = spawn->object;
    OverworldBehaviorConditionStatus status;
    u32 interactionObservation;

    if ((prepared->count > OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
            || prepared->count > prepared->stateCapacity
            || (prepared->count && prepared->states == NULL)))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    if (!OverworldBehaviorConditionAdapter_MovingAllowed(runtime, state, slot)) {
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    }

    buildContext(
        &runtime->context,
        spawn,
        0,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    runtime->context.behaviorClass = state->movementBehaviorClasses[slot];
    OverworldConditionSubject_Populate(
        runtime,
        fieldSystem,
        prepared,
        object,
        slot,
        subjectMovementSpeed,
        terrainAt);
    runtime->frame.world.reservedBinding = OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY;
    populateVisibility(fieldSystem, &runtime->frame.world);
    OverworldPlayerDamageCondition_Read(runtime, state, fieldSystem, slot, NULL);
    interactionObservation = observe != NULL
        ? observe(state, slot, observedProfile, blobBytes, runtime) : 0;
    runtime->frame.world.reserved[0] = (u8)interactionObservation;
    *(NativeVisionWord *)&runtime->frame.world.reserved[1] =
        (u16)(interactionObservation >> 8);
    runtime->frame.world.incomingClaimMask = (u16)(interactionObservation >> 18);
    runtime->frame.world.reservedBinding = OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY;
    status = OverworldBehaviorCondition_EvaluatePrepared(blobBytes, blobSize, prepared,
        &runtime->frame.world, runtime->frame.candidates,
        runtime->frame.world.actorCount, runtime->frame.world.frame,
        &runtime->scratch, &runtime->result);
    if (status != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        runtime->frame.world.reservedBinding = 0;
        return status;
    }
    /* Geometry and chance select only targets that need a native solid
     * tile trace. No timer, capture or published lane changed above. */
    *(NativeVisionWord *)&runtime->frame.world.reserved[1] =
        (u16)(runtime->result.activeApplicationMask
            | runtime->result.triggeredApplicationMask);
    runtime->frame.world.reservedBinding = OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING_NOTICE;
    populateVisibility(fieldSystem, &runtime->frame.world);
    /* The visibility mask is transient. Pickup admission needs the original
     * routed eligibility from this same observation, not the trace mask. */
    *(NativeVisionWord *)&runtime->frame.world.reserved[1] =
        (u16)(interactionObservation >> 8);
    status = OverworldBehaviorCondition_EvaluatePrepared(
        blobBytes,
        blobSize,
        prepared,
        &runtime->frame.world,
        runtime->frame.candidates,
        runtime->frame.world.actorCount,
        runtime->frame.world.frame,
        &runtime->scratch,
        &runtime->result);
    runtime->frame.world.reservedBinding = 0;
    if (status == OVERWORLD_BEHAVIOR_CONDITION_OK) *evaluated = 1;
    return status;
}

static u32 __attribute__((noinline, optimize("Os")))
OverworldBehaviorConditionAdapter_CollectWinningEntries(
    OverworldWildBehaviorConditionRuntime *runtime,
    const OverworldBehaviorConditionPreparedActor *prepared,
    const void *blobBytes, u8 *winningEntryIndex, u16 *winningTraceState,
    u8 *pendingTargetEntry)
{
    u32 timedWinningApplicationMask = 0;
    const OverworldWildBehaviorDataBlob *blob = blobBytes;
    OverworldApplicationBank bank;
    u8 index;

    if (!OverworldApplicationBank_Select(blob, prepared->subjectSpecies, &bank))
        return 0;

    for (index = 0; index < prepared->count; index++) {
        const OverworldWildBehaviorConditionEntry *entry;
        u16 sourceIndex = prepared->catalogEntryIndexes[index];
        int localApplication;
        u8 entryFlags = runtime->scratch.entryFlags[index];

        /* The authenticated prepared evaluator validates all source indexes
         * before any state mutation; no later call changes this prepared list. */
        if (sourceIndex >= blob->header.conditionEntryCount)
            return 0;
        entry = &blob->conditionEntries[sourceIndex];
        localApplication = OverworldApplicationBank_Local(&bank,
            blob->conditionGlobalApplications[sourceIndex]);
        if (localApplication < 0) return 0;
        if (entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TIMED_ENDED)
            *pendingTargetEntry |= 4;

        if ((entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_ACTIVE) != 0
            && runtime->result.winningConditionIds[
                    localApplication]
                == entry->conditionId) {
            if ((entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PRESENTATION_ENTERED)
                && entry->conditionId == runtime->result.resolvedTargetConditionId)
                *pendingTargetEntry |= 2;
            if (entry->activationMode
                    == OVERWORLD_BEHAVIOR_CONDITION_TIMED) {
                timedWinningApplicationMask |=
                    1u << localApplication;
            }
            if (localApplication
                    == runtime->result.winningConditionSourceApplication) {
                *winningEntryIndex = index;
                if (runtime->frame.traceArmed) {
                    *winningTraceState =
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
                        | (entry->activationMode
                                == OVERWORLD_BEHAVIOR_CONDITION_TIMED
                            ? 1u << 15 : 0);
                }
            }
        }
    }
    return timedWinningApplicationMask;
}


#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
/* This synchronous presentation leaf borrows adapter state and callbacks.
 * It cannot acquire code, retain a pointer, or start another motion engine. */
OverworldBehaviorConditionStatus OverworldHopPresentation_Run(OverworldConditionNativeCall *call)
{
    const OverworldHopPresentationOps *ops = call->hopOps;
    if (call->field == NULL || ops == NULL || ops->choices == NULL)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    if (call->operation == OVERWORLD_HOP_PRESENTATION_WILD_INIT) {
        OverworldWildSpawnState *state = call->state;
        LocalMapObject *object = call->hopObject;
        u8 slot = call->slot, direction = call->hopDirection;
        if (state == NULL || slot >= OW_WILD_MAX_SPAWNS || object == NULL
            || state->movementFieldSystem != call->field
            || !state->spawns[slot].active || state->spawns[slot].object != object
            || state->movementSpotStates[slot] != call->hopRequiredState
            || (object->flags & MAPOBJECTFLAG_SINGLE_MOVEMENT) != 0
            || !call->hopCount || ops->startNext == NULL || ops->ensureFrame == NULL)
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
        if (direction > 3) direction = object->curFacing <= 3 ? object->curFacing : 1;
        state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_EMOTING;
        state->movementEmoteJumpsRemaining[slot] = call->hopCount;
        state->movementEmoteTimers[slot] = OVERWORLD_HOP_PRESENTATION_FRAMES * call->hopCount;
        state->movementEmoteSteps[slot] = OVERWORLD_HOP_PRESENTATION_PREP;
        state->movementEmoteDirections[slot] = direction;
        state->movementEmoteEndStates[slot] = call->hopRequiredState;
        state->movementEmoteBubbleIds[slot] = OVERWORLD_HOP_PRESENTATION_NONE;
        state->movementEmoteShowBubbleEachJump[slot] = FALSE;
        state->movementEmotePlayCryOnHop[slot] = FALSE;
        OW_WILD_RUNTIME(state)->movementEmotePlayHopSound[slot] = call->hopOptions & 1u;
        state->movementBattleSettleFrames = 0;
        ops->startNext(state, slot, object);
        if (call->hopOptions & 0x20u) {
            u8 effects = ops->choices(call->hopOptions >> 1);
            if (effects & 1u) state->movementEmoteBubbleIds[slot] = OVERWORLD_HOP_PRESENTATION_HEART;
            state->movementEmotePlayCryOnHop[slot] = effects >> 1;
            state->movementEmoteShowBubbleEachJump[slot] = TRUE;
        }
        ops->ensureFrame(state, call->field);
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    }
    OverworldMountRuntimeState *state = call->hopMount;
    if (state == NULL || state->fieldSystem != call->field)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    u8 *action = (u8 *)(void *)&state->reservedPriorFollowerPolicy;
    if (call->operation == OVERWORLD_HOP_PRESENTATION_MOUNT_FINISH) {
        if (action[0] == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) action[3] &= ~8u;
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    }
    if (call->operation != OVERWORLD_HOP_PRESENTATION_MOUNT_TICK
        || ops->follower == NULL || ops->cry == NULL || ops->heart == NULL)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    if (state->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_HOP
        && state->walkEndState == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP
        && action[0] == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE
        && !(action[3] & 8u)) {
        LocalMapObject *follower = ops->follower();
        if (follower != NULL) {
            if (!(action[3] & 4u)) {
                const OverworldWildBehaviorProfileData *lane = &state->snapshot.profile;
                action[3] = 4u | ops->choices(
                    OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_HEART_CHANCE(lane->chainRepositionJumpCount)
                    | (OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_CRY_CHANCE(lane->onReachAction) << 2));
            }
            action[3] |= 8;
            if (action[3] & 2u) ops->cry(state->snapshot.binding.species, state->snapshot.binding.form);
            if (action[3] & 1u) ops->heart(follower, OVERWORLD_HOP_PRESENTATION_HEART);
        }
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

#endif

/* The capacity owner supplies an authenticated current subject's local map.
 * This operation borrows it and the blob for one call; no result is cached.
 * Arc composition follows ascending global order, with the last present group
 * replacing the whole Arc. A later application without a group inherits. */
static OverworldBehaviorConditionStatus Native_HopArcLookup(
    OverworldConditionNativeCall *call)
{
    const OverworldWildBehaviorDataBlob *blob = call->blob;
    OverworldWildBehaviorConditionRuntime *runtime = call->runtime;
    const u16 *ids = call->hopArcApplicationIds;
    u8 count = call->hopArcApplicationCount;
    u32 applied;
    int local, record;
    const OverworldWildHopArcRecord *winner = NULL;
    if (call->field == NULL || blob == NULL || runtime == NULL
        || call->slot >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || !OverworldConditionPublication_BlobValid(blob, call->blobSize)
        || count > 32 || (count && ids == NULL)
        || !runtime->frame.valid || runtime->frame.world.subject.reserved
        || !runtime->actors[call->slot].valid
        || runtime->actors[call->slot].subject.reserved
        || runtime->actors[call->slot].subject.slot != call->slot
        || !Native_HandleEquals(&runtime->actors[call->slot].subject,
            &runtime->frame.world.subject))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    call->hopArcPacked = 0;
    call->hopArcApplicationId = 0xFFFF;
    call->winningEntryIndex = 0xFF;
    call->reservedOutput = 0;
    /* Unknown local bits cannot become another application's Arc. */
    if (count < 32 && (call->hopArcAppliedMask >> count))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    for (record = 0; record < OWBD_HOP_ARC_RECORD_COUNT; record++)
        if (blob->hopArcs[record].globalApplicationId == 0xFFFF
            || (record && blob->hopArcs[record].globalApplicationId
                <= blob->hopArcs[record - 1].globalApplicationId))
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    applied = call->hopArcAppliedMask & runtime->activeApplicationMasks[call->slot];
    record = 0;
    /* Validate and select in one forward map pass. Later present groups replace
     * the whole result; a zero record remains a selected explicit none. */
    for (local = 0; local < count; local++, applied >>= 1) {
        if (ids[local] == 0xFFFF || (local && ids[local] <= ids[local - 1]))
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        while (record < OWBD_HOP_ARC_RECORD_COUNT
            && blob->hopArcs[record].globalApplicationId < ids[local]) record++;
        if (record < OWBD_HOP_ARC_RECORD_COUNT
            && blob->hopArcs[record].globalApplicationId == ids[local]
            && (applied & 1u)) {
            winner = &blob->hopArcs[record];
            call->winningEntryIndex = (u8)local;
        }
    }
    if (winner != NULL) {
        if ((winner->riseFrames || winner->hangFrames || winner->dropFrames || winner->peakQ4)
            && (!winner->riseFrames || !winner->dropFrames || !winner->peakQ4
                || (u16)winner->riseFrames + winner->hangFrames + winner->dropFrames > 255))
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        call->hopArcApplicationId = winner->globalApplicationId;
        call->hopArcPacked = (u32)winner->riseFrames | ((u32)winner->hangFrames << 8)
            | ((u32)winner->dropFrames << 16) | ((u32)winner->peakQ4 << 24);
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

OverworldBehaviorConditionStatus OverworldConditionNative_Run(OverworldConditionNativeCall *call)
{
    OverworldBehaviorConditionPreparedActor *prepared;
    if(call==NULL || call->version!=OVERWORLD_CONDITION_NATIVE_CALL_VERSION
        || call->size!=sizeof(*call) || call->reserved)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    if (call->operation == OVERWORLD_CONDITION_NATIVE_HOP_ARC_LOOKUP)
        return Native_HopArcLookup(call);
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
    if (call->operation >= OVERWORLD_HOP_PRESENTATION_WILD_INIT
        && call->operation <= OVERWORLD_HOP_PRESENTATION_MOUNT_FINISH)
        return OverworldHopPresentation_Run(call);
#endif
    if (call->operation>OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS
        || call->runtime==NULL || call->blob==NULL || call->slot>=OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS)
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    if (call->operation == OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS)
        return Native_TargetAccess(call);
    call->timedWinningApplicationMask=0;
    call->winningTraceState=0;
    call->winningEntryIndex=OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
    call->reservedOutput=0;
    prepared=&call->runtime->actors[call->slot];
    if(!prepared->valid || prepared->count>OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        || prepared->count>prepared->stateCapacity || (prepared->count && prepared->states==NULL))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    if(call->operation==OVERWORLD_CONDITION_NATIVE_MOVING){
        if(call->state==NULL || call->field==NULL || call->buildContext==NULL || call->terrainAt==NULL)
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
        OverworldBehaviorConditionStatus status=OverworldBehaviorConditionAdapter_EvaluateMovingNotice(call->runtime,call->state,call->field,
            call->blob,call->blobSize,call->slot,call->movementSpeed,call->observedProfile,call->observe,
            call->buildContext,call->terrainAt,Native_Visibility,&call->reservedOutput);
        if(status==OVERWORLD_BEHAVIOR_CONDITION_OK && call->reservedOutput)
            call->operation=OVERWORLD_CONDITION_NATIVE_NORMAL;
        return status;
    }
    if (!OverworldBehaviorCondition_BuildRequest(call->runtime,
        call->forcedProfileIndex == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT
            ? call->runtime->frame.world.subjectRoleMask == OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER
                ? OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER : -1
            : call->forcedProfileIndex, call->blob))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    call->timedWinningApplicationMask=OverworldBehaviorConditionAdapter_CollectWinningEntries(
        call->runtime,prepared,call->blob,&call->winningEntryIndex,&call->winningTraceState,
        &call->reservedOutput);
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}
