#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_mount_action_adapter.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_wild_occupancy.h"
#include "../../include/map_events_internal.h"

/* These private mount calls have checked fixed addresses. The chain adapter
 * shares the field lifetime but cannot fit inside overlay 157's code slot. */
extern void OverworldMount_ProcessPlayerControl(
    FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction,
    u32 newKeys, u32 heldKeys, u32 param5);
extern BOOL OverworldMount_TryStartCustomMotion(
    FIELD_PLAYER_AVATAR *avatar, u8 direction, u8 facingDirection,
    BOOL advanceFirstFrame);
extern u8 OverworldMount_GetInputDirection(u32 keys);
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldMount_ProcessPlayerControl, 0x023BC330\n"
    ".thumb_func\n.thumb_set OverworldMount_TryStartCustomMotion, 0x023BB218\n"
    ".thumb_func\n.thumb_set OverworldMount_GetInputDirection, 0x023BB67C\n"
    ".thumb_func\n.thumb_set OverworldActorPolicy_MountCommand, 0x023BA0E0\n"
    ".thumb_func\n.thumb_set OverworldWildOccupancy_Query, 0x023C0184\n"
    ".thumb_func\n.thumb_set __aeabi_uidivmod, 0x023DEE4C\n"
    ".thumb_func\n.thumb_set memset, 0x023DEEA2\n");

/* This boot-resident tail is the shared Walk timing host for Wild, Follower,
 * and Mounted actors. The caller retains the one actor-owned policy state. */
