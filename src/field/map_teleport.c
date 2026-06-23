#include "../../include/map_teleport.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/maps.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/script.h"
#include "../../include/task.h"

#define MAP_TELEPORT_DEBUG_TASK_PRIORITY 90
#define MAP_TELEPORT_DEBUG_KEYS (PAD_BUTTON_L | PAD_BUTTON_R)
#define MAP_TELEPORT_TILE_HEADBUTT 6
#define MAP_TELEPORT_FIELD_PERMISSION_PROVIDER_OFFSET 0x60
#define MAP_TELEPORT_WARP_ID_SHIFT 8
#define MAP_TELEPORT_WARP_ID_MASK 0xFF00
#define MAP_TELEPORT_DIRECTION_MASK 0x0303

typedef BOOL (*MapTeleportGetPermissionFunc)(
    FieldSystem *fieldSystem,
    int x,
    int y,
    u16 *permission);

typedef struct MapTeleportPermissionProvider {
    void *unk0;
    MapTeleportGetPermissionFunc getPermission;
} MapTeleportPermissionProvider;

typedef struct MapTeleportPlainWarpTaskEnv {
    u32 state;
    Location location;
} MapTeleportPlainWarpTaskEnv;

typedef struct MapTeleportDebugTaskEnv {
    u8 wasHeld;
} MapTeleportDebugTaskEnv;

TaskManager *LONG_CALL FieldSystem_CreateTask(
    FieldSystem *fieldSystem,
    TaskFunc taskFunc,
    void *env);
BOOL LONG_CALL Task_ScriptWarp(TaskManager *taskman);

static SysTask *sMapTeleportDebugTask;

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

static void MapTeleport_PublishRequestResult(MapTeleportResult result)
{
    if (result == MAP_TELEPORT_RESULT_FIELD_BUSY) {
        return;
    }

    gMapTeleportRuntimeRequestResult = result;
    gMapTeleportDebugStatus.requestResult = result;
    gMapTeleportRuntimeRequestCount++;
    gMapTeleportDebugStatus.requestCount = gMapTeleportRuntimeRequestCount;
}

static BOOL MapTeleport_IsMapIdValid(u16 mapId)
{
    return mapId > MAP_DIRECT4 && mapId <= MAP_T10R0801;
}

static BOOL MapTeleport_IsDirectionValid(u16 direction)
{
    return (direction & ~MAP_TELEPORT_DIRECTION_MASK) == 0
        && (direction & 3) <= MAP_TELEPORT_DIRECTION_EAST;
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
    gMapTeleportDebugStatus.ready = ready;

    if (!ready || fieldSystem == NULL || fieldSystem->location == NULL) {
        return;
    }

    gMapTeleportDebugStatus.mapId = fieldSystem->location->mapId;
    gMapTeleportDebugStatus.x = fieldSystem->location->x;
    gMapTeleportDebugStatus.y = fieldSystem->location->z;
    gMapTeleportDebugStatus.direction = fieldSystem->location->direction;
    gMapTeleportDebugStatus.requestResult = gMapTeleportRuntimeRequestResult;
    gMapTeleportDebugStatus.requestCount = gMapTeleportRuntimeRequestCount;
}

static BOOL MapTeleport_GetLoadedPermission(
    FieldSystem *fieldSystem,
    u16 x,
    u16 y,
    u16 *permission)
{
    MapTeleportPermissionProvider *provider;

    provider =
        *(MapTeleportPermissionProvider **)((u8 *)fieldSystem
            + MAP_TELEPORT_FIELD_PERMISSION_PROVIDER_OFFSET);
    return provider != NULL
        && provider->getPermission != NULL
        && provider->getPermission(fieldSystem, x, y, permission);
}

static BOOL MapTeleport_OverlayIsLoadedLandTileWithPermission(
    FieldSystem *fieldSystem,
    u16 x,
    u16 y,
    u16 *permissionOut)
{
    WARP_EVENT *warp;
    COORD_EVENT *coord;
    u32 i;
    u16 permission;

    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        return FALSE;
    }

    if (!MapTeleport_GetLoadedPermission(fieldSystem, x, y, &permission)
        || (permission & 0x8000) != 0) {
        return FALSE;
    }

    if (IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }

    if ((u8)permission >= 16 || (u8)permission == MAP_TELEPORT_TILE_HEADBUTT) {
        return FALSE;
    }

    for (i = fieldSystem->map_events->num_warp_events,
        warp = fieldSystem->map_events->warp_events;
         i != 0;
         i--, warp++) {
        if (warp->x == x && warp->y == y) {
            return FALSE;
        }
    }

    for (i = fieldSystem->map_events->num_coord_events,
        coord = fieldSystem->map_events->coord_events;
         i != 0;
         i--, coord++) {
        if ((u16)(x - coord->x) < coord->w && (u16)(y - coord->y) < coord->h) {
            return FALSE;
        }
    }

    *permissionOut = permission;
    return TRUE;
}

static BOOL MapTeleport_OverlayIsLoadedLandTile(FieldSystem *fieldSystem, u16 x, u16 y)
{
    u16 permission;

    return MapTeleport_OverlayIsLoadedLandTileWithPermission(fieldSystem, x, y, &permission);
}

