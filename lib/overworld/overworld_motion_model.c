#include "overworld_motion_model.h"
#include "overworld_actor_hop_geometry.h"
#ifndef OVERWORLD_MOTION_HOST
__asm__(".global OverworldActorHopGeometry_NextCell\n.type OverworldActorHopGeometry_NextCell, %function\n.thumb\n.thumb_func\n.thumb_set OverworldActorHopGeometry_NextCell, 0x023BFFA2\n");
#endif

#ifdef OVERWORLD_MOTION_HOST
#include <string.h>
#else
u32 __attribute__((noinline, used,
    section(".overworld_motion_slam_rise_height")))
OverworldMotion_SlamRiseUnitHeightNative(u32 progress, u32 total)
{
    u32 height = OverworldMotion_SlamUnitHeight(progress, total);

    return 2u * height - ((height * height) >> 12);
}
#endif

static u16 OverworldMotion_AbsDistance(s16 first, s16 second)
{
    s32 difference = (s32)first - second;

    return difference < 0 ? (u16)-difference : (u16)difference;
}

static u16 OverworldMotion_GreatestCommonDivisor(u32 first, u32 second)
{
    while (second != 0) {
        u32 remainder = first % second;

        first = second;
        second = remainder;
    }
    return first;
}

static u32 OverworldMotion_PathLengthForTiles(
    s16 startX,
    s16 startY,
    s16 targetX,
    s16 targetY)
{
    u16 xDistance = OverworldMotion_AbsDistance(targetX, startX);
    u16 yDistance = OverworldMotion_AbsDistance(targetY, startY);
    u16 common;

    if (xDistance == 0 || yDistance == 0) {
        return (u32)xDistance + yDistance;
    }
    common = OverworldMotion_GreatestCommonDivisor(xDistance, yDistance);
    /* Both normalized axes are odd exactly when both contain the GCD's
     * least significant set bit. Keep the same rational crossing count. */
    return (u32)xDistance + yDistance
        - ((xDistance & yDistance & (common & (0u - common))) != 0
            ? common : 0);
}

static u16 OverworldMotion_PathLength(const OverworldMotionPlan *plan)
{
    return (u16)OverworldMotion_PathLengthForTiles(
        plan->startX,
        plan->startY,
        plan->targetX,
        plan->targetY);
}

static u32 OverworldMotion_DoubledRatioFloor(
    u16 distance,
    u16 elapsed,
    u16 duration)
{
    u32 product = (u32)distance * elapsed;
    u32 quotient = product / duration;
    u32 remainder = product - quotient * duration;

    /* floor(2 * product / duration), without overflowing a 32-bit product. */
    return quotient * 2 + ((remainder * 2) >= duration ? 1 : 0);
}


void __attribute__((noinline)) OverworldActorHopGeometry_Init(
    OverworldActorHopGeometry *geometry, const void *coordinates)
{
    const u8 *bytes = coordinates;
    s32 startX = *(const s16 *)(bytes + 0);
    s32 startY = *(const s16 *)(bytes + 2);
    s32 dx = *(const s16 *)(bytes + 4) - startX;
    s32 dy = *(const s16 *)(bytes + 6) - startY;
    u32 absDx = dx < 0 ? 0u - (u32)dx : (u32)dx;
    u32 absDy = dy < 0 ? 0u - (u32)dy : (u32)dy;
    geometry->tileX = startX;
    geometry->tileY = startY;
    geometry->stepX = dx > 0 ? 1 : -1;
    geometry->stepY = dy > 0 ? 1 : -1;
    geometry->absDx = absDx;
    geometry->absDy = absDy;
    geometry->xBoundary = 1;
    geometry->yBoundary = 1;
    geometry->error = (s32)absDy - absDx;
}

