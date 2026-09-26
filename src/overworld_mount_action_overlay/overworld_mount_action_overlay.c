#include "../../include/overworld_mount_action_adapter.h"
#include "../../include/map_events_internal.h"
#include "../../include/map_teleport.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_wild_occupancy.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/sound.h"
#include "../../include/constants/sndseq.h"

__asm__(
    ".thumb\n"
    ".global OverworldWildOccupancy_Query\n"
    ".thumb_func\n.thumb_set OverworldWildOccupancy_Query, 0x023C0184\n"
    ".global OverworldMount_GetSurfaceId\n"
    ".thumb_func\n.thumb_set OverworldMount_GetSurfaceId, 0x01FF9A70\n"
    ".global memset\n"
    ".thumb_func\n.thumb_set memset, 0x023DEEA2\n"
    ".global OverworldWalk_DeltaX\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaX, 0x023BF59C\n"
    ".global OverworldWalk_DeltaY\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaY, 0x023BF5BE\n");

extern u16 OverworldMount_GetSurfaceId(int targetX, int targetY);

#define OVERWORLD_MOUNT_CHAIN_FORWARD_DISTANCE 2
#define OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND 0x3E
#define OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT (1u << 0)
#define OVERWORLD_MOUNT_HOP_IN_PLACE_FRAMES 64
#define OVERWORLD_MOUNT_HOP_IN_PLACE_ARC_Q4 16
#define OVERWORLD_MOUNT_CHAIN_PENDING 0x80
#define OVERWORLD_MOUNT_REPOSITION_STEP 0x40
#define OVERWORLD_MOUNT_REPOSITION_SKID 0x20
#define OVERWORLD_MOUNT_REPOSITION_DUST 0x10
#define OVERWORLD_MOUNT_REPOSITION_FLAT_MASK 0x60
#define OVERWORLD_MOUNT_REPOSITION_GRID_MARKER 0x90
#define OVERWORLD_MOUNT_REPOSITION_GRID_MASK 0xF0
#define OVERWORLD_MOUNT_REPOSITION_GRID_CENTER 0x95
#define OVERWORLD_MOUNT_ACTION_STATE_ACTION 0
#define OVERWORLD_MOUNT_ACTION_STATE_FIRST 1
#define OVERWORLD_MOUNT_ACTION_STATE_SECOND 2
#define OVERWORLD_MOUNT_ACTION_STATE_THIRD 3

typedef char OverworldMountConditionRequestOffsetMustRemain444[
    offsetof(OverworldWildBehaviorConditionRuntime, request) == 0x444 ? 1 : -1];
typedef char OverworldMountConditionActiveFollowerOffsetMustRemain7B8[
    offsetof(OverworldWildBehaviorConditionRuntime, activeApplicationMasks)
            + OW_WILD_FOLLOWER_SLOT * sizeof(u32) == 0x7B8
        ? 1
        : -1];

const BehaviorResolveRequest * __attribute__((naked, noinline,
    section(".overworld_mount_conditional_admission")))
OverworldMount_ValidateConditionalAdmission(
    const OverworldWildBehaviorConditionRuntime *conditions,
    const OverworldWildBehaviorContext *context)
{
    __asm__(
        "cmp r0, #0\n"
        "beq 2f\n"
        "ldr r2, 4f\n"
        "ldr r3, [r0, r2]\n"
        "cmp r3, #0\n"
        "beq 2f\n"
        "ldr r2, 5f\n"
        "add r0, r2\n"
        "ldr r2, [r0, #16]\n"
        "cmp r2, r3\n"
        "bne 3f\n"
        "ldr r2, [r0, #12]\n"
        "mov r3, #128\n"
        "lsl r3, r3, #20\n"
        "cmp r2, r3\n"
        "bne 3f\n"
        "ldr r2, [r0, #0]\n"
        "ldr r3, [r1, #0]\n"
        "cmp r2, r3\n"
        "bne 3f\n"
        "ldr r2, [r0, #4]\n"
        "ldr r3, [r1, #4]\n"
        "cmp r2, r3\n"
        "bne 3f\n"
        "ldr r2, [r0, #8]\n"
        "ldr r3, [r1, #8]\n"
        "cmp r2, r3\n"
        "bne 3f\n"
        "bx lr\n"
        "2:\n"
        "mov r0, #0\n"
        "bx lr\n"
        "3:\n"
        "mov r0, #1\n"
        "bx lr\n"
        ".align 2\n"
        "4: .word 0x000007B8\n"
        "5: .word 0x00000444\n");
}

