#ifndef OVERWORLD_WILD_OCCUPANCY_H
#define OVERWORLD_WILD_OCCUPANCY_H
#include "overworld_wild_spawns_internal.h"

/* Private Wild code host. Values are borrowed for this call only; no state. */
#define OVERWORLD_WILD_OCCUPANCY_ENTRY_ADDR 0x023C0184
#define OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START 0xB0
#define OW_WILD_FOLLOWER_OBJECT_ID 253
enum {
    OVERWORLD_WILD_OCCUPANCY_OBJECTS,
    OVERWORLD_WILD_OCCUPANCY_NONPLAYER,
    OVERWORLD_WILD_OCCUPANCY_SURFACE,
    OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER
};
BOOL OverworldWildOccupancy_Query(FieldSystem *fieldSystem,
    LocalMapObject *ignoredObject, LocalMapObject *collisionIgnoredObject,
    int x, int y, s32 targetBaseY, int mode);
#endif
