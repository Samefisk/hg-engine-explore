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
    ".global __gnu_thumb1_case_uqi\n"
    ".thumb_func\n.thumb_set __gnu_thumb1_case_uqi, 0x023DEE54\n"
    ".global __gnu_thumb1_case_uhi\n"
    ".thumb_func\n.thumb_set __gnu_thumb1_case_uhi, 0x023DEE78\n"
    ".global OverworldWalk_DeltaX\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaX, 0x023BF59C\n"
    ".global OverworldWalk_DeltaY\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaY, 0x023BF5BE\n");

extern u16 OverworldMount_GetSurfaceId(int targetX, int targetY);

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

typedef char OverworldMountActionContactMarkerLayoutMustStay24[
    sizeof(OverworldMountActionCall) == 24
        && offsetof(OverworldMountActionCall, action) == 5
        ? 1 : -1];
typedef char OverworldMountConditionRequestOffsetMustRemain5AC[
    offsetof(OverworldWildBehaviorConditionRuntime, request) == 0x5AC ? 1 : -1];
typedef char OverworldMountConditionActiveFollowerOffsetMustRemain938[
    offsetof(OverworldWildBehaviorConditionRuntime, activeApplicationMasks)
            + OW_WILD_FOLLOWER_SLOT * sizeof(u32) == 0x938
        ? 1
        : -1];

const BehaviorResolveRequest * __attribute__((naked, noinline,
    section(".overworld_mount_conditional_admission")))
OverworldMount_ValidateConditionalAdmission(
    const OverworldWildBehaviorConditionRuntime *conditions,
    const OverworldWildBehaviorContext *context,
    u32 mountedMask)
{
    /* The caller derives this one-bit mask from the authenticated subject
     * bank. This guard rejects a missing Mounted application before reading
     * its retained request; the mask is never a global application bit. */
    __asm__(
        "cmp r0, #0\n"
        "beq 2f\n"
        "cmp r2, #0\n"
        "beq 3f\n"
        "mov ip, r2\n"
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
        "mov r3, ip\n"
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
        "4: .word 0x00000938\n"
        "5: .word 0x000005AC\n");
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
    reduceCall.effect = distance;
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
    BOOL advances;
    BOOL forced = call->operation == OVERWORLD_MOUNT_ACTION_START_KNOCKBACK;

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
    advances = targetX != player->xCurr || targetY != player->yCurr;
    if (advances) {
        streamResult = OverworldMountAction_Stream(
            state, OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE);
        if (streamResult != OVERWORLD_FIELD_TERRAIN_STREAM_IDLE) {
            return streamResult == OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED
                ? OVERWORLD_MOUNT_ACTION_FINAL
                : OVERWORLD_MOUNT_ACTION_RETRY;
        }
    }
    targetBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
        state->fieldSystem, state->surfaceCatalog, player, targetX, targetY);
    facing = player->curFacing <= 3 ? player->curFacing : direction;
    if (!forced
        && !OW_WILD_BEHAVIOR_WALK_PRESERVES_FACING(
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
    intent.pathAdvancePolicy = advances
        ? OVERWORLD_MOTION_PATH_ADVANCE_PLAYER
        : OVERWORLD_MOTION_PATH_ADVANCE_NONE;
    intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NO_CHAIN;
    if (forced) {
        intent.flags = OVERWORLD_MOTION_FLAG_FORCED;
    }
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
    if (advances
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
    state->motionStreamPreparing = advances;
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

    if (state == NULL || call->avatar == NULL || call->avatar->mapObject == NULL
        || call->direction > 7) {
        return FALSE;
    }
    if ((state->reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX]
            & OVERWORLD_ACTOR_WALK_STEP_SKID) == 0) {
        return TRUE;
    }
    /* Admit each clear skid tile. A later blocker cannot veto this step;
     * the next attempt reports its own collision to the Crash reducer. */
    player = call->avatar->mapObject;
    return OverworldMountAction_IsWalkStepOpen(
        state, player->xCurr, player->yCurr,
        OverworldWalk_DeltaX(call->direction),
        OverworldWalk_DeltaY(call->direction));
}

static OverworldMotionDecision __attribute__((noinline, optimize("Os")))
OverworldMountAction_RequestHopPlan(OverworldActorHopPlanCall *hopPlan)
{
    OverworldActorMotionRequestCall request;
    OverworldActorResult result;

    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;
    request.hopPlan = hopPlan;
    result = OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request);
    if (result != OVERWORLD_ACTOR_RESULT_OK) {
        return result == OVERWORLD_ACTOR_RESULT_RETRY
            ? OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
            : OVERWORLD_MOTION_DECISION_PROFILE;
    }
    return request.decision;
}

