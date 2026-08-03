#include "../../include/map_teleport.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/constants/maps.h"
#include "../../include/constants/species.h"
#include "../../include/config.h"
#include "../../include/io_reg.h"
#include "../../include/map_events_internal.h"
#include "../../include/overlay.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/overworld_wild_spawns_internal.h"

volatile u8 gOverworldFollowerSelectorStateStorage
    __attribute__((section(".overworld_follower_selector_state"), used));
volatile OverworldFollowerTransitionQueueStorage
    gOverworldFollowerTransitionQueueStorage
    __attribute__((section(".overworld_follower_transition_queue"), used));
static u8 sOverworldFollowerSelectorYWasDown;

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
        && address < OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR;
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
            && !OverworldFollowerSelector_IsActiveFlagSet()
            && !OverworldFollowerSelector_IsYPressPending()) {
            OverworldFollowerSelector_ClearYReleasePending();
            OverworldFollowerSelector_SetYPressPending();
        } else if (!yDown
            && sOverworldFollowerSelectorYWasDown
            && (OverworldFollowerSelector_IsActiveFlagSet()
                || OverworldFollowerSelector_IsYPressPending())) {
            OverworldFollowerSelector_SetYReleasePending();
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
            & (PAD_BUTTON_A | PAD_BUTTON_L | PAD_BUTTON_R | PAD_BUTTON_Y))
            == 0) {
        OverworldFollowerSelector_ClearReleaseGate();
    }
}

static u8 sOverworldWildPlayerFrameServiceActive;

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

static BOOL OverworldFieldService_IsCurrentPrimaryObject(
    MapObjectMan *manager,
    const OverworldWildSpawn *spawn,
    int slot,
    u16 previousMapId)
{
    LocalMapObject *object;
    u32 objectAddress;
    u32 objectsStart;
    u32 objectsEnd;

    if (!spawn->active) {
        return TRUE;
    }
    object = spawn->object;
    if (object == NULL || manager == NULL || manager->objects == NULL) {
        return FALSE;
    }

    objectAddress = (u32)object;
    objectsStart = (u32)manager->objects;
    objectsEnd = objectsStart
        + manager->object_count * sizeof(LocalMapObject);
    return objectAddress >= objectsStart
        && objectAddress < objectsEnd
        && (objectAddress - objectsStart) % sizeof(LocalMapObject) == 0
        && spawn->mapId == previousMapId
        && (object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && (object->flags & MAPOBJECTFLAG_KEEP) != 0
        && object->id == OW_WILD_OBJECT_ID_START + slot
        && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT
        && object->unkC == previousMapId;
}

static BOOL OverworldFieldService_IsEnabledMap(u16 mapId)
{
    int encounterDataId;

    /*
     * Encounter lookup is the authority for enabled destinations. If helper
     * validation is unavailable, preservation fails closed and the resident
     * caller takes its destructive transition fallback. The resolver's owned-
     * behavior validation authenticates the complete helper ABI, including
     * normalizeThrowPresentation used later by the transition path.
     */
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)
        || !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
        return FALSE;
    }

    return OverworldFieldService_TryGetEncounterDataIdForMap(
        mapId,
        &encounterDataId);
}

static BOOL OverworldFieldService_PrepareMapHeaderChange(
    OverworldWildSpawnState *state,
    OverworldWildMapHeaderChangeMode mode)
{
    const OverworldWildSpawnsOverlayEntry *entry;

    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        || !OverworldFollowerSelector_IsDirectLoaded()) {
        return FALSE;
    }
    entry = OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY;
    if (entry->prepareMapHeaderChange == NULL) {
        return FALSE;
    }
    return entry->prepareMapHeaderChange(state, mode);
}

static void OverworldFieldService_TransitionPlayerBall(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int command)
{
    const OverworldWildHelperOverlayEntry *entry;

    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)) {
        return;
    }
    entry = OVERWORLD_WILD_HELPER_OVERLAY_ENTRY;
    if (entry->magic == OVERWORLD_WILD_HELPER_OVERLAY_MAGIC
        && entry->version == OVERWORLD_WILD_HELPER_OVERLAY_VERSION
        && entry->size == sizeof(*entry)
        && entry->normalizeThrowPresentation != NULL) {
        entry->normalizeThrowPresentation(fieldSystem, state, command);
    }
}

