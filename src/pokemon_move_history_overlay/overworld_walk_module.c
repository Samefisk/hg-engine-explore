#include "../../include/overworld_walk_module.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/battle.h"
#include "../../include/map_events_internal.h"
#include "../../include/overlay.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_behavior_condition_adapter.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_timing_policy.h"

#define WALK_DIRECTION_NONE 0xFF
#define WALK_DIRECTION_NORTH 0
#define WALK_DIRECTION_SOUTH 1
#define WALK_DIRECTION_WEST 2
#define WALK_DIRECTION_EAST 3
#define WALK_DIRECTION_NORTH_WEST 4
#define WALK_DIRECTION_NORTH_EAST 5
#define WALK_DIRECTION_SOUTH_WEST 6
#define WALK_DIRECTION_SOUTH_EAST 7
#define WALK_COLLISION_CHECK \
    ((int (*)(FIELD_PLAYER_AVATAR *, LocalMapObject *, int))0x0205DA35)
#define WALK_MOUNT_FREEZE_COMMAND 0x3C
#define WALK_MOUNT_AVATAR_FORCED_MOVEMENT (1u << 0)
#define WALK_PLAYER_MOVE_STATE_NONE 0
#define WALK_PLAYER_MOVE_STATE_END 3

#define WALK_PRIVATE_CODE __attribute__((section(".overworld_walk_module")))
#define WALK_PUBLIC_CODE(sectionName) \
    __attribute__((noinline, used, aligned(2), section(sectionName)))

extern void *PokemonMoveHistory_OverlayMemset(
    void *destination,
    int value,
    u32 size);

typedef char OverworldWalkProposeStepAsmValuesMustMatchAbi[
    OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL == 1
        && OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP == 2
        ? 1 : -1];

static u8 WALK_PUBLIC_CODE(".overworld_walk_decelerate_time_body")
OverworldWalk_DecelerateTimeBody(
    u8 time,
    u8 baseTime,
    u8 accelerationStep)
{
    return OverworldWalkTimingPolicy_Decelerate(
        time, baseTime, accelerationStep);
}

extern const u16 sOverworldWalkDirectionKeys[];
__asm__(".section .overworld_walk_decelerate_time_body,\"ax\",%progbits\n"
        ".balign 2\n"
        ".type sOverworldWalkDirectionKeys,%object\n"
        "sOverworldWalkDirectionKeys:\n"
        ".hword 0x40, 0x80, 0x20, 0x10\n"
        ".hword 0x60, 0x50, 0xA0, 0x90\n"
        ".size sOverworldWalkDirectionKeys,.-sOverworldWalkDirectionKeys\n"
        ".previous\n");

u8 __attribute__((naked)) WALK_PUBLIC_CODE(".overworld_walk_decelerate_time")
OverworldWalk_DecelerateTime(
    u8 time,
    u8 baseTime,
    u8 accelerationStep)
{
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word OverworldWalk_DecelerateTimeBody + 1\n");
}

void WALK_PUBLIC_CODE(".overworld_condition_trace")
OverworldBehaviorConditionTrace_Record(
    const OverworldActorHandle *subject,
    const OverworldBehaviorConditionResult *result,
    const OverworldBehaviorConditionEntryState *entryState,
    u16 entryStateBits)
{
    OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace(
        subject,
        OVERWORLD_ACTOR_EVENT_CONDITIONAL_RESOLVED,
        result->winningConditionSourceApplication
            | ((u16)result->resolvedTargetSourceApplication << 5)
            | ((u16)result->resolvedTarget.kind << 10)
            | entryStateBits,
        result->winningConditionId
            | ((u32)result->resolvedTarget.actor.slot << 16),
        (u16)entryState->activeUntil
            | ((u32)(u16)entryState->cooldownUntil << 16));
}

