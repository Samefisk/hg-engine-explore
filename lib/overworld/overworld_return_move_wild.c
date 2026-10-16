#include "../../include/overworld_return_move_wild.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_combat.h"

#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)(state)->movementRuntimeState)
#define OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING 2
#define OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING 4
#define OW_WILD_RUNTIME_ORDINARY_HOP_PENDING 1
#define OW_WILD_RUNTIME_ORDINARY_WALK_PENDING 3
#define OW_WILD_SPAWNER_STAGED_WALK_PENDING 3
#define OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG 0x80
#define OW_WILD_CUSTOM_MOTION_WALK 1
#define OW_WILD_SPAWNER_THROW_TARGET_NONE 0

/* Borrow the same resident Combat admission used by Wild. Keeping this
 * phase clear beside the return record preserves every early hit exit. */
u8 OverworldReturnMoveWild_CombatWork(const OverworldReturnMoveWildContext *input,
    OverworldMotionPlan *plan)
{
    OverworldWildSpawnState *state = input->state;
    u8 work;
    if (!OverworldCombat_IsReady()
        || !input->ops->currentSpawn(input->field, &state->spawns[input->slot]))
        return OVERWORLD_COMBAT_NONE;
    work = OVERWORLD_COMBAT_ENTRY->prepare(state, (u8)input->slot, plan);
    if (work != OVERWORLD_COMBAT_NONE)
        OW_WILD_RUNTIME(state)->returnMoves[input->slot].phase = OW_WILD_RETURN_NONE;
    return work;
}

/* Private physical code host only: Actor Motion owns both real plans. */
static BOOL OverworldReturnMoveWild_CurrentSubject(
    const OverworldWildSpawnState *state,
    int slot,
    u32 context,
    OverworldActorHandle *subject)
{
    OverworldActorQuery query = {0};
    OverworldActorSnapshot snapshot;
    const OverworldActorStateSnapshot *actor = &snapshot.actor;

    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX;
    query.index = (u8)slot;
    if (OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(&query, &snapshot)
            != OVERWORLD_ACTOR_RESULT_OK
        || !snapshot.hasActor || !actor->active
        || actor->handle.slot != slot || actor->handle.generation == 0
        || actor->handle.reserved != 0
        || actor->handle.fieldEpoch == 0
        || actor->handle.fieldEpoch
            != OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(context)
        || actor->handle.mapGeneration == 0
        || actor->handle.mapGeneration
            != OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(context)
        || actor->handle.mapGeneration != state->mapGeneration
        || actor->handle.encounterGeneration == 0
        || actor->handle.encounterGeneration
            != state->spawns[slot].encounterGeneration
        || actor->subjectIdentity != state->spawns[slot].personality
        || (actor->role != OVERWORLD_ACTOR_ROLE_WILD
            && actor->role != OVERWORLD_ACTOR_ROLE_FOLLOWER)
        || actor->inputOwnership) {
        return FALSE;
    }
    *subject = actor->handle;
    return TRUE;
}

