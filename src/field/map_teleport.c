#include "../../include/map_teleport.h"
#include "../../include/overworld_field_terrain_internal.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/constants/maps.h"
#include "../../include/constants/species.h"
#include "../../include/config.h"
#include "../../include/io_reg.h"
#include "../../include/map_events_internal.h"
#include "../../include/overlay.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/overworld_wild_spawns_internal.h"

/* Preserve Thumb metadata for the direct resident helper imports. */
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldFieldService_SyncMountedPresentation, 0x01FFA101\n"
    ".thumb_func\n.thumb_set OverworldFieldTerrainStream_Apply, 0x023BFC60\n");

volatile u8 gOverworldFollowerSelectorStateStorage
    __attribute__((section(".overworld_follower_selector_state"), used));
typedef struct OverworldFieldPrivateFlags {
    u8 followerSelectorYWasDown;
    u8 wildPlayerFrameServiceActive;
} OverworldFieldPrivateFlags;
static volatile OverworldFieldPrivateFlags sOverworldFieldPrivateFlags
    __attribute__((section(".overworld_field_private_flags"), used));
#define sOverworldFollowerSelectorYWasDown \
    sOverworldFieldPrivateFlags.followerSelectorYWasDown
#define sOverworldWildPlayerFrameServiceActive \
    sOverworldFieldPrivateFlags.wildPlayerFrameServiceActive
volatile OverworldFollowerTransitionQueueStorage
    gOverworldFollowerTransitionQueueStorage
    __attribute__((section(".overworld_follower_transition_queue"), used));

typedef struct OverworldFieldTransitionRuntime {
    FieldSystem *fieldSystem;
    MapObjectMan *manager;
    u32 sequence;
    u16 previousMapId;
    u16 currentMapId;
    u8 disposition;
    u8 acknowledgements;
    u8 active;
    u8 reserved;
} OverworldFieldTransitionRuntime;

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char OverworldFieldTransitionPreviousMapOffsetMustRemain12[
    offsetof(OverworldFieldTransitionRuntime, previousMapId) == 12 ? 1 : -1];
typedef char OverworldFieldTransitionCurrentMapOffsetMustRemain14[
    offsetof(OverworldFieldTransitionRuntime, currentMapId) == 14 ? 1 : -1];
typedef char OverworldFieldTransitionDispositionOffsetMustRemain16[
    offsetof(OverworldFieldTransitionRuntime, disposition) == 16 ? 1 : -1];
typedef char OverworldFieldTransitionActiveOffsetMustRemain18[
    offsetof(OverworldFieldTransitionRuntime, active) == 18 ? 1 : -1];
#endif

static OverworldFieldTransitionRuntime sOverworldFieldTransition;

static OverworldFieldTerrainStreamRuntime sOverworldFieldTerrainStream;

__asm__(
    ".global OverworldFieldTransitionRuntimeStorage\n"
    ".set OverworldFieldTransitionRuntimeStorage, sOverworldFieldTransition\n");

BOOL OverworldFieldService_FinishPendingTransition(void);

/* The service table stays in field; its presentation code is boot-resident
 * alongside the gait model so field code cannot overrun its fixed tail. */
extern BOOL OverworldFieldService_SyncMountedPresentation(
    OverworldFieldMountPresentationCall *call);

OverworldFieldTerrainStreamResult
__attribute__((section(".overworld_field_terrain_stream"), used))
OverworldFieldService_TerrainStream(
    const OverworldFieldTerrainStreamCall *call)
{
    return OverworldFieldTerrainStream_Apply(call, &sOverworldFieldTerrainStream);
}

const OverworldFieldMountPresentationEntry
    gOverworldFieldMountPresentationEntry
    __attribute__((section(".overworld_field_mount_presentation_entry"), used)) = {
        OVERWORLD_FIELD_MOUNT_PRESENTATION_MAGIC,
        OVERWORLD_FIELD_MOUNT_PRESENTATION_VERSION,
        sizeof(OverworldFieldMountPresentationEntry),
        OverworldFieldService_SyncMountedPresentation,
        OverworldFieldService_TerrainStream,
    };

BOOL __attribute__((section(".overworld_follower_transition_queue_append"), used))
OverworldFollowerTransitionQueue_AppendResident(u8 command)
{
    volatile OverworldFollowerTransitionQueueStorage *queue =
        &gOverworldFollowerTransitionQueueStorage;

    if (command == 0
        || queue->count >= OVERWORLD_FOLLOWER_TRANSITION_QUEUE_CAPACITY) {
        return FALSE;
    }
    queue->commands |= (u32)command
        << (queue->count
            * OVERWORLD_FOLLOWER_TRANSITION_QUEUE_COMMAND_BITS);
    queue->count++;
    return TRUE;
}