void __attribute__((naked)) WALK_PUBLIC_CODE(".overworld_walk_propose_step")
OverworldWalk_ProposeStep(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call,
    u8 direction,
    u8 facing,
    u8 time,
    u8 stepFlags,
    u8 skidTiles)
{
#if defined(__arm__)
    __asm__(
        ".syntax unified\n"
        "push {lr}\n"
        "strb r2, [r1, #17]\n"
        "strb r3, [r1, #18]\n"
        "ldr r2, [sp, #4]\n"
        "strb r2, [r1, #19]\n"
        "ldr r2, [sp, #8]\n"
        "strb r2, [r1, #20]\n"
        "ldr r2, [sp, #12]\n"
        "strb r2, [r1, #11]\n"
        "movs r2, #1\n"
        "strb r2, [r0, #22]\n"
        "movs r2, #2\n"
        "strb r2, [r1, #16]\n"
        "movs r2, #255\n"
        "strb r2, [r0, #20]\n"
        "ldrb r2, [r0, #2]\n"
        "strb r2, [r1, #24]\n"
        "bl OverworldWalk_MarkPlannedStopSkid\n"
        "pop {pc}\n");
#else
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL;
    policy->bufferedDirection = OW_WILD_WALK_DIRECTION_NONE;
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP;
    call->stepDirection = direction;
    call->facingDirection = facing;
    call->travelTime = time;
    call->stepFlags = stepFlags;
    call->distance = skidTiles;
    call->reserved[0] = policy->walkMomentum.speed;
    OverworldWalk_MarkPlannedStopSkid(policy, call);
#endif
}

BOOL WALK_PRIVATE_CODE OverworldWalk_CopyNativeShadowValue(
    LocalMapObject *object,
    u32 *shadowState,
    s32 *baseY)
{
    const OverworldWildSpawnsOverlayEntry *entry;
    OverworldWildNativeShadowValue value;
    u32 target;

    if (object == NULL || shadowState == NULL || baseY == NULL
        || !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
        return FALSE;
    }
    entry = OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY;
    target = (u32)entry->copyNativeShadowValue;
    if (target != (OVERWORLD_WILD_SPAWNS_COPY_NATIVE_SHADOW_VALUE_ADDR | 1u)) {
        return FALSE;
    }
    value.version = OVERWORLD_WILD_NATIVE_SHADOW_VALUE_VERSION;
    value.size = sizeof(value);
    value.baseY = 0;
    value.slot = (u8)(object->id - OW_WILD_OBJECT_ID_START);
    value.active = FALSE;
    value.encounterGeneration = (u16)(*shadowState >> 16);
    if (!entry->copyNativeShadowValue(object, &value)
        || value.version != OVERWORLD_WILD_NATIVE_SHADOW_VALUE_VERSION
        || value.size != sizeof(value)
        || value.encounterGeneration == 0) {
        return FALSE;
    }
    *shadowState = (*shadowState & 0xFFFF)
        | ((u32)value.encounterGeneration << 16);
    if (!value.active) {
        return FALSE;
    }
    *baseY = value.baseY;
    return TRUE;
}

u8 WALK_PUBLIC_CODE(".overworld_walk_clamp_time")
OverworldWalk_ClampTime(u8 time)
{
    return OverworldWalkTimingPolicy_Clamp(time);
}

u8 __attribute__((naked)) WALK_PUBLIC_CODE(".overworld_walk_accelerate_time")
OverworldWalk_AccelerateTime(
    u8 time,
    u8 fastestTime,
    u8 accelerationStep)
{
    __asm__(
        ".syntax unified\n"
        "cmp r0, #0\n"
        "bne 1f\n"
        "movs r0, #1\n"
        "1:\n"
        "cmp r0, #32\n"
        "bls 2f\n"
        "movs r0, #32\n"
        "2:\n"
        "cmp r1, #0\n"
        "bne 3f\n"
        "movs r1, #1\n"
        "3:\n"
        "cmp r1, #32\n"
        "bls 4f\n"
        "movs r1, #32\n"
        "4:\n"
        "cmp r2, #0\n"
        "beq 8f\n"
        "cmp r2, #33\n"
        "beq 7f\n"
        "cmp r0, r2\n"
        "bhi 6f\n"
        "movs r0, #1\n"
        "b 8f\n"
        "6:\n"
        "subs r0, r0, r2\n"
        "b 8f\n"
        "7:\n"
        "adds r0, #1\n"
        "lsrs r0, r0, #1\n"
        "8:\n"
        "cmp r0, r1\n"
        "bhs 9f\n"
        "movs r0, r1\n"
        "9:\n"
        "bx lr\n");
}