OverworldMotionDecision __attribute__((noinline, optimize("Os")))
OverworldReturnMoveWild_Request(const OverworldReturnMoveWildRequest *input)
{
    if (input == NULL || input->context.ops == NULL
        || (input->flags & ~OVERWORLD_MOTION_FLAG_SLAM) || input->unused)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    OverworldWildSpawnState *state = input->context.state;
    int slot = input->context.slot;
    const OverworldWildBehaviorProfileData *lane = input->lane;
    u8 kind = input->kind, visibilityPolicy = input->visibilityPolicy;
    u8 arcHeightQ4 = input->arcHeightQ4, facing = input->facing;
    u16 duration = input->duration, targetSurfaceId = input->targetSurfaceId;
    u8 spinSpeed = input->spinSpeed, swayWidth = input->swayWidth;

    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildReturnMove *returnMove;
    OverworldActorHandle subject;
    OverworldMotionPlan acceptedPlan;
    OverworldWildSurfaceHit originSurface;
    u16 originSurfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND;
    OverworldActorMotionRequestCall call;
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;
    BOOL forced = (kind & OW_WILD_RUNTIME_MOTION_REQUEST_FORCED) != 0;
    BOOL ordinary;
    BOOL armReturn;
    BOOL returning;
    u8 deferredPause;
    u32 context;

    if (state == NULL || state->movementRuntimeState == NULL
        || input->context.field != state->movementFieldSystem
        || (u32)slot >= OW_WILD_MAX_SPAWNS) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (!forced && state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_FLY_IN)
        kind = OVERWORLD_MOTION_KIND_FLY_IN;

    /* Forced hits reuse this adapter with no lane. Strip the request modifier
     * before the shared Motion owner sees its normal Hop kind. */
    kind &= ~OW_WILD_RUNTIME_MOTION_REQUEST_FORCED;
    if (input->flags && (forced || kind != OVERWORLD_MOTION_KIND_HOP))
        return OVERWORLD_MOTION_DECISION_PROFILE;
    runtime = state->movementRuntimeState;
    returnMove = &runtime->returnMoves[slot];
    context = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    targetSurfaceId = input->context.ops->querySurface(state->movementFieldSystem,
            runtime->movementCustomJumpTargetX[slot],
            runtime->movementCustomJumpTargetY[slot], &originSurface)
        ? originSurface.surfaceId : OW_WILD_SURFACE_ID_NATIVE_GROUND;
    ordinary = !forced && lane != NULL
        && (kind == OVERWORLD_MOTION_KIND_WALK
            || kind == OVERWORLD_MOTION_KIND_HOP)
        && state->movementFieldSystem != NULL
        && state->spawns[slot].active && state->spawns[slot].object != NULL
        && state->movementActorControlModes[slot] == OW_WILD_ACTOR_CONTROL_AUTONOMOUS
        && state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_NONE
        && (state->movementStagedHopPending[slot] == 0
            || (state->movementStagedHopPending[slot]
                    == (kind == OVERWORLD_MOTION_KIND_WALK
                        ? OW_WILD_RUNTIME_ORDINARY_WALK_PENDING
                        : OW_WILD_RUNTIME_ORDINARY_HOP_PENDING)
                && state->movementStagedHopTargetX[slot]
                    == runtime->movementCustomJumpTargetX[slot]
                && state->movementStagedHopTargetY[slot]
                    == runtime->movementCustomJumpTargetY[slot]))
        && ((runtime->throwState.carrierMask
                | runtime->throwState.recoveringMask) & (1u << slot)) == 0
        && runtime->throwState.targets[slot] == 0
        && (runtime->movementCustomJumpStartX[slot]
                != runtime->movementCustomJumpTargetX[slot]
            || runtime->movementCustomJumpStartY[slot]
                != runtime->movementCustomJumpTargetY[slot]);
    returning = !forced && returnMove->phase == OW_WILD_RETURN_PENDING;
    armReturn = ordinary && returnMove->phase == OW_WILD_RETURN_NONE
        && OW_WILD_BEHAVIOR_RETURNS_AFTER_MOVE(lane->continueWhenArrived);
    if (armReturn || returning) {
        BOOL current = ordinary && OverworldReturnMoveWild_CurrentSubject(
            state, slot, context, &subject);
        if (returning && (!current
            || subject.slot != returnMove->subject.slot
            || subject.generation != returnMove->subject.generation
            || subject.fieldEpoch != returnMove->subject.fieldEpoch
            || subject.mapGeneration != returnMove->subject.mapGeneration
            || subject.encounterGeneration != returnMove->subject.encounterGeneration
            || subject.reserved != returnMove->subject.reserved
            || returnMove->fieldSystem != state->movementFieldSystem
            || returnMove->laneState != state->movementSpotStates[slot]
            || kind != returnMove->plan.kind
            || runtime->movementCustomJumpStartX[slot] != returnMove->plan.targetX
            || runtime->movementCustomJumpStartY[slot] != returnMove->plan.targetY
            || runtime->movementCustomJumpStartBaseY[slot] != returnMove->plan.targetBaseY
            || runtime->movementCustomJumpTargetX[slot] != returnMove->plan.startX
            || runtime->movementCustomJumpTargetY[slot] != returnMove->plan.startY
            || runtime->movementCustomJumpTargetBaseY[slot] != returnMove->plan.startBaseY
            || targetSurfaceId != returnMove->originSurfaceId)) {
            return OVERWORLD_MOTION_DECISION_CONTEXT_LOST;
        }
        armReturn = armReturn && current;
    }
    if (armReturn) {
        originSurfaceId = input->context.ops->querySurface(state->movementFieldSystem,
                runtime->movementCustomJumpStartX[slot],
                runtime->movementCustomJumpStartY[slot], &originSurface)
            ? originSurface.surfaceId : OW_WILD_SURFACE_ID_NATIVE_GROUND;
    }
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = kind;
    intent.facing = facing;
    intent.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(context);
    intent.behaviorFingerprint = 0;
    intent.duration = duration;
    intent.arcHeightQ4 = arcHeightQ4;
    intent.spinSpeed = spinSpeed;
    intent.swayWidth = swayWidth;
    if (returning) {
        /* Same accepted visual leg, reversed. Do not sample its style again. */
        intent.duration = returnMove->plan.duration;
        intent.arcHeightQ4 = returnMove->plan.arcHeightQ4;
        intent.spinSpeed = returnMove->plan.spinSpeed;
        intent.swayWidth = returnMove->plan.swayWidth;
    }
    intent.visibilityPolicy = visibilityPolicy;
    intent.pauseFrames = returning ? returnMove->deferredPause
        : forced || kind == OVERWORLD_MOTION_KIND_REPOSITION
        || kind == OVERWORLD_MOTION_KIND_FLY_IN
        || (kind == OVERWORLD_MOTION_KIND_HOP
            && (state->movementStagedHopPending[slot]
                    == OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING
                || state->movementStagedHopPending[slot]
                    == OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING))
        ? 0
        : kind == OVERWORLD_MOTION_KIND_WALK
            ? input->context.ops->resolveWalkPause(lane)
            : lane->hopPause;
    intent.pathAdvancePolicy = kind == OVERWORLD_MOTION_KIND_FLY_IN
        ? OVERWORLD_MOTION_PATH_ADVANCE_NONE
        : OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    deferredPause = intent.pauseFrames;
    if (armReturn) intent.pauseFrames = 0;
    *(u16 *)(void *)&intent.commitPolicy = forced
        ? OVERWORLD_MOTION_COMMIT_NO_CHAIN | (OVERWORLD_MOTION_FLAG_FORCED << 8)
        : armReturn ? OVERWORLD_MOTION_COMMIT_NO_CHAIN
        : kind == OVERWORLD_MOTION_KIND_REPOSITION
        ? OVERWORLD_MOTION_COMMIT_NO_CHAIN
        : kind == OVERWORLD_MOTION_KIND_FLY_IN
            ? OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY
            : OVERWORLD_MOTION_COMMIT_NORMAL;

    intent.flags |= returning ? (returnMove->plan.flags & OVERWORLD_MOTION_FLAG_SLAM)
        : input->flags;

    candidate.targetX = runtime->movementCustomJumpTargetX[slot];
    candidate.targetY = runtime->movementCustomJumpTargetY[slot];
    candidate.targetBaseY = runtime->movementCustomJumpTargetBaseY[slot];
    candidate.rejectionFlags = 0;
    candidate.direction = state->movementPendingDirections[slot];
    candidate.distance = state->movementPendingDistances[slot];

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
    call.plan = armReturn ? &acceptedPlan : NULL;
    call.reserved = 0;
    call.targetSurfaceId = targetSurfaceId;
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&call)
        != OVERWORLD_ACTOR_RESULT_OK) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    /* Actor Motion returns zero on every rejection, so this also clears an
     * adapter token that did not acquire a new motion. */
    runtime->movementMotionIdentities[slot] = call.motionIdentity;
    if (call.decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        if (armReturn) {
            returnMove->subject = subject;
            returnMove->plan = acceptedPlan;
            returnMove->lane = *lane;
            returnMove->fieldSystem = state->movementFieldSystem;
            returnMove->originSurfaceId = originSurfaceId;
            returnMove->laneState = state->movementSpotStates[slot];
            returnMove->deferredPause = deferredPause;
            returnMove->retryFrames = 0;
            returnMove->returnMotionIdentity = 0;
            returnMove->phase = OW_WILD_RETURN_OUTWARD;
        } else if (returning) {
            returnMove->returnMotionIdentity = call.motionIdentity;
            returnMove->phase = OW_WILD_RETURN_RETURNING;
        } else {
            returnMove->phase = OW_WILD_RETURN_NONE;
        }
    }
    return (OverworldMotionDecision)call.decision;
}

