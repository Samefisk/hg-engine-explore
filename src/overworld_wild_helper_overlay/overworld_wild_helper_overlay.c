#include "../../include/overworld_wild_helper.h"

#include "../../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../../include/map_events_internal.h"

#ifndef OW_WILD_DESPAWN_DISTANCE
#define OW_WILD_DESPAWN_DISTANCE 14
#endif
#ifndef OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START
#define OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START 0xB0
#endif
#ifndef OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START
#define OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START 0xC0
#endif
#ifndef OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START
#define OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START 0xD0
#endif
#ifndef OW_WILD_TILE_HEADBUTT
#define OW_WILD_TILE_HEADBUTT 6
#endif
#ifndef OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS
#define OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS 4
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE
#define OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE 16
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS
#define OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS 1
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES
#define OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES 2
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP 1
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES 3
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES 8
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES
#define OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES
#endif
#ifndef OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES
#define OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES
#endif
#ifndef OW_WILD_SPAWNER_SPOT_STATE_ACTIVE
#define OW_WILD_SPAWNER_SPOT_STATE_ACTIVE 2
#endif
#ifndef OW_WILD_SPAWNER_SPOT_STATE_TIRED
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 3
#endif
#ifndef OW_WILD_BEHAVIOR_BOOL_YES
#define OW_WILD_BEHAVIOR_BOOL_YES 1
#endif
#ifndef OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP 0
#endif
#ifndef OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN 1
#endif
#ifndef OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT 2
#endif
#ifndef OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#endif
#ifndef OW_WILD_HEADBUTT_TREE_TOPS_MAX_LOCATIONS
#define OW_WILD_HEADBUTT_TREE_TOPS_MAX_LOCATIONS 512
#endif

typedef struct OverworldWildHeadbuttTreeTopScan {
    int centerX;
    int centerY;
    int radius;
    int minX;
    int maxX;
    int maxY;
    int nextX;
    int nextY;
    u16 emitted;
} OverworldWildHeadbuttTreeTopScan;

typedef struct OverworldWildCoordOffset {
    s8 dx;
    s8 dy;
} OverworldWildCoordOffset;

static int OverworldWildHelper_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildHelper_Max(int a, int b)
{
    return a > b ? a : b;
}

static int OverworldWildHelper_DistanceFromPlayer(FieldSystem *fieldSystem, int x, int y)
{
    int dx = x - GetPlayerXCoord(fieldSystem->playerAvatar);
    int dy = y - GetPlayerYCoord(fieldSystem->playerAvatar);

    return OverworldWildHelper_Max(OverworldWildHelper_Abs(dx), OverworldWildHelper_Abs(dy));
}

static BOOL OverworldWildHelper_IsNearActiveSpawn(
    const OverworldWildSpawnState *state,
    int x,
    int y,
    int radius)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active && state->spawns[i].object != NULL) {
            int spawnX = MapObject_GetCurrentX(state->spawns[i].object);
            int spawnY = MapObject_GetCurrentY(state->spawns[i].object);
            int dx = OverworldWildHelper_Abs(x - spawnX);
            int dy = OverworldWildHelper_Abs(y - spawnY);

            if (OverworldWildHelper_Max(dx, dy) <= radius) {
                return TRUE;
            }
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsPhantomFlickerObjectId(int id)
{
    return (id >= OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START
            && id < OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START + OW_WILD_MAX_SPAWNS)
        || (id >= OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START
            && id < OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START + OW_WILD_MAX_SPAWNS);
}

static BOOL OverworldWildHelper_IsMankeyTreeTopProxyObjectId(int id)
{
    return id >= OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START
        && id < OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START + OW_WILD_MAX_SPAWNS;
}

static BOOL OverworldWildHelper_IsIgnoredVisualObjectId(int id)
{
    return OverworldWildHelper_IsPhantomFlickerObjectId(id)
        || OverworldWildHelper_IsMankeyTreeTopProxyObjectId(id);
}

static BOOL OverworldWildHelper_IsTileOccupiedByObject(FieldSystem *fieldSystem, int x, int y)
{
    u32 i;
    MapObjectMan *mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    LocalMapObject *objects;

    if (x == GetPlayerXCoord(fieldSystem->playerAvatar) && y == GetPlayerYCoord(fieldSystem->playerAvatar)) {
        return TRUE;
    }

    if (mapObjectMan == NULL || mapObjectMan->objects == NULL) {
        return FALSE;
    }

    objects = mapObjectMan->objects;
    for (i = 0; i < mapObjectMan->object_count; i++) {
        LocalMapObject *object = &objects[i];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && !OverworldWildHelper_IsIgnoredVisualObjectId(object->id)
            && (int)MapObject_GetCurrentX(object) == x
            && (int)MapObject_GetCurrentY(object) == y) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsSurfBehavior(u8 behavior)
{
    return behavior == 16 || behavior == 18 || behavior == 21 || behavior == 42;
}

static u8 OverworldWildHelper_SelectStateMovementByte(
    u8 spotState,
    u8 chillValue,
    u8 attentiveValue,
    u8 tiredValue)
{
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE) {
        return attentiveValue;
    }
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        return tiredValue;
    }
    return chillValue;
}

