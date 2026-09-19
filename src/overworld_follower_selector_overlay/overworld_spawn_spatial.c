#include "../../include/overworld_spawn_spatial.h"

#include "../../include/map_events_internal.h"
#include "../../include/pokemon.h"

/* The player-tile predicate lives in the helper tail. Keep its import typed
 * as Thumb so the selector tail can call it without a veneer. */
__asm__(
    ".syntax unified\n"
    ".thumb\n"
    ".thumb_func\n"
    ".global OverworldSpawnSpatial_IsPlayerTile\n"
    ".thumb_set OverworldSpawnSpatial_IsPlayerTile, 0x023C7F60\n"
    ".thumb_func\n"
    ".thumb_set OverworldSpawnSpatial_GetPlayerXCoord, 0x0205C67C\n"
    ".thumb_func\n"
    ".thumb_set OverworldSpawnSpatial_GetPlayerYCoord, 0x0205C688\n");

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

BOOL __attribute__((section(".overworld_spawn_spatial_current_map_object"),
    used, noinline, optimize("Os")))
OverworldSpawnSpatial_IsCurrentMapObject(
    FieldSystem *fieldSystem,
    LocalMapObject *object)
{
    MapObjectMan *mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    LocalMapObject *objects;
    u32 objectAddr;
    u32 startAddr;
    u32 endAddr;

    if (object == NULL || mapObjectMan == NULL || mapObjectMan->objects == NULL) {
        return FALSE;
    }

    objects = mapObjectMan->objects;
    objectAddr = (u32)object;
    startAddr = (u32)objects;
    endAddr = startAddr + mapObjectMan->object_count * sizeof(LocalMapObject);

    return objectAddr >= startAddr && objectAddr < endAddr;
}

static int OverworldSpawnSpatial_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldSpawnSpatial_Max(int a, int b)
{
    return a > b ? a : b;
}

int __attribute__((section(".overworld_spawn_spatial_distance_from_player"),
    used, noinline, optimize("Os")))
OverworldSpawnSpatial_DistanceFromPlayer(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    int dx = x - OverworldSpawnSpatial_GetPlayerXCoord(fieldSystem->playerAvatar);
    int dy = y - OverworldSpawnSpatial_GetPlayerYCoord(fieldSystem->playerAvatar);

    return OverworldSpawnSpatial_Max(
        OverworldSpawnSpatial_Abs(dx),
        OverworldSpawnSpatial_Abs(dy));
}

BOOL __attribute__((section(".overworld_spawn_spatial_object_on_player_tile"),
    used, noinline, optimize("Os")))
OverworldSpawnSpatial_IsObjectOnPlayerTile(
    FieldSystem *fieldSystem,
    LocalMapObject *object)
{
    return object != NULL
        && OverworldSpawnSpatial_IsPlayerTile(
            fieldSystem,
            (int)OverworldSpawnSpatial_ObjectCurrentX(object),
            (int)OverworldSpawnSpatial_ObjectCurrentY(object));
}