static BOOL OverworldReturnMoveWild_CurrentOwner(
    const OverworldReturnMoveWildContext *input, u16 *frame)
{
    if (input == NULL || input->state == NULL || input->ops == NULL
        || input->state->movementRuntimeState == NULL || (u32)input->slot >= OW_WILD_MAX_SPAWNS) return FALSE;
    OverworldWildSpawnState *state = input->state;
    int slot = input->slot;

    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    const OverworldWildReturnMove *move = &runtime->returnMoves[slot];
    OverworldActorQuery query = {0};
    OverworldActorSnapshot snapshot;

    if (move->phase == OW_WILD_RETURN_NONE
        || input->field != state->movementFieldSystem
        || move->fieldSystem != state->movementFieldSystem
        || move->laneState != state->movementSpotStates[slot]
        || !input->ops->currentField(
            state, move->fieldSystem)
        || !input->ops->currentSpawn(
            move->fieldSystem, &state->spawns[slot])
        || state->movementActorControlModes[slot] != OW_WILD_ACTOR_CONTROL_AUTONOMOUS
        || state->movementSpawnRunActive[slot]
        || ((state->captureTargetMask | runtime->throwState.carrierMask
            | runtime->throwState.recoveringMask
            | runtime->spawnPresentations.distanceDespawnPendingMask) & (1u << slot))
        || runtime->throwState.targets[slot]
        || (slot == OW_WILD_FOLLOWER_SLOT && input->ops->mountActive())) {
        return FALSE;
    }
    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE;
    query.actor = move->subject;
    BOOL current = OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(&query, &snapshot)
            == OVERWORLD_ACTOR_RESULT_OK
        && snapshot.hasActor && snapshot.actor.active
        && snapshot.actor.subjectIdentity == state->spawns[slot].personality
        && !snapshot.actor.inputOwnership
        && (snapshot.actor.role == OVERWORLD_ACTOR_ROLE_WILD
            || snapshot.actor.role == OVERWORLD_ACTOR_ROLE_FOLLOWER);
    if (current && frame != NULL) *frame = (u16)snapshot.frame;
    return current;
}

