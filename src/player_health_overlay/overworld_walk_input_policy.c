#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_walk_timing_policy.h"
#include "../../include/overworld_behavior_packed_options.h"
#include "../../include/overworld_hop_effects_internal.h"

/* Actor owns the reply cache. Its physical code host has no HP dependency. */
OverworldActorReply gOverworldActorAcknowledgements[
    OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY]
    __attribute__((section(".overworld_actor_acknowledgements"), used)) = {0};

/* Adapter transport only. Actor remains the owner of elapsed time and carry. */
u32 gOverworldMountWalkProposalReserved
    __attribute__((section(".overworld_mount_walk_proposal_reserved"), used)) = 0;

/* Shared Walk policy code uses a checked free boot-resident code slot.
 * Actor owns all state; this physical host has no Player Health dependency. */
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldWalkPolicy_Memset, 0x023DEEA2\n"
    ".thumb_func\n.thumb_set OverworldWalk_DecelerateTime, 0x023BF400\n"
    ".thumb_func\n.thumb_set OverworldWalk_ProposeStep, 0x023BF45C\n"
    ".thumb_func\n.thumb_set OverworldWalk_ClampTime, 0x023BF488\n"
    ".thumb_func\n.thumb_set OverworldWalk_SkidTiles, 0x023BF4D6\n"
    ".thumb_func\n.thumb_set OverworldWalk_SkidTime, 0x023BF4F0\n"
    ".thumb_func\n.thumb_set OverworldWalk_IsFortyFiveDegreeTurn, 0x023BF5E2\n");

#if defined(__arm__)
/* All independent replace slices share the fixed 106-byte resident slot.
 * The immutable triples are (profile byte, source bit + 1, slice mask).
 * Source bits 33..64 select mask3; the other source bits select mask2. */
__asm__(
    ".section .overworld_behavior_packed_options,\"ax\",%progbits\n"
    ".syntax unified\n"
    ".thumb\n"
    ".thumb_func\n"
    ".global OverworldBehaviorPackedOptions_Apply\n"
    ".type OverworldBehaviorPackedOptions_Apply,%function\n"
    "OverworldBehaviorPackedOptions_Apply:\n"
    "push {r4-r7,lr}\n"
    "mov ip,r2\n"
    "adr r7,3f\n"
    "1:\n"
    "ldrb r2,[r7]\n"
    "cmp r2,#0\n"
    "beq 4f\n"
    "ldrb r3,[r7,#1]\n"
    "ldrb r5,[r7,#2]\n"
    "adds r7,#3\n"
    "ldr r6,[r1,#24]\n"
    "cmp r3,#32\n"
    "bls 5f\n"
    "subs r3,#32\n"
    "ldr r6,[r1,#28]\n"
    "5:\n"
    "lsrs r6,r3\n"
    "bcc 1b\n"
    "6:\n"
    "ldrb r3,[r0,r2]\n"
    "movs r4,r1\n"
    "adds r4,#32\n"
    "ldrb r4,[r4,r2]\n"
    "eors r4,r3\n"
    "ands r4,r5\n"
    "eors r4,r3\n"
    "strb r4,[r0,r2]\n"
    "cmp r2,#79\n"
    "bne 1b\n"
    "pop {r4-r7,pc}\n"
    "4:\n"
    "movs r2,#79\n"
    "mov r5,ip\n"
    "b 6b\n"
    ".balign 4\n"
    "3:\n"
    ".byte 42,14,1, 42,26,2, 42,27,60, 42,28,192\n"
    ".byte 43,15,1, 43,30,254, 57,29,48, 57,31,192\n"
    ".byte 75,17,1, 75,32,192\n"
    ".byte 56,24,254, 56,43,1, 62,25,254, 62,49,1, 0\n"
    ".size OverworldBehaviorPackedOptions_Apply,.-OverworldBehaviorPackedOptions_Apply\n"
    ".text\n");
#else
void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_behavior_packed_options")))
OverworldBehaviorPackedOptions_Apply(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorOverrideProfile *overrideProfile, u32 knockbackMask)
{
    OverworldBehaviorPackedOptions_ApplyInline(profile, overrideProfile, knockbackMask);
}
#endif

u8 __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_profile_skid"))) OverworldWalk_ProfileSkidTiles(
    u8 time, const OverworldWildBehaviorProfileData *lane, BOOL stop)
{
    return OverworldWalkTimingPolicy_ProfileSkidTiles(time,
        OW_WILD_BEHAVIOR_TURN_SKID_ONE_TIME(lane),
        OW_WILD_BEHAVIOR_TURN_SKID_TWO_TIME(lane),
        OW_WILD_BEHAVIOR_STOP_SKID_TIME(lane), stop);
}