void __attribute__((section(".overworld_follower_transition_queue_pop"), used))
OverworldFollowerTransitionQueue_PopResident(void)
{
    volatile OverworldFollowerTransitionQueueStorage *queue =
        &gOverworldFollowerTransitionQueueStorage;

    if (queue->count != 0) {
        queue->commands >>=
            OVERWORLD_FOLLOWER_TRANSITION_QUEUE_COMMAND_BITS;
        queue->count--;
    }
    queue->headIssued = FALSE;
}

static BOOL OverworldFollowerSelector_IsCallable(const void *function)
{
    u32 rawAddress = (u32)function;
    u32 address = rawAddress & ~1u;

    return (rawAddress & 1u) != 0
        && address >= OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR
        && address < OVERWORLD_FOLLOWER_SELECTOR_CALLBACK_END_ADDR;
}

static BOOL __attribute__((noinline))
OverworldFollowerSelector_ValidateLoaded(void)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;

    return entry->magic == OVERWORLD_FOLLOWER_SELECTOR_MAGIC
        && OverworldFollowerSelector_IsCallable(entry->validate)
        && entry->validate();
}

static BOOL OverworldFollowerSelector_ForceDirectUnload(
    FieldSystem *fieldSystem)
{
    BOOL isLoaded = OverworldFollowerSelector_IsDirectLoaded();

    if (isLoaded) {
        if (!OverworldFollowerSelector_ValidateLoaded()
            || !OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->inputCancel(
                fieldSystem)) {
            /* Keep corrupt live code and its BSS resident; unloading loses the
             * only state capable of restoring external callbacks and objects. */
            return FALSE;
        }
        if (!FS_UnloadOverlay(0, OVERLAY_OVERWORLD_FOLLOWER_SELECTOR)) {
            /* Keep ownership published until the managed unload succeeds. */
            OVERWORLD_FOLLOWER_SELECTOR_STATE |=
                OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG
                | OVERWORLD_FOLLOWER_SELECTOR_UNLOAD_PENDING_FLAG;
            return FALSE;
        }
        *(u32 *)OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR = 0;
    }
    OVERWORLD_FOLLOWER_SELECTOR_STATE &= (u8)~(
        OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG
        | OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG
        | OVERWORLD_FOLLOWER_SELECTOR_UNLOAD_PENDING_FLAG
        | OVERWORLD_FOLLOWER_SELECTOR_Y_PRESS_PENDING_FLAG
        | OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG);
    return TRUE;
}

static u32 __attribute__((noinline))
OverworldFollowerSelector_ReadPhysicalKeys(void)
{
    /* Use the once-per-frame raw snapshot, before button-mode remapping. */
    return *(vu32 *)0x021D1144 & PAD_ALL_MASK;
}

/*
 * This callback runs from the field-ready main-queue SysTask, after the stock
 * FieldSystem_Control update. It only observes the global key snapshot and
 * never receives, changes, or calls player movement input.
 */
void __attribute__((section(".overworld_follower_selector_task_poll"), used))
OverworldFollowerSelector_TaskPoll(FieldSystem *fieldSystem)
{
    u32 physicalKeys = OverworldFollowerSelector_ReadPhysicalKeys();
    BOOL yDown = (physicalKeys & PAD_BUTTON_Y) != 0;
    BOOL releaseGated = OverworldFollowerSelector_IsReleaseGated();
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;

    if (!releaseGated) {
        if (yDown
            && !sOverworldFollowerSelectorYWasDown
            && !OverworldFollowerSelector_IsYPressPending()) {
            OverworldFollowerSelector_ClearYReleasePending();
            OverworldFollowerSelector_SetYPressPending();
        } else if (!yDown
            && sOverworldFollowerSelectorYWasDown) {
            /* Confirmation is press-driven. Never turn the opening Y
             * release into an implicit follower selection. */
            OverworldFollowerSelector_ClearYReleasePending();
        }
    }
    sOverworldFollowerSelectorYWasDown = (u8)yDown;

    if (!releaseGated
        && OverworldFollowerSelector_IsDirectLoaded()
        && OverworldFollowerSelector_ValidateLoaded()) {
        entry->inputFilter(fieldSystem);
    }
    if (releaseGated
        && !OverworldFollowerSelector_IsUnloadPending()
        && (physicalKeys
            & (PAD_BUTTON_A | PAD_BUTTON_SELECT | PAD_BUTTON_L
                | PAD_BUTTON_R | PAD_BUTTON_Y))
            == 0) {
        OverworldFollowerSelector_ClearReleaseGate();
    }
}