static void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_displayed_time_code")))
OverworldWalk_SelectDisplayedTimeImpl(
    OverworldActorWalkPolicyCall *call,
    const OverworldActorStateSnapshot *snapshot,
    const OverworldActorPolicyState *policy)
{
    u32 randomState;

    if (call->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
        || (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0) {
        return;
    }
    /* The mounted presentation uses this preceding displayed time only for
     * the visual entry curve. A turn, skid, or fresh run starts linear. */
    call->reserved[3] =
        (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION) != 0
            ? 0 : policy->lastWalkTime;
    u8 variance = OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE(
        call->lane->chainRepositionAllowDiagonal);
    u8 fastest = call->lane->maxWalkSpeed;
    if (fastest > call->lane->chillSpeed) {
        fastest = call->lane->chillSpeed;
    }
    if (fastest < 1) fastest = 1;
    if (fastest > 32) fastest = 32;
    if (call->travelTime == fastest
        && (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION) == 0
        && !OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION(call->lane->walkOptions)
        && call->lane->tilesToAccelerate != 0) {
        u8 count = policy->walkMomentum.tileCounter;
        u8 amount = call->lane->walkAccelerationStep;
        if (amount == 33) {
            variance = count >= 6 ? 0 : variance >> count;
        } else {
            u32 reduction = (u32)count * amount;
            variance = reduction >= variance ? 0 : variance - reduction;
        }
    }
    /* A keyed counter draw is stable across blocked retries and does not
     * change the Chain phase or the game's general random stream. */
    randomState = snapshot->subjectIdentity
        ^ ((u32)snapshot->handle.encounterGeneration << 16)
        ^ snapshot->commitSequence;
    randomState ^= randomState >> 16;
    randomState *= 0x7FEB352Du;
    randomState ^= randomState >> 15;
    randomState *= 0x846CA68Bu;
    randomState ^= randomState >> 16;
    u32 time = call->travelTime
        + (((randomState >> 24) * (variance + 1u)) >> 8);

    if (time > 32) {
        time = 32;
    }
    call->travelTime = time;
}

/* Preserve the public fixed entry while the implementation uses existing
 * free code space after the mounted presentation adapter in this overlay. */
void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_displayed_time")))
OverworldWalk_SelectDisplayedTime(
    OverworldActorWalkPolicyCall *call,
    const OverworldActorStateSnapshot *snapshot,
    const OverworldActorPolicyState *policy)
{
    OverworldWalk_SelectDisplayedTimeImpl(call, snapshot, policy);
}

static BOOL __attribute__((noinline)) Chain_Reduce(
    OverworldMountRuntimeState *state,
    u8 operation,
    u8 flags,
    u8 chainAction,
    u8 chainTicks,
    OverworldActorWalkPolicyCall *call)
{
    memset(call, 0, sizeof(*call));
    call->version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call->size = sizeof(*call);
    call->lane = &state->snapshot.profile;
    call->actorSlot = OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT;
    call->laneState = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    call->operation = operation;
    call->flags = flags;
    call->chainAction = chainAction;
    call->chainTicks = chainTicks;
    call->locomotion = state->snapshot.profile.chillAction;
    return OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
        ->reduceWalk(call);
}

void __attribute__((noinline, used,
        section(".overworld_mount_reset_momentum")))
OverworldMount_ResetMomentum(void)
{
    const OverworldMountRuntimeState *state =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;

    if (state->walkEndState != OVERWORLD_MOUNT_WALK_END_CHAIN_HOP
        || !state->presentationAttached) {
        (void)OverworldActorPolicy_MountCommand(
            OVERWORLD_ACTOR_WALK_POLICY_RESET, NULL);
    }
}

static u8 __attribute__((noinline, used, optimize("Os"),
        section(".overworld_mount_forward_hop")))
Chain_StartForwardHop(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    const OverworldActorPolicyView *policy,
    u8 direction,
    BOOL obstacleOnly)
{
    OverworldWildBehaviorProfileData *lane = &state->snapshot.profile;
    u8 oldAction = lane->chillAction;
    u8 oldMin = lane->hopMinDistance;
    u8 oldMax = lane->hopMaxDistance;
    u8 oldTime = lane->hopTime;
    u8 oldEndState = state->walkEndState;
    u8 startResult;
    int frontX;
    int frontY;

    if (direction > (obstacleOnly ? 3 : 7)) {
        return 0;
    }
    if (avatar->state != PLAYER_STATE_WALKING
        || (avatar->unk0 & 1u) != 0
        || state->motionCooldown != 0) {
        return obstacleOnly ? 0 : 2;
    }
    if (obstacleOnly) {
        if (lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_WALK
            || lane->hopAllowVerticalObstacles != 1
            || lane->hopMinDistance != 2 || lane->hopMaxDistance != 2
            || state->snapshot.motionMode != OVERWORLD_MOUNT_MOTION_NONE
            || state->motionStreamPreparing || state->pendingFieldStep
            || policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_NONE
            || policy->motionPhase != OVERWORLD_MOTION_PHASE_IDLE
            || policy->pendingSkid != 0
            || state->fieldSystem->taskman != NULL
            || (((lane->walkOptions
                    & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0
                    || policy->walkMomentum.speed != 0)
                && policy->walkMomentum.direction <= 3
                && policy->walkMomentum.direction != direction)) {
            return 0;
        }
        frontX = avatar->mapObject->xCurr
            + (direction == 2 ? -1 : direction == 3);
        frontY = avatar->mapObject->yCurr
            + (direction == 0 ? -1 : direction == 1);
        if (frontX < 0 || frontY < 0
            || (!IsMetatileBlockedAt(state->fieldSystem, frontX, frontY)
                && !OverworldWildOccupancy_Query(state->fieldSystem,
                    avatar->mapObject, NULL, frontX, frontY, 0,
                    OVERWORLD_WILD_OCCUPANCY_NONPLAYER))) {
            return 0;
        }
    }
    lane->chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
    lane->hopMinDistance = 2;
    lane->hopMaxDistance = 2;
    lane->hopTime = policy->walkMomentum.speed != 0
        ? policy->walkMomentum.speed
        : lane->chillSpeed;
    state->walkEndState = OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;
    startResult = OverworldMount_TryStartCustomMotion(
        avatar, direction, direction, FALSE);
    if (startResult != 1) {
        state->walkEndState = oldEndState;
    }
    lane->chillAction = oldAction;
    lane->hopMinDistance = oldMin;
    lane->hopMaxDistance = oldMax;
    lane->hopTime = oldTime;
    return startResult;
}

static BOOL Chain_ActionActive(
    const OverworldMountRuntimeState *state,
    const OverworldActorPolicyView *policy)
{
    return state->reservedPriorFollowerPolicy != 0
        || (policy->chainPauseAction & 0xF0) == 0x90;
}

static u8 Chain_StartAdapterAction(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    const OverworldActorPolicyView *policy,
    u8 action)
{
    OverworldActorWalkPolicyCall reduceCall;
    OverworldMountActionCall actionCall;
    u8 result;

    if (!Chain_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING,
            0, 0, 0, &reduceCall)) {
        return OVERWORLD_MOUNT_ACTION_RETRY;
    }
    memset(&actionCall, 0, sizeof(actionCall));
    actionCall.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
    actionCall.size = sizeof(actionCall);
    actionCall.operation = OVERWORLD_MOUNT_ACTION_START_CHAIN;
    actionCall.action = action;
    actionCall.state = state;
    actionCall.avatar = avatar;
    actionCall.policy = policy;
    result = OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&actionCall);
    if (result == OVERWORLD_MOUNT_ACTION_RETRY) {
        (void)Chain_Reduce(state,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_PUT_PENDING,
            0, action, policy->chainPauseTicks, &reduceCall);
    }
    return result;
}

