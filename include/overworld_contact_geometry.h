#ifndef OVERWORLD_CONTACT_GEOMETRY_H
#define OVERWORLD_CONTACT_GEOMETRY_H
#include "types.h"
typedef struct PlayerHealthContactSegment {
    s32 oldX, oldY, oldZ;
    s32 newX, newY, newZ;
    u8 landingSample;
} PlayerHealthContactSegment;

BOOL OverworldContactGeometry_Intersects(const PlayerHealthContactSegment *);
#endif