static void OverworldFieldService_DiscardRetainedPrimaries(
    MapObjectMan *manager,
    OverworldWildSpawnState *state)
{
    LocalMapObject *object;
    u32 objectIndex;
    int slot;
    BOOL overlayPrepared;

    overlayPrepared = OverworldFieldService_PrepareMapHeaderChange(
        state,
        OW_WILD_MAP_HEADER_CHANGE_DISCARD);
    if (!overlayPrepared) {
        OverworldFieldService_TransitionPlayerBall(
            gFieldSysPtr,
            state,
            OW_WILD_HELPER_THROW_PRESENTATION_TRANSITION_DISCARD);
    }

    /*
     * Scan the authenticated manager instead of trusting a possibly stale
     * logical pointer. The high object IDs and script ID are owned by this
     * system, so this also removes a duplicated retained presentation.
     */
    if (manager != NULL && manager->objects != NULL) {
        for (objectIndex = 0; objectIndex < manager->object_count; objectIndex++) {
            object = &manager->objects[objectIndex];
            if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
                && object->id >= OW_WILD_OBJECT_ID_START
                && object->id < OW_WILD_OBJECT_ID_START + OW_WILD_MAX_SPAWNS
                && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT
                && (object->flags & MAPOBJECTFLAG_KEEP) != 0) {
                DeleteMapObject(object);
            }
        }
    }

    if (state == NULL) {
        return;
    }
    state->battleGraceSteps = OW_WILD_FIELD_READY_DELAY_FRAMES;
    gOverworldWildFieldIdleRearmPending |=
        OW_WILD_FIELD_IDLE_REARM_PENDING
        | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
    if (!overlayPrepared) {
        /*
         * Keep encounter records until overlay 149 next runs its ordinary
         * map-change clear; that path reserves and persists loaded shinies.
         */
        for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
            state->spawns[slot].object = NULL;
        }
    } else {
        state->mapGeneration++;
        if (state->mapGeneration == 0) {
            state->mapGeneration = 1;
        }
        state->mapObjectMan = NULL;
        state->mapObjects = NULL;
        state->movementFieldSystem = NULL;
        state->pendingPersonality = 0;
    }
    state->mapId = MAP_NOTHING;
    state->pendingSlot = -1;
    state->movementQueuedBattleSlot = -1;
    state->pendingSpecies = SPECIES_NONE;
    state->pendingLevel = 0;
    state->pendingShiny = FALSE;
    state->pendingMapGeneration = 0;
    state->pendingEncounterGeneration = 0;
    state->captureTargetMask = 0;
    state->presentationRestorePending = FALSE;
}