static BOOL OverworldMountAction_IsRetryDecision(u16 decision)
{
    return decision == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
        || decision == OVERWORLD_MOTION_DECISION_OCCUPIED
        || decision == OVERWORLD_MOTION_DECISION_RESERVED
        || decision == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
}

static u8 *OverworldMountAction_State(OverworldMountRuntimeState *state)
{
    return (u8 *)(void *)&state->reservedPriorFollowerPolicy;
}

static LocalMapObject *OverworldMountAction_Follower(void)
{
    return sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT].object;
}

static BOOL OverworldMountAction_Reduce(
    OverworldMountRuntimeState *state,
    u8 operation,
    u8 direction,
    u8 distance)
{
    OverworldActorWalkPolicyCall reduceCall;

    reduceCall.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    reduceCall.size = sizeof(reduceCall);
    reduceCall.actorSlot = OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT;
    reduceCall.operation = operation;
    reduceCall.direction = direction;
    reduceCall.distance = distance;
    return OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
        ->reduceWalk(&reduceCall);
}

static void OverworldMountAction_SetFacing(
    OverworldMountRuntimeState *state,
    u8 direction)
{
    LocalMapObject *follower = OverworldMountAction_Follower();
    LocalMapObject *player;

    if (direction > 3 || state->fieldSystem == NULL
        || state->fieldSystem->playerAvatar == NULL) {
        return;
    }
    player = state->fieldSystem->playerAvatar->mapObject;
    player->curFacing = direction;
    player->nextFacing = direction;
    player->curFacingBak = direction;
    player->nextFacingBak = direction;
    if (follower != NULL) {
        follower->curFacing = direction;
        follower->nextFacing = direction;
        follower->curFacingBak = direction;
        follower->nextFacingBak = direction;
    }
}

static OverworldFieldTerrainStreamResult OverworldMountAction_Stream(
    OverworldMountRuntimeState *state,
    u8 operation)
{
    const OverworldFieldMountPresentationEntry *entry =
        OVERWORLD_FIELD_MOUNT_PRESENTATION_ENTRY;
    OverworldFieldTerrainStreamCall streamCall;

    if (entry->magic != OVERWORLD_FIELD_MOUNT_PRESENTATION_MAGIC
        || entry->version != OVERWORLD_FIELD_MOUNT_PRESENTATION_VERSION
        || entry->size != sizeof(*entry) || entry->terrainStream == NULL) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
    }
    memset(&streamCall, 0, sizeof(streamCall));
    streamCall.version = OVERWORLD_FIELD_TERRAIN_STREAM_CALL_VERSION;
    streamCall.size = sizeof(streamCall);
    streamCall.fieldSystem = state->fieldSystem;
    streamCall.fieldContext = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    streamCall.motionIdentity = state->motionIdentity;
    streamCall.targetX = state->motionTargetX;
    streamCall.targetY = state->motionTargetY;
    streamCall.operation = operation;
    return entry->terrainStream(&streamCall);
}

static void OverworldMountAction_Boundary(
    OverworldMountRuntimeState *state,
    u8 acknowledgements,
    u8 reason)
{
    OverworldActorMotionBoundaryCall boundaryCall;

    memset(&boundaryCall, 0, sizeof(boundaryCall));
    boundaryCall.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    boundaryCall.size = sizeof(boundaryCall);
    boundaryCall.operation = OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY;
    boundaryCall.actorSlot = OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT;
    boundaryCall.acknowledgements = acknowledgements;
    boundaryCall.cancelReason = reason;
    boundaryCall.motionIdentity = state->motionIdentity;
    (void)OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->boundary(&boundaryCall);
}

