#include "../../include/overworld_follower_selector.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/constants/species.h"
#include "../../include/overlay.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/task.h"

#define FOLLOWER_SELECTOR_HOLD_FRAMES 15
#define FOLLOWER_SELECTOR_TASK_PRIORITY 89
#define FIELD_SYSTEM_LAST_TOUCH_MENU_INPUT_OFFSET 0xD0

typedef BOOL (*FieldSystemIsPlayerMovementAllowedFunc)(FieldSystem *fieldSystem);

#define FIELD_SYSTEM_IS_PLAYER_MOVEMENT_ALLOWED \
    ((FieldSystemIsPlayerMovementAllowedFunc)(0x0203E13C | 1))

u8 OverworldWildSpawns_GetSelectedFollowerPartySlot(FieldSystem *fieldSystem)
{
    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    }
    return SaveMisc_GetCustomFollowerPartySlot(
        Sav2_Misc_get(fieldSystem->savedata));
}

BOOL OverworldWildSpawns_IsFollowerPartySlotEligible(
    FieldSystem *fieldSystem,
    u8 partySlot)
{
    struct Party *party;
    struct PartyPokemon *pokemon;

    if (fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || partySlot >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT) {
        return FALSE;
    }
    party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party == NULL || partySlot >= party->count) {
        return FALSE;
    }
    pokemon = Party_GetMonByIndex(party, partySlot);
    return pokemon != NULL
        && GetMonData(pokemon, MON_DATA_SPECIES, NULL) != SPECIES_NONE
        && GetMonData(pokemon, MON_DATA_IS_EGG, NULL) == FALSE
        && GetMonData(pokemon, MON_DATA_LEVEL, NULL) != 0
        && GetMonData(pokemon, MON_DATA_HP, NULL) != 0;
}

u8 OverworldWildSpawns_GetEligibleFollowerPartyMask(FieldSystem *fieldSystem)
{
    u8 mask = 0;
    u8 partySlot;

    for (partySlot = 0;
         partySlot < CUSTOM_FOLLOWER_PARTY_SLOT_COUNT;
         partySlot++) {
        if (OverworldWildSpawns_IsFollowerPartySlotEligible(
                fieldSystem,
                partySlot)) {
            mask |= (u8)(1 << partySlot);
        }
    }
    return mask;
}

BOOL OverworldWildSpawns_SelectFollowerPartySlot(
    FieldSystem *fieldSystem,
    u8 partySlot)
{
    if (fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || (partySlot != CUSTOM_FOLLOWER_PARTY_SLOT_NONE
            && !OverworldWildSpawns_IsFollowerPartySlotEligible(
                fieldSystem,
                partySlot))) {
        return FALSE;
    }
    if (partySlot != CUSTOM_FOLLOWER_PARTY_SLOT_NONE
        && sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT].active
        && sOverworldWildSpawnState.activeFollowerPartySlot == partySlot) {
        partySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    }
    SaveMisc_SetCustomFollowerPartySlot(
        Sav2_Misc_get(fieldSystem->savedata),
        partySlot);
    sOverworldWildSpawnState.spawnCooldown = 0;
    gOverworldWildFieldIdleRearmPending |=
        OW_WILD_FIELD_IDLE_REARM_PENDING
        | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
    return TRUE;
}

typedef enum OverworldFollowerSelectorInputState {
    FOLLOWER_SELECTOR_INPUT_IDLE = 0,
    FOLLOWER_SELECTOR_INPUT_PENDING,
    FOLLOWER_SELECTOR_INPUT_TAP_ONLY,
    FOLLOWER_SELECTOR_INPUT_VISIBLE,
} OverworldFollowerSelectorInputState;

static FieldSystem *sFollowerSelectorFieldSystem;
static SysTask *sFollowerSelectorTask;
static u16 sFollowerSelectorMapId;
static u16 sFollowerSelectorPreviousPhysicalKeys;
static u8 sFollowerSelectorHoldFrames;
static u8 sFollowerSelectorHighlightedSlot;
static u8 sFollowerSelectorInputState;