void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_policy_reset")))
OverworldActorWalkPolicy_ResetState(
    OverworldActorPolicyState *policy,
    BOOL initialize,
    u8 baseSpeed,
    u8 laneState)
{
    typedef u32 WalkMomentumWord __attribute__((may_alias));
    WalkMomentumWord *words = (WalkMomentumWord *)&policy->walkMomentum;

    /* This resident owner is size-bound. Reset the packed byte state with two
     * aligned words instead of linking the larger byte-wise memset sequence. */
    words[0] = OW_WILD_WALK_DIRECTION_NONE;
    words[1] = OW_WILD_WALK_DIRECTION_NONE;
    if (initialize) {
        words[0] |= (u32)baseSpeed << 16 | (u32)baseSpeed << 24;
        words[1] = laneState;
    }
    policy->bufferedDirection = OW_WILD_WALK_DIRECTION_NONE;
    policy->stopPending = FALSE;
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
    policy->pendingSkid = FALSE;
    policy->lastWalkTime = 0;
    policy->linearElapsed = 0;
    policy->linearCarry = 0;
    policy->linearMode = FALSE;
    policy->linearCapFrames = 0;
    policy->chainStepsRemaining = 0;
    policy->deferredChainPauseTicks = 0;
    policy->deferredChainPauseAction = 0;
}

void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_policy_crash")))
OverworldActorWalkPolicy_Crash(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call,
    u8 baseSpeed,
    u8 laneState)
{
    OverworldActorWalkPolicy_ResetState(policy, TRUE, baseSpeed, laneState);
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
    call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_CRASH;
    call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
}

/* Pure private policy helpers share the unused ends of the fixed Reset and
 * Crash reserves. Actor owns their state; no Player Health state is read. */
u32 __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_policy_variance")))
OverworldActorWalkPolicy_SampleVariance(OverworldActorPolicyState *policy, u8 range)
{
    policy->variancePhase = (u8)(policy->variancePhase * 73u + 41u);
    return ((u16)*(volatile u8 *)&policy->variancePhase * (range + 1u)) >> 8;
}

BOOL __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_policy_chain_chance")))
OverworldActorWalkPolicy_SampleChainChance(u32 chance)
{
    return gf_rand() % 100u < chance;
}

#if defined(__arm__)
/* One pure two-roll choice occupies the measured 46-byte Mount-finish gap. */
__asm__(
    ".section .overworld_hop_effect_choice,\"ax\",%progbits\n"
    ".syntax unified\n"
    ".thumb\n"
    ".thumb_func\n"
    ".global OverworldActorWalkPolicy_SampleHopEffects\n"
    ".type OverworldActorWalkPolicy_SampleHopEffects,%function\n"
    "OverworldActorWalkPolicy_SampleHopEffects:\n"
    "push {r4-r6,lr}\n"
    "movs r4,r0\n"
    "movs r5,#0\n"
    "movs r6,#1\n"
    "1:\n"
    "movs r0,#3\n"
    "ands r0,r4\n"
    "beq 2f\n"
    "subs r0,#1\n"
    "movs r1,#25\n"
    "lsls r1,r0\n"
    "movs r0,r1\n"
    "bl OverworldActorWalkPolicy_SampleChainChance\n"
    "cmp r0,#0\n"
    "beq 2f\n"
    "orrs r5,r6\n"
    "2:\n"
    "lsrs r4,#2\n"
    "lsls r6,#1\n"
    "cmp r6,#4\n"
    "bne 1b\n"
    "movs r0,r5\n"
    "pop {r4-r6,pc}\n"
    ".size OverworldActorWalkPolicy_SampleHopEffects,.-OverworldActorWalkPolicy_SampleHopEffects\n"
    ".syntax divided\n"
    ".text\n");
#else
u8 OverworldActorWalkPolicy_SampleHopEffects(u32 codes)
{
    return OverworldActorWalkPolicy_SampleHopEffectsInline(codes);
}
#endif

/* Private code host is parent Field. INPUT is admitted only by the current
 * field role; Actor still owns tuning, direction and all pending motion. */
