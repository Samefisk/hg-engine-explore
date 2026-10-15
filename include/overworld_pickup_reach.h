#ifndef OVERWORLD_PICKUP_REACH_H
#define OVERWORLD_PICKUP_REACH_H
#include "overworld_pickup_route.h"
/* Both route goals and atomic pickup use authored distance/height limits.
 * Support and accepted-motion checks belong to the native caller. */
static inline OverworldPickupRouteEdgeResult OverworldPickupReach_Check(
    const OverworldPickupRoutePosition *standing,
    const OverworldPickupRoutePosition *cargo, u8 distance, u8 heightUnits)
{
    s32 dx, dy, height;
    if (standing == 0 || cargo == 0 || distance == 0 || distance > 8
        || heightUnits > 64) return OVERWORLD_PICKUP_ROUTE_EDGE_INVALID;
    dx = (s32)standing->x-cargo->x; if (dx < 0) dx = -dx;
    dy = (s32)standing->y-cargo->y; if (dy < 0) dy = -dy;
    height = standing->baseY-cargo->baseY; if (height < 0) height = -height;
    return (dx != 0 || dy != 0) && dx <= distance && dy <= distance
        && height <= ((s32)heightUnits << 12)
        ? OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL : OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;
}
#endif