static u8 OverworldMountAction_PlanHopTrajectory(
    OverworldMountActionCall *call)
{
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
    if (OverworldMountAction_RequestHopPlan(&hopPlan)
            != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return FALSE;
    }
    *call->trajectory = hopPlan.trajectory;
    return TRUE;
}

static OverworldMotionDecision __attribute__((noinline, optimize("Os")))
OverworldMountAction_PlanReposition(
    OverworldMountRuntimeState *state,
    LocalMapObject *player,
    u8 action,
    u8 distance,
    int targetX,
    int targetY,
    u16 *duration,
    u8 *arcHeightQ4)
{
    OverworldActorHopPlanCall hopPlan;
    OverworldMotionDecision decision;

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
    decision = OverworldMountAction_RequestHopPlan(&hopPlan);
    if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        *duration = hopPlan.trajectory & 0xFFFF;
        *arcHeightQ4 = hopPlan.trajectory >> 16;
    }
    return decision;
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
    u32 remaining = OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMP_COUNT(
        lane->chainRepositionJumpCount);
    u32 startIndex;
    u32 attempt;
    u32 directionIndex;
    u32 packedOffset;
    u32 distance;
    u32 travelDistance;
    u32 tile;
    int dx;
    int dy;
    int targetX;
    int targetY;
    u16 duration = 0;
    u8 arcHeightQ4 = 0;
    u8 startResult;
    BOOL skid;
    OverworldActorPolicyView gridPolicy;
    OverworldMotionDecision decision;
    BOOL retry = FALSE;

    if ((encodedRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) != 0) {
        remaining = (encodedRemaining - 1) & 0x0F;
    }
    if (remaining == 0) {
        goto finished;
    }
    startIndex = gf_rand();
    if ((encodedRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) != 0) {
        startIndex = 0x56703412u
            >> ((actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD] & 7) << 2);
    }
    skid = (encodedRemaining & OVERWORLD_MOUNT_REPOSITION_FLAT_MASK)
        == OVERWORLD_MOUNT_REPOSITION_SKID;
    distance = skid ? lane->chainRepositionDistance : 1;
    if (skid && !OverworldActorPolicy_Inspect(
            OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT, &gridPolicy)) {
        return OVERWORLD_MOUNT_ACTION_RETRY;
    }
    for (attempt = 0; attempt < 8; attempt++) {
        directionIndex = (startIndex + attempt) & 7;
        if (((&lane->chainRepositionAllowCardinal)[directionIndex >> 2]
                & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK) == 0) {
            continue;
        }
        packedOffset = 0xA8206491u >> (directionIndex << 2);
        dx = (packedOffset & 3) - 1;
        dy = ((packedOffset >> 2) & 3) - 1;
        travelDistance = distance;
        targetX = player->xCurr;
        targetY = player->yCurr;
        if (skid) {
            if ((u32)((gridPolicy.chainPauseAction & 3) + dx) > 2
                || (u32)(((gridPolicy.chainPauseAction >> 2) & 3) + dy) > 2) {
                continue;
            }
            for (tile = 0; tile < distance; tile++) {
                if (!OverworldMountAction_IsWalkStepOpen(
                        state, targetX, targetY, dx, dy)) {
                    break;
                }
                targetX += dx;
                targetY += dy;
            }
            travelDistance = tile;
        } else {
            targetX += dx;
            targetY += dy;
        }
        if (!skid && (targetX < 0 || targetY < 0
            || !OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
                OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
                OW_WILD_FOLLOWER_SLOT,
                state->fieldSystem,
                lane->chillAllowedTerrainMask,
                targetX,
                targetY,
                targetX,
                targetY))) {
            if (targetX >= 0 && targetY >= 0
                && OverworldMountAction_IsOccupied(
                    state, player, targetX, targetY)) {
                retry = TRUE;
            }
            continue;
        }
        for (;;) {
            if (travelDistance == 0) {
                duration = lane->chainRepositionSpeed != 0
                    ? lane->chainRepositionSpeed : 1;
                arcHeightQ4 = 0;
                decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
                break;
            }
            decision = OverworldMountAction_PlanReposition(
                state, player, call->action, (u8)travelDistance,
                targetX, targetY, &duration, &arcHeightQ4);
            if (!skid || (decision != OVERWORLD_MOTION_DECISION_BLOCKED
                    && decision != OVERWORLD_MOTION_DECISION_TERRAIN)) {
                break;
            }
            travelDistance--;
            targetX -= dx;
            targetY -= dy;
        }
        if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            if (skid || (decision != OVERWORLD_MOTION_DECISION_BLOCKED
                && decision != OVERWORLD_MOTION_DECISION_TERRAIN)) {
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
            (u8)travelDistance,
            duration,
            arcHeightQ4);
        if (startResult == OVERWORLD_MOUNT_ACTION_STARTED) {
            encodedRemaining = (u8)(remaining
                | (OW_WILD_BEHAVIOR_SKID_BOOLEAN(lane->chainRepositionDust) << 4)
                | OVERWORLD_MOUNT_CHAIN_PENDING
                | (encodedRemaining & OVERWORLD_MOUNT_REPOSITION_FLAT_MASK));
            if (!OverworldMountAction_Reduce(state,
                    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE,
                    travelDistance != 0 ? (u8)(dx + dy * 4) : 0,
                    encodedRemaining)) {
                OverworldMountAction_Boundary(
                    state,
                    OVERWORLD_ACTOR_BOUNDARY_CANCEL,
                    OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
                retry = FALSE;
                goto finished;
            }
            actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call->action;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = 0;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND] = 0;
            actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD] =
                (u8)directionIndex
                    | (skid && travelDistance != distance ? 0x80 : 0);
            return OVERWORLD_MOUNT_ACTION_STARTED;
        }
        if (startResult == OVERWORLD_MOUNT_ACTION_RETRY) {
            retry = TRUE;
            break;
        }
        retry = FALSE;
        goto finished;
    }
    if ((encodedRemaining & OVERWORLD_MOUNT_CHAIN_PENDING) == 0 || !retry) {
        goto finished;
    }
    return OVERWORLD_MOUNT_ACTION_RETRY;