static int OverworldWildHelper_DiagnosticBuildDirections(int dx, int dy, u8 *directions)
{
    int count = 0;

    if (dx == 0 && dy == 0) {
        return 0;
    }

    if (OverworldWildHelper_Abs(dx) >= OverworldWildHelper_Abs(dy)) {
        if (dx > 0) {
            directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT;
        }
        if (dx < 0 && count < OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
            directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT;
        }
        if (dy > 0 && count < OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
            directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
        }
        if (dy < 0 && count < OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
            directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP;
        }
        return count;
    }

    if (dy > 0) {
        directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
    }
    if (dy < 0 && count < OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
        directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP;
    }
    if (dx > 0 && count < OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
        directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT;
    }
    if (dx < 0 && count < OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
        directions[count++] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT;
    }

    return count;
}

static int OverworldWildHelper_GetCanopyLongJumpDistance(int dx, int dy)
{
    return OverworldWildHelper_Max(OverworldWildHelper_Abs(dx), OverworldWildHelper_Abs(dy));
}

static BOOL OverworldWildHelper_IsCanopyLongJumpVectorShape(int dx, int dy)
{
    int absDx = OverworldWildHelper_Abs(dx);
    int absDy = OverworldWildHelper_Abs(dy);

    if (absDx == 0 && absDy == 0) {
        return FALSE;
    }

    if (absDx == 0 || absDy == 0) {
        return TRUE;
    }

#if OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP
    return absDx == absDy;
#else
    return FALSE;
#endif
}

static u8 OverworldWildHelper_GetBehaviorHopMinDistance(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    u8 minDistance;

    if (profile == NULL) {
        return OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES;
    }
    minDistance = OverworldWildHelper_SelectStateMovementByte(
        spotState,
        profile->hopMinDistance,
        profile->attentiveHopMinDistance,
        profile->tiredHopMinDistance);
    if (minDistance == 0) {
        return OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES;
    }
    return minDistance;
}

static u8 OverworldWildHelper_GetBehaviorHopMaxDistance(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    u8 minDistance = OverworldWildHelper_GetBehaviorHopMinDistance(profile, spotState);
    u8 maxDistance;

    if (profile == NULL) {
        return OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES;
    }
    maxDistance = OverworldWildHelper_SelectStateMovementByte(
        spotState,
        profile->hopMaxDistance,
        profile->attentiveHopMaxDistance,
        profile->tiredHopMaxDistance);
    if (maxDistance == 0) {
        return OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES;
    }
    if (maxDistance < minDistance) {
        return minDistance;
    }
    return maxDistance;
}