void __attribute__((noinline, used,
        section(".overworld_mount_chain_entry")))
OverworldMount_ChainControl(
    FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction,
    u32 newKeys, u32 heldKeys, u32 param5)
{
    OverworldMountRuntimeState *state =
        (OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    OverworldActorPolicyView policy;
    OverworldActorWalkPolicyCall call;
    u8 action;

    /* The original control function waited for this field-step receipt. */
    if (state->pendingFieldStep) {
        return;
    }
    if (state->snapshot.phase != OVERWORLD_MOUNT_PHASE_RIDING
        || !state->presentationAttached
        || state->fieldSystem == NULL || avatar == NULL
        || state->fieldSystem->playerAvatar != avatar
        || !OverworldActorPolicy_Inspect(
            OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT, &policy)) {
        goto ordinary;
    }
    if (policy.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_CHAIN) {
        if (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE) {
            return;
        }
        if (!Chain_Reduce(state,
                OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT,
                OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED,
                0, 0, &call)
            || !OverworldActorPolicy_Inspect(
                OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT, &policy)) {
            return;
        }
    }
    if (Chain_ActionActive(state, &policy)) {
        return;
    }
    if ((policy.chainPauseAction & 0x80) == 0) {
        goto ordinary;
    }
    if (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE) {
        return;
    }
    action = policy.chainPauseAction & 0x7F;
    if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD) {
        action = Chain_StartForwardHop(state, avatar, &policy,
            policy.walkMomentum.direction, FALSE);
        if (action == 2) {
            return;
        }
        if (action == 0) {
            goto consume;
        }
    } else if (action == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE) {
        state->motionCooldown = (u16)policy.chainPauseTicks * 2;
        state->walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
    } else if (action >= OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE
        && action <= OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
        action = Chain_StartAdapterAction(state, avatar, &policy, action);
        if (action != OVERWORLD_MOUNT_ACTION_FINAL) {
            return;
        }
        goto ordinary;
    } else {
        goto consume;
    }
    (void)Chain_Reduce(state,
        OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING,
        0, 0, 0, &call);
    return;

consume:
    (void)Chain_Reduce(state,
        OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING,
        0, 0, 0, &call);
ordinary:
    /* Stock Walk refuses a blocked tile before it saves a step proposal.
     * Try the opted-in obstacle Hop at this input boundary instead. */
    if (state->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && state->presentationAttached
        && !state->bufferedTogglePending
        && state->fieldSystem != NULL
        && state->fieldSystem->playerAvatar == avatar
        && OverworldActorPolicy_Inspect(
            OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT, &policy)) {
        u8 requestedDirection = OverworldMount_GetInputDirection(
            newKeys | heldKeys);

        if (Chain_StartForwardHop(state, avatar, &policy,
                requestedDirection, TRUE) == 1) {
            return;
        }
    }
    OverworldMount_ProcessPlayerControl(
        avatar, param1, direction, newKeys, heldKeys, param5);
}

u8 __attribute__((noinline, used,
        section(".overworld_mount_buffer_direction")))
OverworldMount_BufferedDirection(u32 keys)
{
    const OverworldMountRuntimeState *state =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    u8 direction = OverworldMount_GetInputDirection(keys);

    /* Player control normalizes held input at the boundary. Never store a
     * diagonal direction that this profile cannot take. */
    if ((u8)(direction - 4) <= 3
        && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        return OW_WILD_WALK_DIRECTION_NONE;
    }
    return direction;
}