finished:
    (void)OverworldMountAction_Reduce(state,
        OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
    state->reservedPriorFollowerPolicy = 0;
    return retry ? OVERWORLD_MOUNT_ACTION_RETRY
        : OVERWORLD_MOUNT_ACTION_FINAL;
}

static u8 __attribute__((noinline, optimize("Os")))
OverworldMountAction_RunChain(OverworldMountActionCall *call)
{
    OverworldMountRuntimeState *state = call->state;
    OverworldActorPolicyView policy;
    LocalMapObject *follower;
    u8 *actionState;
    u8 action;
    u8 direction;
    u8 mode = 0;
    u32 frames;
    u32 remaining;
    u8 result;
    int targetX;
    int targetY;
    u16 appliedThrough;
    u16 priorAppliedThrough;
    BOOL first = call->operation == OVERWORLD_MOUNT_ACTION_START_CHAIN;

    if (first) {
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
            targetX = call->avatar->mapObject->xCurr;
            targetY = call->avatar->mapObject->yCurr;
            remaining = call->policy->chainPauseTicks != 0
                ? call->policy->chainPauseTicks - 1 : 0;
            goto hop;
        }
        if (call->action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
            frames = call->policy->chainPauseTicks;
#if defined(__arm__)
            __asm__(".syntax unified\ncmp %0,#1\nbhi 1f\nmovs %0,#3\nb 2f\n"
                "1:\nlsls %0,#1\ncmp %0,#255\nbls 2f\nmovs %0,#255\n2:\n.syntax divided\n"
                : "+l"(frames) : : "cc");
#else
            frames *= 2;
            if (frames < 3) {
                frames = 3;
            } else if (frames > 255) {
                frames = 255;
            }
#endif
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
        state->reservedPriorFollowerPolicy = 0;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call->action;
        return OverworldMountAction_RunReposition(call, mode);
    }
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
        mode = OVERWORLD_ACTOR_LOOK_RETURN;
        do {
            direction = (u8)OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
                ->resolveLook(
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD], mode,
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND],
                    actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST]);
            if ((s8)direction >= 0) {
                break;
            }
        } while (mode-- != OVERWORLD_ACTOR_LOOK_FIRST);
        OverworldMountAction_SetFacing(state, direction);
        if (actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == 0) {
            state->reservedPriorFollowerPolicy = 0;
            return OVERWORLD_MOUNT_ACTION_FINAL;
        }
        return OVERWORLD_MOUNT_ACTION_STARTED;
    }
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS
        && OW_WILD_BEHAVIOR_SKID_BOOLEAN(state->snapshot.profile.chainRepositionDust)) {
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
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS
        && (actionState[OVERWORLD_MOUNT_ACTION_STATE_THIRD] & 0x80) != 0) {
        (void)OverworldMountAction_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT, 0,
            OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
        PlaySE(SEQ_SE_DP_WALL_HIT);
        (void)OverworldMountAction_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH, 0, 0);
        state->reservedPriorFollowerPolicy = 0;
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) {
        if (actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] != 0
            && policy.motionPhase == OVERWORLD_MOTION_PHASE_IDLE) {
            direction = actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND];
            targetX = state->motionTargetX;
            targetY = state->motionTargetY;
            remaining = actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] - 1;
            goto hop;
        }
        goto hopFinished;
    }
    call->action = action;
    return OverworldMountAction_RunReposition(
        call, policy.chainStepsRemaining);

