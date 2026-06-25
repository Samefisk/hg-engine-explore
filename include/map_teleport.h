#ifndef MAP_TELEPORT_H
#define MAP_TELEPORT_H

#include "types.h"

typedef struct FieldSystem FieldSystem;

#define MAP_TELEPORT_OVERLAY_ENTRY_ADDR 0x023C8000
#define MAP_TELEPORT_OVERLAY_MAGIC 0x4D54504C
#define MAP_TELEPORT_OVERLAY_VERSION 3
#define MAP_TELEPORT_DEBUG_DESTINATION_ADDR 0x023C8014
#define MAP_TELEPORT_DEBUG_STATUS_ADDR 0x023C801C
#define MAP_TELEPORT_DEBUG_STATUS_MAGIC 0x4D545053
#define MAP_TELEPORT_DEBUG_STATUS_VERSION 1
#define MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED 0xFFFE
#define MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE 0xFFFF
#define MAP_TELEPORT_ENCOUNTER_DESTINATION_ENTRY_ADDR 0x023C8034
#define MAP_TELEPORT_ENCOUNTER_DESTINATION_MAGIC 0x4D544544
#define MAP_TELEPORT_ENCOUNTER_DESTINATION_VERSION 1
#define MAP_TELEPORT_DESTINATION_WARP_ID_Y 0x03FF
#define MAP_TELEPORT_TEMPORARY_RETURN_STEPS 10

typedef enum MapTeleportDirection {
    MAP_TELEPORT_DIRECTION_NORTH = 0,
    MAP_TELEPORT_DIRECTION_SOUTH = 1,
    MAP_TELEPORT_DIRECTION_WEST = 2,
    MAP_TELEPORT_DIRECTION_EAST = 3,
} MapTeleportDirection;

// x/y are field Location coordinates consumed by the stock field warp task.
// Pokegear/world-map display coordinates must be converted before calling.
// If y is MAP_TELEPORT_DESTINATION_WARP_ID_Y, x is a game-authored warp id
// for mapId and the stock warp task resolves the final landing coordinate.
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

typedef enum MapTeleportTemporaryReturnStepState {
    MAP_TELEPORT_TEMPORARY_RETURN_INACTIVE = 0,
    MAP_TELEPORT_TEMPORARY_RETURN_WAITING_FOR_ARRIVAL,
} MapTeleportTemporaryReturnStepState;

typedef struct MapTeleportTemporaryReturnState {
    u16 returnMapId;
    u16 returnX;
    u16 returnY;
    u16 targetMapId;
    u16 lastX;
    u16 lastY;
    u8 returnDirection;
    u8 stepState;
} MapTeleportTemporaryReturnState;

typedef struct MapTeleportTransitionRuntimeState {
    u8 state;
    u8 frame;
} MapTeleportTransitionRuntimeState;

typedef MapTeleportResult (*MapTeleportRequestFunc)(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination);
typedef BOOL (*MapTeleportLoadedLandTileFunc)(FieldSystem *fieldSystem, u16 x, u16 y);
typedef void (*MapTeleportDebugPollFunc)(FieldSystem *fieldSystem);
typedef u16 (*MapTeleportEncounterDestinationCountFunc)(void);
typedef const MapTeleportDestination *(*MapTeleportEncounterDestinationByIndexFunc)(u16 index);
typedef const MapTeleportDestination *(*MapTeleportEncounterDestinationByMapIdFunc)(u16 mapId);

typedef struct MapTeleportOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    MapTeleportRequestFunc request;
    MapTeleportLoadedLandTileFunc isLoadedLandTile;
    MapTeleportDebugPollFunc pollDebug;
} MapTeleportOverlayEntry;

typedef struct MapTeleportDebugStatus {
    u32 magic;
    u16 version;
    u16 size;
    u16 mapId;
    u16 x;
    u16 y;
    u16 direction;
    u16 requestResult;
    u16 requestCount;
    u16 ready;
    u16 destinationIndex;
} MapTeleportDebugStatus;