u8 OverworldMotion_GetPathAdvanceTile(
    const OverworldMotionPlan *plan,
    u16 advanceIndex,
    s16 *tileX,
    s16 *tileY)
{
    u32 pathLength;
    u16 step;
    OverworldActorHopGeometry geometry;
    if (plan == NULL || tileX == NULL || tileY == NULL) {
        return FALSE;
    }
    pathLength = OverworldMotion_PathLengthForTiles(
        plan->startX, plan->startY, plan->targetX, plan->targetY);
    if (pathLength > 0xFFFFu || advanceIndex > pathLength) {
        return FALSE;
    }
    OverworldActorHopGeometry_Init(&geometry, &plan->startX);
    for (step = 0; step < advanceIndex; step++) {
        OverworldActorHopGeometry_NextCell(&geometry);
    }
    *tileX = geometry.tileX;
    *tileY = geometry.tileY;
    return TRUE;
}

static u16 OverworldMotion_PathProgress(
    const OverworldMotionPlan *plan,
    u16 elapsed,
    u32 fullPathLength)
{
    u16 xDistance = OverworldMotion_AbsDistance(
        plan->targetX, plan->startX);
    u16 yDistance = OverworldMotion_AbsDistance(
        plan->targetY, plan->startY);
    /* Full length already subtracts the coincident crossing stride. */
    u16 common = (u32)xDistance + yDistance - fullPathLength;
    u32 xThreshold;
    u32 yThreshold;
    u32 xCrossings;
    u32 yCrossings;
    u32 simultaneousCrossings = 0;
    u16 travelFrames = (plan->flags & OVERWORLD_MOTION_FLAG_SLAM)
        ? plan->arcRiseFrames : plan->duration;

    if (elapsed >= travelFrames) {
        return (u16)fullPathLength;
    }
    /*
     * A tile center crosses the Nth axis boundary at
     * (2N - 1) / (2 * axisDistance). Count those rational events directly;
     * render sway and signed fixed-point rounding must not create authority.
     */
    xThreshold = OverworldMotion_DoubledRatioFloor(
        xDistance, elapsed, travelFrames);
    yThreshold = OverworldMotion_DoubledRatioFloor(
        yDistance, elapsed, travelFrames);
    xCrossings = (xThreshold + 1) / 2;
    yCrossings = (yThreshold + 1) / 2;
    if (xCrossings > xDistance) {
        xCrossings = xDistance;
    }
    if (yCrossings > yDistance) {
        yCrossings = yDistance;
    }
    if (common != 0) {
        u32 simultaneousThreshold = OverworldMotion_DoubledRatioFloor(
            common, elapsed, travelFrames);

        simultaneousCrossings = (simultaneousThreshold + 1) / 2;
        if (simultaneousCrossings > common) {
            simultaneousCrossings = common;
        }
    }
    return (u16)(xCrossings + yCrossings - simultaneousCrossings);
}

static u8 OverworldMotion_SlamPhasesValid(
    u8 kind, u16 duration, u8 peak, u8 rise, u8 hang)
{
#ifdef OVERWORLD_MOTION_HOST
    return kind == OVERWORLD_MOTION_KIND_HOP && peak != 0 && rise != 0
        && (u16)rise + hang < duration;
#else
    return OverworldMotion_SlamPhaseCheck(kind, peak, rise,
        (s32)duration - hang);
#endif
}