static void OverworldFollowerSelectorInput_DiscardTouchMenuInput(
    FieldSystem *fieldSystem)
{
    if (fieldSystem != NULL) {
        /* Touch requests made while selector-owned are intentionally lost. */
        *(u16 *)((u8 *)fieldSystem
            + FIELD_SYSTEM_LAST_TOUCH_MENU_INPUT_OFFSET) = 0;
    }
}

static void OverworldFollowerSelectorInput_ResetState(void)
{
    sFollowerSelectorFieldSystem = NULL;
    sFollowerSelectorTask = NULL;
    sFollowerSelectorMapId = 0;
    sFollowerSelectorPreviousPhysicalKeys = 0;
    sFollowerSelectorHoldFrames = 0;
    sFollowerSelectorHighlightedSlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_IDLE;
}

static BOOL OverworldFollowerSelectorInput_IsFieldContextCurrent(
    FieldSystem *fieldSystem)
{
    return fieldSystem != NULL
        && fieldSystem == gFieldSysPtr
        && fieldSystem->location != NULL
        && fieldSystem->taskman == NULL
        && FIELD_SYSTEM_IS_PLAYER_MOVEMENT_ALLOWED(fieldSystem)
        && (u16)fieldSystem->location->mapId == sFollowerSelectorMapId;
}

static BOOL OverworldFollowerSelectorInput_IsPlayerBallActive(void)
{
    const OverworldWildHelperOverlayEntry *entry;

    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)) {
        return FALSE;
    }
    entry = OVERWORLD_WILD_HELPER_OVERLAY_ENTRY;
    return entry->magic == OVERWORLD_WILD_HELPER_OVERLAY_MAGIC
        && entry->version == OVERWORLD_WILD_HELPER_OVERLAY_VERSION
        && entry->size == sizeof(*entry)
        && entry->getPlayerBallProjectileObject != NULL
        && entry->getPlayerBallProjectileObject() != NULL;
}

static u8 OverworldFollowerSelectorInput_FirstEligibleSlot(u8 eligibleMask)
{
    u8 slot;

    for (slot = 0; slot < CUSTOM_FOLLOWER_PARTY_SLOT_COUNT; slot++) {
        if ((eligibleMask & (1 << slot)) != 0) {
            return slot;
        }
    }
    return CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
}

static u8 OverworldFollowerSelectorInput_CycleSlot(
    u8 eligibleMask,
    u8 currentSlot,
    int direction)
{
    int step;
    int slot = currentSlot;

    for (step = 0; step < CUSTOM_FOLLOWER_PARTY_SLOT_COUNT; step++) {
        slot += direction;
        if (slot < 0) {
            slot = CUSTOM_FOLLOWER_PARTY_SLOT_COUNT - 1;
        } else if (slot >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT) {
            slot = 0;
        }
        if ((eligibleMask & (1 << slot)) != 0) {
            return (u8)slot;
        }
    }
    return currentSlot;
}

static void OverworldFollowerSelectorInput_Close(SysTask *task)
{
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_VISIBLE
        || OverworldFollowerSelectorUI_IsOpen()) {
        OverworldFollowerSelectorUI_Close();
    }
    OverworldFollowerSelectorInput_ResetState();
    if (task != NULL) {
        DestroySysTask(task);
    }
}

static void OverworldFollowerSelectorInput_Task(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;

    if (task != sFollowerSelectorTask
        || fieldSystem != sFollowerSelectorFieldSystem
        || !OverworldFollowerSelectorInput_IsFieldContextCurrent(fieldSystem)) {
        OverworldFollowerSelector_SetReleaseGate();
        if (fieldSystem == gFieldSysPtr) {
            OverworldFollowerSelectorInput_DiscardTouchMenuInput(fieldSystem);
        }
        OverworldFollowerSelectorInput_Close(task);
        return;
    }
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_VISIBLE) {
        OverworldFollowerSelectorUI_Update();
    }
}

