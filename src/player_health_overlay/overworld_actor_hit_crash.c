#include "../../include/overworld_actor_system_internal.h"

/* Actor-owned code in the existing boot-resident HP161 gap. No HP state or
 * second motion engine lives here. Preserve the shared model's Thumb import. */
__asm__(".thumb\n.thumb_func\n.thumb_set OverworldMotion_Suspend, 0x023B98A4\n");

BOOL __attribute__((noinline, used, optimize("Os"),
    section(".overworld_actor_hit_crash")))
OverworldActorHitCrash_Apply(
    OverworldActorRuntimeSlot *slot,
    OverworldActorWalkPolicyCall *call,
    u16 fieldEpoch)
{
    typedef u16 HitCrashHalfword __attribute__((may_alias));
    typedef u32 HitCrashWord __attribute__((may_alias));
    HitCrashHalfword *receipt = (HitCrashHalfword *)(void *)call->reserved;
    OverworldActorStateSnapshot *actor = &slot->snapshot;
    OverworldMotionState *motion = &slot->motion;
    OverworldActorPolicyState *policy = &slot->policy;
    BOOL moving = motion->phase == OVERWORLD_MOTION_PHASE_MOVING
        || motion->phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING;
    BOOL settling = motion->phase == OVERWORLD_MOTION_PHASE_SETTLING;
    u16 identity = actor->reservationId;

    if (call->version != OVERWORLD_ACTOR_WALK_POLICY_VERSION
        || call->size != sizeof(*call) || !actor->active
        || call->actorSlot != actor->handle.slot
        || call->operation != OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH
        || fieldEpoch == 0 || actor->handle.fieldEpoch != fieldEpoch
        || receipt[1] != fieldEpoch) {
        return FALSE;
    }
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
    call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_NONE;
    if (call->flags == OVERWORLD_ACTOR_WALK_HIT_CRASH_SETTLE) {
        if (receipt[0] == 0 || receipt[0] != identity
            || identity != motion->plan.reservationId
            || motion->plan.fieldEpoch != fieldEpoch
            || motion->phase != OVERWORLD_MOTION_PHASE_SUSPENDED) {
            return FALSE;
        }
        /* The role already restored the saved origin/base and removed its
         * native command. Drop the old transaction without END or COMMIT. */
        *(HitCrashWord *)(void *)&actor->logicalX =
            *(HitCrashWord *)(void *)&actor->originX;
        *(HitCrashWord *)(void *)&actor->renderX =
            *(HitCrashWord *)(void *)&actor->originX;
        *(HitCrashWord *)(void *)&actor->targetX =
            *(HitCrashWord *)(void *)&actor->originX;
        goto released;
    }
    if (call->flags != OVERWORLD_ACTOR_WALK_HIT_CRASH_START
        || (moving
            ? identity == 0 || identity != motion->plan.reservationId
                || motion->plan.fieldEpoch != fieldEpoch
                || motion->commitPublished != 0
                || (motion->plan.kind != OVERWORLD_MOTION_KIND_WALK
                    && motion->plan.kind != OVERWORLD_MOTION_KIND_SKID)
            : identity != 0
                || (settling
                    ? !motion->commitPublished
                        || motion->plan.fieldEpoch != fieldEpoch
                        || (motion->plan.kind != OVERWORLD_MOTION_KIND_WALK
                            && motion->plan.kind != OVERWORLD_MOTION_KIND_SKID)
                        || actor->logicalX != motion->plan.targetX
                        || actor->logicalY != motion->plan.targetY
                    : motion->phase != OVERWORLD_MOTION_PHASE_IDLE))) {
        return FALSE;
    }
    /* A turn buffer and a fast ordinary Walk are not yet a due skid. */
    if (!policy->pendingSkid && !policy->walkMomentum.skidRemaining
        && !policy->stopPending
        && !(moving && motion->plan.kind == OVERWORLD_MOTION_KIND_SKID)
        && !(policy->pendingStep == OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL
            && (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0)) {
        return TRUE;
    }
    if (!OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY->reduceWalk(
            policy, actor, call)) {
        return FALSE;
    }
    receipt[0] = identity;
    if (moving) {
        OverworldMotion_Suspend(motion);
        actor->motionPhase = OVERWORLD_MOTION_PHASE_SUSPENDED;
        actor->reserved1 = 0;
    } else if (settling) {
        /* This tile already committed. End only its authored pause and keep
         * that completed tile as the knockback origin. It needs no settlement
         * token and must never emit a second COMMIT or old END. */
        *(HitCrashWord *)(void *)&actor->renderX =
            *(HitCrashWord *)(void *)&actor->logicalX;
        goto released;
    }
    return TRUE;

released:
    motion->phase = OVERWORLD_MOTION_PHASE_IDLE;
    motion->phaseBeforeSuspend = OVERWORLD_MOTION_PHASE_IDLE;
    motion->elapsed = 0;
    motion->settleRemaining = 0;
    policy->pendingFirstPathAdvance = 0;
    policy->pendingLastPathAdvance = 0;
    policy->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
    actor->motionPhase = OVERWORLD_MOTION_PHASE_IDLE;
    actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;
    actor->motionElapsed = 0;
    actor->motionDuration = 0;
    actor->reserved1 = 0;
    actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;
    actor->reservationId = 0;
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
    return TRUE;
}
