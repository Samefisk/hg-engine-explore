#ifndef MAP_TELEPORT_H
#define MAP_TELEPORT_H

#include "types.h"

typedef struct FieldSystem FieldSystem;

#define MAP_TELEPORT_OVERLAY_ENTRY_ADDR 0x023C8000
#define MAP_TELEPORT_OVERLAY_MAGIC 0x4D54504C
#define MAP_TELEPORT_OVERLAY_VERSION 1
#define MAP_TELEPORT_DEBUG_DESTINATION_ADDR 0x023C8014

typedef enum MapTeleportDirection {
    MAP_TELEPORT_DIRECTION_NORTH = 0,
    MAP_TELEPORT_DIRECTION_SOUTH = 1,
    MAP_TELEPORT_DIRECTION_WEST = 2,
    MAP_TELEPORT_DIRECTION_EAST = 3,
} MapTeleportDirection;

// x/y are field Location coordinates consumed by the stock field warp task.
// Pokegear/world-map display coordinates must be converted before calling.
typedef struct MapTeleportDestination {
    u16 mapId;
    u16 x;
    u16 y;
    u16 direction;
} MapTeleportDestination;

typedef enum MapTeleportResult {
    MAP_TELEPORT_RESULT_OK = 0,
    MAP_TELEPORT_RESULT_OVERLAY_UNAVAILABLE,
    MAP_TELEPORT_RESULT_INVALID_FIELD,
    MAP_TELEPORT_RESULT_FIELD_BUSY,
    MAP_TELEPORT_RESULT_INVALID_DESTINATION,
    MAP_TELEPORT_RESULT_UNSAFE_LOADED_TILE,
} MapTeleportResult;

typedef MapTeleportResult (*MapTeleportRequestFunc)(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination);
typedef BOOL (*MapTeleportLoadedLandTileFunc)(FieldSystem *fieldSystem, u16 x, u16 y);
typedef void (*MapTeleportStartDebugTaskFunc)(FieldSystem *fieldSystem);

typedef struct MapTeleportOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    MapTeleportRequestFunc request;
    MapTeleportLoadedLandTileFunc isLoadedLandTile;
    MapTeleportStartDebugTaskFunc startDebugTask;
} MapTeleportOverlayEntry;

#define MAP_TELEPORT_OVERLAY_ENTRY \
    ((const MapTeleportOverlayEntry *)MAP_TELEPORT_OVERLAY_ENTRY_ADDR)
#define MAP_TELEPORT_DEBUG_DESTINATION \
    ((MapTeleportDestination *)MAP_TELEPORT_DEBUG_DESTINATION_ADDR)

static inline const MapTeleportOverlayEntry *MapTeleport_GetOverlayEntry(void)
{
    const MapTeleportOverlayEntry *entry = MAP_TELEPORT_OVERLAY_ENTRY;

    if (entry->magic != MAP_TELEPORT_OVERLAY_MAGIC
        || entry->version != MAP_TELEPORT_OVERLAY_VERSION
        || entry->size != sizeof(MapTeleportOverlayEntry)) {
        return NULL;
    }

    return entry;
}

static inline MapTeleportResult MapTeleport_Request(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    const MapTeleportOverlayEntry *entry = MapTeleport_GetOverlayEntry();

    if (entry == NULL || entry->request == NULL) {
        return MAP_TELEPORT_RESULT_OVERLAY_UNAVAILABLE;
    }

    return entry->request(fieldSystem, destination);
}

// Only validates collision for the currently loaded map. Cross-map callers must
// pass a vetted complete map and a known in-bounds land tile.
static inline BOOL MapTeleport_IsLoadedLandTile(FieldSystem *fieldSystem, u16 x, u16 y)
{
    const MapTeleportOverlayEntry *entry = MapTeleport_GetOverlayEntry();

    if (entry == NULL || entry->isLoadedLandTile == NULL) {
        return FALSE;
    }

    return entry->isLoadedLandTile(fieldSystem, x, y);
}

static inline void MapTeleport_StartDebugTask(FieldSystem *fieldSystem)
{
    const MapTeleportOverlayEntry *entry = MapTeleport_GetOverlayEntry();

    if (entry != NULL && entry->startDebugTask != NULL) {
        entry->startDebugTask(fieldSystem);
    }
}

#endif // MAP_TELEPORT_H