BOOL MapTeleport_TrySelectRandomLoadedLandTile(
    FieldSystem *fieldSystem,
    MapTeleportDestination *destination)
{
    u16 count = 0;
    u16 permission;
    BOOL preferNonzero = FALSE;
    int centerX;
    int centerY;
    int x;
    int y;

    if (!MapTeleport_IsFieldStructReady(fieldSystem) || destination == NULL) {
        return FALSE;
    }

    centerX = fieldSystem->location->x;
    centerY = fieldSystem->location->z;
    for (y = centerY & ~31; y < ((centerY & ~31) + 32); y++) {
        for (x = centerX & ~31; x < ((centerX & ~31) + 32); x++) {
            if ((x != centerX || y != centerY)
                && MapTeleport_OverlayIsLoadedLandTileWithPermission(
                    fieldSystem,
                    (u16)x,
                    (u16)y,
                    &permission)) {
                if (permission != 0) {
                    if (!preferNonzero) {
                        preferNonzero = TRUE;
                        count = 0;
                    }
                } else if (preferNonzero) {
                    continue;
                }
                count++;
                if ((gf_rand() % count) == 0) {
                    destination->mapId = fieldSystem->location->mapId;
                    destination->x = (u16)x;
                    destination->y = (u16)y;
                    destination->direction = fieldSystem->location->direction;
                }
            }
        }
    }

    return count != 0;
}

static void MapTeleport_StartPlainWarpTask(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    MapTeleportPlainWarpTaskEnv *env;

    env = sys_AllocMemoryLo(11, sizeof(MapTeleportPlainWarpTaskEnv));
    env->state = 0;
    env->location.mapId = destination->mapId;
    env->location.warpId = (destination->direction >> MAP_TELEPORT_WARP_ID_SHIFT) - 1;
    env->location.x = destination->x;
    env->location.z = destination->y;
    env->location.direction = destination->direction & 3;
    FieldSystem_CreateTask(fieldSystem, Task_ScriptWarp, env);
}

static MapTeleportResult MapTeleport_OverlayRequestInternal(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination,
    BOOL validateLoadedTile)
{
    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        return MAP_TELEPORT_RESULT_INVALID_FIELD;
    }

    if (!MapTeleport_IsDestinationValid(destination)) {
        return MAP_TELEPORT_RESULT_INVALID_DESTINATION;
    }

    if (fieldSystem->taskman != NULL) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (validateLoadedTile
        && destination->mapId == fieldSystem->location->mapId
        && (destination->direction & MAP_TELEPORT_WARP_ID_MASK) == 0
        && !MapTeleport_OverlayIsLoadedLandTile(fieldSystem, destination->x, destination->y)) {
        return MAP_TELEPORT_RESULT_UNSAFE_LOADED_TILE;
    }

    MapTeleport_StartPlainWarpTask(fieldSystem, destination);
    return MAP_TELEPORT_RESULT_OK;
}

static MapTeleportResult MapTeleport_OverlayRequest(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    return MapTeleport_OverlayRequestInternal(fieldSystem, destination, TRUE);
}

static BOOL MapTeleport_DebugKeysHeld(void)
{
    return (PAD_Read() & MAP_TELEPORT_DEBUG_KEYS) == MAP_TELEPORT_DEBUG_KEYS;
}

static void MapTeleport_DebugTask(SysTask *task, void *data)
{
    MapTeleportDebugTaskEnv *env = (MapTeleportDebugTaskEnv *)data;
    FieldSystem *fieldSystem = gFieldSysPtr;
    const MapTeleportDestination *destination;
    MapTeleportDestination randomDestination;
    MapTeleportResult result;
    u16 destinationIndex = MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE;

    (void)task;
    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        MapTeleport_UpdateDebugStatus(fieldSystem, FALSE);
        return;
    }

    MapTeleport_UpdateDebugStatus(fieldSystem, TRUE);
    if (!MapTeleport_DebugKeysHeld()) {
        env->wasHeld = FALSE;
        return;
    }

    if (env->wasHeld) {
        return;
    }

    env->wasHeld = TRUE;
    if (gMapTeleportDebugStatus.destinationIndex
        == MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED) {
        destination = &gMapTeleportDebugDestination;
        destinationIndex = MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED;
    } else {
        destinationIndex = gMapTeleportDebugStatus.destinationIndex;
        if (destinationIndex >= OWED_ENCOUNTER_AREA_COUNT) {
            destinationIndex = gf_rand() % OWED_ENCOUNTER_AREA_COUNT;
            gMapTeleportDebugStatus.destinationIndex =
                MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE;
        }
        if (destinationIndex != MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE) {
            if (MapTeleport_TrySelectEncounterDestinationByIndex(
                    destinationIndex,
                    &randomDestination)) {
                if ((randomDestination.direction & MAP_TELEPORT_WARP_ID_MASK) == 0) {
                    if (randomDestination.mapId == fieldSystem->location->mapId) {
                        destination = MapTeleport_TrySelectRandomLoadedLandTile(
                            fieldSystem,
                            &randomDestination)
                            ? &randomDestination
                            : NULL;
                    } else {
                        randomDestination.x += gf_rand() & 1;
                        destination = &randomDestination;
                    }
                } else {
                    destination = &randomDestination;
                }
            } else {
                destination = NULL;
            }
        } else {
            destination = NULL;
        }
    }

    result = MapTeleport_OverlayRequestInternal(
        fieldSystem,
        destination,
        destinationIndex == MAP_TELEPORT_DEBUG_DESTINATION_INDEX_FORCED);
    MapTeleport_PublishRequestResult(result);
}

static void MapTeleport_StartDebugTaskImpl(FieldSystem *fieldSystem)
{
    MapTeleportDebugTaskEnv *env;

    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        MapTeleport_UpdateDebugStatus(fieldSystem, FALSE);
        return;
    }

    MapTeleport_UpdateDebugStatus(fieldSystem, TRUE);
    if (sMapTeleportDebugTask != NULL) {
        return;
    }

    env = sys_AllocMemoryLo(11, sizeof(MapTeleportDebugTaskEnv));
    env->wasHeld = TRUE;
    sMapTeleportDebugTask = CreateSysTask(
        MapTeleport_DebugTask,
        env,
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