static BOOL OverworldFieldService_TryGetEncounterDataIdForMapImpl(
    u16 mapId,
    int *encounterDataId)
{
    const OverworldWildBehaviorOverlayEntry *behaviorEntry;
    const OverworldWildEncounterLookupDataEntry *lookupEntry;
    u32 i;

    if (mapId == MAP_NOTHING
        || encounterDataId == NULL
        || !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)
        || !OVERWORLD_WILD_HELPER_OVERLAY_VALIDATE(
            OVERWORLD_WILD_HELPER_OWNED_BEHAVIOR)) {
        return FALSE;
    }

    behaviorEntry = OVERWORLD_WILD_BEHAVIOR_OVERLAY_ENTRY;
    lookupEntry = OVERWORLD_WILD_LEGACY_ENCOUNTER_LOOKUP_ENTRY;
    if (behaviorEntry->magic != OVERWORLD_WILD_BEHAVIOR_OVERLAY_MAGIC
        || behaviorEntry->version != OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION
        || behaviorEntry->size != sizeof(*behaviorEntry)
        || lookupEntry->mapIds == NULL
        || lookupEntry->dataIds == NULL
        || lookupEntry->count != OWED_ENCOUNTER_AREA_COUNT) {
        return FALSE;
    }

    for (i = 0; i < lookupEntry->count; i++) {
        if (lookupEntry->mapIds[i] == mapId) {
            *encounterDataId = lookupEntry->dataIds[i];
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldFieldService_IsEnabledMap(u16 mapId)
{
    int encounterDataId;

    /*
     * Encounter lookup is the authority for enabled destinations. If helper
     * validation is unavailable, preservation fails closed and the resident
     * caller takes its destructive transition fallback. The resolver's owned-
     * behavior validation authenticates the complete helper ABI, including
     * the typed presentation command used later by the transition path.
     */
    return OverworldFieldService_TryGetEncounterDataIdForMap(
        mapId,
        &encounterDataId);
}

static BOOL OverworldFieldService_EnsureTransitionAdapters(void)
{
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        && !HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION, 0)) {
        return FALSE;
    }
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)
        && !HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_HELPER, 0)) {
        return FALSE;
    }
    if (!OverworldFollowerSelector_IsDirectLoaded()
        && !HandleLoadOverlay(OVERLAY_OVERWORLD_FOLLOWER_SELECTOR, 0)) {
        return FALSE;
    }
    return TRUE;
}

static u8 OverworldFieldService_AcknowledgementForWork(u8 work)
{
    if (work == OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE) {
        return OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED;
    }
    if (work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND) {
        return OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND;
    }
    return OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED;
}

static BOOL OverworldFieldService_ApplyTransitionWork(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    const OverworldActorTransitionCall *call)
{
    /* The resident field driver owns transition order. Mount consumes the
     * typed actor command directly before wild objects are canonicalized or
     * rebound; the wild adapter no longer proxies mount lifecycle work. */
    if (!OVERWORLD_MOUNT_OVERLAY_ENTRY->transition(call)) {
        return FALSE;
    }
    return OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->applyTransitionWork(
        fieldSystem,
        state,
        call);
}