u8 WALK_PUBLIC_CODE(".overworld_walk_skid_tiles")
OverworldWalk_SkidTiles(u8 time)
{
    return OverworldWalkTimingPolicy_SkidTiles(time);
}

u8 WALK_PUBLIC_CODE(".overworld_walk_skid_time")
OverworldWalk_SkidTime(u8 time)
{
    return OverworldWalkTimingPolicy_SkidTime(time);
}

void WALK_PUBLIC_CODE(".overworld_walk_stop_skid_plan")
OverworldWalk_MarkPlannedStopSkid(
    const OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call)
{
    u8 turnSkidOptions = call->lane->tilesBeforeTurnSkid;

    (void)policy;

    if ((call->stepFlags & (OVERWORLD_ACTOR_WALK_STEP_SKID
                | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID
                | OVERWORLD_ACTOR_WALK_STEP_CONTINUATION))
            == OVERWORLD_ACTOR_WALK_STEP_SKID
        && OW_WILD_BEHAVIOR_PLANS_TURN_SKID_PATH(
            turnSkidOptions)) {
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH;
        call->reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX] =
            call->distance;
    }
}

BOOL WALK_PUBLIC_CODE(".overworld_walk_stomp_applies")
OverworldWalk_StompApplies(u8 time, u8 threshold)
{
    return OverworldWalkTimingPolicy_StompApplies(time, threshold);
}

u8 WALK_PUBLIC_CODE(".overworld_walk_direction_from_keys")
OverworldWalk_DirectionFromKeys(u32 keys)
{
    return OverworldWalkDirectionPolicy_FromKeys(keys);
}

/* These fixed ABI entries are halfword-aligned. Keep their literal-bearing
 * C bodies word-aligned; forcing an input section to alignment 2 breaks Thumb
 * PC-relative literal loads. The tail branch preserves the caller's LR. */
__asm__(".section .overworld_walk_direction_key,\"ax\",%progbits\n"
        ".balign 2\n.thumb\n.global OverworldWalk_DirectionKey\n"
        ".type OverworldWalk_DirectionKey,%function\n.thumb_func\n"
        "OverworldWalk_DirectionKey:\n"
        "b OverworldWalk_DirectionKeyBody\n"
        ".size OverworldWalk_DirectionKey,.-OverworldWalk_DirectionKey\n"
        ".previous\n");

/* Keep the C name for local calls and compiler analysis; other translation
 * units still enter through the fixed assembly symbol above. */
u32 OverworldWalk_DirectionKey(u8 direction) __asm__("OverworldWalk_DirectionKeyBody");
u32 WALK_PUBLIC_CODE(".overworld_walk_direction_key_body")
OverworldWalk_DirectionKey(u8 direction)
{
    return direction < 8 ? sOverworldWalkDirectionKeys[direction] : 0;
}

int WALK_PUBLIC_CODE(".overworld_walk_delta_x")
OverworldWalk_DeltaX(u8 direction)
{
    return OverworldWalkDirectionPolicy_DeltaX(direction);
}

int WALK_PUBLIC_CODE(".overworld_walk_delta_y")
OverworldWalk_DeltaY(u8 direction)
{
    return OverworldWalkDirectionPolicy_DeltaY(direction);
}

BOOL WALK_PUBLIC_CODE(".overworld_walk_is_forty_five_degree_turn")
OverworldWalk_IsFortyFiveDegreeTurn(u8 from, u8 to)
{
    return OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn(from, to);
}

u8 WALK_PUBLIC_CODE(".overworld_walk_direction_from_delta")
OverworldWalk_DirectionFromDelta(int dx, int dy)
{
    return OverworldWalkDirectionPolicy_FromDelta(dx, dy);
}

static void WALK_PRIVATE_CODE Walk_GetComponents(
    u8 direction,
    u8 *vertical,
    u8 *horizontal)
{
    *vertical = direction >= WALK_DIRECTION_SOUTH_WEST
        ? WALK_DIRECTION_SOUTH
        : WALK_DIRECTION_NORTH;
    *horizontal = (direction & 1u)
        ? WALK_DIRECTION_EAST
        : WALK_DIRECTION_WEST;
}

