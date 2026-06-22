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

typedef struct MapTeleportPlainWarpTaskEnv {
    u32 state;
    Location location;
} MapTeleportPlainWarpTaskEnv;

TaskManager *LONG_CALL FieldSystem_CreateTask(
    FieldSystem *fieldSystem,
    TaskFunc taskFunc,
    void *env);
BOOL LONG_CALL Task_ScriptWarp(TaskManager *taskman);

static BOOL sMapTeleportRequestPending;
static SysTask *sMapTeleportDebugTask;
static FieldSystem *sMapTeleportDebugFieldSystem;
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

MapTeleportDebugStatus gMapTeleportDebugStatus
    __attribute__((section(".map_teleport_debug_status"), used)) = {
    MAP_TELEPORT_DEBUG_STATUS_MAGIC,
    MAP_TELEPORT_DEBUG_STATUS_VERSION,
    sizeof(MapTeleportDebugStatus),
    MAP_NOTHING,
    0,
    0,
    MAP_TELEPORT_DIRECTION_SOUTH,
    MAP_TELEPORT_RESULT_INVALID_FIELD,
    0,
    FALSE,
    MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE,
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

static void MapTeleport_UpdateDebugStatus(FieldSystem *fieldSystem, BOOL ready)
{
    gMapTeleportDebugStatus.magic = MAP_TELEPORT_DEBUG_STATUS_MAGIC;
    gMapTeleportDebugStatus.version = MAP_TELEPORT_DEBUG_STATUS_VERSION;
    gMapTeleportDebugStatus.size = sizeof(MapTeleportDebugStatus);
    gMapTeleportDebugStatus.ready = ready;

    if (!ready || fieldSystem == NULL || fieldSystem->location == NULL) {
        gMapTeleportDebugStatus.mapId = MAP_NOTHING;
        gMapTeleportDebugStatus.x = 0;
        gMapTeleportDebugStatus.y = 0;
        gMapTeleportDebugStatus.direction = MAP_TELEPORT_DIRECTION_SOUTH;
        gMapTeleportDebugStatus.destinationIndex = MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE;
        return;
    }

    gMapTeleportDebugStatus.mapId = fieldSystem->location->mapId;
    gMapTeleportDebugStatus.x = fieldSystem->location->x;
    gMapTeleportDebugStatus.y = fieldSystem->location->z;
    gMapTeleportDebugStatus.direction = fieldSystem->location->direction;
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

static void MapTeleport_StartPlainWarpTask(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    MapTeleportPlainWarpTaskEnv *env;

    env = sys_AllocMemoryLo(11, sizeof(MapTeleportPlainWarpTaskEnv));
    env->state = 0;
    env->location.mapId = destination->mapId;
    env->location.warpId = -1;
    env->location.x = destination->x;
    env->location.z = destination->y;
    env->location.direction = destination->direction;
    FieldSystem_CreateTask(fieldSystem, Task_ScriptWarp, env);
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

    if (fieldSystem->taskman != NULL) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (destination->mapId == fieldSystem->location->mapId
        && !MapTeleport_OverlayIsLoadedLandTile(fieldSystem, destination->x, destination->y)) {
        return MAP_TELEPORT_RESULT_UNSAFE_LOADED_TILE;
    }

    sMapTeleportRequestPending = TRUE;
    sMapTeleportPendingFrames = MAP_TELEPORT_PENDING_TIMEOUT_FRAMES;
    sMapTeleportPendingDestination = *destination;
    MapTeleport_StartPlainWarpTask(fieldSystem, destination);
    return MAP_TELEPORT_RESULT_OK;
}

static BOOL MapTeleport_DebugKeysHeld(void)
{
    return (PAD_Read() & MAP_TELEPORT_DEBUG_KEYS) == MAP_TELEPORT_DEBUG_KEYS;
}

static void MapTeleport_DebugTask(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;
    const MapTeleportDestination *destination;
    MapTeleportResult result;
    u16 count;
    u16 destinationIndex = MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE;

    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        MapTeleport_UpdateDebugStatus(fieldSystem, FALSE);
        sMapTeleportDebugTask = NULL;
        sMapTeleportDebugFieldSystem = NULL;
        DestroySysTask(task);
        return;
    }

    MapTeleport_UpdateDebugStatus(fieldSystem, TRUE);
    MapTeleport_UpdatePending(fieldSystem);
    if (!MapTeleport_DebugKeysHeld()) {
        sMapTeleportDebugWasHeld = FALSE;
        return;
    }

    if (sMapTeleportDebugWasHeld) {
        return;
    }

    sMapTeleportDebugWasHeld = TRUE;
    if (gMapTeleportDebugStatus.destinationIndex
        == MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED) {
        destination = &gMapTeleportDebugDestination;
        destinationIndex = MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED;
    } else {
        count = MapTeleport_GetEncounterDestinationCount();
        if (count != 0) {
            destinationIndex = gf_rand() % count;
            destination = MapTeleport_GetEncounterDestinationByIndex(destinationIndex);
        } else {
            destination = NULL;
        }
    }

    result = MapTeleport_OverlayRequest(fieldSystem, destination);
    gMapTeleportDebugStatus.destinationIndex = destinationIndex;
    gMapTeleportDebugStatus.requestResult = result;
    gMapTeleportDebugStatus.requestCount++;
}

static void MapTeleport_StartDebugTaskImpl(FieldSystem *fieldSystem)
{
    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        MapTeleport_UpdateDebugStatus(fieldSystem, FALSE);
        return;
    }

    MapTeleport_UpdateDebugStatus(fieldSystem, TRUE);
    if (sMapTeleportDebugTask != NULL) {
        if (sMapTeleportDebugFieldSystem == fieldSystem) {
            return;
        }

        DestroySysTask(sMapTeleportDebugTask);
        sMapTeleportDebugTask = NULL;
        sMapTeleportDebugFieldSystem = NULL;
    }

    sMapTeleportDebugWasHeld = MapTeleport_DebugKeysHeld();
    sMapTeleportDebugTask = CreateSysTask(
        MapTeleport_DebugTask,
        fieldSystem,
        MAP_TELEPORT_DEBUG_TASK_PRIORITY);
    if (sMapTeleportDebugTask != NULL) {
        sMapTeleportDebugFieldSystem = fieldSystem;
    }
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