hop:
    result = OverworldMountAction_StartMotion(
        call, OVERWORLD_MOTION_KIND_HOP, direction, targetX, targetY, 0,
        OVERWORLD_MOUNT_HOP_IN_PLACE_FRAMES,
        OVERWORLD_MOUNT_HOP_IN_PLACE_ARC_Q4);
    if (result == OVERWORLD_MOUNT_ACTION_STARTED) {
        actionState[OVERWORLD_MOUNT_ACTION_STATE_ACTION] =
            OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = remaining;
        actionState[OVERWORLD_MOUNT_ACTION_STATE_SECOND] = direction;
        PlaySE(SEQ_SE_GS_UFO_JUMP);
    } else if (!first && result != OVERWORLD_MOUNT_ACTION_RETRY) {
        goto hopFinished;
    }
    return result;
hopFinished:
    state->reservedPriorFollowerPolicy = 0;
    return OVERWORLD_MOUNT_ACTION_FINAL;
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
    call->state->reservedPriorFollowerPolicy = 0;
    return OVERWORLD_MOUNT_ACTION_STARTED;
}

static u8 OverworldMountAction_StartKnockback(OverworldMountActionCall *call)
{
    const OverworldMotionPlan *plan =
        (const OverworldMotionPlan *)call->trajectory;
    OverworldMountRuntimeState *state = call->state;

    if (state == NULL || plan == NULL) {
        return OVERWORLD_MOUNT_ACTION_FINAL;
    }
    /* The resident planner validates the plan and waits for mounted END.
     * StartMotion validates the live avatar, owner and idle motion shell. */
    (void)OverworldMountAction_CancelChain(call);
    return OverworldMountAction_StartMotion(call,
        OVERWORLD_MOTION_KIND_HOP, plan->direction,
        plan->targetX, plan->targetY, plan->distance,
        plan->duration, plan->arcHeightQ4);
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
    /* The caller passes the exact ledge Hop or B Jump distance. */
    targetX = state->motionStartX
        + OverworldWalkDirectionPolicy_DeltaX(call->direction) * call->action;
    targetY = state->motionStartY
        + OverworldWalkDirectionPolicy_DeltaY(call->direction) * call->action;
    /* The landing classifier rejects a negative coordinate itself. */
    if (!OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
            OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
            OW_WILD_FOLLOWER_SLOT,
            state->fieldSystem,
            /* The marker also selects one-tile Walk edges, which a cardinal
             * ledge Hop can never pass. Only a diagonal (4-7) Hop needs its
             * strict side tiles; this sets 0x8000 for exactly those. Every
             * mount may land in water: a non-water-runner splashes and is
             * returned to its takeoff tile by the mount tick. */
            state->snapshot.profile.chillAllowedTerrainMask
                | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER
                | ((call->direction & 4)
                    * (OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER / 4)),
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
    switch (call->operation) {
    case OVERWORLD_MOUNT_ACTION_WALK_CORRIDOR:
        call->result = OverworldMountAction_WalkCorridor(call);
        break;
    case OVERWORLD_MOUNT_ACTION_START_CHAIN:
    case OVERWORLD_MOUNT_ACTION_TICK_CHAIN:
        call->result = OverworldMountAction_RunChain(call);
        break;
    case OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN:
        call->result = OverworldMountAction_CancelChain(call);
        break;
    case OVERWORLD_MOUNT_ACTION_CHAIN_FORWARD_TARGET:
        call->result = OverworldMountAction_ChainForwardTarget(call);
        break;
    case OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY:
        call->result = OverworldMountAction_PlanHopTrajectory(call);
        break;
    case OVERWORLD_MOUNT_ACTION_START_KNOCKBACK:
        call->result = OverworldMountAction_StartKnockback(call);
        break;
    }
    return call->result;
}