static BOOL WALK_PRIVATE_CODE Walk_CanCardinal(
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction)
{
    return WALK_COLLISION_CHECK(avatar, avatar->mapObject, direction) == 0;
}

static BOOL WALK_PRIVATE_CODE __attribute__((noinline)) Walk_ValidateDiagonalLanding(
    OverworldMountRuntimeState *state, int targetX, int targetY)
{
    return OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
        OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
        OW_WILD_FOLLOWER_SLOT,
        state->fieldSystem,
        state->snapshot.profile.chillAllowedTerrainMask,
        targetX, targetY, targetX, targetY);
}

__asm__(".section .overworld_walk_strict_diagonal_allowed,\"ax\",%progbits\n"
        ".balign 2\n.thumb\n.global OverworldWalk_StrictDiagonalAllowed\n"
        ".type OverworldWalk_StrictDiagonalAllowed,%function\n.thumb_func\n"
        "OverworldWalk_StrictDiagonalAllowed:\n"
        "b OverworldWalk_StrictDiagonalAllowedBody\n"
        ".size OverworldWalk_StrictDiagonalAllowed,.-OverworldWalk_StrictDiagonalAllowed\n"
        ".previous\n");

BOOL OverworldWalk_StrictDiagonalAllowed(
    OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar,
    u8 direction) __asm__("OverworldWalk_StrictDiagonalAllowedBody");
static u16 WALK_PUBLIC_CODE(".overworld_walk_strict_diagonal_allowed_body")
Walk_DiagonalRejection(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction)
{
    u8 vertical;
    u8 horizontal;
    int targetX;
    int targetY;

    if (direction < 4 || direction > 7) {
        return OVERWORLD_MOTION_CANDIDATE_BAD_DIRECTION;
    }
    Walk_GetComponents(direction, &vertical, &horizontal);
    targetX = avatar->mapObject->xCurr + OverworldWalk_DeltaX(direction);
    targetY = avatar->mapObject->yCurr + OverworldWalk_DeltaY(direction);
    if (!Walk_CanCardinal(avatar, vertical)
        || !Walk_CanCardinal(avatar, horizontal)) {
        return OVERWORLD_MOTION_CANDIDATE_SIDE_BLOCKED;
    }
    return targetX < 0 || targetY < 0
            || !Walk_ValidateDiagonalLanding(state, targetX, targetY)
        ? OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN
        : 0;
}

BOOL WALK_PUBLIC_CODE(".overworld_walk_strict_diagonal_allowed_body")
OverworldWalk_StrictDiagonalAllowed(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction)
{
    return Walk_DiagonalRejection(state, avatar, direction) == 0;
}

u8 WALK_PUBLIC_CODE(".overworld_walk_diagonal_facing")
OverworldWalk_DiagonalFacing(
    LocalMapObject *player,
    u8 direction,
    u32 newKeys)
{
    u8 vertical;
    u8 horizontal;

    Walk_GetComponents(direction, &vertical, &horizontal);
    if (player->curFacing == vertical || player->curFacing == horizontal) {
        return (u8)player->curFacing;
    }
    return (newKeys & OverworldWalk_DirectionKey(horizontal)) != 0
        ? horizontal
        : vertical;
}

/* Code host only: this private adapter uses the spare, explicitly bounded
 * boot-resident range after Field terrain code. Actor Motion owns the reason
 * trace and never acquires a reservation for this rejected candidate. */
