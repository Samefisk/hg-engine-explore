#include "../../include/map_teleport.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/maps.h"
#include "../../include/constants/sndseq.h"
#include "../../include/io_reg.h"
#include "../../include/map_events_internal.h"
#include "../../include/script.h"
#include "../../include/sound.h"
#include "../../include/task.h"

#define MAP_TELEPORT_PENDING_TIMEOUT_FRAMES 240
#define MAP_TELEPORT_DEBUG_KEYS (PAD_BUTTON_L | PAD_BUTTON_R)
#define MAP_TELEPORT_TILE_HEADBUTT 6
#define MAP_TELEPORT_BLACK_TRANSITION_SE SEQ_SE_DP_TELE
#define MAP_TELEPORT_BLACK_FADE_STEPS 1
#define MAP_TELEPORT_MASTER_BRIGHT_DARKEN 0x8000
#define MAP_TELEPORT_MASTER_BRIGHT_MAX 16

typedef struct MapTeleportPlainWarpTaskEnv {
    u32 state;
    Location location;
} MapTeleportPlainWarpTaskEnv;

typedef enum MapTeleportTransitionState {
    MAP_TELEPORT_TRANSITION_INACTIVE = 0,
    MAP_TELEPORT_TRANSITION_FADE_OUT,
    MAP_TELEPORT_TRANSITION_START_WARP,
    MAP_TELEPORT_TRANSITION_WAIT_WARP,
    MAP_TELEPORT_TRANSITION_FADE_IN,
} MapTeleportTransitionState;

TaskManager *LONG_CALL FieldSystem_CreateTask(
    FieldSystem *fieldSystem,
    TaskFunc taskFunc,
    void *env);
BOOL LONG_CALL Task_ScriptWarp(TaskManager *taskman);

static BOOL sMapTeleportRequestPending;
static u8 sMapTeleportDebugWasHeld;
static u16 sMapTeleportPendingFrames;
static MapTeleportDestination sMapTeleportPendingDestination;

static MapTeleportResult MapTeleport_OverlayRequest(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination);
static BOOL MapTeleport_StartPlainWarpTask(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination);

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