static void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_field_walk_input_tuning")))
OverworldWalkInput_RefreshTuning(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call,
    u8 baseSpeed,
    BOOL linear)
{
    OverworldWildWalkMomentumState *state = &policy->walkMomentum;
    u8 visibleSpeed;
    if (state->speed == 0 || state->spotState != call->laneState) {
        OverworldActorWalkPolicy_ResetState(
            policy, TRUE, baseSpeed, call->laneState);
        policy->linearMode = linear;
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
    } else if (state->baseSpeed != baseSpeed || policy->linearMode != linear) {
        visibleSpeed = policy->lastWalkTime != 0
            ? policy->lastWalkTime : state->speed;
        state->baseSpeed = baseSpeed;
        policy->linearMode = linear;
        policy->linearElapsed = linear
            ? OverworldWalkTimingPolicy_LinearElapsedForTime(
                baseSpeed, call->lane->maxWalkSpeed,
                call->lane->tilesToAccelerate, visibleSpeed)
            : 0;
        policy->linearCarry = 0;
        policy->linearCapFrames = 0;
    }
}

void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_input_policy")))
OverworldActorWalkPolicy_ReduceInput(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call)
{
    OverworldWildWalkMomentumState *state = &policy->walkMomentum;
    u8 requestedDirection = call->direction;
    u8 baseSpeed = OverworldWalk_ClampTime(
        call->lane->chillSpeed);
    u8 visibleSpeed;
    u8 skidTiles;
    u8 turnSpeed;
    BOOL linear = call->lane->walkAccelerationStep
        == OVERWORLD_WALK_ACCELERATION_LINEAR_SPEED;

    if ((requestedDirection < 4
            && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                call->lane->hopAllowNonCardinal))
        || (requestedDirection >= 4
            && requestedDirection != OW_WILD_WALK_DIRECTION_NONE
            && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                call->lane->hopAllowNonCardinal))) {
        /* A rejected candidate is not a stop request. In particular, Wild
         * direction search must not clear an unfinished movement chain. */
        return;
    }
    OverworldWalkInput_RefreshTuning(policy, call, baseSpeed, linear);
    if (policy->bufferedDirection != OW_WILD_WALK_DIRECTION_NONE
        && policy->bufferedDirection != state->direction) {
        requestedDirection = policy->bufferedDirection;
    }
    if (state->skidRemaining != 0) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        return;
    }
    /* Walk variance may leave the displayed tile behind nominal momentum.
     * A turn or stop must brake from the speed the player just saw. */
    visibleSpeed = policy->lastWalkTime != 0
        ? policy->lastWalkTime : state->speed;
    if (requestedDirection == OW_WILD_WALK_DIRECTION_NONE) {
        skidTiles = OverworldWalk_ProfileSkidTiles(visibleSpeed, call->lane, TRUE);
        if (state->direction != OW_WILD_WALK_DIRECTION_NONE && skidTiles != 0) {
            if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP) != 0
                && !policy->stopPending) {
                policy->stopPending = TRUE;
                call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
                return;
            }
            policy->stopPending = FALSE;
            OverworldWalk_ProposeStep(
                policy, call, state->direction, state->direction,
                OverworldWalk_SkidTime(visibleSpeed),
                OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                    | OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID,
                skidTiles);
            return;
        }
        OverworldActorWalkPolicy_ResetState(
            policy, TRUE, baseSpeed, call->laneState);
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
        return;
    }
    policy->stopPending = FALSE;
    if (state->direction == OW_WILD_WALK_DIRECTION_NONE
        || requestedDirection == state->direction) {
        u8 time = state->speed;
        u8 carry = policy->linearCarry;

        if (linear && !OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION(
                call->lane->walkOptions)) {
            time = OverworldWalkTimingPolicy_LinearDuration(
                OverworldWalkTimingPolicy_LinearTimeQ8(baseSpeed,
                    call->lane->maxWalkSpeed, call->lane->tilesToAccelerate,
                    policy->linearElapsed), carry, &carry);
        }
        OverworldWalk_ProposeStep(
            policy, call, requestedDirection, requestedDirection,
            time, call->stepFlags, 0);
        if (linear) {
            call->reserved[0] = time;
            call->reserved[1] = carry;
            call->reserved[2] = policy->linearElapsed;
        }
        return;
    }
    if (!OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(call->lane->walkOptions)) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        call->stepDirection = state->direction;
        policy->bufferedDirection = OW_WILD_WALK_DIRECTION_NONE;
        return;
    }
    skidTiles = OverworldWalk_IsFortyFiveDegreeTurn(
            state->direction, requestedDirection)
        ? 0
        : OverworldWalk_ProfileSkidTiles(visibleSpeed, call->lane, FALSE);
    if (linear) {
        u8 elapsed = policy->linearElapsed > policy->lastWalkTime
            ? policy->linearElapsed - policy->lastWalkTime : 0;
        u8 carry;

        turnSpeed = OverworldWalkTimingPolicy_LinearDuration(
            OverworldWalkTimingPolicy_LinearTimeQ8(baseSpeed,
                call->lane->maxWalkSpeed, call->lane->tilesToAccelerate,
                elapsed), 0, &carry);
        call->reserved[2] = elapsed;
    } else {
        turnSpeed = OverworldWalk_DecelerateTime(
            visibleSpeed, state->baseSpeed, call->lane->walkAccelerationStep);
    }
    if (skidTiles != 0
        && (call->flags
            & OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID) == 0
        && OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(
            call->lane->tilesBeforeTurnSkid) != 0
        && state->turnDirection >= OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(
            call->lane->tilesBeforeTurnSkid)) {
        OverworldWalk_ProposeStep(
            policy, call, state->direction, requestedDirection,
            OverworldWalk_SkidTime(visibleSpeed),
            OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                | OVERWORLD_ACTOR_WALK_STEP_SKID,
            skidTiles);
        call->reserved[0] = turnSpeed;
        return;
    }
    OverworldWalk_ProposeStep(
        policy, call, requestedDirection, requestedDirection,
        turnSpeed,
        OVERWORLD_ACTOR_WALK_STEP_VALIDATE
            | OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION,
        0);
    /* A rejected turn must not change momentum. Commit the slower nominal
     * time only after the engine accepts this proposal. */
    call->reserved[0] = turnSpeed;
}