typedef struct MapTeleportEncounterDestinationEntry {
    u32 magic;
    u16 version;
    u16 size;
    u16 count;
    u16 reserved;
    MapTeleportEncounterDestinationByIndexFunc byIndex;
    MapTeleportEncounterDestinationByMapIdFunc byMapId;
} MapTeleportEncounterDestinationEntry;

extern MapTeleportTemporaryReturnState gMapTeleportTemporaryReturnState;
extern MapTeleportTransitionRuntimeState gMapTeleportTransitionState;

#define MAP_TELEPORT_OVERLAY_ENTRY \
    ((const MapTeleportOverlayEntry *)MAP_TELEPORT_OVERLAY_ENTRY_ADDR)
#define MAP_TELEPORT_DEBUG_DESTINATION \
    ((MapTeleportDestination *)MAP_TELEPORT_DEBUG_DESTINATION_ADDR)
#define MAP_TELEPORT_DEBUG_STATUS \
    ((const MapTeleportDebugStatus *)MAP_TELEPORT_DEBUG_STATUS_ADDR)
#define MAP_TELEPORT_ENCOUNTER_DESTINATION_ENTRY \
    ((const MapTeleportEncounterDestinationEntry *)MAP_TELEPORT_ENCOUNTER_DESTINATION_ENTRY_ADDR)

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

static inline void MapTeleport_PollDebug(FieldSystem *fieldSystem)
{
    const MapTeleportOverlayEntry *entry = MapTeleport_GetOverlayEntry();

    if (entry == NULL) {
        return;
    }

    entry->pollDebug(fieldSystem);
}

static inline const MapTeleportDebugStatus *MapTeleport_GetDebugStatus(void)
{
    const MapTeleportDebugStatus *status = MAP_TELEPORT_DEBUG_STATUS;

    if (status->magic != MAP_TELEPORT_DEBUG_STATUS_MAGIC
        || status->version != MAP_TELEPORT_DEBUG_STATUS_VERSION
        || status->size != sizeof(MapTeleportDebugStatus)) {
        return NULL;
    }

    return status;
}

static inline const MapTeleportEncounterDestinationEntry *
MapTeleport_GetEncounterDestinationEntry(void)
{
    const MapTeleportEncounterDestinationEntry *entry =
        MAP_TELEPORT_ENCOUNTER_DESTINATION_ENTRY;

    if (entry->magic != MAP_TELEPORT_ENCOUNTER_DESTINATION_MAGIC
        || entry->version != MAP_TELEPORT_ENCOUNTER_DESTINATION_VERSION
        || entry->size != sizeof(MapTeleportEncounterDestinationEntry)) {
        return NULL;
    }

    return entry;
}

static inline u16 MapTeleport_GetEncounterDestinationCount(void)
{
    const MapTeleportEncounterDestinationEntry *entry =
        MapTeleport_GetEncounterDestinationEntry();

    if (entry == NULL || entry->byIndex == NULL) {
        return 0;
    }

    return entry->count;
}

// Encounter destination lookup pointers may refer to overlay-local scratch
// storage. Copy the value or call MapTeleport_Request before another lookup.
static inline const MapTeleportDestination *
MapTeleport_GetEncounterDestinationByIndex(u16 index)
{
    const MapTeleportEncounterDestinationEntry *entry =
        MapTeleport_GetEncounterDestinationEntry();

    if (entry == NULL || entry->byIndex == NULL) {
        return NULL;
    }

    return entry->byIndex(index);
}

static inline const MapTeleportDestination *
MapTeleport_GetEncounterDestinationByMapId(u16 mapId)
{
    const MapTeleportEncounterDestinationEntry *entry =
        MapTeleport_GetEncounterDestinationEntry();

    if (entry == NULL || entry->byMapId == NULL) {
        return NULL;
    }

    return entry->byMapId(mapId);
}

#endif // MAP_TELEPORT_H
