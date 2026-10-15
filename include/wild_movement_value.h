#ifndef WILD_MOVEMENT_VALUE_H
#define WILD_MOVEMENT_VALUE_H

#include "types.h"

typedef struct FieldSystem FieldSystem;
typedef struct OverworldWildSpawnState OverworldWildSpawnState;
typedef struct OverworldWildBehaviorProfileData OverworldWildBehaviorProfileData;

/* A value query owned by wild movement. The resident code does not own actors
 * or HP; the wild overlay keeps authority over tile admission. */
typedef struct WildMovementCircleQuery {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    const OverworldWildBehaviorProfileData *lane;
    BOOL (*tileAllowed)(FieldSystem *, u16, int, int);
    int slot;
    int objectX;
    int objectY;
    int playerX;
    int playerY;
    int targetX;
    int targetY;
} WildMovementCircleQuery;

BOOL WildMovementValue_SelectCircleTarget(WildMovementCircleQuery *query);
void WildMovementValue_AppendFleeDirections(
    u8 *directions, int *directionCount, int fleeDx, int fleeDy);
u16 WildMovementValue_GetThrowUnstableMask(
    OverworldWildSpawnState *state, const u8 *motionModes);

#endif