void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_mount_save_proposal")))
Walk_MountSaveProposal(
    OverworldMountRuntimeState *state,
    const OverworldActorWalkPolicyCall *policyCall)
{
    if (policyCall->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
        return;
    }
    OverworldMountWalkProposal_SaveReserved(policyCall);
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


void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_proposal_save_reserved")))
OverworldMountWalkProposal_SaveReserved(const OverworldActorWalkPolicyCall *call)
{
    OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[0] = call->reserved[1];
    OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[1] = call->reserved[2];
    OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2] = call->distance;
}

void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_proposal_restore_reserved")))
OverworldMountWalkProposal_RestoreReserved(OverworldActorWalkPolicyCall *call)
{
    call->reserved[1] = OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[0];
    call->reserved[2] = OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[1];
}

void *OverworldWalkPolicy_Memset(void *destination, int value, u32 size);

BOOL __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_mount_finish")))
OverworldMountWalkProposal_Finish(
    const OverworldMountRuntimeState *state, BOOL started,
    BOOL crashOnBlocked, OverworldActorWalkPolicyCall *output)
{
    OverworldWalkPolicy_Memset(output, 0, sizeof(*output));
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
    /* Admission distance is transported with the exact INPUT proposal.
     * START_RESULT must not recompute it from a changed timing policy. */
    output->distance = OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2];
    output->reserved[0] = state->reservedPolicyProfile[
        OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX];
    OverworldMountWalkProposal_RestoreReserved(output);
    if (crashOnBlocked) {
        output->flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED;
    }
    return OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
        ->reduceWalk(output);
}

/* A field transition (crossing into the next map) resets every slot's Walk
 * policy. The Follower keeps walking with the player, so it keeps its
 * momentum: restarting at base speed made a Sprint Follower fall several tiles
 * behind after each border and cut diagonally at the next turn. Pending step,
 * chain and skid state are still cleared. Lives at the ITCM end (0x01FFFF80). */
void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_walk_policy_transition_reset")))
OverworldActorWalkPolicy_ResetKeepingFollowerMomentum(
    OverworldActorPolicyState *policy, u32 actorSlot)
{
    typedef u32 WalkMomentumWord __attribute__((may_alias));
    WalkMomentumWord *words = (WalkMomentumWord *)&policy->walkMomentum;
    u32 first = words[0];
    u32 second = words[1];
    const OverworldActorSystemState *actors =
        (const OverworldActorSystemState *)OVERWORLD_ACTOR_SYSTEM_STATE_ADDR;

    OverworldActorWalkPolicy_ResetState(policy, FALSE, 0, 0);
    if (actorSlot == OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT
        && (u8)(first >> 16) != 0 /* speed */
        && (u8)(actors->transition.phase - OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE)
            < (OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE
                - OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE)) {
        words[0] = first;
        words[1] = second & ~0xFF00u; /* no carried skid */
    }
}