static u8 OverworldMountAction_StartMotion(
    OverworldMountActionCall *call,
    u8 kind,
    u8 direction,
    int targetX,
    int targetY,
    u8 distance,
    u16 duration,
    u8 arcHeightQ4)
{
    OverworldMountRuntimeState *state = call->state;
    FIELD_PLAYER_AVATAR *avatar = call->avatar;
    OverworldActorMotionRequestCall request;
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;
    LocalMapObject *follower = OverworldMountAction_Follower();
    LocalMapObject *player;
    s32 targetBaseY;
    u8 facing;
    OverworldActorResult actorResult;
    OverworldFieldTerrainStreamResult streamResult;

    if (state == NULL || avatar == NULL || state->fieldSystem == NULL
        || state->fieldSystem->playerAvatar != avatar || follower == NULL
        || avatar->mapObject == NULL || duration == 0) {
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if (state->snapshot.motionMode != OVERWORLD_MOUNT_MOTION_NONE
        || state->motionCooldown != 0) {
        return OVERWORLD_MOUNT_ACTION_RETRY;
    }
    player = avatar->mapObject;
    if (targetX != player->xCurr || targetY != player->yCurr) {
        streamResult = OverworldMountAction_Stream(
            state, OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE);
        if (streamResult != OVERWORLD_FIELD_TERRAIN_STREAM_IDLE) {
            return streamResult == OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED
                ? OVERWORLD_MOUNT_ACTION_FINAL
                : OVERWORLD_MOUNT_ACTION_RETRY;
        }
    }
    targetBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
        state->fieldSystem,
        state->surfaceCatalog,
        player,
        targetX,
        targetY);
    facing = player->curFacing <= 3 ? player->curFacing : direction;
    if (!OW_WILD_BEHAVIOR_WALK_PRESERVES_FACING(
            state->snapshot.profile.walkOptions)) {
        facing = targetX != player->xCurr
            ? 2 + (targetX > player->xCurr)
            : targetY != player->yCurr ? (targetY > player->yCurr) : facing;
    }
    memset(&intent, 0, sizeof(intent));
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = kind;
    intent.facing = facing;
    intent.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());
    intent.duration = duration;
    intent.arcHeightQ4 = arcHeightQ4;
    intent.visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_VISIBLE;
    intent.pathAdvancePolicy = targetX == player->xCurr
            && targetY == player->yCurr
        ? OVERWORLD_MOTION_PATH_ADVANCE_NONE
        : OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;
    intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NO_CHAIN;
    candidate.targetX = (s16)targetX;
    candidate.targetY = (s16)targetY;
    candidate.targetBaseY = targetBaseY;
    candidate.rejectionFlags = 0;
    candidate.direction = direction;
    candidate.distance = distance;
    candidate.reservationId = 0;
    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;
    request.actorSlot = OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT;
    request.candidateCount = 1;
    request.reserved = 0;
    request.startX = player->xCurr;
    request.startY = player->yCurr;
    request.startBaseY = (s32)player->posVec[1];
    request.intent = &intent;
    request.candidates = &candidate;
    request.plan = NULL;
    request.targetSurfaceId = OverworldMount_GetSurfaceId(targetX, targetY);
    actorResult = OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request);
    if (actorResult != OVERWORLD_ACTOR_RESULT_OK) {
        return actorResult == OVERWORLD_ACTOR_RESULT_RETRY
            ? OVERWORLD_MOUNT_ACTION_RETRY
            : OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if (request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return OverworldMountAction_IsRetryDecision(request.decision)
            ? OVERWORLD_MOUNT_ACTION_RETRY
            : OVERWORLD_MOUNT_ACTION_FINAL;
    }
    state->motionIdentity = request.motionIdentity;
    state->motionStartX = player->xCurr;
    state->motionStartY = player->yCurr;
    state->motionTargetX = (s16)targetX;
    state->motionTargetY = (s16)targetY;
    state->motionStartBaseY = (s32)player->posVec[1];
    state->motionTargetBaseY = targetBaseY;
    if ((targetX != player->xCurr || targetY != player->yCurr)
        && OverworldMountAction_Stream(state, OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN)
            != OVERWORLD_FIELD_TERRAIN_STREAM_WAITING) {
        OverworldMountAction_Boundary(
            state, OVERWORLD_ACTOR_BOUNDARY_CANCEL,
            OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
        state->motionIdentity = 0;
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    memset(state->reservedPolicyState, 0,
        OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX);
    state->motionStreamPreparing = targetX != player->xCurr
        || targetY != player->yCurr;
    state->snapshot.motionMode = OVERWORLD_MOUNT_MOTION_HOP;
    state->walkEndState = OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;
    state->motionDirection = facing;
    state->motionArcHeightQ4 = arcHeightQ4;
    state->motionFlicker = 0;
    state->motionFrameCount = duration;
    state->motionElapsed = 0;
    state->motionLandingPauseStarted = FALSE;
    state->savedFollowerShadowSuppressed =
        (follower->flags & MAPOBJECTFLAG_UNK20) != 0;
    if (!state->motionStreamPreparing) {
        OverworldMountAction_Boundary(
            state,
            OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY,
            0);
    }
    avatar->unk0 |= OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
    PlayerAvatar_ResetMovement(avatar);
    MapObject_SetPositionFromVectorAndDirection(
        player, (VecFx32 *)player->posVec, facing);
    OverworldMountAction_SetFacing(state, facing);
    MapObject_StartMovementCommandInternal(
        player, OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND);
    MapObject_StartMovementCommandInternal(
        follower, OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND);
    return OVERWORLD_MOUNT_ACTION_STARTED;
}

static BOOL OverworldMountAction_IsWalkCorridorTileOpen(
    OverworldMountRuntimeState *state,
    int x,
    int y)
{
    return x >= 0 && y >= 0
        && OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
            OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
            OW_WILD_FOLLOWER_SLOT,
            state->fieldSystem,
            state->snapshot.profile.chillAllowedTerrainMask,
            x, y, -1, -1);
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldMountAction_IsWalkStepOpen(
    OverworldMountRuntimeState *state,
    int x,
    int y,
    int dx,
    int dy)
{
    if ((dx & dy) != 0
        && (!OverworldMountAction_IsWalkCorridorTileOpen(state, x + dx, y)
            || !OverworldMountAction_IsWalkCorridorTileOpen(state, x, y + dy))) {
        return FALSE;
    }
    return OverworldMountAction_IsWalkCorridorTileOpen(
        state, x + dx, y + dy);
}

static u8 __attribute__((noinline, optimize("Os")))
OverworldMountAction_WalkCorridor(OverworldMountActionCall *call)
{
    OverworldMountRuntimeState *state = call->state;
    LocalMapObject *player;
    u8 flags;
    u8 distance;
    u8 turnDirection = OVERWORLD_WALK_DIRECTION_NONE;
    int x;
    int y;
    int dx;
    int dy;
    int nextX;
    int nextY;

    if (state == NULL || call->avatar == NULL || call->avatar->mapObject == NULL
        || call->direction > 7) {
        return FALSE;
    }
    player = call->avatar->mapObject;
    flags = state->reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX];
    if ((flags & OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH) == 0) {
        return TRUE;
    }
    distance = state->reservedPolicyProfile[
        OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX];
    if ((flags & (OVERWORLD_ACTOR_WALK_STEP_SKID
                | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID))
            == OVERWORLD_ACTOR_WALK_STEP_SKID) {
        turnDirection = state->reservedPolicyState[
            OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX];
    } else if ((flags & OVERWORLD_ACTOR_WALK_STEP_SKID) == 0) {
        distance++;
    }
    if (distance == 0) {
        return FALSE;
    }
    x = player->xCurr;
    y = player->yCurr;
    dx = OverworldWalk_DeltaX(call->direction);
    dy = OverworldWalk_DeltaY(call->direction);
    do {
        nextX = x + dx;
        nextY = y + dy;
        if (!OverworldMountAction_IsWalkStepOpen(state, x, y, dx, dy)) {
            /* The caller has admitted Walk. It may reach the tile before a
             * two-tile Hop; the landing gate matches the actual Hop start.
             * Never relax the skid path or its turn exit. */
            if ((flags & (OVERWORLD_ACTOR_WALK_STEP_SKID
                        | OVERWORLD_ACTOR_WALK_STEP_POST_SKID)) == 0
                && state->reservedPolicyProfile[
                    OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX] == 1
                && distance == 1
                && call->direction <= 3
                && state->snapshot.profile.hopMinDistance == 2
                && state->snapshot.profile.hopMaxDistance == 2
                && state->snapshot.profile.hopAllowVerticalObstacles == 1
                && nextX >= 0 && nextY >= 0
                && (IsMetatileBlockedAt(state->fieldSystem, nextX, nextY)
                    || OverworldWildOccupancy_Query(
                        state->fieldSystem, player, NULL, nextX, nextY, 0,
                        OVERWORLD_WILD_OCCUPANCY_NONPLAYER))
                && !IsMetatileBlockedAt(
                    state->fieldSystem, nextX + dx, nextY + dy)
                && OverworldMountAction_IsWalkCorridorTileOpen(
                    state, nextX + dx, nextY + dy)) {
                return TRUE;
            }
            return FALSE;
        }
        x = nextX;
        y = nextY;
    } while (--distance != 0);
    if (turnDirection == OVERWORLD_WALK_DIRECTION_NONE) {
        return TRUE;
    }
    dx = OverworldWalk_DeltaX(turnDirection);
    dy = OverworldWalk_DeltaY(turnDirection);
    return OverworldMountAction_IsWalkStepOpen(state, x, y, dx, dy);
}

static u8 OverworldMountAction_PlanHopTrajectory(
    OverworldMountActionCall *call)
{
    OverworldActorMotionRequestCall request;
    OverworldActorHopPlanCall hopPlan;

    if (call->state == NULL || call->avatar == NULL
        || call->avatar->mapObject == NULL || call->trajectory == NULL
        || call->action == 0) {
        return FALSE;
    }
    hopPlan.operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
    hopPlan.spotState = 0;
    hopPlan.lane = &call->state->snapshot.profile;
    hopPlan.fieldSystem = call->state->fieldSystem;
    hopPlan.surfaceCatalog = call->state->surfaceCatalog;
    hopPlan.object = call->avatar->mapObject;
    hopPlan.startBaseY = call->state->motionStartBaseY;
    hopPlan.targetBaseY = call->state->motionTargetBaseY;
    hopPlan.startX = call->state->motionStartX;
    hopPlan.startY = call->state->motionStartY;
    hopPlan.targetX = call->state->motionTargetX;
    hopPlan.targetY = call->state->motionTargetY;
    hopPlan.distance = call->action;
    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;
    request.hopPlan = &hopPlan;
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request)
            != OVERWORLD_ACTOR_RESULT_OK
        || request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return FALSE;
    }
    *call->trajectory = hopPlan.trajectory;
    return TRUE;
}