BOOL __attribute__((noinline, optimize("Os")))
OverworldReturnMoveWild_IsCurrent(const OverworldReturnMoveWildContext *input)
{
    return OverworldReturnMoveWild_CurrentOwner(input, NULL);
}

void __attribute__((noinline, optimize("Os")))
OverworldReturnMoveWild_TryStart(const OverworldReturnMoveWildContext *input)
{
    if (input == NULL || input->state == NULL || input->ops == NULL
        || input->state->movementRuntimeState == NULL || (u32)input->slot >= OW_WILD_MAX_SPAWNS) return;
    OverworldWildSpawnState *state = input->state;
    FieldSystem *fieldSystem = input->field;
    int slot = input->slot;

    OverworldWildReturnMove *move = &OW_WILD_RUNTIME(state)->returnMoves[slot];
    OverworldWildBehaviorProfile profile;
    OverworldWildSurfaceHit surface;
    LocalMapObject *object;
    OverworldMotionDecision decision;
    u16 frame;
    int dx, dy;
    u8 direction;
    const u16 allowed = OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;

    if (move->phase != OW_WILD_RETURN_PENDING) return;
    if (!OverworldReturnMoveWild_CurrentOwner(input, &frame)) goto cancel;
    /* Several native movement passes can share one Actor frame. A temporary
     * reservation spends one retry frame, not one retry for every pass. */
    if (move->retryFrames != 0 && move->retryFrame == frame) return;
    object = state->spawns[slot].object;
    if (object->xCurr != move->plan.targetX || object->yCurr != move->plan.targetY
        || (s32)object->posVec[1] != move->plan.targetBaseY
        || (input->ops->querySurface(fieldSystem,
                move->plan.startX, move->plan.startY, &surface)
            ? surface.surfaceId : OW_WILD_SURFACE_ID_NATIVE_GROUND)
                != move->originSurfaceId
        || input->ops->groundBaseY(fieldSystem, object,
                move->plan.startX, move->plan.startY) != move->plan.startBaseY)
        goto cancel;
    decision = input->ops->classifyLanding(
        state, slot, fieldSystem,
        allowed | (move->plan.kind == OVERWORLD_MOTION_KIND_WALK
            ? OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER : 0),
        move->plan.startX, move->plan.startY, move->plan.startX, move->plan.startY);
    if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) goto rejected;

    profile.owner = profile.tired = move->lane;
    dx = move->plan.startX - object->xCurr;
    dy = move->plan.startY - object->yCurr;
    direction = input->ops->directionFromDelta(dx, dy);
    state->movementStagedHopOriginX[slot] = object->xCurr;
    state->movementStagedHopOriginY[slot] = object->yCurr;
    state->movementStagedHopTargetX[slot] = move->plan.startX;
    state->movementStagedHopTargetY[slot] = move->plan.startY;
    state->movementStagedHopPending[slot] = move->plan.kind == OVERWORLD_MOTION_KIND_WALK
        ? OW_WILD_SPAWNER_STAGED_WALK_PENDING : 1;
    state->movementPreviousTileLocked[slot] = FALSE;
    if (move->plan.kind == OVERWORLD_MOTION_KIND_WALK) {
        OverworldActorWalkPolicyCall call;

        /* This is an owned inverse step, not a new Ram/turn decision.
         * Use the existing Walk proposal and terminal transaction. */
        profile.owner.walkOptions &= ~OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
        profile.tired.walkOptions = profile.owner.walkOptions;
        input->ops->initPolicyCall(&call, slot,
            OVERWORLD_ACTOR_WALK_POLICY_BUFFER_DIRECTION);
        call.direction = OW_WILD_WALK_DIRECTION_NONE;
        (void)input->ops->reduceWalk(&call);
        input->ops->initPolicyCall(&call, slot, OVERWORLD_ACTOR_WALK_POLICY_INPUT);
        call.lane = (move->laneState == OW_WILD_SPOT_STATE_TIRED ? &profile.tired : &profile.owner);
        call.laneState = move->laneState; call.direction = direction;
        call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED
            | OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID;
        call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_VALIDATE;
        decision = OVERWORLD_MOTION_DECISION_DIRECTION;
        if (input->ops->reduceWalk(&call)
            && call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call.stepDirection == direction) {
            decision = input->ops->startTimed(
                state, fieldSystem, slot, object, direction, move->plan.distance,
                move->plan.startX, move->plan.startY, &profile,
                OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG, call.travelTime);
            call.operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
            call.startResult = decision == OVERWORLD_MOTION_DECISION_ACCEPTED
                ? OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED
                : OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
            (void)input->ops->reduceWalk(&call);
        }
        if (move->phase == OW_WILD_RETURN_RETURNING) return;
    } else {
        decision = input->ops->startTimed(
            state, fieldSystem, slot, object, direction, move->plan.distance,
            move->plan.startX, move->plan.startY, &profile, FALSE, 0);
        if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) return;
    }
    input->ops->clearStaged(state, slot);
