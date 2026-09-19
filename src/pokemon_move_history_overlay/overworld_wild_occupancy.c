#include "../../include/overworld_wild_occupancy.h"
#include "../../include/config.h"
#include "../../include/map_events_internal.h"

/* The native reader is shared, not the policy: each Wild wrapper chooses its
 * original player/height rules and retains its original instrumentation. */
BOOL __attribute__((noinline, used, section(".overworld_wild_occupancy")))
OverworldWildOccupancy_Query(FieldSystem *fieldSystem,
    LocalMapObject *ignoredObject, LocalMapObject *collisionIgnoredObject,
    int x, int y, s32 targetBaseY, int mode)
{
    MapObjectMan *manager;
    LocalMapObject *player = NULL;
    u32 i;

    if (mode == OVERWORLD_WILD_OCCUPANCY_OBJECTS) {
        manager = (MapObjectMan *)fieldSystem->mapObjectMan;
        if (x == GetPlayerXCoord(fieldSystem->playerAvatar)
            && y == GetPlayerYCoord(fieldSystem->playerAvatar)) {
            return TRUE;
        }
        if (manager == NULL) {
            return FALSE;
        }
    } else {
        if (fieldSystem == NULL || fieldSystem->mapObjectMan == NULL) {
            return FALSE;
        }
        manager = (MapObjectMan *)fieldSystem->mapObjectMan;
        player = fieldSystem->playerAvatar != NULL
            ? fieldSystem->playerAvatar->mapObject : NULL;
        if (mode == OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER
            && player != NULL && player != ignoredObject
            && player->xCurr == x && player->yCurr == y
            && (s32)player->posVec[1] == targetBaseY) {
            return TRUE;
        }
    }
    if (manager->objects == NULL) {
        return FALSE;
    }
    for (i = 0; i < manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];
        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && object != ignoredObject && object != player
            && object != collisionIgnoredObject
            && object->id != OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID
#ifdef DISABLE_FOLLOWER_POKEMON
            && object->id != OW_WILD_FOLLOWER_OBJECT_ID
#endif
            && !(object->id >= OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START
                && object->id < OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START + OW_WILD_MAX_SPAWNS)
            && object->xCurr == x && object->yCurr == y
            && (mode < OVERWORLD_WILD_OCCUPANCY_SURFACE
                || (s32)object->posVec[1] == targetBaseY)) {
            return TRUE;
        }
    }
    return FALSE;
}