static OverworldMotionDecision OverworldMountAction_PlanReposition(
    OverworldMountRuntimeState *state,
    LocalMapObject *player,
    u8 action,
    u8 distance,
    int targetX,
    int targetY,
    u16 *duration,
    u8 *arcHeightQ4)
{
    OverworldActorMotionRequestCall request;
    OverworldActorHopPlanCall hopPlan;
    OverworldActorResult result;

    hopPlan.operation = action
            == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS
        ? OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY
        : OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY;
    hopPlan.spotState = 0;
    hopPlan.trajectory = action
            == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS
        ? 0 : state->snapshot.profile.chainRepositionSpeed;
    hopPlan.lane = &state->snapshot.profile;
    hopPlan.fieldSystem = state->fieldSystem;
    hopPlan.surfaceCatalog = state->surfaceCatalog;
    hopPlan.object = player;
    hopPlan.startBaseY = (s32)player->posVec[1];
    hopPlan.targetBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
        state->fieldSystem,
        state->surfaceCatalog,
        player,
        targetX,
        targetY);
    hopPlan.startX = player->xCurr;
    hopPlan.startY = player->yCurr;
    hopPlan.targetX = (s16)targetX;
    hopPlan.targetY = (s16)targetY;
    hopPlan.distance = distance;
    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;
    request.hopPlan = &hopPlan;
    result = OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request);
    if (result != OVERWORLD_ACTOR_RESULT_OK) {
        return result == OVERWORLD_ACTOR_RESULT_RETRY
            ? OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
            : OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (request.decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        *duration = hopPlan.trajectory & 0xFFFF;
        *arcHeightQ4 = hopPlan.trajectory >> 16;
    }
    return request.decision;
}

