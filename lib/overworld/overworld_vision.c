#include "../../include/overworld_vision.h"

#if defined(OVERWORLD_VISION_HOST) \
    || defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <stdint.h>
typedef int32_t s32;
typedef uint32_t u32;
#endif

static u32 OverworldVision_Abs(s32 value)
{
    return value < 0 ? (u32)-value : (u32)value;
}

u8 OverworldVision_IsValidSpec(const OverworldVisionSpec *spec)
{
    return spec != 0
        && spec->range != 0
        && spec->range <= OVERWORLD_VISION_MAX_RANGE
        && (spec->options == OVERWORLD_VISION_CONE_FORWARD_90
            || spec->options == OVERWORLD_VISION_DEFAULT_OPTIONS);
}

u8 OverworldVision_IsInView(
    const OverworldVisionSpec *spec,
    s16 observerX,
    s16 observerY,
    u8 observerFacing,
    s16 targetX,
    s16 targetY)
{
    s32 dx;
    s32 dy;
    u32 xDistance;
    u32 yDistance;
    u32 distance;
    s32 forward;
    u32 lateral;

    if (!OverworldVision_IsValidSpec(spec)
        || observerFacing > OVERWORLD_VISION_FACING_EAST) {
        return 0;
    }

    dx = (s32)targetX - observerX;
    dy = (s32)targetY - observerY;
    xDistance = OverworldVision_Abs(dx);
    yDistance = OverworldVision_Abs(dy);
    distance = xDistance > yDistance ? xDistance : yDistance;

    if (distance == 0 || distance > spec->range) {
        return 0;
    }
    if (distance == 1
        && (spec->options & OVERWORLD_VISION_ADJACENT_AWARENESS) != 0) {
        return 1;
    }

    if ((observerFacing & 2) != 0) {
        forward = dx;
        lateral = yDistance;
    } else {
        forward = dy;
        lateral = xDistance;
    }
    if ((observerFacing & 1) == 0) {
        forward = -forward;
    }
    return forward > 0 && lateral <= (u32)forward;
}

#if !defined(OVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME)
u8 OverworldVision_CanSee(
    const OverworldVisionSpec *spec,
    s16 observerX,
    s16 observerY,
    u8 observerFacing,
    s16 targetX,
    s16 targetY,
    u8 occluded)
{
    if (!OverworldVision_IsInView(
            spec,
            observerX,
            observerY,
            observerFacing,
            targetX,
            targetY)) {
        return 0;
    }
    return occluded == 0;
}
#endif
