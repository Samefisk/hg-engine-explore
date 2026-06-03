#include "../include/map_events_internal.h"
#include "../include/overworld_wild_movement.h"

#define OW_WILD_DIRECTION_UP 0
#define OW_WILD_DIRECTION_DOWN 1
#define OW_WILD_DIRECTION_LEFT 2
#define OW_WILD_DIRECTION_RIGHT 3
#define OW_WILD_WALK_UP_COMMAND 0x08
#define OW_WILD_CUSTOM_MOVE_DECISION_COOLDOWN 8

typedef void (*OverworldWildMovementFunc)(LocalMapObject *object);

typedef struct OverworldWildMovementDescriptor {
    u32 movement;
    OverworldWildMovementFunc init;
    OverworldWildMovementFunc update;
    OverworldWildMovementFunc finish;
    OverworldWildMovementFunc cleanup;
} OverworldWildMovementDescriptor;

static int OverworldWildCustomMovement_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildCustomMovement_AddDirection(u32 *directions, int count, int delta, u32 positiveDirection, u32 negativeDirection)
{
    if (delta > 0) {
        directions[count++] = positiveDirection;
    } else if (delta < 0) {
        directions[count++] = negativeDirection;
    }

    return count;
}

static int OverworldWildCustomMovement_BuildDirections(LocalMapObject *object, u32 *directions)
{
    FieldSystem *fieldSystem = object->fsys;
    int objectX;
    int objectY;
    int playerX;
    int playerY;
    int dx;
    int dy;
    int count = 0;
    int behavior = MapObject_GetParam(object, OW_WILD_MOVEMENT_PARAM_BEHAVIOR);

    if (fieldSystem == NULL || fieldSystem->playerAvatar == NULL) {
        return 0;
    }

    objectX = MapObject_GetCurrentX(object);
    objectY = MapObject_GetCurrentY(object);
    playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    playerY = GetPlayerYCoord(fieldSystem->playerAvatar);

    dx = playerX - objectX;
    dy = playerY - objectY;

    if (behavior == OW_WILD_MOVEMENT_BEHAVIOR_FLEE_PLAYER) {
        dx = -dx;
        dy = -dy;
    } else if (OverworldWildCustomMovement_Abs(dx) + OverworldWildCustomMovement_Abs(dy) <= 1) {
        return 0;
    }

    if (OverworldWildCustomMovement_Abs(dx) >= OverworldWildCustomMovement_Abs(dy)) {
        count = OverworldWildCustomMovement_AddDirection(directions, count, dx, OW_WILD_DIRECTION_RIGHT, OW_WILD_DIRECTION_LEFT);
        count = OverworldWildCustomMovement_AddDirection(directions, count, dy, OW_WILD_DIRECTION_DOWN, OW_WILD_DIRECTION_UP);
    } else {
        count = OverworldWildCustomMovement_AddDirection(directions, count, dy, OW_WILD_DIRECTION_DOWN, OW_WILD_DIRECTION_UP);
        count = OverworldWildCustomMovement_AddDirection(directions, count, dx, OW_WILD_DIRECTION_RIGHT, OW_WILD_DIRECTION_LEFT);
    }

    return count;
}

static void OverworldWildCustomMovement_TryStartStep(LocalMapObject *object)
{
    u32 directions[2];
    int count;
    int i;

    count = OverworldWildCustomMovement_BuildDirections(object, directions);
    for (i = 0; i < count; i++) {
        u32 direction = directions[i];

        if (!MapObject_IsMovementDirectionBlocked(object, direction)) {
            u32 movementCommand = MapObject_MovementCommandFromDirection(direction, OW_WILD_WALK_UP_COMMAND);

            MapObject_StartMovementCommand(object, movementCommand);
            MapObject_SetSingleMovementActive(object);
            break;
        }
    }
}

void OverworldWildCustomMovement_Init(LocalMapObject *object)
{
    MapObject_SetParam(object, gf_rand() % OW_WILD_CUSTOM_MOVE_DECISION_COOLDOWN, OW_WILD_MOVEMENT_PARAM_COOLDOWN);
}

void OverworldWildCustomMovement_Update(LocalMapObject *object)
{
    int cooldown;

    if (MapObject_IsSingleMovementActive(object)) {
        if (MapObject_UpdateMovementCommand(object)) {
            MapObject_ClearSingleMovementActive(object);
        }
        return;
    }

    cooldown = MapObject_GetParam(object, OW_WILD_MOVEMENT_PARAM_COOLDOWN);
    if (cooldown > 0) {
        MapObject_SetParam(object, cooldown - 1, OW_WILD_MOVEMENT_PARAM_COOLDOWN);
        return;
    }

    MapObject_SetParam(object, OW_WILD_CUSTOM_MOVE_DECISION_COOLDOWN, OW_WILD_MOVEMENT_PARAM_COOLDOWN);
    OverworldWildCustomMovement_TryStartStep(object);
}

void OverworldWildCustomMovement_Finish(LocalMapObject *object)
{
    (void)object;
}

void OverworldWildCustomMovement_Cleanup(LocalMapObject *object)
{
    (void)object;
}

OverworldWildMovementDescriptor ALIGN4 gOverworldWildCustomMovementDescriptor = {
    OW_WILD_MOVE_CUSTOM_AI,
    OverworldWildCustomMovement_Init,
    OverworldWildCustomMovement_Update,
    OverworldWildCustomMovement_Finish,
    OverworldWildCustomMovement_Cleanup,
};
