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

typedef void (*FieldInputUpdateFunc)(
    void *fieldInput,
    FieldSystem *fieldSystem,
    u16 newKeys,
    u16 heldKeys);

#define FIELD_INPUT_UPDATE ((FieldInputUpdateFunc)(0x021E6928 | 1))
#define FIELD_SYSTEM_LAST_TOUCH_MENU_INPUT_OFFSET 0xD0

static u8 sOverworldFollowerSelectorDirectLoaded;
volatile u8 gOverworldFollowerSelectorStateStorage
    __attribute__((section(".overworld_follower_selector_state"), used));

static void OverworldFollowerSelector_DiscardTouchMenuInput(
    FieldSystem *fieldSystem)
{
    if (fieldSystem != NULL) {
        *(u16 *)((u8 *)fieldSystem
            + FIELD_SYSTEM_LAST_TOUCH_MENU_INPUT_OFFSET) = 0;
    }
}

static BOOL OverworldFollowerSelector_ForceDirectUnload(
    FieldSystem *fieldSystem)
{
    if (sOverworldFollowerSelectorDirectLoaded
        && OverworldFollowerSelector_CanCallInputCancel()) {
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->inputCancel(fieldSystem);
    }
    *(u32 *)OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR = 0;
    if (sOverworldFollowerSelectorDirectLoaded
        && !FS_UnloadOverlay(0, OVERLAY_OVERWORLD_FOLLOWER_SELECTOR)) {
        /* Keep ownership published so no caller can load over live code. */
        OverworldFollowerSelector_SetReleaseGate();
        return FALSE;
    }
    sOverworldFollowerSelectorDirectLoaded = FALSE;
    OverworldFollowerSelector_ClearDirectLoaded();
    return TRUE;
}

static BOOL OverworldFollowerSelector_TryDirectLoad(void)
{
    if (sOverworldFollowerSelectorDirectLoaded) {
        if (OverworldFollowerSelector_Validate()) {
            return TRUE;
        }
        (void)OverworldFollowerSelector_ForceDirectUnload(NULL);
        return FALSE;
    }
    OverworldFollowerSelector_ClearDirectLoaded();

    *(u32 *)OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR = 0;
    if (!LoadOverlayNormal(0, OVERLAY_OVERWORLD_FOLLOWER_SELECTOR)) {
        return FALSE;
    }
    sOverworldFollowerSelectorDirectLoaded = TRUE;
    OverworldFollowerSelector_SetDirectLoaded();
    if (!OverworldFollowerSelector_Validate()) {
        (void)OverworldFollowerSelector_ForceDirectUnload(NULL);
        return FALSE;
    }
    return TRUE;
}

/*
 * FieldInput_Update consumes Y as the registered-item shortcut before any of
 * the resident overworld tasks run.  This wrapper is therefore the selector's
 * only input-arbitration point: overlay 152 decides whether Y is still a tap
 * or has become a hold, then the filtered keys continue through stock field
 * input unchanged.
 *
 * Overlay 131 is linked to the field overlay, so this entry is always present
 * while the patched FieldSystem_Control call site can execute.  The selector
 * overlay remains optional. A cold-load failure leaves native Y intact; a
 * loaded-but-invalid ABI fails closed, unloads immediately, and waits for all
 * owned buttons to be released before field input can resume.
 */