static BOOL OverworldWildHelper_IsBehaviorHopVectorShape(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int dx,
    int dy)
{
    int absDx = OverworldWildHelper_Abs(dx);
    int absDy = OverworldWildHelper_Abs(dy);

    if (absDx == 0 && absDy == 0) {
        return FALSE;
    }

    if (absDx == 0 || absDy == 0) {
        return TRUE;
    }

    return profile != NULL
        && OverworldWildHelper_SelectStateMovementByte(
            spotState,
            profile->hopAllowNonCardinal,
            profile->attentiveHopAllowNonCardinal,
            profile->tiredHopAllowNonCardinal) == OW_WILD_BEHAVIOR_BOOL_YES
        && absDx == absDy;
}

static BOOL OverworldWildHelper_TryGetBehaviorHopVector(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    int jumpDistance;
    u8 directions[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];

    if (!OverworldWildHelper_IsBehaviorHopVectorShape(profile, spotState, dx, dy)
        || OverworldWildHelper_DiagnosticBuildDirections(dx, dy, directions) == 0) {
        return FALSE;
    }

    jumpDistance = OverworldWildHelper_GetCanopyLongJumpDistance(dx, dy);
    if (jumpDistance < OverworldWildHelper_GetBehaviorHopMinDistance(profile, spotState)
        || jumpDistance > OverworldWildHelper_GetBehaviorHopMaxDistance(profile, spotState)) {
        return FALSE;
    }

    if (direction != NULL) {
        *direction = directions[0];
    }
    if (distance != NULL) {
        *distance = (u8)jumpDistance;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_IsHeadbuttMapTile(FieldSystem *fieldSystem, int x, int y)
{
    if (fieldSystem == NULL || x < 0 || y < 0) {
        return FALSE;
    }

    return GetMetatileBehaviorAt(fieldSystem, x, y) == OW_WILD_TILE_HEADBUTT;
}

static BOOL OverworldWildHelper_IsLandMapTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if (fieldSystem == NULL || x < 0 || y < 0) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (behavior == OW_WILD_TILE_HEADBUTT || OverworldWildHelper_IsSurfBehavior(behavior)) {
        return FALSE;
    }

    return !IsMetatileBlockedAt(fieldSystem, x, y);
}

#if OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS
static BOOL OverworldWildHelper_IsHeadbuttTreeTopSouthLandAnchor(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildHelper_IsHeadbuttMapTile(fieldSystem, x, y)
        && OverworldWildHelper_IsLandMapTile(fieldSystem, x, y + 1);
}

static BOOL OverworldWildHelper_IsShiftedSouthLandTreeTop(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildHelper_IsHeadbuttMapTile(fieldSystem, x, y)
        && OverworldWildHelper_IsHeadbuttTreeTopSouthLandAnchor(
            fieldSystem,
            x,
            y + OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES);
}
#endif

static BOOL OverworldWildHelper_IsHeadbuttTreeTopSurfaceTile(FieldSystem *fieldSystem, int x, int y)
{
    static const OverworldWildCoordOffset landOffsets[] = {
        { 0, -1 },
        { 0, 1 },
        { -1, 0 },
        { 1, 0 },
    };
    u32 i;

    if (!OverworldWildHelper_IsHeadbuttMapTile(fieldSystem, x, y)) {
        return FALSE;
    }

#if OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS
    if (OverworldWildHelper_IsHeadbuttTreeTopSouthLandAnchor(fieldSystem, x, y)) {
        return FALSE;
    }
    if (OverworldWildHelper_IsShiftedSouthLandTreeTop(fieldSystem, x, y)) {
        return TRUE;
    }
#endif

    for (i = 0; i < NELEMS(landOffsets); i++) {
        if (OverworldWildHelper_IsLandMapTile(
                fieldSystem,
                x + landOffsets[i].dx,
                y + landOffsets[i].dy)) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsHeadbuttTreeTopLocation(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildHelper_IsHeadbuttTreeTopSurfaceTile(fieldSystem, x, y);
}

static BOOL OverworldWildHelper_InitHeadbuttTreeTopScan(
    FieldSystem *fieldSystem,
    OverworldWildHeadbuttTreeTopScan *scan,
    int centerX,
    int centerY,
    int radius)
{
    if (fieldSystem == NULL
        || scan == NULL
        || centerX < 0
        || centerY < 0
        || radius < 0) {
        return FALSE;
    }

    memset(scan, 0, sizeof(*scan));
    scan->centerX = centerX;
    scan->centerY = centerY;
    scan->radius = radius;
    scan->minX = centerX - radius;
    scan->maxX = centerX + radius;
    scan->maxY = centerY + radius;
    scan->nextX = scan->minX;
    scan->nextY = centerY - radius;
    if (scan->minX < 0) {
        scan->minX = 0;
    }
    if (scan->nextX < 0) {
        scan->nextX = 0;
    }
    if (scan->nextY < 0) {
        scan->nextY = 0;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_NextHeadbuttTreeTopCandidate(
    FieldSystem *fieldSystem,
    OverworldWildHeadbuttTreeTopScan *scan,
    int *x,
    int *y)
{
    if (fieldSystem == NULL || scan == NULL || x == NULL || y == NULL) {
        return FALSE;
    }

    while (scan->nextY <= scan->maxY
        && scan->emitted < OW_WILD_HEADBUTT_TREE_TOPS_MAX_LOCATIONS) {
        int candidateX = scan->nextX;
        int candidateY = scan->nextY;

        scan->nextX++;
        if (scan->nextX > scan->maxX) {
            scan->nextX = scan->minX;
            scan->nextY++;
        }
        if (candidateX < 0 || candidateY < 0) {
            continue;
        }
        if (OverworldWildHelper_Max(
                OverworldWildHelper_Abs(candidateX - scan->centerX),
                OverworldWildHelper_Abs(candidateY - scan->centerY)) > scan->radius) {
            continue;
        }
        if (!OverworldWildHelper_IsHeadbuttTreeTopLocation(fieldSystem, candidateX, candidateY)) {
            continue;
        }

        scan->emitted++;
        *x = candidateX;
        *y = candidateY;
        return TRUE;
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsCanopyHopAvoidTarget(
    const OverworldWildSpawnState *state,
    int slot,
    int targetX,
    int targetY)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->movementCanopyHopAvoidValid[slot]) {
        return FALSE;
    }

    return state->movementCanopyHopAvoidX[slot] == targetX
        && state->movementCanopyHopAvoidY[slot] == targetY;
}

static BOOL OverworldWildHelper_TryUseRandomHeadbuttTreeHopCandidate(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int treeX,
    int treeY,
    BOOL ignoreAvoidTarget,
    int *targetX,
    int *targetY,
    int *bestDistance,
    u32 *candidateCount)
{
    int candidateDistance;
    u8 candidateJumpDistance;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || (treeX == currentX && treeY == currentY)
        || targetX == NULL
        || targetY == NULL
        || bestDistance == NULL
        || candidateCount == NULL) {
        return FALSE;
    }

    if (!OverworldWildHelper_TryGetBehaviorHopVector(
            profile,
            state->movementSpotStates[slot],
            treeX - currentX,
            treeY - currentY,
            NULL,
            &candidateJumpDistance)
        || (!ignoreAvoidTarget && OverworldWildHelper_IsCanopyHopAvoidTarget(state, slot, treeX, treeY))
        || OverworldWildHelper_DistanceFromPlayer(fieldSystem, treeX, treeY) > OW_WILD_DESPAWN_DISTANCE
        || OverworldWildHelper_IsNearActiveSpawn(state, treeX, treeY, 0)) {
        return FALSE;
    }
    candidateDistance = candidateJumpDistance;

    if (candidateDistance < *bestDistance) {
        return FALSE;
    }
    if (candidateDistance > *bestDistance) {
        *bestDistance = candidateDistance;
        *candidateCount = 0;
    }

    (*candidateCount)++;
    if ((gf_rand() % *candidateCount) == 0) {
        *targetX = treeX;
        *targetY = treeY;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_TryUseCloserHeadbuttTreeHopCandidate(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int desiredX,
    int desiredY,
    int treeX,
    int treeY,
    BOOL ignoreAvoidTarget,
    int *targetX,
    int *targetY,
    int *bestScore,
    int *bestDistance,
    u32 *candidateCount)
{
    int currentScore;
    int candidateScore;
    int candidateDistance;
    u8 candidateJumpDistance;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || (treeX == currentX && treeY == currentY)
        || targetX == NULL
        || targetY == NULL
        || bestScore == NULL
        || bestDistance == NULL
        || candidateCount == NULL) {
        return FALSE;
    }

    if (!OverworldWildHelper_TryGetBehaviorHopVector(
            profile,
            state->movementSpotStates[slot],
            treeX - currentX,
            treeY - currentY,
            NULL,
            &candidateJumpDistance)
        || (!ignoreAvoidTarget && OverworldWildHelper_IsCanopyHopAvoidTarget(state, slot, treeX, treeY))
        || OverworldWildHelper_DistanceFromPlayer(fieldSystem, treeX, treeY) > OW_WILD_DESPAWN_DISTANCE
        || OverworldWildHelper_IsNearActiveSpawn(state, treeX, treeY, 0)) {
        return FALSE;
    }
    candidateDistance = candidateJumpDistance;

    currentScore = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(desiredX - currentX),
        OverworldWildHelper_Abs(desiredY - currentY));
    candidateScore = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(desiredX - treeX),
        OverworldWildHelper_Abs(desiredY - treeY));
    if (candidateScore >= currentScore) {
        return FALSE;
    }

    if (candidateDistance < *bestDistance
        || (candidateDistance == *bestDistance && candidateScore > *bestScore)) {
        return FALSE;
    }

    if (candidateDistance > *bestDistance || candidateScore < *bestScore) {
        *bestDistance = candidateDistance;
        *bestScore = candidateScore;
        *candidateCount = 0;
    }

    (*candidateCount)++;
    if ((gf_rand() % *candidateCount) == 0) {
        *targetX = treeX;
        *targetY = treeY;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_TryUseReturnHeadbuttTreeHopCandidate(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int treeX,
    int treeY,
    int *targetX,
    int *targetY,
    int *bestScore,
    u32 *candidateCount)
{
    int candidateScore;
    u8 candidateDistance;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || (treeX == currentX && treeY == currentY)
        || targetX == NULL
        || targetY == NULL
        || bestScore == NULL
        || candidateCount == NULL) {
        return FALSE;
    }

    if (!OverworldWildHelper_TryGetBehaviorHopVector(
            profile,
            state->movementSpotStates[slot],
            treeX - currentX,
            treeY - currentY,
            NULL,
            &candidateDistance)
        || OverworldWildHelper_DistanceFromPlayer(fieldSystem, treeX, treeY) > OW_WILD_DESPAWN_DISTANCE
        || OverworldWildHelper_IsNearActiveSpawn(state, treeX, treeY, 0)) {
        return FALSE;
    }

    candidateScore = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(treeX - currentX),
        OverworldWildHelper_Abs(treeY - currentY));
    if (candidateScore > *bestScore) {
        return FALSE;
    }

    if (candidateScore < *bestScore) {
        *bestScore = candidateScore;
        *candidateCount = 0;
    }

    (*candidateCount)++;
    if ((gf_rand() % *candidateCount) == 0) {
        *targetX = treeX;
        *targetY = treeY;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_IsWalkableLandTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if (x < 0 || y < 0) {
        return FALSE;
    }
    if (OverworldWildHelper_IsTileOccupiedByObject(fieldSystem, x, y)) {
        return FALSE;
    }
    if (IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (behavior == OW_WILD_TILE_HEADBUTT || OverworldWildHelper_IsSurfBehavior(behavior)) {
        return FALSE;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_IsCanopyTreeHopLandCrossing(
    FieldSystem *fieldSystem,
    int currentX,
    int currentY,
    int targetX,
    int targetY)
{
    int dx;
    int dy;
    int distance;
    int step;

    if (fieldSystem == NULL) {
        return FALSE;
    }

    dx = targetX - currentX;
    dy = targetY - currentY;
    distance = OverworldWildHelper_Max(OverworldWildHelper_Abs(dx), OverworldWildHelper_Abs(dy));
    if (distance <= 1 || !OverworldWildHelper_IsCanopyLongJumpVectorShape(dx, dy)) {
        return FALSE;
    }

    if (dx != 0) {
        dx /= distance;
    }
    if (dy != 0) {
        dy /= distance;
    }

    for (step = 1; step < distance; step++) {
        int x = currentX + dx * step;
        int y = currentY + dy * step;

        if (x < 0 || y < 0) {
            continue;
        }
        if (OverworldWildHelper_IsWalkableLandTile(fieldSystem, x, y)) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryPickHeadbuttTreeHopTarget(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int *targetX,
    int *targetY)
{
    OverworldWildHeadbuttTreeTopScan scan;
    u32 candidateCount = 0;
    int bestDistance = 0;
    int avoidPass;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->location == NULL
        || fieldSystem->playerAvatar == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || profile == NULL
        || targetX == NULL
        || targetY == NULL) {
        return FALSE;
    }

    for (avoidPass = 0; avoidPass < 2 && candidateCount == 0; avoidPass++) {
        BOOL ignoreAvoidTarget = avoidPass != 0;
        int treeX;
        int treeY;

        bestDistance = 0;
        if (!OverworldWildHelper_InitHeadbuttTreeTopScan(
                fieldSystem,
                &scan,
                currentX,
                currentY,
                OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE)) {
            continue;
        }
        while (OverworldWildHelper_NextHeadbuttTreeTopCandidate(
                   fieldSystem,
                   &scan,
                   &treeX,
                   &treeY)) {
            OverworldWildHelper_TryUseRandomHeadbuttTreeHopCandidate(
                state,
                fieldSystem,
                profile,
                slot,
                currentX,
                currentY,
                treeX,
                treeY,
                ignoreAvoidTarget,
                targetX,
                targetY,
                &bestDistance,
                &candidateCount);
        }
    }

    return candidateCount != 0;
}

static BOOL OverworldWildHelper_TryPickHeadbuttTreeReturnTarget(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int *targetX,
    int *targetY)
{
    OverworldWildHeadbuttTreeTopScan scan;
    u32 candidateCount = 0;
    int treeX;
    int treeY;
    int bestScore = 255;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->location == NULL
        || fieldSystem->playerAvatar == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || profile == NULL
        || targetX == NULL
        || targetY == NULL) {
        return FALSE;
    }

    if (!OverworldWildHelper_InitHeadbuttTreeTopScan(
            fieldSystem,
            &scan,
            currentX,
            currentY,
            OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE)) {
        return FALSE;
    }

    while (OverworldWildHelper_NextHeadbuttTreeTopCandidate(
               fieldSystem,
               &scan,
               &treeX,
               &treeY)) {
        OverworldWildHelper_TryUseReturnHeadbuttTreeHopCandidate(
            state,
            fieldSystem,
            profile,
            slot,
            currentX,
            currentY,
            treeX,
            treeY,
            targetX,
            targetY,
            &bestScore,
            &candidateCount);
    }

    return candidateCount != 0;
}

static BOOL OverworldWildHelper_TryPickHeadbuttTreeHopTargetToward(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int desiredX,
    int desiredY,
    int *targetX,
    int *targetY)
{
    OverworldWildHeadbuttTreeTopScan scan;
    u32 candidateCount = 0;
    int bestScore = 255;
    int bestDistance = 0;
    int avoidPass;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->location == NULL
        || fieldSystem->playerAvatar == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || profile == NULL
        || targetX == NULL
        || targetY == NULL) {
        return FALSE;
    }

    for (avoidPass = 0; avoidPass < 2 && candidateCount == 0; avoidPass++) {
        BOOL ignoreAvoidTarget = avoidPass != 0;
        int treeX;
        int treeY;

        bestScore = 255;
        bestDistance = 0;
        if (!OverworldWildHelper_InitHeadbuttTreeTopScan(
                fieldSystem,
                &scan,
                currentX,
                currentY,
                OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE)) {
            continue;
        }
        while (OverworldWildHelper_NextHeadbuttTreeTopCandidate(
                   fieldSystem,
                   &scan,
                   &treeX,
                   &treeY)) {
            OverworldWildHelper_TryUseCloserHeadbuttTreeHopCandidate(
                state,
                fieldSystem,
                profile,
                slot,
                currentX,
                currentY,
                desiredX,
                desiredY,
                treeX,
                treeY,
                ignoreAvoidTarget,
                targetX,
                targetY,
                &bestScore,
                &bestDistance,
                &candidateCount);
        }
    }

    return candidateCount != 0;
}

static BOOL OverworldWildHelper_TryPickCanopyHopperTreeTopHopTarget(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int *targetX,
    int *targetY)
{
    OverworldWildHeadbuttTreeTopScan scan;
    u32 candidateCount = 0;
    BOOL bestCrossesLand = FALSE;
    int avoidPass;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || targetX == NULL
        || targetY == NULL) {
        return FALSE;
    }

    for (avoidPass = 0; avoidPass < 2 && candidateCount == 0; avoidPass++) {
        BOOL ignoreAvoidTarget = avoidPass != 0;
        int candidateX;
        int candidateY;

        bestCrossesLand = FALSE;
        if (!OverworldWildHelper_InitHeadbuttTreeTopScan(
                fieldSystem,
                &scan,
                currentX,
                currentY,
                OverworldWildHelper_GetBehaviorHopMaxDistance(
                    profile,
                    state->movementSpotStates[slot]))) {
            continue;
        }
        while (OverworldWildHelper_NextHeadbuttTreeTopCandidate(
                   fieldSystem,
                   &scan,
                   &candidateX,
                   &candidateY)) {
            int dx = candidateX - currentX;
            int dy = candidateY - currentY;
            u8 distance;
            BOOL crossesLand;

            if (candidateX == currentX && candidateY == currentY) {
                continue;
            }
            if (!OverworldWildHelper_TryGetBehaviorHopVector(
                    profile,
                    state->movementSpotStates[slot],
                    dx,
                    dy,
                    NULL,
                    &distance)
                || (!ignoreAvoidTarget
                    && OverworldWildHelper_IsCanopyHopAvoidTarget(state, slot, candidateX, candidateY))) {
                continue;
            }

            crossesLand = OverworldWildHelper_IsCanopyTreeHopLandCrossing(
                fieldSystem,
                currentX,
                currentY,
                candidateX,
                candidateY);
            if (bestCrossesLand && !crossesLand) {
                continue;
            }
            if (crossesLand && !bestCrossesLand) {
                bestCrossesLand = TRUE;
                candidateCount = 0;
            }

            candidateCount++;
            if ((gf_rand() % candidateCount) == 0) {
                *targetX = candidateX;
                *targetY = candidateY;
            }
        }
    }

    return candidateCount != 0;
}

const OverworldWildHelperOverlayEntry gOverworldWildHelperOverlayEntry
    __attribute__((section(".overworld_wild_helper_entry"), used)) = {
        OVERWORLD_WILD_HELPER_MAGIC,
        OVERWORLD_WILD_HELPER_VERSION,
        sizeof(OverworldWildHelperOverlayEntry),
        OverworldWildHelper_TryPickHeadbuttTreeHopTarget,
        OverworldWildHelper_TryPickHeadbuttTreeReturnTarget,
        OverworldWildHelper_TryPickHeadbuttTreeHopTargetToward,
        OverworldWildHelper_TryPickCanopyHopperTreeTopHopTarget,
    };

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
