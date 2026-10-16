#include "../include/overworld_wild_spawns_internal.h"
#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/buttons.h"
#include "../include/constants/species.h"
#include "../include/battle.h"
#include "../include/map_teleport.h"
#include "../include/overlay.h"
#include "../include/overworld_follower_selector.h"
#include "../include/overworld_combat.h"
#include "../include/script.h"
#include "../include/task.h"

#define OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE 0x01
#define OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE 0x02
#define OW_WILD_BATTLE_FLAG_HP_TRACKING_ACTIVE 0x04
#define OW_WILD_HP_SLOT_COUNT 10
#define OW_WILD_FIELD_READY_INITIAL_SPAWN 0
#define OW_WILD_DISABLE_PLAYER_STEP_HOOK 0
#define OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY 0
OverworldWildSpawnState sOverworldWildSpawnState = {
    .mapId = MAP_NOTHING,
    .pendingSlot = -1,
    .movementQueuedBattleSlot = -1,
    .activeFollowerPartySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE,
};

static u32 sBattleHpPersonality;
static u32 sBattlePersonalityOverrideValue;
static FieldSystem *sFieldReadyTaskFieldSystem;
static u16 sFieldReadyTaskMapId;
OverworldWildResidentData gOverworldWildResidentData;

__asm__(
    ".global gOverworldWildFieldIdleRearmPending\n"
    ".set gOverworldWildFieldIdleRearmPending, gOverworldWildResidentData\n"
    ".type gOverworldWildFieldIdleRearmPending, %object\n"
    ".global gOverworldWildBattleFlags\n"
    ".set gOverworldWildBattleFlags, gOverworldWildResidentData + 1\n"
    ".type gOverworldWildBattleFlags, %object\n"
    ".size gOverworldWildBattleFlags, 1\n"
    ".global gOverworldWildSavedHp\n"
    ".set gOverworldWildSavedHp, gOverworldWildResidentData + 2\n"
    ".type gOverworldWildSavedHp, %object\n"
    ".size gOverworldWildSavedHp, 20\n");
#define gOverworldWildFieldIdleRearmPending \
    (gOverworldWildResidentData.pendingFlags)
#define gOverworldWildBattleFlags (gOverworldWildResidentData.battleFlags)
#define gOverworldWildSavedHp (gOverworldWildResidentData.savedHp)
extern u32 space_for_setmondata;
extern void OverworldFollowerSelectorTaskPollEntry(FieldSystem *fieldSystem);
__asm__(
    ".global OverworldFollowerSelectorTaskPollEntry\n"
    ".type OverworldFollowerSelectorTaskPollEntry, %function\n"
    ".set OverworldFollowerSelectorTaskPollEntry, 0x023BD4A1\n");

static const OverworldWildSpawnsOverlayEntry *OverworldWildSpawns_GetOverlayEntry(BOOL deferColdLoad);

static void OverworldWildSpawns_CaptureMountToggle(FieldSystem *fieldSystem)
{
    /* Match the Y selector's raw field-frame keys, before button remapping. */
    u8 togglePressed = (*(vu32 *)0x021D1148 >> 2) & 1;

    OVERWORLD_MOUNT_TOGGLE_DOWN = (*(vu32 *)0x021D1144 >> 2) & 1;
    if (togglePressed
        && !OverworldFollowerSelector_IsActiveFlagSet()) {
        OVERWORLD_MOUNT_TOGGLE_PENDING =
            OVERWORLD_MOUNT_TOGGLE_RETRY_FRAMES;
    }
}

