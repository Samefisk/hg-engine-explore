#include "overworld_motion_model.h"

#ifdef OVERWORLD_MOTION_HOST
#include <string.h>
#endif

static u16 OverworldMotion_AbsDistance(s16 first, s16 second)
{
    s32 difference = (s32)first - second;

    return difference < 0 ? (u16)-difference : (u16)difference;
}

static u16 OverworldMotion_GreatestCommonDivisor(u16 first, u16 second)
{
    while (second != 0) {
        u16 remainder = first % second;

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
    return (u32)xDistance + yDistance
        - (((xDistance / common) & 1) != 0
                && ((yDistance / common) & 1) != 0
            ? common
            : 0);
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

u8 OverworldMotion_GetPathAdvanceTile(
    const OverworldMotionPlan *plan,
    u16 advanceIndex,
    s16 *tileX,
    s16 *tileY)
{
    u32 pathLength;
    u16 xDistance;
    u16 yDistance;
    u32 xBoundary = 1;
    u32 yBoundary = 1;
    s16 x;
    s16 y;
    s16 xStep;
    s16 yStep;
    u16 step;

    if (plan == NULL || tileX == NULL || tileY == NULL) {
        return FALSE;
    }
    pathLength = OverworldMotion_PathLengthForTiles(
        plan->startX, plan->startY, plan->targetX, plan->targetY);
    if (pathLength > 0xFFFFu || advanceIndex > pathLength) {
        return FALSE;
    }
    xDistance = OverworldMotion_AbsDistance(plan->targetX, plan->startX);
    yDistance = OverworldMotion_AbsDistance(plan->targetY, plan->startY);
    x = plan->startX;
    y = plan->startY;
    xStep = plan->targetX > plan->startX ? 1 : -1;
    yStep = plan->targetY > plan->startY ? 1 : -1;
    for (step = 0; step < advanceIndex; step++) {
        u64 xTime = xDistance == 0
            ? ~(u64)0
            : (u64)xBoundary * yDistance;
        u64 yTime = yDistance == 0
            ? ~(u64)0
            : (u64)yBoundary * xDistance;

        if (xTime <= yTime) {
            x += xStep;
            xBoundary += 2;
        }
        if (yTime <= xTime) {
            y += yStep;
            yBoundary += 2;
        }
    }
    *tileX = x;
    *tileY = y;
    return TRUE;
}

static u16 OverworldMotion_PathProgress(
    const OverworldMotionPlan *plan,
    u16 elapsed)
{
    u16 xDistance = OverworldMotion_AbsDistance(
        plan->targetX, plan->startX);
    u16 yDistance = OverworldMotion_AbsDistance(
        plan->targetY, plan->startY);
    u16 common = OverworldMotion_GreatestCommonDivisor(xDistance, yDistance);
    u32 xThreshold;
    u32 yThreshold;
    u32 xCrossings;
    u32 yCrossings;
    u32 simultaneousCrossings = 0;

    if (elapsed >= plan->duration) {
        return OverworldMotion_PathLength(plan);
    }
    /*
     * A tile center crosses the Nth axis boundary at
     * (2N - 1) / (2 * axisDistance). Count those rational events directly;
     * render sway and signed fixed-point rounding must not create authority.
     */
    xThreshold = OverworldMotion_DoubledRatioFloor(
        xDistance, elapsed, plan->duration);
    yThreshold = OverworldMotion_DoubledRatioFloor(
        yDistance, elapsed, plan->duration);
    xCrossings = (xThreshold + 1) / 2;
    yCrossings = (yThreshold + 1) / 2;
    if (xCrossings > xDistance) {
        xCrossings = xDistance;
    }
    if (yCrossings > yDistance) {
        yCrossings = yDistance;
    }
    if (common != 0
        && ((xDistance / common) & 1) != 0
        && ((yDistance / common) & 1) != 0) {
        u32 simultaneousThreshold = OverworldMotion_DoubledRatioFloor(
            common, elapsed, plan->duration);

        simultaneousCrossings = (simultaneousThreshold + 1) / 2;
        if (simultaneousCrossings > common) {
            simultaneousCrossings = common;
        }
    }
    return (u16)(xCrossings + yCrossings - simultaneousCrossings);
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
        || intent->duration == 0
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
        || plan->duration == 0
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
    s64 delta;
    s64 quotient;
    s64 remainder;

    if (elapsed >= total || total == 0) {
        return target;
    }
    delta = (s64)target - start;
    quotient = delta / total;
    remainder = delta - quotient * total;
    return (s32)(start + quotient * elapsed
        + remainder * elapsed / total);
}

static s32 OverworldMotion_Arc(const OverworldMotionPlan *plan, u16 elapsed)
{
    u32 curve;

    if (plan->arcHeightQ4 == 0 || elapsed >= plan->duration) {
        return 0;
    }
    /* Keep the deployed renderer's truncation order exactly. */
    curve = (4u * elapsed * (plan->duration - elapsed)) / plan->duration;
    return (s32)(plan->arcHeightQ4
        * ((curve << 12) / plan->duration));
}

static s32 OverworldMotion_Sway(const OverworldMotionPlan *plan, u16 elapsed)
{
    OverworldMotionPlan swayPlan;
    u32 swayElapsed;
    s32 sway;

    if (plan->swayWidth == 0 || elapsed >= plan->duration) {
        return 0;
    }
    swayPlan = *plan;
    swayPlan.arcHeightQ4 = plan->swayWidth;
    swayElapsed = (u32)elapsed << 1;
    sway = OverworldMotion_Arc(
        &swayPlan,
        (u16)(swayElapsed >= plan->duration
            ? swayElapsed - plan->duration
            : swayElapsed));
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
    u16 pathLength = OverworldMotion_PathLength(plan);
    u16 pathAdvance;
    s32 pathX;
    s32 pathZ;

    memset(sample, 0, sizeof(*sample));
    pathX = OverworldMotion_Lerp(
        (s32)plan->startX * 0x10000 + 0x8000,
        (s32)plan->targetX * 0x10000 + 0x8000,
        state->elapsed,
        plan->duration);
    pathZ = OverworldMotion_Lerp(
        (s32)plan->startY * 0x10000 + 0x8000,
        (s32)plan->targetY * 0x10000 + 0x8000,
        state->elapsed,
        plan->duration);
    pathAdvance = OverworldMotion_PathProgress(plan, state->elapsed);
    sample->renderX = pathX;
    sample->renderZ = pathZ;
    sample->baseY = OverworldMotion_Lerp(
        plan->startBaseY,
        plan->targetBaseY,
        state->elapsed,
        plan->duration);
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
        plan->spinSpeed);
    sample->visible = plan->visibilityPolicy
            == OVERWORLD_MOTION_VISIBILITY_HIDDEN
        ? FALSE
        : plan->visibilityPolicy == OVERWORLD_MOTION_VISIBILITY_FLICKER
            ? (u8)(((state->elapsed / 2) & 1) == 0)
            : TRUE;
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