static BOOL MapTeleport_DestinationUsesWarpId(
    const MapTeleportDestination *destination)
{
    return destination != NULL
        && destination->y == MAP_TELEPORT_DESTINATION_WARP_ID_Y;
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

static BOOL MapTeleport_CurrentLocationDiffersFromTemporaryReturn(
    FieldSystem *fieldSystem,
    const MapTeleportTemporaryReturnState *temporaryReturn)
{
    return fieldSystem->location->mapId != temporaryReturn->returnMapId
        || fieldSystem->location->x != temporaryReturn->returnX
        || fieldSystem->location->z != temporaryReturn->returnY;
}

static u16 MapTeleport_AbsDiffU16(u16 a, u16 b)
{
    return a > b ? a - b : b - a;
}

static void MapTeleport_ArmTemporaryReturn(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *target,
    MapTeleportTemporaryReturnState *temporaryReturn)
{
    if (target == NULL || temporaryReturn == NULL) {
        return;
    }

    temporaryReturn->returnMapId = fieldSystem->location->mapId;
    temporaryReturn->returnX = fieldSystem->location->x;
    temporaryReturn->returnY = fieldSystem->location->z;
    temporaryReturn->targetMapId = target->mapId;
    temporaryReturn->lastX = 0;
    temporaryReturn->lastY = 0;
    temporaryReturn->returnDirection = fieldSystem->location->direction;
    temporaryReturn->stepState = MAP_TELEPORT_TEMPORARY_RETURN_WAITING_FOR_ARRIVAL;
}

static void MapTeleport_PlayBlackTransitionSE(void)
{
    GF_Snd_LoadSeqEx(
        MAP_TELEPORT_BLACK_TRANSITION_SE,
        NNS_SND_ARC_LOAD_ALL);
    StopSE(MAP_TELEPORT_BLACK_TRANSITION_SE);
    PlaySE(MAP_TELEPORT_BLACK_TRANSITION_SE);
}

static void MapTeleport_ConfirmTemporaryReturnArrival(
    FieldSystem *fieldSystem,
    MapTeleportTemporaryReturnState *temporaryReturn)
{
    if (temporaryReturn == NULL
        || temporaryReturn->stepState
            != MAP_TELEPORT_TEMPORARY_RETURN_WAITING_FOR_ARRIVAL
        || !MapTeleport_IsFieldStructReady(fieldSystem)) {
        return;
    }

    if (fieldSystem->location->mapId != temporaryReturn->targetMapId
        || !MapTeleport_CurrentLocationDiffersFromTemporaryReturn(
            fieldSystem,
            temporaryReturn)) {
        temporaryReturn->stepState = MAP_TELEPORT_TEMPORARY_RETURN_INACTIVE;
        return;
    }

    temporaryReturn->lastX = fieldSystem->location->x;
    temporaryReturn->lastY = fieldSystem->location->z;
    temporaryReturn->stepState = MAP_TELEPORT_TEMPORARY_RETURN_STEPS + 1;
}

static BOOL MapTeleport_IsTemporaryReturnDestination(
    const MapTeleportDestination *destination,
    const MapTeleportTemporaryReturnState *temporaryReturn)
{
    return destination != NULL
        && temporaryReturn != NULL
        && !MapTeleport_DestinationUsesWarpId(destination)
        && destination->mapId == temporaryReturn->returnMapId
        && destination->x == temporaryReturn->returnX
        && destination->y == temporaryReturn->returnY
        && destination->direction == temporaryReturn->returnDirection;
}

static BOOL MapTeleport_TemporaryReturnBlocksRequest(
    const MapTeleportDestination *destination)
{
    if (gMapTeleportTemporaryReturnState.stepState
        <= MAP_TELEPORT_TEMPORARY_RETURN_WAITING_FOR_ARRIVAL) {
        return FALSE;
    }

    return !MapTeleport_IsTemporaryReturnDestination(
        destination,
        &gMapTeleportTemporaryReturnState);
}

static void MapTeleport_UpdateTemporaryReturn(
    FieldSystem *fieldSystem,
    MapTeleportTemporaryReturnState *temporaryReturn)
{
    MapTeleportDestination returnDestination;
    MapTeleportResult result;

    if (temporaryReturn == NULL
        || temporaryReturn->stepState == MAP_TELEPORT_TEMPORARY_RETURN_INACTIVE
        || !MapTeleport_IsFieldStructReady(fieldSystem)
        || fieldSystem->taskman != NULL) {
        return;
    }

    if (temporaryReturn->stepState == MAP_TELEPORT_TEMPORARY_RETURN_WAITING_FOR_ARRIVAL) {
        return;
    }

    if (fieldSystem->location->mapId != temporaryReturn->targetMapId) {
        temporaryReturn->stepState = MAP_TELEPORT_TEMPORARY_RETURN_INACTIVE;
        return;
    }

    if (fieldSystem->location->x == temporaryReturn->lastX
        && fieldSystem->location->z == temporaryReturn->lastY) {
        return;
    }

    if (MapTeleport_AbsDiffU16(fieldSystem->location->x, temporaryReturn->lastX)
        + MapTeleport_AbsDiffU16(fieldSystem->location->z, temporaryReturn->lastY) != 1) {
        temporaryReturn->lastX = fieldSystem->location->x;
        temporaryReturn->lastY = fieldSystem->location->z;
        return;
    }

    if (temporaryReturn->stepState > 2) {
        temporaryReturn->stepState--;
        temporaryReturn->lastX = fieldSystem->location->x;
        temporaryReturn->lastY = fieldSystem->location->z;
        return;
    }

    returnDestination.mapId = temporaryReturn->returnMapId;
    returnDestination.x = temporaryReturn->returnX;
    returnDestination.y = temporaryReturn->returnY;
    returnDestination.direction = temporaryReturn->returnDirection;
    result = MapTeleport_OverlayRequest(fieldSystem, &returnDestination);
    if (result != MAP_TELEPORT_RESULT_FIELD_BUSY) {
        temporaryReturn->stepState = MAP_TELEPORT_TEMPORARY_RETURN_INACTIVE;
    }
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

static BOOL MapTeleport_PendingDestinationReached(FieldSystem *fieldSystem)
{
    if (!MapTeleport_IsFieldStructReady(fieldSystem)
        || fieldSystem->location->mapId != sMapTeleportPendingDestination.mapId) {
        return FALSE;
    }

    return MapTeleport_DestinationUsesWarpId(&sMapTeleportPendingDestination)
        || (fieldSystem->location->x == sMapTeleportPendingDestination.x
            && fieldSystem->location->z == sMapTeleportPendingDestination.y);
}

static void MapTeleport_SetBlackFadeLevel(u8 level)
{
    u16 brightness;

    if (level > MAP_TELEPORT_MASTER_BRIGHT_MAX) {
        level = MAP_TELEPORT_MASTER_BRIGHT_MAX;
    }

    if (level == 0) {
        brightness = 0;
    } else {
        brightness = MAP_TELEPORT_MASTER_BRIGHT_DARKEN | level;
    }

    reg_GX_MASTER_BRIGHT = brightness;
    reg_GXS_DB_MASTER_BRIGHT = brightness;
}

static void MapTeleport_BeginTransition(void)
{
    gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_FADE_OUT;
    gMapTeleportTransitionState.frame = 0;
    MapTeleport_SetBlackFadeLevel(0);
}

static u8 MapTeleport_BlackFadeLevelFromFrame(u8 frame)
{
    if (frame == 0) {
        return 0;
    }

    if (frame >= MAP_TELEPORT_BLACK_FADE_STEPS) {
        return MAP_TELEPORT_MASTER_BRIGHT_MAX;
    }

    return (frame * MAP_TELEPORT_MASTER_BRIGHT_MAX
        + MAP_TELEPORT_BLACK_FADE_STEPS - 1)
        / MAP_TELEPORT_BLACK_FADE_STEPS;
}

static BOOL MapTeleport_FadeOutToBlack(void)
{
    if (gMapTeleportTransitionState.frame < MAP_TELEPORT_BLACK_FADE_STEPS) {
        gMapTeleportTransitionState.frame++;
    }

    MapTeleport_SetBlackFadeLevel(
        MapTeleport_BlackFadeLevelFromFrame(gMapTeleportTransitionState.frame));
    return gMapTeleportTransitionState.frame >= MAP_TELEPORT_BLACK_FADE_STEPS;
}

static BOOL MapTeleport_FadeInFromBlack(void)
{
    if (gMapTeleportTransitionState.frame != 0) {
        gMapTeleportTransitionState.frame--;
    }

    MapTeleport_SetBlackFadeLevel(
        MapTeleport_BlackFadeLevelFromFrame(gMapTeleportTransitionState.frame));
    return gMapTeleportTransitionState.frame == 0;
}

static BOOL MapTeleport_UpdateTransition(FieldSystem *fieldSystem)
{
    if (gMapTeleportTransitionState.state == MAP_TELEPORT_TRANSITION_INACTIVE) {
        return FALSE;
    }

    switch (gMapTeleportTransitionState.state) {
    case MAP_TELEPORT_TRANSITION_FADE_OUT:
        if (fieldSystem->taskman != NULL) {
            return TRUE;
        }

        if (MapTeleport_FadeOutToBlack()) {
            MapTeleport_PlayBlackTransitionSE();
            gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_START_WARP;
        }
        return TRUE;

    case MAP_TELEPORT_TRANSITION_START_WARP:
        if (fieldSystem->taskman != NULL) {
            return TRUE;
        }

        MapTeleport_SetBlackFadeLevel(MAP_TELEPORT_MASTER_BRIGHT_MAX);
        if (!MapTeleport_StartPlainWarpTask(fieldSystem, &sMapTeleportPendingDestination)) {
            sMapTeleportRequestPending = FALSE;
            sMapTeleportPendingFrames = 0;
            gMapTeleportTransitionState.frame = MAP_TELEPORT_BLACK_FADE_STEPS;
            gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_FADE_IN;
            return TRUE;
        }
        gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_WAIT_WARP;
        return TRUE;

    case MAP_TELEPORT_TRANSITION_WAIT_WARP:
        MapTeleport_SetBlackFadeLevel(MAP_TELEPORT_MASTER_BRIGHT_MAX);
        if (fieldSystem->taskman == NULL
            && (MapTeleport_PendingDestinationReached(fieldSystem)
                || !sMapTeleportRequestPending)) {
            sMapTeleportRequestPending = FALSE;
            sMapTeleportPendingFrames = 0;
            MapTeleport_ConfirmTemporaryReturnArrival(
                fieldSystem,
                &gMapTeleportTemporaryReturnState);
            gMapTeleportTransitionState.frame = MAP_TELEPORT_BLACK_FADE_STEPS;
            gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_FADE_IN;
        }
        return TRUE;

    case MAP_TELEPORT_TRANSITION_FADE_IN:
        if (MapTeleport_FadeInFromBlack()) {
            gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_INACTIVE;
        }
        return TRUE;
    }

    gMapTeleportTransitionState.state = MAP_TELEPORT_TRANSITION_INACTIVE;
    MapTeleport_SetBlackFadeLevel(0);
    return FALSE;
}

static void MapTeleport_UpdatePending(FieldSystem *fieldSystem)
{
    if (!sMapTeleportRequestPending) {
        return;
    }

    if (MapTeleport_PendingDestinationReached(fieldSystem)
        && fieldSystem->taskman == NULL) {
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

static BOOL MapTeleport_StartPlainWarpTask(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    MapTeleportPlainWarpTaskEnv *env;

    env = sys_AllocMemoryLo(11, sizeof(MapTeleportPlainWarpTaskEnv));
    if (env == NULL) {
        return FALSE;
    }

    env->state = 0;
    env->location.mapId = destination->mapId;
    if (MapTeleport_DestinationUsesWarpId(destination)) {
        env->location.warpId = destination->x;
        env->location.x = -1;
        env->location.z = -1;
    } else {
        env->location.warpId = -1;
        env->location.x = destination->x;
        env->location.z = destination->y;
    }
    env->location.direction = destination->direction;
    if (FieldSystem_CreateTask(fieldSystem, Task_ScriptWarp, env) == NULL) {
        sys_FreeMemoryEz(env);
        return FALSE;
    }

    return TRUE;
}

static MapTeleportResult MapTeleport_OverlayRequest(
    FieldSystem *fieldSystem,
    const MapTeleportDestination *destination)
{
    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        return MAP_TELEPORT_RESULT_INVALID_FIELD;
    }

    MapTeleport_UpdatePending(fieldSystem);
    if (gMapTeleportTransitionState.state != MAP_TELEPORT_TRANSITION_INACTIVE) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (sMapTeleportRequestPending) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (!MapTeleport_IsDestinationValid(destination)) {
        return MAP_TELEPORT_RESULT_INVALID_DESTINATION;
    }

    if (MapTeleport_TemporaryReturnBlocksRequest(destination)) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (fieldSystem->taskman != NULL) {
        return MAP_TELEPORT_RESULT_FIELD_BUSY;
    }

    if (!MapTeleport_DestinationUsesWarpId(destination)
        && destination->mapId == fieldSystem->location->mapId
        && !MapTeleport_OverlayIsLoadedLandTile(fieldSystem, destination->x, destination->y)) {
        return MAP_TELEPORT_RESULT_UNSAFE_LOADED_TILE;
    }

    sMapTeleportRequestPending = TRUE;
    sMapTeleportPendingFrames = MAP_TELEPORT_PENDING_TIMEOUT_FRAMES;
    sMapTeleportPendingDestination = *destination;
    MapTeleport_BeginTransition();
    return MAP_TELEPORT_RESULT_OK;
}

static BOOL MapTeleport_DebugKeysHeld(void)
{
    return (PAD_Read() & MAP_TELEPORT_DEBUG_KEYS) == MAP_TELEPORT_DEBUG_KEYS;
}

static void MapTeleport_PollDebugImpl(FieldSystem *fieldSystem)
{
    const MapTeleportDestination *destination;
    MapTeleportResult result;
    u16 count;
    u16 destinationIndex = MAP_TELEPORT_DEBUG_DESTINATION_INDEX_NONE;

    if (!MapTeleport_IsFieldStructReady(fieldSystem)) {
        MapTeleport_UpdateDebugStatus(fieldSystem, FALSE);
        return;
    }

    MapTeleport_UpdateDebugStatus(fieldSystem, TRUE);
    MapTeleport_UpdatePending(fieldSystem);
    if (MapTeleport_UpdateTransition(fieldSystem)) {
        return;
    }

    MapTeleport_UpdateTemporaryReturn(fieldSystem, &gMapTeleportTemporaryReturnState);
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
    if (result == MAP_TELEPORT_RESULT_OK) {
        MapTeleport_ArmTemporaryReturn(
            fieldSystem,
            destination,
            &gMapTeleportTemporaryReturnState);
    }
    gMapTeleportDebugStatus.destinationIndex = destinationIndex;
    gMapTeleportDebugStatus.requestResult = result;
    gMapTeleportDebugStatus.requestCount++;
}

const MapTeleportOverlayEntry gMapTeleportOverlayEntry
    __attribute__((section(".map_teleport_entry"), used)) = {
    MAP_TELEPORT_OVERLAY_MAGIC,
    MAP_TELEPORT_OVERLAY_VERSION,
    sizeof(MapTeleportOverlayEntry),
    MapTeleport_OverlayRequest,
    MapTeleport_OverlayIsLoadedLandTile,
    MapTeleport_PollDebugImpl,
};