static BOOL OverworldMountAction_IsOccupied(
    OverworldMountRuntimeState *state,
    LocalMapObject *player,
    int targetX,
    int targetY)
{
    OverworldWildSurfaceHit surface;
    LocalMapObject *follower = OverworldMountAction_Follower();
    s32 targetBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
        state->fieldSystem,
        state->surfaceCatalog,
        player,
        targetX,
        targetY);
    int mode = OVERWORLD_WILD_OCCUPANCY_OBJECTS;

    if (OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->querySurface(
            state->fieldSystem,
            state->surfaceCatalog,
            targetX,
            targetY,
            &surface)
        && surface.surfaceId != OW_WILD_SURFACE_ID_NATIVE_GROUND) {
        targetBaseY = surface.height != 0
            ? surface.height : targetBaseY;
        mode = OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER;
    }
    return OverworldWildOccupancy_Query(
        state->fieldSystem,
        follower,
        player,
        targetX,
        targetY,
        targetBaseY,
        mode);
}

static u8 OverworldMountAction_RunReposition(
    OverworldMountActionCall *call,
    u8 encodedRemaining)
{
    OverworldMountRuntimeState *state = call->state;
    OverworldWildBehaviorProfileData *lane = &state->snapshot.profile;
    LocalMapObject *player = call->avatar->mapObject;
    u8 *actionState = OverworldMountAction_State(state);
    u32 remaining = lane->chainRepositionJumpCount;
    u32 startIndex;
    u32 attempt;
    u32 directionIndex;
    u32 packedOffset;
    u32 distance;
    int targetX;
    int targetY;
    u16 duration = 0;
    u8 arcHeightQ4 = 0;
    u8 startResult;
    OverworldMotionDecision decision;
    BOOL retry = FALSE;

    if ((encodedRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) != 0) {
        remaining = (encodedRemaining - 1) & 0x0F;
    }
    if (remaining == 0) {
        (void)OverworldMountAction_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
        memset(actionState, 0, sizeof(state->reservedPriorFollowerPolicy));
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    startIndex = gf_rand();
    if ((encodedRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) != 0) {
        startIndex = 0x56703412u
            >> (actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD] << 2);
    }
    distance = (encodedRemaining & OVERWORLD_MOUNT_REPOSITION_FLAT_MASK)
            == OVERWORLD_MOUNT_REPOSITION_SKID
        ? lane->chainRepositionDistance : 1;
    for (attempt = 0; attempt < 8; attempt++) {
        directionIndex = (startIndex + attempt) & 7;
        if (((&lane->chainRepositionAllowCardinal)[directionIndex >> 2]
                & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK) == 0) {
            continue;
        }
        packedOffset = 0xA8206491u >> (directionIndex << 2);
        targetX = player->xCurr + ((packedOffset & 3) - 1) * distance;
        targetY = player->yCurr
            + (((packedOffset >> 2) & 3) - 1) * distance;
        if (targetX < 0 || targetY < 0
            || !OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
                OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
                OW_WILD_FOLLOWER_SLOT,
                state->fieldSystem,
                lane->chillAllowedTerrainMask,
                targetX,
                targetY,
                targetX,
                targetY)) {
            if (targetX >= 0 && targetY >= 0
                && OverworldMountAction_IsOccupied(
                    state, player, targetX, targetY)) {
                retry = TRUE;
            }
            continue;
        }
        decision = OverworldMountAction_PlanReposition(
            state,
            player,
            call->action,
            (u8)distance,
            targetX,
            targetY,
            &duration,
            &arcHeightQ4);
        if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            if (decision != OVERWORLD_MOTION_DECISION_BLOCKED
                && decision != OVERWORLD_MOTION_DECISION_TERRAIN) {
                retry = TRUE;
                break;
            }
            continue;
        }
        startResult = OverworldMountAction_StartMotion(
            call,
            OVERWORLD_MOTION_KIND_REPOSITION,
            (u8)directionIndex,
            targetX,
            targetY,
            (u8)distance,
            duration,
            arcHeightQ4);
        if (startResult == OVERWORLD_MOUNT_ACTION_STARTED) {
            encodedRemaining = (u8)(remaining
                | (lane->chainRepositionDust << 4)
                | OVERWORLD_MOUNT_CHAIN_PENDING
                | (encodedRemaining & OVERWORLD_MOUNT_REPOSITION_FLAT_MASK));
            if (!OverworldMountAction_Reduce(state,
                    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE,
                    (u8)((packedOffset & 3) - 1
                        + (((packedOffset >> 2) & 3) - 1) * 4),
                    encodedRemaining)) {
                OverworldMountAction_Boundary(
                    state,
                    OVERWORLD_ACTOR_BOUNDARY_CANCEL,
                    OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
                (void)OverworldMountAction_Reduce(state,
                    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH,
                    0, 0);
                memset(actionState, 0,
                    sizeof(state->reservedPriorFollowerPolicy));
                return OVERWORLD_MOUNT_ACTION_FINAL;
            }
            actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call->action;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = 0;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND] = 0;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD] =
                (u8)directionIndex;
            return OVERWORLD_MOUNT_ACTION_STARTED;
        }
        if (startResult == OVERWORLD_MOUNT_ACTION_RETRY) {
            retry = TRUE;
            break;
        }
        (void)OverworldMountAction_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
        memset(actionState, 0, sizeof(state->reservedPriorFollowerPolicy));
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if ((encodedRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) == 0 || !retry) {
        (void)OverworldMountAction_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
        memset(actionState, 0, sizeof(state->reservedPriorFollowerPolicy));
    }
    return retry
        ? OVERWORLD_MOUNT_ACTION_RETRY : OVERWORLD_MOUNT_ACTION_FINAL;
}