void __attribute__((section(".overworld_follower_selector_input_hook"), used))
OverworldFollowerSelector_FieldInputUpdateHook(
    void *fieldInput,
    FieldSystem *fieldSystem,
    u16 newKeys,
    u16 heldKeys)
{
    if (OverworldFollowerSelector_IsReleaseGated()) {
        BOOL allReleased = heldKeys == 0
            && (PAD_Read() & (PAD_BUTTON_L | PAD_BUTTON_R)) == 0;
        BOOL selectorUnloaded =
            OverworldFollowerSelector_ForceDirectUnload(fieldSystem);

        /* Consume the release frame too; no held input reaches resumed field. */
        newKeys = 0;
        heldKeys = 0;
        OverworldFollowerSelector_DiscardTouchMenuInput(fieldSystem);
        if (allReleased && selectorUnloaded) {
            OverworldFollowerSelector_ClearReleaseGate();
        }
        FIELD_INPUT_UPDATE(fieldInput, fieldSystem, newKeys, heldKeys);
        return;
    }
    if ((newKeys & PAD_BUTTON_Y) != 0
        && !sOverworldFollowerSelectorDirectLoaded) {
        (void)OverworldFollowerSelector_TryDirectLoad();
    }
    if (sOverworldFollowerSelectorDirectLoaded) {
        if (!OverworldFollowerSelector_Validate()) {
            newKeys = 0;
            heldKeys = 0;
            OverworldFollowerSelector_SetReleaseGate();
            OverworldFollowerSelector_DiscardTouchMenuInput(fieldSystem);
            (void)OverworldFollowerSelector_ForceDirectUnload(fieldSystem);
            FIELD_INPUT_UPDATE(fieldInput, fieldSystem, newKeys, heldKeys);
            return;
        }
        OverworldFollowerSelector_InputFilter(
            fieldSystem,
            &newKeys,
            &heldKeys);
        if (!OverworldFollowerSelector_IsActive()) {
            /* The call has returned to overlay 131, so 152 is safe to free. */
            (void)OverworldFollowerSelector_ForceDirectUnload(fieldSystem);
        }
    }
    FIELD_INPUT_UPDATE(fieldInput, fieldSystem, newKeys, heldKeys);
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
        && spawn->objectId == OW_WILD_OBJECT_ID_START + slot
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

    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
        return FALSE;
    }
    entry = OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY;
    if (entry->prepareMapHeaderChange == NULL) {
        return FALSE;
    }
    entry->prepareMapHeaderChange(state, mode);
    return TRUE;
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
        state->mapId = MAP_NOTHING;
        state->captureTargetMask = 0;
        state->pendingSlot = -1;
        state->movementQueuedBattleSlot = -1;
        state->pendingSpecies = SPECIES_NONE;
        state->pendingLevel = 0;
        state->pendingShiny = FALSE;
        state->pendingMapGeneration = 0;
        state->pendingEncounterGeneration = 0;
        state->presentationRestorePending = FALSE;
        return;
    }

    memset(state->spawns, 0, sizeof(state->spawns));
    state->mapGeneration++;
    if (state->mapGeneration == 0) {
        state->mapGeneration = 1;
    }
    state->mapId = MAP_NOTHING;
    state->mapObjectMan = NULL;
    state->mapObjects = NULL;
    state->movementFieldSystem = NULL;
    state->pendingSlot = -1;
    state->movementQueuedBattleSlot = -1;
    state->pendingPersonality = 0;
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
    (void)OverworldFieldService_PrepareMapHeaderChange(
        state,
        OW_WILD_MAP_HEADER_CHANGE_PRESERVE);

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
    (void)OverworldFieldService_PrepareMapHeaderChange(
        state,
        OW_WILD_MAP_HEADER_CHANGE_CANONICALIZE);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        if (!state->spawns[slot].active) {
            continue;
        }
        if (state->movementBehaviorClasses[slot]
            == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
            state->movementBehaviorClasses[slot] =
                OW_WILD_BEHAVIOR_CLASS_DEFAULT;
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
 * Preserve the old field-overlay frame pump: the R-button fast path avoids
 * loading overlay 149 until it is needed, while an in-progress player-ball
 * action keeps receiving frames after R is released.
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

    if (!sOverworldWildPlayerFrameServiceActive
        && (reg_PAD_KEYINPUT & PAD_BUTTON_R) != 0) {
        return TRUE;
    }
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
        (void)HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION, 0);
        return TRUE;
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
