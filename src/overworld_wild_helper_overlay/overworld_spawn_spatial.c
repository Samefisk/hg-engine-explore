#include "../../include/overworld_spawn_spatial.h"

#include "../../include/map_events_internal.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/pokemon.h"

/* These are resident Thumb entries. Keep the aliases in this translation
 * unit so direct calls do not grow instruction-mode veneers. */
__asm__(
    ".syntax unified\n"
    ".thumb\n"
    ".thumb_func\n"
    ".global OverworldSpawnSpatial_IsCurrentMapObject\n"
    ".thumb_set OverworldSpawnSpatial_IsCurrentMapObject, 0x023C2200\n"
    ".thumb_func\n"
    ".thumb_set OverworldSpawnSpatial_GetPlayerXCoord, 0x0205C67C\n"
    ".thumb_func\n"
    ".thumb_set OverworldSpawnSpatial_GetPlayerYCoord, 0x0205C688\n"
    ".thumb_func\n"
    ".thumb_set OverworldWalk_DeltaX, 0x023BF59C\n"
    ".thumb_func\n"
    ".thumb_set OverworldWalk_DeltaY, 0x023BF5BE\n");

extern int OverworldSpawnSpatial_GetPlayerXCoord(FIELD_PLAYER_AVATAR *avatar);
extern int OverworldSpawnSpatial_GetPlayerYCoord(FIELD_PLAYER_AVATAR *avatar);

static inline __attribute__((always_inline)) u32
OverworldSpawnSpatial_ObjectCurrentX(LocalMapObject *object)
{
    return *(volatile u32 *)&object->xCurr;
}

static inline __attribute__((always_inline)) u32
OverworldSpawnSpatial_ObjectCurrentY(LocalMapObject *object)
{
    return *(volatile u32 *)&object->yCurr;
}

BOOL __attribute__((section(".overworld_spawn_spatial_player_tile"), used,
    noinline, optimize("Os")))
OverworldSpawnSpatial_IsPlayerTile(FieldSystem *fieldSystem, int x, int y)
{
    return fieldSystem != NULL
        && fieldSystem->playerAvatar != NULL
        && x == OverworldSpawnSpatial_GetPlayerXCoord(fieldSystem->playerAvatar)
        && y == OverworldSpawnSpatial_GetPlayerYCoord(fieldSystem->playerAvatar);
}

BOOL __attribute__((section(".overworld_spawn_spatial_player_front_tile"), used,
    noinline, optimize("Os")))
OverworldSpawnSpatial_IsPlayerFrontTile(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    LocalMapObject *playerObject;
    u8 playerFacing;

    if (fieldSystem == NULL || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }

    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject == NULL
        || !OverworldSpawnSpatial_IsCurrentMapObject(fieldSystem, playerObject)
        || (playerObject->flags & MAPOBJECTFLAG_ACTIVE) == 0) {
        return FALSE;
    }

    playerFacing = playerObject->curFacing;
    if (playerFacing > 3) {
        return FALSE;
    }

    return x == (int)OverworldSpawnSpatial_ObjectCurrentX(playerObject)
            + OverworldWalk_DeltaX(playerFacing)
        && y == (int)OverworldSpawnSpatial_ObjectCurrentY(playerObject)
            + OverworldWalk_DeltaY(playerFacing);
}