static BOOL OverworldFollowerSelectorInput_Begin(FieldSystem *fieldSystem)
{
    u8 eligibleMask;
    u8 selectedSlot;

    if (sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_IDLE
        || fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || fieldSystem->taskman != NULL
        || !FIELD_SYSTEM_IS_PLAYER_MOVEMENT_ALLOWED(fieldSystem)
        || OverworldFollowerSelectorInput_IsPlayerBallActive()) {
        return FALSE;
    }
    eligibleMask = OverworldWildSpawns_GetEligibleFollowerPartyMask(
        fieldSystem);
    if (eligibleMask == 0) {
        return FALSE;
    }
    selectedSlot = OverworldWildSpawns_GetSelectedFollowerPartySlot(
        fieldSystem);
    if (selectedSlot >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT
        || (eligibleMask & (1 << selectedSlot)) == 0) {
        selectedSlot = OverworldFollowerSelectorInput_FirstEligibleSlot(
            eligibleMask);
    }
    sFollowerSelectorTask = CreateSysTask(
        OverworldFollowerSelectorInput_Task,
        fieldSystem,
        FOLLOWER_SELECTOR_TASK_PRIORITY);
    if (sFollowerSelectorTask == NULL) {
        return FALSE;
    }
    sFollowerSelectorFieldSystem = fieldSystem;
    sFollowerSelectorMapId = (u16)fieldSystem->location->mapId;
    sFollowerSelectorPreviousPhysicalKeys = PAD_Read();
    sFollowerSelectorHoldFrames = 0;
    sFollowerSelectorHighlightedSlot = selectedSlot;
    sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_PENDING;
    return TRUE;
}

