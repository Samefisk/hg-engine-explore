/* Field-owned engine adapter, physically hosted in boot-resident overlay 153.
 * Mutable state stays in overlay 131 and retains its field-load lifetime.
 * This private entry does not own motion, policy, or a second stream clock. */
#include "../../include/overworld_field_terrain_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_actor_system_internal.h"

/* The resident clear helper is Thumb; keep that mode at the direct call. */
#if defined(__arm__)
__asm__(
    ".thumb\n"
    ".global memset\n.thumb_func\n.thumb_set memset, 0x023DEEA2\n");
#endif

#define FIELD_STREAM_CODE \
    __attribute__((section(".overworld_field_terrain_stream_code")))

static FIELD_STREAM_CODE BOOL OverworldFieldTerrainStream_ValidateCall(
    const OverworldFieldTerrainStreamCall *call)
{
    const OverworldActorCompatibilityEntry *entry =
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY;
    OverworldActorFieldContext context;

    if (call == NULL
        || call->version != OVERWORLD_FIELD_TERRAIN_STREAM_CALL_VERSION
        || call->size != sizeof(*call)
        || call->fieldSystem == NULL
        || call->operation > OVERWORLD_FIELD_TERRAIN_STREAM_REBIND
        || entry->magic != OVERWORLD_ACTOR_SYSTEM_COMPAT_MAGIC
        || entry->version != OVERWORLD_ACTOR_SYSTEM_COMPAT_VERSION
        || entry->size != sizeof(*entry)
        || entry->getContext == NULL) {
        return FALSE;
    }
    context = entry->getContext();
    return call->fieldContext == context;
}

static FIELD_STREAM_CODE void *OverworldFieldTerrainStream_GetLandDataManager(
    FieldSystem *fieldSystem)
{
    return *(void **)((u8 *)fieldSystem + 0x2C);
}

static FIELD_STREAM_CODE BOOL OverworldFieldTerrainStream_MatchesActive(
    const OverworldFieldTerrainStreamCall *call,
    const OverworldFieldTerrainStreamRuntime *runtime)
{
    return runtime->active
        && call->motionIdentity != 0
        && call->fieldSystem == runtime->fieldSystem
        && call->motionIdentity
            == runtime->motionIdentity
        && call->fieldContext == runtime->fieldContext;
}

static FIELD_STREAM_CODE BOOL OverworldFieldTerrainStream_AnchorWasSampled(
    void *manager,
    const OverworldFieldTerrainStreamRuntime *runtime)
{
    return *(s32 *)((u8 *)manager + 0xD0)
            == runtime->watchedAnchor.x
        && *(s32 *)((u8 *)manager + 0xD8)
            == runtime->watchedAnchor.z;
}

static FIELD_STREAM_CODE BOOL OverworldFieldTerrainStream_RestoreWatcher(
    const OverworldFieldTerrainStreamRuntime *runtime)
{
    FieldSystem *fieldSystem = runtime->fieldSystem;
    void *manager;

    if (fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL) {
        return FALSE;
    }
    manager = OverworldFieldTerrainStream_GetLandDataManager(fieldSystem);
    if (manager == NULL) {
        return FALSE;
    }
    /* The stock helper also overwrites the last sampled position. A watcher
     * change is not a completed land load, so keep that sample untouched. */
    *(VecFx32 **)((u8 *)manager + 0xDC) =
        (VecFx32 *)fieldSystem->playerAvatar->mapObject->posVec;
    return TRUE;
}

static FIELD_STREAM_CODE void OverworldFieldTerrainStream_Clear(
    OverworldFieldTerrainStreamRuntime *runtime)
{
    memset(
        runtime,
        0,
        sizeof(*runtime));
}

OverworldFieldTerrainStreamResult
__attribute__((noinline, used, section(".overworld_field_terrain_stream_entry")))
OverworldFieldTerrainStream_Apply(
    const OverworldFieldTerrainStreamCall *call,
    OverworldFieldTerrainStreamRuntime *runtime)
{
    FieldSystem *fieldSystem;
    LocalMapObject *player;
    void *manager;
    s32 targetX;
    s32 targetZ;

    if (!OverworldFieldTerrainStream_ValidateCall(call)) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
    }
    if (call->operation == OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE) {
        if (runtime->active) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;
        }
        manager = OverworldFieldTerrainStream_GetLandDataManager(
            call->fieldSystem);
        return manager == NULL || *((u8 *)manager + 0xA0) != 0
            ? OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY
            : OVERWORLD_FIELD_TERRAIN_STREAM_IDLE;
    }
    if (call->operation == OVERWORLD_FIELD_TERRAIN_STREAM_REBIND) {
        if (!runtime->active) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_IDLE;
        }
        if (call->fieldSystem != runtime->fieldSystem) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
        }
        runtime->fieldContext = call->fieldContext;
        return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;
    }
    if (call->operation == OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN) {
        if (call->motionIdentity == 0) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
        }
        if (runtime->active) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY;
        }
        fieldSystem = call->fieldSystem;
        if (fieldSystem->playerAvatar == NULL
            || fieldSystem->playerAvatar->mapObject == NULL) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
        }
        manager = OverworldFieldTerrainStream_GetLandDataManager(fieldSystem);
        if (manager == NULL || *((u8 *)manager + 0xA0) != 0) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY;
        }
        player = fieldSystem->playerAvatar->mapObject;
        runtime->watchedAnchor =
            *(VecFx32 *)player->posVec;
        runtime->fieldSystem = fieldSystem;
        runtime->fieldContext = call->fieldContext;
        runtime->motionIdentity = call->motionIdentity;
        /* Let the stock loader sample the new watcher on its own update. */
        *(VecFx32 **)((u8 *)manager + 0xDC) =
            &runtime->watchedAnchor;
        runtime->active = TRUE;
        return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;
    }
    if (call->operation == OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL) {
        if (!runtime->active) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_IDLE;
        }
        if (call->fieldSystem != runtime->fieldSystem
            || call->motionIdentity != runtime->motionIdentity) {
            return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
        }
        (void)OverworldFieldTerrainStream_RestoreWatcher(runtime);
        OverworldFieldTerrainStream_Clear(runtime);
        return OVERWORLD_FIELD_TERRAIN_STREAM_IDLE;
    }
    if (!OverworldFieldTerrainStream_MatchesActive(call, runtime)) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
    }

    manager = OverworldFieldTerrainStream_GetLandDataManager(call->fieldSystem);
    if (manager == NULL) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
    }
    targetX =
        ((u32)(u16)call->targetX << 16) + 0x8000;
    targetZ =
        ((u32)(u16)call->targetY << 16) + 0x8000;
    if (*((u8 *)manager + 0xA0) != 0
        || !OverworldFieldTerrainStream_AnchorWasSampled(manager, runtime)) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;
    }
    if (runtime->watchedAnchor.x
        != targetX) {
        runtime->watchedAnchor.x +=
            runtime->watchedAnchor.x
                    < targetX
                ? 0x10000
                : -0x10000;
        return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;
    }
    if (runtime->watchedAnchor.z
        != targetZ) {
        runtime->watchedAnchor.z +=
            runtime->watchedAnchor.z
                    < targetZ
                ? 0x10000
                : -0x10000;
        return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;
    }
    return OVERWORLD_FIELD_TERRAIN_STREAM_READY;
}