rejected:
    if ((decision == OVERWORLD_MOTION_DECISION_RESERVED
            || decision == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
            || decision == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE)
        && move->retryFrames++ < 2) {
        move->retryFrame = frame;
        return;
    }
cancel:
    /* A changed or blocked origin cannot hold autonomous control forever. */
    state->movementCooldowns[slot] = move->deferredPause;
    move->phase = OW_WILD_RETURN_NONE;
}

/* Physical code host only; this is the existing Actor Walk terminal adapter. */
static BOOL OverworldReturnMoveWild_FinishWalk(
    const OverworldReturnMoveWildContext *input,
    OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives,
    BOOL stopAfterCommit)
{
    const OverworldWildBehaviorProfileData *lane;
    OverworldActorPolicyView policy;
    OverworldActorWalkPolicyCall call;
    BOOL handled;
    BOOL sharedWalk;
    BOOL throwReservation;
    OverworldWildSpawnState *state = input->state;
    int slot = input->slot;
    LocalMapObject *object = state->spawns[slot].object;
    u8 spotState = state->movementSpotStates[slot];

    lane = spotState == OW_WILD_SPOT_STATE_TIRED ? &profile->tired : &profile->owner;
    if (object == NULL) {
        /* Spawn teardown can finish the command after its object is gone.
         * Do not pass that stale completion into skid callbacks. */
        input->ops->initPolicyCall(&call, slot, OVERWORLD_ACTOR_WALK_POLICY_RESET);
        if (slot != OW_WILD_FOLLOWER_SLOT || !input->ops->mountActive())
            (void)input->ops->reduceWalk(&call);
        return TRUE;
    }
    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        return FALSE;
    }
    sharedWalk = OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
        == OW_WILD_CUSTOM_MOTION_WALK;
    throwReservation = OW_WILD_RUNTIME(state)->throwState.targets[slot]
        != OW_WILD_SPAWNER_THROW_TARGET_NONE;
    if (!sharedWalk && throwReservation) {
        return TRUE;
    }
    handled = policy.pendingSkid != 0;
    input->ops->initPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_COMMIT);
    call.lane = lane;
    call.direction = state->movementLastDirections[slot];
    call.distance = state->movementLastDistances[slot];
    call.laneState = spotState;
    /* This callback only runs after an accepted Walk finishes. The policy
     * must commit that Walk before it can advance the Movement Chain. The
     * custom presentation mode only chooses the terminal adapter; it is not
     * the semantic source of whether a Walk was active. */
    call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED
        | OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    if (OW_WILD_RUNTIME(state)->returnMoves[slot].phase
            == OW_WILD_RETURN_OUTWARD) {
        call.flags &= ~OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    }
    if (OW_WILD_RUNTIME(state)->returnMoves[slot].phase != OW_WILD_RETURN_NONE)
        stopAfterCommit = TRUE;
    if (sharedWalk) {
        if (!OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
                ->terminalWalk(
                    &call,
                    OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS,
                    policy.pendingLastPathAdvance,
                    OW_WILD_RUNTIME(state)->movementMotionIdentities[slot])
            || (call.reserved[OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX]
                    != OVERWORLD_MOTION_PHASE_IDLE
                && call.reserved[
                    OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX]
                    != OVERWORLD_MOTION_PHASE_SETTLING)) {
            return TRUE;
        }
        /* Keep the shared mode live until the actor has reduced and committed
         * the terminal Walk. A retry must not fall into the legacy reducer. */
        input->ops->clearCustomJump(state, slot);
    } else if (!input->ops->reduceWalk(&call)) {
        return FALSE;
    }
    if (stopAfterCommit || throwReservation) {
        return throwReservation;
    }
    /* The terminal transaction is complete. Build the engine-only step
     * adapter afterward so GCC can reuse the policy stack. */
    OverworldWildDirectionStepContext stepContext;
    stepContext.state = state;
    stepContext.fieldSystem = state->movementFieldSystem;
    stepContext.object = object;
    stepContext.profile = profile;
    stepContext.primitives = primitives;
    stepContext.slot = (u8)slot;
    stepContext.allowedTile = lane->chillAllowedTerrainMask;
    (void)input->ops->executeWalk(&stepContext, &call);
    if (handled
        && OverworldActorPolicy_Inspect((u8)slot, &policy)
        && policy.walkMomentum.skidRemaining == 0) {
        input->ops->commitChain(
            state,
            slot,
            profile);
    }
    /* Handled skid completions return before Movement Chain accounting. */
    return handled;
}

