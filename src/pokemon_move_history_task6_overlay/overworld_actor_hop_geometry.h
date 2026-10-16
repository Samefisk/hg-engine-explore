#ifndef OVERWORLD_ACTOR_HOP_GEOMETRY_H
#define OVERWORLD_ACTOR_HOP_GEOMETRY_H

#ifndef OVERWORLD_MOTION_HOST
#include "../../include/types.h"
#endif

/* Private boundary state. Each call advances exactly one crossed cell. */
typedef struct OverworldActorHopGeometry {
    s32 tileX;
    s32 tileY;
    s32 stepX;
    s32 stepY;
    u32 absDx;
    u32 absDy;
    u32 xBoundary;
    u32 yBoundary;
    s32 error;
    u32 entryNumerator;
    u32 entryDenominator;
} OverworldActorHopGeometry;

/* Native/private ABI: four contiguous aligned s16 coordinates in the current
 * plan/call object, ordered startX,startY,targetX,targetY. Entry fractions are
 * written by NextCell before they are read; Init does not read or publish them. */
void OverworldActorHopGeometry_Init(OverworldActorHopGeometry *, const void *);

void OverworldActorHopGeometry_NextCell(OverworldActorHopGeometry *geometry);

#endif