static void OverworldWildSpawns_FieldReadyTask(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;

    if (fieldSystem != gFieldSysPtr) {
        if (sFieldReadyTaskFieldSystem == fieldSystem) {
            sFieldReadyTaskFieldSystem = NULL;
        }
        DestroySysTask(task);
        return;
    }

    /* This task can temporarily stop before the extension frame service runs.
     * Keep a short Select press from being lost in that gap after a Hop. */
    OverworldWildSpawns_CaptureMountToggle(fieldSystem);
    /* Keep the packaged overlay-129 call at its fixed cross-overlay address. */
    __asm__("nop\n nop\n nop\n nop\n");

    if (!sub_0203DF8C(fieldSystem)) {
        gOverworldWildFieldIdleRearmPending |=
            OW_WILD_FIELD_IDLE_REARM_PENDING
            | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        return;
    }

    if (fieldSystem->taskman != NULL) {
        if (IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
            OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->onFieldBusy(
                fieldSystem,
                &sOverworldWildSpawnState,
                &gOverworldWildResidentData);
        } else {
            gOverworldWildFieldIdleRearmPending |=
                OW_WILD_FIELD_IDLE_REARM_PENDING
                | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        }
        return;
    }
    if (sFieldReadyTaskMapId != (u16)fieldSystem->location->mapId) {
        OverworldFieldMapHeaderChangeResult transitionResult;
        u16 previousMapId = sFieldReadyTaskMapId;
        u16 currentMapId = (u16)fieldSystem->location->mapId;

        transitionResult = OverworldFieldService_OnMapHeaderChanged(
            fieldSystem,
            &sOverworldWildSpawnState,
            previousMapId,
            currentMapId);
        if (transitionResult == OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE) {
            /*
             * Do not abandon KEEP actors while overlay 131 is cold. Keeping
             * the old task map id makes this transition retry before any
             * player-step processing can observe a half-migrated context.
             */
            gOverworldWildFieldIdleRearmPending |=
                OW_WILD_FIELD_IDLE_REARM_PENDING
                | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
            return;
        }

        sFieldReadyTaskMapId = currentMapId;
        return;
    }
    /* Overlay 131 is guaranteed resident after the map-service guard above. */
    /* Refresh stale map state before any input-driven presentation runs. */
    if (gOverworldWildFieldIdleRearmPending != 0) {
        if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
            (void)HandleLoadOverlay(
                OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION,
                0);
            return;
        }
        if ((OVERWORLD_FOLLOWER_SELECTOR_STATE
                & OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG) == 0
            || OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->validate == NULL
            || !OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->validate()) {
            return;
        }
        (void)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->onPlayerStep(
            fieldSystem,
            &sOverworldWildSpawnState,
            &gOverworldWildResidentData);
        if (gOverworldWildFieldIdleRearmPending != 0) {
            return;
        }
    }
    /* Read the current frame's Y edge only after map state is current. */
    OverworldFollowerSelectorTaskPollEntry(fieldSystem);
    /* The field services now see the current map and object manager. */
    OverworldFieldService_PollFrame(fieldSystem);
#if OW_WILD_FIELD_READY_INITIAL_SPAWN
    OverworldWildSpawns_OnPlayerStep(fieldSystem);
#endif
    /*
     * Keep the resident helper addresses used by overlay 155 stable. The
     * remaining fence accounts for the resident Select-edge latch above.
     */
    __asm__("");
}

static const OverworldWildSpawnsOverlayEntry *OverworldWildSpawns_GetOverlayEntry(BOOL deferColdLoad)
{
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)) {
        if (!HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION, 0)
            || deferColdLoad) {
            return NULL;
        }
    }

    return OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY;
}

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem)
{
#if OW_WILD_DISABLE_PLAYER_STEP_HOOK
    (void)fieldSystem;
    return FALSE;
#else
    const OverworldWildSpawnsOverlayEntry *entry;

    if (sFieldReadyTaskFieldSystem != fieldSystem) {
        gOverworldWildFieldIdleRearmPending |=
            OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        OverworldWildSpawns_OnFieldSystemReady(fieldSystem);
        return FALSE;
    }
    if (fieldSystem->taskman != NULL
        || sFieldReadyTaskMapId != (u16)fieldSystem->location->mapId
        || gOverworldWildFieldIdleRearmPending != 0) {
        return FALSE;
    }
    entry = OverworldWildSpawns_GetOverlayEntry(TRUE);
    if (entry == NULL) {
        return FALSE;
    }

#if OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY
    (void)fieldSystem;
    return FALSE;
#endif

    return entry->onPlayerStep(
        fieldSystem,
        &sOverworldWildSpawnState,
        &gOverworldWildResidentData);
#endif
}

void OverworldWildSpawns_OnFieldSystemReady(FieldSystem *fieldSystem)
{
#if OW_WILD_DISABLE_PLAYER_STEP_HOOK
    (void)fieldSystem;
#else
    if (sFieldReadyTaskFieldSystem != fieldSystem) {
        SysTask *task = CreateSysTask(
            OverworldWildSpawns_FieldReadyTask,
            fieldSystem,
            OW_WILD_FIELD_READY_DELAY_FRAMES);

        if (task != NULL) {
            sFieldReadyTaskMapId = 0;
            sFieldReadyTaskFieldSystem = fieldSystem;
        }
    }
#endif
}

