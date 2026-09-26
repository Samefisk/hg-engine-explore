#ifndef OVERWORLD_WALK_TIMING_POLICY_H
#define OVERWORLD_WALK_TIMING_POLICY_H

#include "types.h"

#define OVERWORLD_WALK_TIMING_MIN 1
#define OVERWORLD_WALK_TIMING_MAX 32
#define OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2 33
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
        return value <= OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2;
    }
    return TRUE;
}

#undef OVERWORLD_WALK_TIMING_INLINE

#endif // OVERWORLD_WALK_TIMING_POLICY_H