static u16 WALK_PUBLIC_CODE(".overworld_walk_candidate_rejection")
Walk_RejectDiagonalCandidate(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction,
    u16 rejectionFlags)
{
    OverworldActorMotionRequestCall call;
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;

    PokemonMoveHistory_OverlayMemset(&call, 0, sizeof(call));
    PokemonMoveHistory_OverlayMemset(&intent, 0, sizeof(intent));
    PokemonMoveHistory_OverlayMemset(&candidate, 0, sizeof(candidate));
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = OVERWORLD_MOTION_KIND_WALK;
    intent.facing = direction;
    intent.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());
    intent.duration = OverworldWalkTimingPolicy_Clamp(
        state->snapshot.profile.chillSpeed);
    candidate.targetX = avatar->mapObject->xCurr
        + OverworldWalk_DeltaX(direction);
    candidate.targetY = avatar->mapObject->yCurr
        + OverworldWalk_DeltaY(direction);
    candidate.direction = direction;
    candidate.distance = 1;
    candidate.rejectionFlags = rejectionFlags;
    call.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    call.size = sizeof(call);
    call.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;
    call.actorSlot = OW_WILD_FOLLOWER_SLOT;
    call.startX = avatar->mapObject->xCurr;
    call.startY = avatar->mapObject->yCurr;
    call.intent = &intent;
    call.candidates = &candidate;
    call.candidateCount = 1;
    (void)OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&call);
    return rejectionFlags;
}

u16 WALK_PUBLIC_CODE(".overworld_walk_resolve_mounted_diagonal")
OverworldWalk_ResolveMountedDiagonal(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    u8 direction = OverworldWalk_DirectionFromKeys(*newKeys | *heldKeys);
    u8 vertical;
    u8 horizontal;
    u8 first;
    u16 rejectionFlags;

    if (direction < 4 || direction > 7) {
        return 0;
    }
    if (OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        /* Keep rejected input distinct from a genuine NONE/stop request.
         * The mount adapter submits this candidate to Actor Motion, then
         * consumes the input before it can reach Walk momentum policy. */
        rejectionFlags = Walk_DiagonalRejection(state, avatar, direction);
        if (rejectionFlags != 0) {
            return Walk_RejectDiagonalCandidate(
                state, avatar, direction, rejectionFlags);
        }
        return 0;
    }
    if (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        *newKeys &= ~PAD_PLUS_KEY_MASK;
        *heldKeys &= ~PAD_PLUS_KEY_MASK;
        return 0;
    }
    Walk_GetComponents(direction, &vertical, &horizontal);
    first = avatar->mapObject->curFacing == vertical
            || avatar->mapObject->curFacing == horizontal
        ? (u8)avatar->mapObject->curFacing
        : OverworldWalk_DiagonalFacing(avatar->mapObject, direction, *newKeys);
    if (!Walk_CanCardinal(avatar, first)) {
        first = first == vertical ? horizontal : vertical;
        if (!Walk_CanCardinal(avatar, first)) {
            first = WALK_DIRECTION_NONE;
        }
    }
    *newKeys = (*newKeys & ~PAD_PLUS_KEY_MASK)
        | OverworldWalk_DirectionKey(first);
    *heldKeys = (*heldKeys & ~PAD_PLUS_KEY_MASK)
        | OverworldWalk_DirectionKey(first);
    return 0;
}

static BOOL WALK_PRIVATE_CODE Walk_MountCanControl(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar)
{
    return state->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && state->presentationAttached
        && avatar != NULL
        && state->fieldSystem != NULL
        && state->fieldSystem->playerAvatar == avatar
        && avatar->state == PLAYER_STATE_WALKING
        && (avatar->unk0 & WALK_MOUNT_AVATAR_FORCED_MOVEMENT) == 0;
}

static void __attribute__((noinline)) WALK_PRIVATE_CODE
Walk_MountForceDirection(
    u32 *newKeys,
    u32 *heldKeys,
    u8 direction)
{
    u32 key = OverworldWalk_DirectionKey(direction);

    *newKeys = (*newKeys & ~PAD_PLUS_KEY_MASK) | key;
    *heldKeys = (*heldKeys & ~PAD_PLUS_KEY_MASK) | key;
}

static void Walk_MountSaveProposal(
    OverworldMountRuntimeState *state,
    const OverworldActorWalkPolicyCall *policyCall);