static OverworldFieldMapHeaderChangeResult OverworldFieldService_OnMapHeaderChangedImpl(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 previousMapId,
    u16 currentMapId)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    LocalMapObject *object;
    MapObjectMan *manager;
    u32 objectIndex;
    int slot;

    if (fieldSystem == NULL
        || state == NULL
        || previousMapId == currentMapId
        || fieldSystem->location == NULL) {
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
    }

    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (fieldSystem->location->mapId != currentMapId
        || fieldSystem->playerAvatar == NULL
        || !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        || OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->prepareMapHeaderChange == NULL
        || manager == NULL
        || manager->objects == NULL
        || state->mapId != previousMapId
        || state->mapObjectMan != manager
        || state->mapObjects != manager->objects) {
        OverworldFieldService_DiscardRetainedPrimaries(
            manager,
            state);
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
    }

    if (!OverworldFieldService_IsEnabledMap(currentMapId)) {
        OverworldFieldService_DiscardRetainedPrimaries(
            manager,
            state);
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
    }
    helperEntry = OVERWORLD_WILD_HELPER_OVERLAY_ENTRY;

    for (objectIndex = 0; objectIndex < manager->object_count; objectIndex++) {
        object = &manager->objects[objectIndex];
        if ((object->flags & (MAPOBJECTFLAG_ACTIVE | MAPOBJECTFLAG_KEEP))
                != (MAPOBJECTFLAG_ACTIVE | MAPOBJECTFLAG_KEEP)
            || object->id < OW_WILD_OBJECT_ID_START
            || object->id >= OW_WILD_OBJECT_ID_START + OW_WILD_MAX_SPAWNS
            || object->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
            continue;
        }
        slot = object->id - OW_WILD_OBJECT_ID_START;
        if (!state->spawns[slot].active
            || state->spawns[slot].object != object) {
            OverworldFieldService_DiscardRetainedPrimaries(
                manager,
                state);
            return OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
        }
    }

    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        if (!OverworldFieldService_IsCurrentPrimaryObject(
                manager,
                &state->spawns[slot],
                slot,
                previousMapId)) {
            OverworldFieldService_DiscardRetainedPrimaries(
                manager,
                state);
            return OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
        }
    }

    /* The overlay owns transient task/effect cleanup and far-sample reset. */
    if (!OverworldFieldService_PrepareMapHeaderChange(
            state,
            OW_WILD_MAP_HEADER_CHANGE_PRESERVE)) {
        OverworldFieldService_DiscardRetainedPrimaries(manager, state);
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
    }

    state->mapGeneration++;
    if (state->mapGeneration == 0) {
        state->mapGeneration = 1;
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        OverworldWildSpawn *spawn = &state->spawns[slot];

        if (!spawn->active) {
            continue;
        }
        spawn->mapId = currentMapId;
        spawn->object->unkC = currentMapId;
    }

    state->mapId = currentMapId;
    state->mapObjectMan = manager;
    state->mapObjects = manager->objects;
    state->movementFieldSystem = fieldSystem;
    state->pendingSlot = -1;
    state->movementQueuedBattleSlot = -1;
    state->pendingMapGeneration = 0;
    state->pendingEncounterGeneration = 0;
    state->battleGraceSteps = 0;
    state->presentationRestorePending = FALSE;
    if (!OverworldFieldService_PrepareMapHeaderChange(
            state,
            OW_WILD_MAP_HEADER_CHANGE_CANONICALIZE)) {
        OverworldFieldService_DiscardRetainedPrimaries(manager, state);
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED;
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        if (!state->spawns[slot].active) {
            continue;
        }
        helperEntry->normalizeThrowPresentation(fieldSystem, state, slot);
    }
    helperEntry->normalizeThrowPresentation(
        fieldSystem,
        state,
        OW_WILD_HELPER_THROW_PRESENTATION_TRANSITION_RESUME);
    sOverworldWildPlayerFrameServiceActive = TRUE;
    return OVERWORLD_FIELD_MAP_HEADER_CHANGE_PRESERVED;
}

/*
 * Preserve the old field-overlay frame pump: R or Y wakes the linked
 * overworld services, while an in-progress player-ball or selector action
 * keeps receiving frames after the button is released.
 */
static BOOL OverworldFieldService_PollFrameImpl(FieldSystem *fieldSystem)
{
    const OverworldWildSpawnsOverlayEntry *entry;

    if (fieldSystem == NULL) {
        if (!OverworldFollowerSelector_ForceDirectUnload(NULL)) {
            return FALSE;
        }
        sOverworldWildPlayerFrameServiceActive = FALSE;
        return TRUE;
    }

    if (IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
        if (OverworldFollowerSelector_IsDirectLoaded()) {
            goto runFieldService;
        }
    } else if (!sOverworldWildPlayerFrameServiceActive
        && (reg_PAD_KEYINPUT & (PAD_BUTTON_R | PAD_BUTTON_Y))
            == (PAD_BUTTON_R | PAD_BUTTON_Y)
        && !OverworldFollowerSelector_IsYPressPending()) {
        return TRUE;
    }
    (void)HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION, 0);
    if (OverworldFollowerSelector_IsYPressPending()
        && !OverworldFollowerSelector_IsReleaseGated()
        && OverworldFollowerSelector_IsDirectLoaded()
        && OverworldFollowerSelector_ValidateLoaded()) {
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->inputFilter(fieldSystem);
    }
    return TRUE;

runFieldService:
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