u32 OverworldWildSpawns_PopPendingBattle(FieldSystem *fieldSystem, LocalMapObject *talkedObject)
{
    const OverworldWildSpawnsOverlayEntry *entry;
    u16 pendingSpecies;
    u32 pendingBattle;

    if (sOverworldWildSpawnState.pendingSpecies == SPECIES_NONE
        || sOverworldWildSpawnState.pendingLevel == 0) {
        entry = OverworldWildSpawns_GetOverlayEntry(FALSE);
        if (entry == NULL
            || !entry->tryPrimeBattleFromTalk(
                fieldSystem,
                &sOverworldWildSpawnState,
                talkedObject)) {
            return 0;
        }
    }

    pendingSpecies = sOverworldWildSpawnState.pendingSpecies;
    pendingBattle = (pendingSpecies & OW_WILD_SPECIES_MASK)
        | (sOverworldWildSpawnState.pendingLevel << OVERWORLD_WILD_PENDING_BATTLE_LEVEL_SHIFT)
        | (sOverworldWildSpawnState.pendingShiny << OVERWORLD_WILD_PENDING_BATTLE_SHINY_SHIFT);

    space_for_setmondata = pendingSpecies >> OW_WILD_FORM_SHIFT;
    sBattlePersonalityOverrideValue = sOverworldWildSpawnState.pendingPersonality;
    sBattleHpPersonality = sOverworldWildSpawnState.pendingPersonality;
    gOverworldWildBattleFlags = OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE
        | OW_WILD_BATTLE_FLAG_HP_TRACKING_ACTIVE;
    if (sOverworldWildSpawnState.pendingShiny) {
        gOverworldWildBattleFlags |= OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE;
    }

    sOverworldWildSpawnState.pendingSpecies = SPECIES_NONE;
    sOverworldWildSpawnState.pendingLevel = 0;
    sOverworldWildSpawnState.pendingShiny = FALSE;

    return pendingBattle;
}

BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality, BOOL *shiny)
{
    if ((gOverworldWildBattleFlags
            & (OVERWORLD_WILD_BATTLE_FLAG_SUPPRESS_PERSONALITY_OVERRIDE
                | OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE))
        != OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE) {
        return FALSE;
    }

    *personality = sBattlePersonalityOverrideValue;
    *shiny = (gOverworldWildBattleFlags
        & OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE) != 0;
    sBattlePersonalityOverrideValue = 0;
    gOverworldWildBattleFlags &= (u8)~(OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE
        | OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE);

    return TRUE;
}

void LONG_CALL OverworldWildSpawns_OnBattleContextUpdate(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome)
{
    if (OverworldCombat_IsReady()) {
        OVERWORLD_COMBAT_ENTRY->battleUpdate(
            bsys, ctx, battleOutcome, sBattleHpPersonality);
    }
}

void OverworldWildSpawns_CleanupPendingBattle(FieldSystem *fieldSystem, u32 battleResult)
{
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry(FALSE);
    u8 disposition = OW_WILD_BATTLE_DISPOSITION_RETAIN;
    int battleSlot = sOverworldWildSpawnState.pendingSlot;

    if (entry != NULL) {
        disposition = entry->cleanupPendingBattle(
            fieldSystem,
            &sOverworldWildSpawnState,
            (u16)battleResult);
    } else {
        sOverworldWildSpawnState.pendingPersonality = 0;
        sOverworldWildSpawnState.pendingSlot = -1;
        sOverworldWildSpawnState.movementQueuedBattleSlot = -1;
    }

    if (disposition == OW_WILD_BATTLE_DISPOSITION_DEFEATED
        || disposition == OW_WILD_BATTLE_DISPOSITION_CAUGHT) {
        if (battleSlot >= 0 && battleSlot < OW_WILD_HP_SLOT_COUNT) {
            gOverworldWildSavedHp[battleSlot] = 0;
        }
    }

    sBattlePersonalityOverrideValue = 0;
    sBattleHpPersonality = 0;
    gOverworldWildBattleFlags = 0;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