void WALK_PUBLIC_CODE(".overworld_walk_filter_mounted_input")
OverworldWalk_FilterMountedInput(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    OverworldActorPolicyView policy;
    OverworldActorWalkPolicyCall call;
    OverworldRoleControllerInput roleInput;
    OverworldRoleControllerOutput roleOutput;
    u8 requestedDirection;

    if (!OverworldActorPolicy_Inspect(OW_WILD_FOLLOWER_SLOT, &policy)
        || !Walk_MountCanControl(state, avatar)
        || (avatar->unk14 != WALK_PLAYER_MOVE_STATE_NONE
            && avatar->unk14 != WALK_PLAYER_MOVE_STATE_END)
        || policy.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED) {
        return;
    }
    if (policy.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL) {
        Walk_MountForceDirection(
            newKeys, heldKeys,
            state->reservedPolicyState[
                OVERWORLD_MOUNT_WALK_STEP_DIRECTION_INDEX]);
        return;
    }
    requestedDirection = OverworldWalk_DirectionFromKeys(*heldKeys | *newKeys);
    if (requestedDirection != WALK_DIRECTION_NONE) {
        PokemonMoveHistory_OverlayMemset(
            &roleInput, 0, sizeof(roleInput));
        roleInput.version = OVERWORLD_ROLE_CONTROLLER_VERSION;
        roleInput.size = sizeof(roleInput);
        roleInput.role = OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
        roleInput.event = OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST;
        roleInput.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
        roleInput.requestedDirection = requestedDirection;
        roleInput.committedDirection = policy.walkMomentum.direction;
        roleInput.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
        if ((state->snapshot.profile.walkOptions
                & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0) {
            roleInput.flags |= OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
        }
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(
            &roleInput, &roleOutput);
        if (roleOutput.decision
                != OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
            || roleOutput.intentKind
                != OVERWORLD_ROLE_CONTROLLER_INTENT_WALK) {
            *newKeys &= ~PAD_PLUS_KEY_MASK;
            *heldKeys &= ~PAD_PLUS_KEY_MASK;
            return;
        }
        requestedDirection = roleOutput.direction;
    }
    PokemonMoveHistory_OverlayMemset(&call, 0, sizeof(call));
    call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call.size = sizeof(call);
    call.lane = &state->snapshot.profile;
    call.actorSlot = OW_WILD_FOLLOWER_SLOT;
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_INPUT;
    call.direction = requestedDirection;
    call.stepDirection = WALK_DIRECTION_NONE;
    call.facingDirection = WALK_DIRECTION_NONE;
    call.laneState = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP;
    call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_VALIDATE;
    call.reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX] = 0;
    if (requestedDirection != WALK_DIRECTION_NONE
        && (roleOutput.intentFlags
            & OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN) != 0) {
        call.flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    }
    if (requestedDirection != WALK_DIRECTION_NONE
        && (roleOutput.intentFlags
            & OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED) != 0) {
        call.flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED;
    }
    if (!OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
            ->reduceWalk(&call)) {
        return;
    }
    if (call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
        && (call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_STOP_SKID) != 0) {
        call.stepFlags |= OVERWORLD_ACTOR_WALK_STEP_PLANNED_STOP_SKID;
        call.reserved[OVERWORLD_ACTOR_WALK_POLICY_STOP_SKID_TILES_INDEX] =
            call.distance;
    }
    if ((call.stepFlags
            & OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION) != 0) {
        avatar->mapObject->flags &= ~MAPOBJECTFLAG_UNK7;
    }
    Walk_MountSaveProposal(state, &call);
    if (call.stepDirection != WALK_DIRECTION_NONE
        && call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
        /* START_RESULT runs after the mounted engine request. Keep the
         * nominal policy time so presentation variance does not become
         * momentum and a turn can commit its one-level slowdown. */
        state->reservedPolicyProfile[
            OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX] = call.reserved[0];
        Walk_MountForceDirection(newKeys, heldKeys, call.stepDirection);
    } else {
        *newKeys &= ~PAD_PLUS_KEY_MASK;
        *heldKeys &= ~PAD_PLUS_KEY_MASK;
    }
}

static void WALK_PRIVATE_CODE Walk_SetFacing(
    LocalMapObject *object,
    u8 direction)
{
    object->curFacing = direction;
    object->nextFacing = direction;
    object->curFacingBak = direction;
    object->nextFacingBak = direction;
}