void OverworldFollowerSelectorInput_Filter(
    FieldSystem *fieldSystem,
    u16 *newKeys,
    u16 *heldKeys)
{
    u16 physicalKeys;
    u16 physicalNewKeys;
    u16 directionalNewKeys;
    u16 directionalHeldKeys;
    u8 eligibleMask;
    u8 nextSlot;
    BOOL yHeld;

    if (newKeys == NULL || heldKeys == NULL) {
        return;
    }
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_IDLE) {
        if ((*newKeys & PAD_BUTTON_Y) == 0
            || !OverworldFollowerSelectorInput_Begin(fieldSystem)) {
            return;
        }
    }
    if (fieldSystem != sFollowerSelectorFieldSystem
        || !OverworldFollowerSelectorInput_IsFieldContextCurrent(fieldSystem)) {
        /* Fail closed on the invalid frame and through the following release. */
        *newKeys = 0;
        *heldKeys = 0;
        OverworldFollowerSelectorInput_DiscardTouchMenuInput(fieldSystem);
        OverworldFollowerSelector_SetReleaseGate();
        OverworldFollowerSelectorInput_Cancel(fieldSystem);
        return;
    }

    directionalNewKeys = *newKeys & PAD_PLUS_KEY_MASK;
    directionalHeldKeys = *heldKeys & PAD_PLUS_KEY_MASK;
    yHeld = (*heldKeys & PAD_BUTTON_Y) != 0;
    /*
     * Pending/tap states own field input completely.  Once the selector is
     * visible, only directional input is restored below so stock field input
     * remains responsible for collision and player movement.  Y, shoulders,
     * actions, menus, and touch remain selector-owned or suppressed.
     */
    *newKeys = 0;
    *heldKeys = 0;
    OverworldFollowerSelectorInput_DiscardTouchMenuInput(fieldSystem);
    physicalKeys = PAD_Read();
    physicalNewKeys = physicalKeys & ~sFollowerSelectorPreviousPhysicalKeys;

    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_PENDING
        || sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_TAP_ONLY) {
        if (!yHeld) {
            /* Recreate the one-frame logical Y press expected by stock input. */
            *newKeys |= PAD_BUTTON_Y;
            OverworldFollowerSelector_SetReleaseGate();
            OverworldFollowerSelectorInput_Close(sFollowerSelectorTask);
            return;
        }
        if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_TAP_ONLY) {
            sFollowerSelectorPreviousPhysicalKeys = physicalKeys;
            return;
        }
        if (sFollowerSelectorHoldFrames < FOLLOWER_SELECTOR_HOLD_FRAMES) {
            sFollowerSelectorHoldFrames++;
        }
        if (sFollowerSelectorHoldFrames >= FOLLOWER_SELECTOR_HOLD_FRAMES) {
            if (!OverworldFollowerSelectorUI_Open(
                    fieldSystem,
                    sFollowerSelectorHighlightedSlot)) {
                /* Keep owning Y until release, then degrade to a normal tap. */
                sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_TAP_ONLY;
            } else {
                sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_VISIBLE;
            }
        }
        sFollowerSelectorPreviousPhysicalKeys = physicalKeys;
        return;
    }

    if (!yHeld) {
        (void)OverworldWildSpawns_SelectFollowerPartySlot(
            fieldSystem,
            sFollowerSelectorHighlightedSlot);
        /* Keep a still-held shoulder from leaking into the Player Ball. */
        OverworldFollowerSelector_SetReleaseGate();
        OverworldFollowerSelectorInput_Close(sFollowerSelectorTask);
        return;
    }

    eligibleMask = OverworldWildSpawns_GetEligibleFollowerPartyMask(
        fieldSystem);
    if (eligibleMask == 0) {
        OverworldFollowerSelectorInput_Cancel(fieldSystem);
        return;
    }
    if ((eligibleMask & (1 << sFollowerSelectorHighlightedSlot)) == 0) {
        nextSlot = OverworldFollowerSelectorInput_FirstEligibleSlot(eligibleMask);
    } else if ((physicalNewKeys & (PAD_BUTTON_L | PAD_BUTTON_R))
            == PAD_BUTTON_L) {
        nextSlot = OverworldFollowerSelectorInput_CycleSlot(
            eligibleMask,
            sFollowerSelectorHighlightedSlot,
            -1);
    } else if ((physicalNewKeys & (PAD_BUTTON_L | PAD_BUTTON_R))
            == PAD_BUTTON_R) {
        nextSlot = OverworldFollowerSelectorInput_CycleSlot(
            eligibleMask,
            sFollowerSelectorHighlightedSlot,
            1);
    } else {
        nextSlot = sFollowerSelectorHighlightedSlot;
    }
    if (nextSlot != sFollowerSelectorHighlightedSlot) {
        sFollowerSelectorHighlightedSlot = nextSlot;
        OverworldFollowerSelectorUI_SetSelection(nextSlot);
    }
    sFollowerSelectorPreviousPhysicalKeys = physicalKeys;
    *newKeys = directionalNewKeys;
    *heldKeys = directionalHeldKeys;
}

void OverworldFollowerSelectorInput_Cancel(FieldSystem *fieldSystem)
{
    FieldSystem *ownedFieldSystem = sFollowerSelectorFieldSystem;

    if (sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_IDLE
        || sFollowerSelectorTask != NULL
        || OverworldFollowerSelectorUI_IsOpen()) {
        OverworldFollowerSelector_SetReleaseGate();
        if (fieldSystem == NULL) {
            fieldSystem = ownedFieldSystem;
        }
        if (fieldSystem == gFieldSysPtr) {
            OverworldFollowerSelectorInput_DiscardTouchMenuInput(fieldSystem);
        }
        OverworldFollowerSelectorInput_Close(sFollowerSelectorTask);
    }
}

BOOL OverworldFollowerSelectorInput_IsActive(void)
{
    return sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_IDLE;
}