static OverworldFieldMapHeaderChangeResult OverworldFieldService_OnMapHeaderChangedImpl(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 previousMapId,
    u16 currentMapId)
{
    OverworldActorTransitionCall call;
    OverworldActorResult result;
    OverworldActorFieldContext context;
    MapObjectMan *manager;
    BOOL preserve = TRUE;
    int exchange;

    if (fieldSystem == NULL
        || state == NULL
        || previousMapId == currentMapId
        || fieldSystem->location == NULL) {
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
    }

    if (!OverworldFieldService_EnsureTransitionAdapters()) {
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;

    if (!sOverworldFieldTransition.active) {
        preserve = fieldSystem->location->mapId == currentMapId
            && fieldSystem->playerAvatar != NULL
            && manager != NULL
            && manager->objects != NULL
            && state->mapId == previousMapId
            && state->mapObjectMan == manager
            && state->mapObjects == manager->objects
            && OverworldFieldService_IsEnabledMap(currentMapId);
        /* The typed wild adapter canonicalizes or clears each retained slot.
         * Do not repeat that object walk in the driver before the actor has
         * established the transition epoch. */
        memset(&sOverworldFieldTransition, 0, sizeof(sOverworldFieldTransition));
        /* Actor context survives this overlay being unloaded. Both 16-bit
         * generations advance together, so the packed value also preserves
         * sequence ordering when they wrap and skip zero. Keep it for retries. */
        context = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
        sOverworldFieldTransition.sequence = context;
        sOverworldFieldTransition.fieldSystem = fieldSystem;
        sOverworldFieldTransition.manager = manager;
        sOverworldFieldTransition.previousMapId = previousMapId;
        sOverworldFieldTransition.currentMapId = currentMapId;
        sOverworldFieldTransition.disposition = preserve
            ? OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE
            : OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD;
        sOverworldFieldTransition.active = TRUE;
    } else if (sOverworldFieldTransition.fieldSystem != fieldSystem
        || sOverworldFieldTransition.manager != manager
        || sOverworldFieldTransition.previousMapId != previousMapId
        || sOverworldFieldTransition.currentMapId != currentMapId) {
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
    }

    for (exchange = 0; exchange < 4; exchange++) {
        memset(&call, 0, sizeof(call));
        call.version = OVERWORLD_ACTOR_TRANSITION_CALL_VERSION;
        call.size = sizeof(call);
        call.sequence = sOverworldFieldTransition.sequence;
        call.previousFieldContext = sOverworldFieldTransition.sequence;
        call.previousMapId = sOverworldFieldTransition.previousMapId;
        call.currentMapId = sOverworldFieldTransition.currentMapId;
        call.disposition = sOverworldFieldTransition.disposition;
        call.acknowledgements = sOverworldFieldTransition.acknowledgements;
        result = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->transition(&call);
        if (result != OVERWORLD_ACTOR_RESULT_OK) {
            return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
        }
        if (call.work == OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE) {
            preserve = sOverworldFieldTransition.disposition
                == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE;
            memset(&sOverworldFieldTransition, 0, sizeof(sOverworldFieldTransition));
            sOverworldWildPlayerFrameServiceActive = TRUE;
            return preserve
                ? OVERWORLD_FIELD_MAP_HEADER_CHANGE_PRESERVED
                : OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
        }
        sOverworldFieldTransition.disposition = call.disposition;
        if (!OverworldFieldService_ApplyTransitionWork(
                fieldSystem,
                state,
                &call)) {
            if (call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
                && sOverworldFieldTransition.disposition
                    == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE) {
                sOverworldFieldTransition.disposition =
                    OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD;
                continue;
            }
            return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
        }
        sOverworldFieldTransition.acknowledgements |=
            OverworldFieldService_AcknowledgementForWork(call.work);
    }
    return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
}

__asm__(
    ".global OverworldFieldService_OnMapHeaderChangedResident\n"
    ".thumb_func\n"
    ".thumb_set OverworldFieldService_OnMapHeaderChangedResident, "
    "OverworldFieldService_OnMapHeaderChangedImpl\n");

/*
 * Preserve the old field-overlay frame pump: R, Y, or Select wakes the linked
 * overworld services, while an in-progress player-ball, selector, or mount
 * action keeps receiving frames after the button is released.
 */
static BOOL OverworldFieldService_PollFrameImpl(FieldSystem *fieldSystem)
{
    const OverworldWildSpawnsOverlayEntry *entry;

    if (fieldSystem == NULL) {
        /* A trainer task stops the idle field task that normally retries a
         * transition. The resident helper finishes it as DISCARD first. */
        if (!OverworldFieldService_FinishPendingTransition()) {
            return FALSE;
        }
        if (!OverworldFollowerSelector_ForceDirectUnload(NULL)) {
            return FALSE;
        }
        sOverworldWildPlayerFrameServiceActive = FALSE;
        return TRUE;
    }

    if (!OverworldFollowerSelector_IsDirectLoaded()) {
        if (!sOverworldWildPlayerFrameServiceActive
            && (reg_PAD_KEYINPUT
                    & (PAD_BUTTON_R | PAD_BUTTON_Y | PAD_BUTTON_SELECT))
                == (PAD_BUTTON_R | PAD_BUTTON_Y | PAD_BUTTON_SELECT)
            && !OverworldFollowerSelector_IsYPressPending()) {
            return TRUE;
        }
        if (!HandleLoadOverlay(
                OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION,
                0)) {
            return FALSE;
        }
    }

    if (OverworldFollowerSelector_IsYPressPending()
        && !OverworldFollowerSelector_IsReleaseGated()
        && OverworldFollowerSelector_IsDirectLoaded()
        && OverworldFollowerSelector_ValidateLoaded()) {
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->inputFilter(fieldSystem);
    }
    entry = OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY;
    sOverworldWildPlayerFrameServiceActive = entry->onPlayerFrame(
        fieldSystem,
        &sOverworldWildSpawnState);
    return TRUE;
}

const OverworldFieldServiceEntry gOverworldFieldServiceEntry
    __attribute__((section(".overworld_field_service_entry"), used)) = {
    OVERWORLD_FIELD_SERVICE_MAGIC,
    OverworldFieldService_OnMapHeaderChangedImpl,
    OverworldFieldService_PollFrameImpl,
    OverworldFieldService_TryGetEncounterDataIdForMapImpl,
};
