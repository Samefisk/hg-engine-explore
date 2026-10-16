#ifndef OVERWORLD_WALK_TIMING_POLICY_H
#define OVERWORLD_WALK_TIMING_POLICY_H

#include "types.h"

#define OVERWORLD_WALK_TIMING_MIN 1
#define OVERWORLD_WALK_TIMING_MAX 32
#define OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2 33
#define OVERWORLD_WALK_ACCELERATION_LINEAR_SPEED 34
#define OVERWORLD_WALK_TIMING_INLINE \
    static inline __attribute__((always_inline))

OVERWORLD_WALK_TIMING_INLINE u8
OverworldWalkTimingPolicy_Clamp(u8 travelTime)
{
    if (travelTime < OVERWORLD_WALK_TIMING_MIN) {
        return OVERWORLD_WALK_TIMING_MIN;
    }
    if (travelTime > OVERWORLD_WALK_TIMING_MAX) {
        return OVERWORLD_WALK_TIMING_MAX;
    }
    return travelTime;
}

/* Q8 tile time is the reciprocal of speed interpolated over moving frames.
 * Keep the fraction until admission; rejected proposals never consume it. */
OVERWORLD_WALK_TIMING_INLINE u16 OverworldWalkTimingPolicy_LinearTimeQ8(
    u8 baseTime, u8 fastestTime, u8 rampFrames, u8 movingFrames)
{
    u32 denominator;

    baseTime = OverworldWalkTimingPolicy_Clamp(baseTime);
    fastestTime = OverworldWalkTimingPolicy_Clamp(fastestTime);
    if (fastestTime >= baseTime) {
        return (u16)baseTime << 8;
    }
    if (rampFrames == 0 || movingFrames >= rampFrames) {
        return (u16)fastestTime << 8;
    }
    denominator = (u32)fastestTime * rampFrames
        + (u32)(baseTime - fastestTime) * movingFrames;
#if defined(__arm__)
    /* The resident unsigned divide entry is Thumb. A named function pointer
     * avoids redefining compiler-helper symbols supplied by the overlay link. */
    return ((u32 (*)(u32, u32))0x023DEE4D)(
        (u32)baseTime * fastestTime * rampFrames << 8, denominator);
#else
    return ((u32)baseTime * fastestTime * rampFrames << 8) / denominator;
#endif
}

OVERWORLD_WALK_TIMING_INLINE u8 OverworldWalkTimingPolicy_LinearDuration(
    u16 timeQ8, u8 carry, u8 *nextCarry)
{
    u16 accumulated = timeQ8 + carry;

    *nextCarry = (u8)accumulated;
    return OverworldWalkTimingPolicy_Clamp((u8)(accumulated >> 8));
}

/* Translate the visible tile time into a new linear-speed curve. A profile
 * entry changes tuning, not the actor's current direction or skid. */
OVERWORLD_WALK_TIMING_INLINE u8 OverworldWalkTimingPolicy_LinearElapsedForTime(
    u8 baseTime, u8 fastestTime, u8 rampFrames, u8 visibleTime)
{
    u32 numerator;
    u32 denominator;

    baseTime = OverworldWalkTimingPolicy_Clamp(baseTime);
    fastestTime = OverworldWalkTimingPolicy_Clamp(fastestTime);
    visibleTime = OverworldWalkTimingPolicy_Clamp(visibleTime);
    if (visibleTime >= baseTime || fastestTime >= baseTime) {
        return 0;
    }
    if (visibleTime <= fastestTime) {
        return rampFrames;
    }
    numerator = (u32)fastestTime * rampFrames * (baseTime - visibleTime);
    denominator = (u32)visibleTime * (baseTime - fastestTime);
#if defined(__arm__)
    return ((u32 (*)(u32, u32))0x023DEE4D)(
        numerator + denominator - 1u, denominator);
#else
    return (numerator + denominator - 1u) / denominator;
#endif
}

OVERWORLD_WALK_TIMING_INLINE u8 OverworldWalkTimingPolicy_Accelerate(
    u8 currentTravelTime,
    u8 fastestTravelTime,
    u8 accelerationStep)
{
    u8 nextTravelTime;

    currentTravelTime = OverworldWalkTimingPolicy_Clamp(currentTravelTime);
    fastestTravelTime = OverworldWalkTimingPolicy_Clamp(fastestTravelTime);
    if (accelerationStep == 0) {
        nextTravelTime = currentTravelTime;
    } else if (accelerationStep == OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2) {
        nextTravelTime = (currentTravelTime + 1u) / 2u;
    } else {
        nextTravelTime = currentTravelTime > accelerationStep
            ? currentTravelTime - accelerationStep
            : OVERWORLD_WALK_TIMING_MIN;
    }
    return nextTravelTime < fastestTravelTime
        ? fastestTravelTime
        : nextTravelTime;
}