BOOL __attribute__((noinline, optimize("Os")))
OverworldReturnMoveWild_Finish(const OverworldReturnMoveWildContext *input,
    OverworldWildBehaviorProfile *profile,
    OverworldWildBehaviorPrimitives *primitives, u8 flags)
{
    if (flags & OVERWORLD_RETURN_MOVE_START) {
        OverworldReturnMoveWild_TryStart(input);
        return FALSE;
    }
    OverworldWildSpawnState *state = input->state;
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    int slot = input->slot;
    OverworldWildReturnMove *move = &runtime->returnMoves[slot];
    LocalMapObject *object = state->spawns[slot].object;

    if (flags & OVERWORLD_RETURN_MOVE_WALK_TERMINAL)
        return OverworldReturnMoveWild_FinishWalk(input, profile, primitives,
            (flags & OVERWORLD_RETURN_MOVE_STOP_AFTER_COMMIT) != 0);
    if (move->phase == OW_WILD_RETURN_NONE) return FALSE;
    if (flags & OVERWORLD_RETURN_MOVE_BEFORE_WALK) {
        /* The accepted pair owns its original lane until both legs close. */
        if ((flags & (OVERWORLD_RETURN_MOVE_COMBAT_OWNED | OVERWORLD_RETURN_MOVE_DESPAWN))
            || !OverworldReturnMoveWild_IsCurrent(input)
            || runtime->movementMotionIdentities[slot]
                != (move->phase == OW_WILD_RETURN_RETURNING
                    ? move->returnMotionIdentity : move->plan.reservationId)
            || object->xCurr != (move->phase == OW_WILD_RETURN_RETURNING
                    ? move->plan.startX : move->plan.targetX)
            || object->yCurr != (move->phase == OW_WILD_RETURN_RETURNING
                    ? move->plan.startY : move->plan.targetY)) {
            move->phase = OW_WILD_RETURN_NONE;
        } else {
            profile->owner = profile->tired = move->lane;
            primitives->chillLocomotion = primitives->tiredLocomotion =
                move->plan.kind == OVERWORLD_MOTION_KIND_WALK
                    ? OW_WILD_BEHAVIOR_LOCOMOTION_WALK : OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
            primitives->chillTarget = primitives->tiredTarget = move->lane.chillTarget;
        }
    }
    if (flags & OVERWORLD_RETURN_MOVE_AFTER_WALK) {
        if (move->phase == OW_WILD_RETURN_OUTWARD) {
            /* All outward reservations close before the same frame's return. */
            move->phase = OW_WILD_RETURN_PENDING;
            state->movementCooldowns[slot] = 0;
            return TRUE;
        }
        if (move->phase == OW_WILD_RETURN_RETURNING) move->phase = OW_WILD_RETURN_NONE;
    }
    return FALSE;
}