static OverworldMotionDecision OverworldMotion_CandidateDecision(u16 flags)
{
    if (flags & OVERWORLD_MOTION_CANDIDATE_WORLD_BUSY) {
        return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_BAD_DIRECTION) {
        return OVERWORLD_MOTION_DECISION_DIRECTION;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_SIDE_BLOCKED) {
        return OVERWORLD_MOTION_DECISION_SIDE_TILE;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN) {
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_OCCUPIED) {
        return OVERWORLD_MOTION_DECISION_OCCUPIED;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_RESERVED) {
        return OVERWORLD_MOTION_DECISION_RESERVED;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_BLOCKED) {
        return OVERWORLD_MOTION_DECISION_BLOCKED;
    }
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

OverworldMotionDecision OverworldMotion_SelectPlan(
    const OverworldMotionIntent *intent,
    s16 startX,
    s16 startY,
    s32 startBaseY,
    const OverworldMotionCandidate *candidates,
    u8 candidateCount,
    OverworldMotionPlan *plan,
    u8 *selectedIndex)
{
    OverworldMotionDecision decision = OVERWORLD_MOTION_DECISION_NO_CANDIDATE;
    u8 i;

    if (intent == NULL || candidates == NULL || plan == NULL
        || intent->version != OVERWORLD_MOTION_MODEL_VERSION
        || intent->kind == OVERWORLD_MOTION_KIND_NONE
        || (intent->duration == 0
            && intent->kind != OVERWORLD_MOTION_KIND_TELEPORT)
        || ((intent->flags & OVERWORLD_MOTION_FLAG_SLAM)
            && !OverworldMotion_SlamPhasesValid(intent->kind, intent->duration,
                intent->arcHeightQ4, intent->arcRiseFrames, intent->arcHangFrames))
        || candidateCount == 0
        || candidateCount > OVERWORLD_MOTION_MAX_CANDIDATES) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    for (i = 0; i < candidateCount; i++) {
        decision = OverworldMotion_CandidateDecision(candidates[i].rejectionFlags);
        if (decision == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY) {
            return decision;
        }
        if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
            if (OverworldMotion_PathLengthForTiles(
                    startX,
                    startY,
                    candidates[i].targetX,
                    candidates[i].targetY) > 0xFFFFu) {
                return OVERWORLD_MOTION_DECISION_PROFILE;
            }
            memset(plan, 0, sizeof(*plan));
            plan->version = OVERWORLD_MOTION_MODEL_VERSION;
            plan->kind = intent->kind;
            plan->facing = intent->facing;
            plan->fieldEpoch = intent->fieldEpoch;
            plan->behaviorFingerprint = intent->behaviorFingerprint;
            plan->startX = startX;
            plan->startY = startY;
            plan->targetX = candidates[i].targetX;
            plan->targetY = candidates[i].targetY;
            plan->startBaseY = startBaseY;
            plan->targetBaseY = candidates[i].targetBaseY;
            plan->duration = intent->duration;
            plan->reservationId = candidates[i].reservationId;
            plan->direction = candidates[i].direction;
            plan->distance = candidates[i].distance;
            plan->arcHeightQ4 = intent->arcHeightQ4;
            plan->spinSpeed = intent->spinSpeed;
            plan->swayWidth = intent->swayWidth;
            plan->visibilityPolicy = intent->visibilityPolicy;
            plan->pauseFrames = intent->pauseFrames;
            plan->pathAdvancePolicy = intent->pathAdvancePolicy;
            plan->commitPolicy = intent->commitPolicy;
            plan->flags = intent->flags;
            if (selectedIndex != NULL) {
                *selectedIndex = i;
            }
            return decision;
        }
    }
    return decision;
}

void OverworldMotion_Reset(OverworldMotionState *state)
{
    if (state != NULL) {
        memset(state, 0, sizeof(*state));
    }
}