static u8 OverworldMountAction_StartChain(OverworldMountActionCall *call)
{
    OverworldMountRuntimeState *state = call->state;
    u8 *actionState;
    u8 mode = 0;
    u8 frames;
    u8 direction;

    if (state == NULL || call->avatar == NULL
        || call->avatar->mapObject == NULL || call->policy == NULL
        || !call->policy->actorActive
        || call->avatar->state != PLAYER_STATE_WALKING
        || (call->avatar->unk0 & OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT)
            != 0
        || state->motionCooldown != 0
        || (call->policy->motionPhase != OVERWORLD_MOTION_PHASE_IDLE
            && call->policy->motionPhase != OVERWORLD_MOTION_PHASE_CANCELED)) {
        return OVERWORLD_MOUNT_ACTION_RETRY;
    }
    actionState = OverworldMountAction_State(state);
    if (actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] != 0) {
        return OVERWORLD_MOUNT_ACTION_RETRY;
    }
    direction = call->avatar->mapObject->curFacing <= 3
        ? call->avatar->mapObject->curFacing : 1;
    if (call->action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) {
        u8 result = OverworldMountAction_StartMotion(
            call,
            OVERWORLD_MOTION_KIND_HOP,
            direction,
            call->avatar->mapObject->xCurr,
            call->avatar->mapObject->yCurr,
            0,
            OVERWORLD_MOUNT_HOP_IN_PLACE_FRAMES,
            OVERWORLD_MOUNT_HOP_IN_PLACE_ARC_Q4);

        if (result == OVERWORLD_MOUNT_ACTION_STARTED) {
            actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call->action;
            PlaySE(SEQ_SE_GS_UFO_JUMP);
        }
        return result;
    }
    if (call->action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
        frames = call->policy->chainPauseTicks < 2
            ? 3 : call->policy->chainPauseTicks > 127
                ? 255 : call->policy->chainPauseTicks * 2;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call->action;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = frames;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND] = frames;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD] =
            OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
                ->buildLookPlan(direction);
        direction = (u8)OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
            ->resolveLook(
                actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD],
                OVERWORLD_ACTOR_LOOK_FIRST,
                0,
                0);
        OverworldMountAction_SetFacing(state, direction);
        return OVERWORLD_MOUNT_ACTION_STARTED;
    }
    if (call->action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS) {
        mode = OVERWORLD_MOUNT_REPOSITION_STEP;
    } else if (call->action
        == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
        mode = OVERWORLD_MOUNT_REPOSITION_SKID;
    } else if (call->action
        != OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS) {
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if (!OverworldMountAction_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_BEGIN,
            OVERWORLD_MOUNT_REPOSITION_GRID_CENTER,
            mode)) {
        return OVERWORLD_MOUNT_ACTION_RETRY;
    }
    memset(actionState, 0, sizeof(state->reservedPriorFollowerPolicy));
    actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call->action;
    return OverworldMountAction_RunReposition(call, mode);
}