BOOL WALK_PUBLIC_CODE(".overworld_walk_start_mounted_flat")
OverworldWalk_StartMountedFlat(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *follower,
    u8 direction,
    u8 facingDirection,
    BOOL advanceFirstFrame,
    BOOL (*beginSharedMotion)(BOOL advanceFirstFrame))
{
    LocalMapObject *player;
    int targetX;
    int targetY;

    if (state->motionCooldown != 0 || avatar == NULL || follower == NULL) {
        return FALSE;
    }
    player = avatar->mapObject;
    if (direction < WALK_DIRECTION_NORTH_WEST
        && !Walk_CanCardinal(avatar, direction)) {
        return FALSE;
    }
    targetX = player->xCurr + OverworldWalk_DeltaX(direction);
    targetY = player->yCurr + OverworldWalk_DeltaY(direction);
    state->motionStartBaseY = (s32)player->posVec[1];
    state->motionStartX = (s16)player->xCurr;
    state->motionStartY = (s16)player->yCurr;
    state->motionTargetBaseY =
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
            state->fieldSystem,
            state->surfaceCatalog,
            player,
            targetX,
            targetY);
    state->motionTargetX = (s16)targetX;
    state->motionTargetY = (s16)targetY;
    state->snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
    state->motionDirection = facingDirection;
    state->motionArcHeightQ4 = 0;
    state->savedFollowerShadowSuppressed =
        (follower->flags & MAPOBJECTFLAG_UNK20) != 0;
    state->motionCooldown = 0;
    state->motionLandingPauseStarted = FALSE;
    state->motionFrameCount = OverworldWalk_ClampTime(
        state->reservedPolicyState[
            OVERWORLD_MOUNT_WALK_TRAVEL_TIME_INDEX]);
    state->motionElapsed = 0;
    /* Reserve the tile before any engine command or facing write. Rejection
     * must leave the mounted pair unchanged. */
    if (!beginSharedMotion(advanceFirstFrame)) {
        return FALSE;
    }
    avatar->unk8 = WALK_MOUNT_FREEZE_COMMAND;
    avatar->unk10 = 1;
    avatar->unk14 = 2;
    MapObject_SetPositionFromVectorAndDirection(
        player,
        (VecFx32 *)player->posVec,
        facingDirection);
    Walk_SetFacing(player, facingDirection);
    Walk_SetFacing(follower, facingDirection);
    MapObject_StartMovementCommandInternal(player, WALK_MOUNT_FREEZE_COMMAND);
    /* The mounted follower is already removed from wild movement scheduling
     * and mirrors the player every field tick. Giving it an independent stock
     * command lets that command write the previous render tile after the
     * player commits, causing a one-frame full-tile split at every boundary. */
    return TRUE;
}

static void WALK_PUBLIC_CODE(".overworld_walk_start_mounted_flat")
Walk_MountSaveProposal(
    OverworldMountRuntimeState *state,
    const OverworldActorWalkPolicyCall *policyCall)
{
    if (policyCall->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
        return;
    }
    state->reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] =
        policyCall->stepFlags;
    state->motionFlicker = policyCall->reserved[3];
    state->reservedPolicyProfile[
        OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX] =
            policyCall->reserved[
                OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX];
    state->reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_DIRECTION_INDEX] =
        policyCall->stepDirection;
    state->reservedPolicyState[
        OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX] =
            policyCall->facingDirection;
    state->reservedPolicyState[OVERWORLD_MOUNT_WALK_TRAVEL_TIME_INDEX] =
        policyCall->travelTime;
}

/* Keep canceled custom motion on a complete tile. The mount state stores the
 * two start coordinates directly before the two target coordinates, followed
 * by start and target base height. */
void __attribute__((naked, noinline, used, aligned(2),
        section(".overworld_walk_mount_abort")))
OverworldWalkMount_RebaseMotionTargetImpl(
    OverworldMountRuntimeState *state)
{
    __asm__(
        "add r0, #0x98\n"
        "ldr r1, [r0, #0]\n"
        "str r1, [r0, #4]\n"
        "ldr r1, [r0, #8]\n"
        "str r1, [r0, #12]\n"
        "bx lr\n");
}