OverworldMotionDecision OverworldMotion_Begin(
    OverworldMotionState *state,
    const OverworldMotionPlan *plan)
{
    if (state == NULL || plan == NULL
        || plan->version != OVERWORLD_MOTION_MODEL_VERSION
        || plan->kind == OVERWORLD_MOTION_KIND_NONE
        || (plan->duration == 0
            && plan->kind != OVERWORLD_MOTION_KIND_TELEPORT)
        || ((plan->flags & OVERWORLD_MOTION_FLAG_SLAM)
            && !OverworldMotion_SlamPhasesValid(plan->kind, plan->duration,
                plan->arcHeightQ4, plan->arcRiseFrames, plan->arcHangFrames))
        || OverworldMotion_PathLengthForTiles(
            plan->startX,
            plan->startY,
            plan->targetX,
            plan->targetY) > 0xFFFFu) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (state->phase != OVERWORLD_MOTION_PHASE_IDLE
        && state->phase != OVERWORLD_MOTION_PHASE_CANCELED) {
        return OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
    }
    OverworldMotion_Reset(state);
    state->plan = *plan;
    state->phase = OVERWORLD_MOTION_PHASE_MOVING;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static s32 OverworldMotion_Lerp(s32 start, s32 target, u16 elapsed, u16 total)
{
    s32 delta;
    s32 quotient;
    s32 remainder;
    u32 fractional;

    if (elapsed >= total || total == 0) {
        return target;
    }
    delta = target - start;
    quotient = delta / total;
    remainder = delta - quotient * total;
    fractional = (u32)(remainder < 0 ? -remainder : remainder)
        * elapsed / total;
    return start + quotient * elapsed
        + (remainder < 0 ? -(s32)fractional : (s32)fractional);
}

static s32 __attribute__((noinline)) OverworldMotion_SymmetricArc(
    u32 peak, u32 elapsed, u32 duration)
{
    u32 curve;
    if (peak == 0 || elapsed >= duration) { return 0; }
    curve = (4u * elapsed * (duration - elapsed)) / duration;
    return (s32)(peak * ((curve << 12) / duration));
}

static s32 OverworldMotion_Arc(const OverworldMotionPlan *plan, u16 elapsed)
{
    u32 curve;

    if (plan->arcHeightQ4 == 0 || elapsed >= plan->duration) {
        return 0;
    }
    if (plan->flags & OVERWORLD_MOTION_FLAG_SLAM) {
        if (elapsed <= plan->arcRiseFrames) {
            curve = OverworldMotion_SlamRiseUnitHeight(elapsed, plan->arcRiseFrames);
        } else if (elapsed <= (u16)plan->arcRiseFrames + plan->arcHangFrames) {
            curve = 0x1000;
        } else {
            curve = OverworldMotion_SlamUnitHeight(plan->duration - elapsed,
                plan->duration - plan->arcRiseFrames - plan->arcHangFrames);
        }
        return (s32)(plan->arcHeightQ4 * curve);
    }
    return OverworldMotion_SymmetricArc(plan->arcHeightQ4, elapsed,
        plan->duration);
}

static s32 OverworldMotion_Sway(const OverworldMotionPlan *plan, u16 elapsed)
{
    u32 swayElapsed;
    s32 sway;

    if ((plan->flags & OVERWORLD_MOTION_FLAG_SLAM)
        || plan->swayWidth == 0 || elapsed >= plan->duration) {
        return 0;
    }
    swayElapsed = (u32)elapsed << 1;
    sway = OverworldMotion_SymmetricArc(plan->swayWidth,
        (u16)(swayElapsed >= plan->duration
            ? swayElapsed - plan->duration
            : swayElapsed), plan->duration);
    return swayElapsed >= plan->duration ? -sway : sway;
}

static u8 OverworldMotion_SpinFacing(u8 facing, u16 elapsed, u8 spinSpeed)
{
    u8 step;

    if (spinSpeed == 0) {
        return facing;
    }
    /* The engine stores N/S/W/E. Spin order is N/E/S/W. */
    step = (u8)(((facing >> 1) & 1)
        | (((facing ^ (facing >> 1)) & 1) << 1));
    step = (u8)((step + elapsed / spinSpeed) & 3);
    return (u8)(((step & 1) << 1)
        | ((step ^ (step >> 1)) & 1));
}

static void OverworldMotion_Sample(
    const OverworldMotionState *state,
    OverworldMotionSample *sample)
{
    const OverworldMotionPlan *plan = &state->plan;
    u32 fullPathLength = OverworldMotion_PathLengthForTiles(
        plan->startX, plan->startY, plan->targetX, plan->targetY);
    u16 pathLength = (u16)fullPathLength;
    u16 pathAdvance;
    s32 pathX;
    s32 pathZ;
    u16 travelFrames = (plan->flags & OVERWORLD_MOTION_FLAG_SLAM)
        ? plan->arcRiseFrames : plan->duration;

    memset(sample, 0, sizeof(*sample));
    pathX = OverworldMotion_Lerp(
        (s32)plan->startX * 0x10000 + 0x8000,
        (s32)plan->targetX * 0x10000 + 0x8000,
        state->elapsed,
        travelFrames);
    pathZ = OverworldMotion_Lerp(
        (s32)plan->startY * 0x10000 + 0x8000,
        (s32)plan->targetY * 0x10000 + 0x8000,
        state->elapsed,
        travelFrames);
    pathAdvance = OverworldMotion_PathProgress(plan, state->elapsed, fullPathLength);
    sample->renderX = pathX;
    sample->renderZ = pathZ;
    sample->baseY = OverworldMotion_Lerp(
        plan->startBaseY,
        plan->targetBaseY,
        state->elapsed,
        travelFrames);
    sample->heightOffset = OverworldMotion_Arc(plan, state->elapsed);
    sample->swayOffset = OverworldMotion_Sway(plan, state->elapsed);
    sample->renderY = sample->baseY + sample->heightOffset;
    if (plan->startY == plan->targetY) {
        sample->renderZ += sample->swayOffset;
    } else {
        sample->renderX += sample->swayOffset;
    }
    sample->elapsed = state->elapsed;
    sample->duration = plan->duration;
    if (state->pathAdvancesPublished < pathLength) {
        sample->firstPathAdvance = state->pathAdvancesPublished + 1;
        sample->lastPathAdvance = pathAdvance;
    }
    sample->facing = OverworldMotion_SpinFacing(
        plan->facing,
        state->elapsed,
        (plan->flags & OVERWORLD_MOTION_FLAG_SLAM) ? 0 : plan->spinSpeed);
    sample->visible = plan->visibilityPolicy
            == OVERWORLD_MOTION_VISIBILITY_HIDDEN
        ? FALSE
        : plan->visibilityPolicy == OVERWORLD_MOTION_VISIBILITY_FLICKER
            ? (u8)(((state->elapsed / 2) & 1) == 0)
            : TRUE;
}

OverworldMotionDecision OverworldMotion_Read(
    const OverworldMotionState *state,
    u16 fieldEpoch,
    OverworldMotionSample *sample)
{
    if (sample == NULL) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    memset(sample, 0, sizeof(*sample));
    if (state == NULL
        || state->phase == OVERWORLD_MOTION_PHASE_IDLE
        || state->phase == OVERWORLD_MOTION_PHASE_CANCELED) {
        return OVERWORLD_MOTION_DECISION_NO_CANDIDATE;
    }
    if (state->plan.fieldEpoch != fieldEpoch) {
        return OVERWORLD_MOTION_DECISION_STALE_FIELD;
    }
    OverworldMotion_Sample(state, sample);
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

u16 OverworldMotion_Tick(
    OverworldMotionState *state,
    u16 fieldEpoch,
    OverworldMotionSample *sample)
{
    u16 flags = 0;

    if (sample == NULL) {
        return 0;
    }
    memset(sample, 0, sizeof(*sample));
    if (state == NULL
        || state->phase == OVERWORLD_MOTION_PHASE_IDLE
        || state->phase == OVERWORLD_MOTION_PHASE_CANCELED) {
        return 0;
    }
    if (state->plan.fieldEpoch != fieldEpoch) {
        OverworldMotion_Suspend(state);
        OverworldMotion_Sample(state, sample);
        return 0;
    }
    if (state->phase == OVERWORLD_MOTION_PHASE_SUSPENDED) {
        OverworldMotion_Sample(state, sample);
        return 0;
    }
    if (state->phase == OVERWORLD_MOTION_PHASE_MOVING) {
        if (state->elapsed < state->plan.duration) {
            state->elapsed++;
        }
        OverworldMotion_Sample(state, sample);
        flags |= OVERWORLD_MOTION_TICK_MOVED;
        if (sample->firstPathAdvance != 0
            && sample->lastPathAdvance >= sample->firstPathAdvance
            && state->plan.pathAdvancePolicy
                != OVERWORLD_MOTION_PATH_ADVANCE_NONE) {
            flags |= OVERWORLD_MOTION_TICK_PATH_ADVANCED;
            state->pathAdvancesPublished = sample->lastPathAdvance;
        }
        if (state->plan.visibilityPolicy
            != OVERWORLD_MOTION_VISIBILITY_VISIBLE) {
            flags |= OVERWORLD_MOTION_TICK_VISIBILITY;
        }
        if (state->elapsed >= state->plan.duration) {
            state->phase = OVERWORLD_MOTION_PHASE_COMMIT_PENDING;
            flags |= OVERWORLD_MOTION_TICK_REACHED_TARGET
                | OVERWORLD_MOTION_TICK_COMMIT_READY;
        }
    } else if (state->phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        OverworldMotion_Sample(state, sample);
        flags |= OVERWORLD_MOTION_TICK_COMMIT_READY;
    } else if (state->phase == OVERWORLD_MOTION_PHASE_SETTLING) {
        OverworldMotion_Sample(state, sample);
        if (state->settleRemaining != 0) {
            state->settleRemaining--;
        }
        if (state->settleRemaining == 0) {
            state->phase = OVERWORLD_MOTION_PHASE_IDLE;
            flags |= OVERWORLD_MOTION_TICK_FINISHED;
        }
    }
    sample->flags = flags;
    return flags;
}

OverworldMotionDecision OverworldMotion_AcknowledgeCommit(
    OverworldMotionState *state,
    u16 fieldEpoch)
{
    if (state == NULL || state->phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        return OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
    }
    if (state->plan.fieldEpoch != fieldEpoch) {
        OverworldMotion_Suspend(state);
        return OVERWORLD_MOTION_DECISION_STALE_FIELD;
    }
    if (!state->commitPublished) {
        state->commitPublished = TRUE;
        state->commitSequence++;
    }
    state->settleRemaining = state->plan.pauseFrames;
    state->phase = state->settleRemaining == 0
        ? OVERWORLD_MOTION_PHASE_IDLE
        : OVERWORLD_MOTION_PHASE_SETTLING;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

void OverworldMotion_Suspend(OverworldMotionState *state)
{
    if (state != NULL
        && state->phase != OVERWORLD_MOTION_PHASE_IDLE
        && state->phase != OVERWORLD_MOTION_PHASE_CANCELED
        && state->phase != OVERWORLD_MOTION_PHASE_SUSPENDED) {
        state->phaseBeforeSuspend = state->phase;
        state->phase = OVERWORLD_MOTION_PHASE_SUSPENDED;
    }
}

OverworldMotionDecision OverworldMotion_Resume(
    OverworldMotionState *state,
    u16 fieldEpoch)
{
    if (state == NULL || state->phase != OVERWORLD_MOTION_PHASE_SUSPENDED) {
        return OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
    }
    if (state->plan.fieldEpoch != fieldEpoch) {
        return OVERWORLD_MOTION_DECISION_STALE_FIELD;
    }
    state->phase = state->phaseBeforeSuspend;
    state->phaseBeforeSuspend = OVERWORLD_MOTION_PHASE_IDLE;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

OverworldMotionDecision OverworldMotion_RebindField(
    OverworldMotionState *state,
    u16 previousFieldEpoch,
    u16 reboundFieldEpoch)
{
    if (state == NULL || state->phase != OVERWORLD_MOTION_PHASE_SUSPENDED) {
        return OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
    }
    if (state->plan.fieldEpoch != previousFieldEpoch) {
        return OVERWORLD_MOTION_DECISION_STALE_FIELD;
    }
    state->plan.fieldEpoch = reboundFieldEpoch;
    return OverworldMotion_Resume(state, reboundFieldEpoch);
}

void OverworldMotion_Cancel(OverworldMotionState *state, u8 reason)
{
    if (state != NULL
        && state->phase != OVERWORLD_MOTION_PHASE_IDLE
        && state->phase != OVERWORLD_MOTION_PHASE_CANCELED) {
        state->cancelReason = reason;
        state->phase = OVERWORLD_MOTION_PHASE_CANCELED;
    }
}