static u8 OverworldMountAction_TickChain(OverworldMountActionCall *call)
{
    OverworldMountRuntimeState *state = call->state;
    OverworldActorPolicyView policy;
    LocalMapObject *follower;
    u8 *actionState;
    u8 action;
    u8 direction;
    u16 appliedThrough;
    u16 priorAppliedThrough;

    if (state == NULL) {
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    actionState = OverworldMountAction_State(state);
    action = actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION];
    if (!OverworldActorPolicy_Inspect(
            OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT, &policy)) {
        return action != 0
            ? OVERWORLD_MOUNT_ACTION_STARTED : OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if (action == 0
        && (policy.chainPauseAction & OVERWORLD_MOUNT_REPOSITION_GRID_MASK)
            == OVERWORLD_MOUNT_REPOSITION_GRID_MARKER
        && (policy.chainStepsRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) != 0) {
        action = (policy.chainStepsRemaining
                & OVERWORLD_MOUNT_REPOSITION_FLAT_MASK)
                == OVERWORLD_MOUNT_REPOSITION_STEP
            ? OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS
            : (policy.chainStepsRemaining
                    & OVERWORLD_MOUNT_REPOSITION_FLAT_MASK)
                    == OVERWORLD_MOUNT_REPOSITION_SKID
                ? OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS
                : OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = action;
    }
    if (action == 0) {
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
        if (actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] != 0) {
            actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST]--;
        }
        direction = (u8)OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
            ->resolveLook(
                actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD],
                OVERWORLD_ACTOR_LOOK_RETURN,
                actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND],
                actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST]);
        if ((s8)direction < 0) {
            direction = (u8)OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY
                ->policy->resolveLook(
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD],
                    OVERWORLD_ACTOR_LOOK_SECOND,
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND],
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST]);
        }
        if ((s8)direction < 0) {
            direction = (u8)OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY
                ->policy->resolveLook(
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD],
                    OVERWORLD_ACTOR_LOOK_FIRST,
                    0,
                    0);
        }
        OverworldMountAction_SetFacing(state, direction);
        if (actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == 0) {
            memset(actionState, 0,
                sizeof(state->reservedPriorFollowerPolicy));
            return OVERWORLD_MOUNT_ACTION_FINAL;
        }
        return OVERWORLD_MOUNT_ACTION_STARTED;
    }
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS
        && state->snapshot.profile.chainRepositionDust) {
        appliedThrough = state->reservedPolicyState[
                OVERWORLD_MOUNT_BOUNDARY_APPLIED_LO_INDEX]
            | ((u16)state->reservedPolicyState[
                    OVERWORLD_MOUNT_BOUNDARY_APPLIED_HI_INDEX] << 8);
        priorAppliedThrough = actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST]
            | ((u16)actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND] << 8);
        follower = OverworldMountAction_Follower();
        if (appliedThrough != 0 && appliedThrough != priorAppliedThrough
            && follower != NULL) {
            OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY
                ->playLandingHopParticle(follower);
            actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = appliedThrough;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND] =
                appliedThrough >> 8;
        }
    }
    if (state->snapshot.motionMode != OVERWORLD_MOUNT_MOTION_NONE
        || (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE
            && policy.motionPhase != OVERWORLD_MOTION_PHASE_CANCELED)) {
        return OVERWORLD_MOUNT_ACTION_STARTED;
    }
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) {
        memset(actionState, 0, sizeof(state->reservedPriorFollowerPolicy));
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    call->action = action;
    return OverworldMountAction_RunReposition(
        call, policy.chainStepsRemaining);
}