OVERWORLD_WALK_TIMING_INLINE u8
OverworldWalkTimingPolicy_Decelerate(
    u8 currentTravelTime,
    u8 baseTravelTime,
    u8 accelerationStep)
{
    u8 nextTravelTime;
    u8 previousTravelTime;

    currentTravelTime = OverworldWalkTimingPolicy_Clamp(currentTravelTime);
    baseTravelTime = OverworldWalkTimingPolicy_Clamp(baseTravelTime);
    if (currentTravelTime >= baseTravelTime) {
        return baseTravelTime;
    }
    if (accelerationStep == 0) {
        return currentTravelTime;
    }
    if (accelerationStep != OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2) {
        nextTravelTime = currentTravelTime + accelerationStep;
        return nextTravelTime > baseTravelTime
            ? baseTravelTime
            : nextTravelTime;
    }

    previousTravelTime = baseTravelTime;
    nextTravelTime = baseTravelTime;
    while (nextTravelTime > currentTravelTime) {
        previousTravelTime = nextTravelTime;
        nextTravelTime = (nextTravelTime + 1u) / 2u;
    }
    return previousTravelTime;
}

OVERWORLD_WALK_TIMING_INLINE u8
OverworldWalkTimingPolicy_SkidTiles(u8 travelTime)
{
    if (travelTime <= 1) {
        return 4;
    }
    if (travelTime <= 4) {
        return 2;
    }
    if (travelTime <= 6) {
        return 1;
    }
    return 0;
}

/* A selected two-tile skid retains the legacy four tiles at time1. A
 * one-turn-only selection stays one tile. Stop uses its own admission limit
 * and preserves the legacy count at time4/time1 after admission. */
OVERWORLD_WALK_TIMING_INLINE u8
OverworldWalkTimingPolicy_ProfileSkidTiles(
    u8 travelTime, u8 oneTurnTime, u8 twoTurnTime, u8 stopTime, BOOL stop)
{
    /* A zero time wraps to255, above every authored 0..127 threshold. */
    u8 elapsed = travelTime - 1u;
    if (stop) {
        if (elapsed >= stopTime) return 0;
        return travelTime <= 1 ? 4 : travelTime <= 4 ? 2 : 1;
    }
    if (elapsed < twoTurnTime) {
        return travelTime <= 1 ? 4 : 2;
    }
    return elapsed < oneTurnTime;
}

OVERWORLD_WALK_TIMING_INLINE u8
OverworldWalkTimingPolicy_SkidTime(u8 travelTime)
{
    travelTime = OverworldWalkTimingPolicy_Clamp(travelTime);
    return travelTime > (OVERWORLD_WALK_TIMING_MAX / 2)
        ? OVERWORLD_WALK_TIMING_MAX
        : travelTime * 2u;
}

OVERWORLD_WALK_TIMING_INLINE BOOL OverworldWalkTimingPolicy_StompApplies(
    u8 travelTime,
    u8 stompAtTravelTime)
{
    return stompAtTravelTime != 0
        && OverworldWalkTimingPolicy_Clamp(travelTime)
            <= OverworldWalkTimingPolicy_Clamp(stompAtTravelTime);
}

OVERWORLD_WALK_TIMING_INLINE u8
OverworldWalkTimingPolicy_ResumeAfterSkid(
    u8 priorTravelTime,
    u8 baseTravelTime,
    u8 accelerationStep,
    BOOL stopSkid)
{
    return stopSkid
        ? OverworldWalkTimingPolicy_Clamp(baseTravelTime)
        : OverworldWalkTimingPolicy_Decelerate(
            priorTravelTime, baseTravelTime, accelerationStep);
}

OVERWORLD_WALK_TIMING_INLINE BOOL
OverworldWalkTimingPolicy_ValidateExactOverrideValue(
    u8 fieldIndex,
    u8 value)
{
    if (fieldIndex == 7 || fieldIndex == 49 || fieldIndex == 56) {
        return value >= OVERWORLD_WALK_TIMING_MIN
            && value <= OVERWORLD_WALK_TIMING_MAX;
    }
    if (fieldIndex == 36 || fieldIndex == 66) {
        return value <= OVERWORLD_WALK_TIMING_MAX;
    }
    if (fieldIndex == 67) {
        return value <= OVERWORLD_WALK_ACCELERATION_LINEAR_SPEED;
    }
    return TRUE;
}

#undef OVERWORLD_WALK_TIMING_INLINE

#endif // OVERWORLD_WALK_TIMING_POLICY_H
