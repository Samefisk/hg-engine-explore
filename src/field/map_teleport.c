#include "../../include/map_teleport.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/maps.h"
#include "../../include/map_events_internal.h"
#include "../../include/script.h"
#include "../../include/task.h"

#define MAP_TELEPORT_PENDING_TIMEOUT_FRAMES 240
#define MAP_TELEPORT_DEBUG_TASK_PRIORITY 90
#define MAP_TELEPORT_DEBUG_KEYS (PAD_BUTTON_L | PAD_BUTTON_R)
#define MAP_TELEPORT_TILE_HEADBUTT 6

void LONG_CALL sub_020538C0(
    FieldSystem *fieldSystem,
    u32 mapId,
    int warpId,
    int x,
    int y,
    int direction);

static BOOL sMapTeleportRequestPending;
static SysTask *sMapTeleportDebugTask;
static u8 sMapTeleportDebugWasHeld;
static u16 sMapTeleportPendingFrames;
static MapTeleportDestination sMapTeleportPendingDestination;

MapTeleportDestination gMapTeleportDebugDestination
    __attribute__((section(".map_teleport_debug_destination"), used)) = {
    MAP_T20,
    0x02B7,
    0x018D,
    MAP_TELEPORT_DIRECTION_SOUTH,
};

static BOOL MapTeleport_IsSurfBehavior(u8 behavior)
{
    return behavior == 16 || behavior == 18 || behavior == 21 || behavior == 42;
}

static BOOL MapTeleport_IsMapIdValid(u16 mapId)
{
    return mapId > MAP_DIRECT4 && mapId <= MAP_T10R0801;
}

static BOOL MapTeleport_IsDirectionValid(u16 direction)
{
    return direction <= MAP_TELEPORT_DIRECTION_EAST;
}

static BOOL MapTeleport_IsDestinationValid(const MapTeleportDestination *destination)
{
    return destination != NULL
        && MapTeleport_IsMapIdValid(destination->mapId)
        && MapTeleport_IsDirectionValid(destination->direction);
}

static BOOL MapTeleport_IsFieldStructReady(FieldSystem *fieldSystem)
{
    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || fieldSystem->map_events == NULL
        || fieldSystem->map_matrix == NULL) {
        return FALSE;
    }

    return TRUE;
}

static BOOL MapTeleport_OverlayIsLoadedLandTile(FieldSystem *fieldSystem, u16 x, u16 y)
{
    u8 behavior;

    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        return FALSE;
    }

    if (IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    return behavior != MAP_TELEPORT_TILE_HEADBUTT && !MapTeleport_IsSurfBehavior(behavior);
}

static void MapTeleport_UpdatePending(FieldSystem *fieldSystem)
{
    if (!sMapTeleportRequestPending) {
        return;
    }

    if (MapTeleport_IsFieldStructReady(fieldSystem)
        && fieldSystem->location->mapId == sMapTeleportPendingDestination.mapId
        && fieldSystem->location->x == sMapTeleportPendingDestination.x
        && fieldSystem->location->z == sMapTeleportPendingDestination.y) {
        sMapTeleportRequestPending = FALSE;
        sMapTeleportPendingFrames = 0;
        return;
    }

    if (sMapTeleportPendingFrames != 0) {
        sMapTeleportPendingFrames--;
        if (sMapTeleportPendingFrames == 0) {
            sMapTeleportRequestPending = FALSE;
        }
    }
}

static MapTeleportResult MapTeleport_OverlayRequest(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        return MAP_TELEPORT_RESULT_INVALID_FIELD;
    }

    MapTeleport_UpdatePending(fieldSystem);
    if (sMapTeleportRequestPending) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (!MapTeleport_IsDestinationValid(destination)) {
        return MAP_TELEPORT_RESULT_INVALID_DESTINATION;
    }

    if (destination->mapId == fieldSystem->location->mapId
        && !MapTeleport_OverlayIsLoadedLandTile(fieldSystem, destination->x, destination->y)) {
        return MAP_TELEPORT_RESULT_UNSAFE_LOADED_TILE;
    }

    sMapTeleportRequestPending = TRUE;
    sMapTeleportPendingFrames = MAP_TELEPORT_PENDING_TIMEOUT_FRAMES;
    sMapTeleportPendingDestination = *destination;
    sub_020538C0(
        fieldSystem,
        destination->mapId,
        -1,
        destination->x,
        destination->y,
        destination->direction);
    return MAP_TELEPORT_RESULT_OK;
}

static BOOL MapTeleport_DebugKeysHeld(void)
{
    return (PAD_Read() & MAP_TELEPORT_DEBUG_KEYS) == MAP_TELEPORT_DEBUG_KEYS;
}

static void MapTeleport_DebugTask(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;

    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        sMapTeleportDebugTask = NULL;
        DestroySysTask(task);
        return;
    }

    if (!MapTeleport_DebugKeysHeld()) {
        sMapTeleportDebugWasHeld = FALSE;
        return;
    }

    if (sMapTeleportDebugWasHeld) {
        return;
    }

    sMapTeleportDebugWasHeld = TRUE;
    (void)MapTeleport_OverlayRequest(fieldSystem, &gMapTeleportDebugDestination);
}

static void MapTeleport_StartDebugTaskImpl(FieldSystem *fieldSystem)
{
    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        return;
    }

    if (sMapTeleportDebugTask != NULL) {
        DestroySysTask(sMapTeleportDebugTask);
    }

    sMapTeleportDebugWasHeld = MapTeleport_DebugKeysHeld();
    sMapTeleportDebugTask = CreateSysTask(
        MapTeleport_DebugTask,
        fieldSystem,
        MAP_TELEPORT_DEBUG_TASK_PRIORITY);
}

const MapTeleportOverlayEntry gMapTeleportOverlayEntry
    __attribute__((section(".map_teleport_entry"), used)) = {
    MAP_TELEPORT_OVERLAY_MAGIC,
    MAP_TELEPORT_OVERLAY_VERSION,
    sizeof(MapTeleportOverlayEntry),
    MapTeleport_OverlayRequest,
    MapTeleport_OverlayIsLoadedLandTile,
    MapTeleport_StartDebugTaskImpl,
};