static u8 OverworldMountAction_CancelChain(OverworldMountActionCall *call)
{
    OverworldActorPolicyView policy;
    u8 *actionState;

    if (call->state == NULL) {
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    actionState = OverworldMountAction_State(call->state);
    if (actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION]
            >= OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS
        && actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION]
            <= OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
        (void)OverworldMountAction_Reduce(call->state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
    } else if (OverworldActorPolicy_Inspect(
            OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT, &policy)
        && (policy.chainPauseAction & OVERWORLD_MOUNT_REPOSITION_GRID_MASK)
            == OVERWORLD_MOUNT_REPOSITION_GRID_MARKER) {
        (void)OverworldMountAction_Reduce(call->state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
    }
    memset(actionState, 0, sizeof(call->state->reservedPriorFollowerPolicy));
    return OVERWORLD_MOUNT_ACTION_STARTED;
}

static u8 OverworldMountAction_ChainForwardTarget(
    OverworldMountActionCall *call)
{
    OverworldMountRuntimeState *state = call->state;
    int targetX;
    int targetY;

    if (state == NULL || state->fieldSystem == NULL || call->direction > 7) {
        return FALSE;
    }
    targetX = state->motionStartX
        + OverworldWalkDirectionPolicy_DeltaX(call->direction)
            * OVERWORLD_MOUNT_CHAIN_FORWARD_DISTANCE;
    targetY = state->motionStartY
        + OverworldWalkDirectionPolicy_DeltaY(call->direction)
            * OVERWORLD_MOUNT_CHAIN_FORWARD_DISTANCE;
    if (targetX < 0 || targetY < 0
        || !OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
            OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
            OW_WILD_FOLLOWER_SLOT,
            state->fieldSystem,
            state->snapshot.profile.chillAllowedTerrainMask
                | OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER,
            targetX,
            targetY,
            targetX,
            targetY)) {
        return FALSE;
    }
    state->motionTargetX = (s16)targetX;
    state->motionTargetY = (s16)targetY;
    return TRUE;
}

u8 __attribute__((noinline, used, section(".overworld_mount_action_entry")))
OverworldMountActionAdapter_Dispatch(OverworldMountActionCall *call)
{
    if (call == NULL
        || call->version != OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION
        || call->size != sizeof(*call)) {
        return FALSE;
    }
    call->result = FALSE;
    if (call->operation == OVERWORLD_MOUNT_ACTION_WALK_CORRIDOR) {
        call->result = OverworldMountAction_WalkCorridor(call);
    } else if (call->operation == OVERWORLD_MOUNT_ACTION_START_CHAIN) {
        call->result = OverworldMountAction_StartChain(call);
    } else if (call->operation == OVERWORLD_MOUNT_ACTION_TICK_CHAIN) {
        call->result = OverworldMountAction_TickChain(call);
    } else if (call->operation == OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN) {
        call->result = OverworldMountAction_CancelChain(call);
    } else if (call->operation
        == OVERWORLD_MOUNT_ACTION_CHAIN_FORWARD_TARGET) {
        call->result = OverworldMountAction_ChainForwardTarget(call);
    } else if (call->operation
        == OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY) {
        call->result = OverworldMountAction_PlanHopTrajectory(call);
    }
    return call->result;
}
