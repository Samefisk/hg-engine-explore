#include "../include/overworld_wild_spawns_internal.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/species.h"
#include "../include/battle.h"
#include "../include/map_teleport.h"
#include "../include/map_events_internal.h"
#include "../include/overlay.h"
#include "../include/script.h"
#include "../include/task.h"

#define OW_WILD_BATTLE_OUTCOME_PLAYER_FLED 5
#define OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE 0x01
#define OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE 0x02
#define OW_WILD_BATTLE_FLAG_HP_TRACKING_ACTIVE 0x04
#define OW_WILD_BATTLE_FLAG_HP_APPLIED 0x08
#define OW_WILD_BATTLE_FLAG_HP_RECORDED 0x10
#define OW_WILD_HP_SLOT_COUNT 10
#define OW_WILD_FIELD_READY_INITIAL_SPAWN 0
#define OW_WILD_DISABLE_PLAYER_STEP_HOOK 0
#define OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY 0

typedef struct OverworldWildSavedHp {
    u32 personality;
    u16 hp;
    u8 active;
} OverworldWildSavedHp;

static OverworldWildSpawnState sOverworldWildSpawnState = {
    .mapId = MAP_NOTHING,
    .pendingSlot = -1,
    .movementQueuedBattleSlot = -1,
};

static OverworldWildSavedHp sSavedHp[OW_WILD_HP_SLOT_COUNT];
static u32 sBattleHpPersonality;
static u32 sBattlePersonalityOverrideValue;
MapTeleportTemporaryReturnState gMapTeleportTemporaryReturnState
    __attribute__((section(".map_teleport_runtime"), aligned(2))) = {0};
MapTeleportTransitionRuntimeState gMapTeleportTransitionState
    __attribute__((section(".map_teleport_runtime"), aligned(2))) = {0};
static FieldSystem *sFieldReadyTaskFieldSystem;
static u16 sFieldReadyTaskMapId;
static u8 sBattleFlags;
extern u32 space_for_setmondata;

static void OverworldWildSpawns_FieldReadyTask(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;

    if (fieldSystem != gFieldSysPtr) {
        if (sFieldReadyTaskFieldSystem == fieldSystem) {
            sFieldReadyTaskFieldSystem = NULL;
            sOverworldWildSpawnState.battleGraceSteps = 0;
        }
        DestroySysTask(task);
        return;
    }

    if (fieldSystem->taskman != NULL) {
        return;
    }

    if (fieldSystem->location != NULL
        && sFieldReadyTaskMapId != (u16)fieldSystem->location->mapId) {
        sOverworldWildSpawnState.presentationRestorePending = TRUE;
        if (sOverworldWildSpawnState.battleGraceSteps == 0) {
            sOverworldWildSpawnState.battleGraceSteps = OW_WILD_FIELD_READY_DELAY_FRAMES;
        } else {
            sOverworldWildSpawnState.battleGraceSteps--;
        }
        if (sOverworldWildSpawnState.battleGraceSteps != 0) {
            return;
        }

        sFieldReadyTaskMapId = (u16)fieldSystem->location->mapId;
    } else if (sOverworldWildSpawnState.battleGraceSteps != 0) {
        sOverworldWildSpawnState.battleGraceSteps--;
        if (sOverworldWildSpawnState.battleGraceSteps != 0) {
            return;
        }
    }

    MapTeleport_PollDebug(fieldSystem);

#if OW_WILD_FIELD_READY_INITIAL_SPAWN
    OverworldWildSpawns_OnPlayerStep(fieldSystem);
#endif
}

static const OverworldWildSpawnsOverlayEntry *OverworldWildSpawns_GetOverlayEntry(void)
{
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        && !HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION, 0)) {
        return NULL;
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

    entry = OverworldWildSpawns_GetOverlayEntry();
    if (entry == NULL) {
        return FALSE;
    }

#if OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY
    (void)fieldSystem;
    return FALSE;
#endif

    return entry->onPlayerStep(fieldSystem, &sOverworldWildSpawnState);
#endif
}

void OverworldWildSpawns_OnFieldSystemReady(FieldSystem *fieldSystem)
{
#if OW_WILD_DISABLE_PLAYER_STEP_HOOK
    (void)fieldSystem;
#else
    if (sFieldReadyTaskFieldSystem != fieldSystem) {
        sFieldReadyTaskMapId = 0;
        CreateSysTask(
            OverworldWildSpawns_FieldReadyTask,
            fieldSystem,
            OW_WILD_FIELD_READY_DELAY_FRAMES);
        sFieldReadyTaskFieldSystem = fieldSystem;
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
        entry = OverworldWildSpawns_GetOverlayEntry();
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
    sBattleFlags = OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE
        | OW_WILD_BATTLE_FLAG_HP_TRACKING_ACTIVE;
    if (sOverworldWildSpawnState.pendingShiny) {
        sBattleFlags |= OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE;
    }

    sOverworldWildSpawnState.pendingSpecies = SPECIES_NONE;
    sOverworldWildSpawnState.pendingLevel = 0;
    sOverworldWildSpawnState.pendingShiny = FALSE;

    return pendingBattle;
}

static int OverworldWildSpawns_FindSavedHpSlot(u32 personality)
{
    int i;

    for (i = 0; i < OW_WILD_HP_SLOT_COUNT; i++) {
        if (sSavedHp[i].active && sSavedHp[i].personality == personality) {
            return i;
        }
    }

    return -1;
}

static int OverworldWildSpawns_FindFreeSavedHpSlot(void)
{
    int i;

    for (i = 0; i < OW_WILD_HP_SLOT_COUNT; i++) {
        if (!sSavedHp[i].active) {
            return i;
        }
    }

    return 0;
}

static void OverworldWildSpawns_ClearSavedHp(u32 personality)
{
    int slot = OverworldWildSpawns_FindSavedHpSlot(personality);

    if (slot >= 0) {
        sSavedHp[slot].active = FALSE;
    }
}

static void OverworldWildSpawns_SaveHp(u32 personality, u16 hp)
{
    int slot;

    if (personality == 0 || hp == 0) {
        return;
    }

    slot = OverworldWildSpawns_FindSavedHpSlot(personality);
    if (slot < 0) {
        slot = OverworldWildSpawns_FindFreeSavedHpSlot();
    }

    sSavedHp[slot].personality = personality;
    sSavedHp[slot].hp = hp;
    sSavedHp[slot].active = TRUE;
}

static u16 OverworldWildSpawns_GetSavedHp(u32 personality)
{
    int slot = OverworldWildSpawns_FindSavedHpSlot(personality);

    if (slot < 0) {
        return 0;
    }

    return sSavedHp[slot].hp;
}

static u16 OverworldWildSpawns_ClampBattleHp(const struct BattlePokemon *mon, u16 hp)
{
    if (mon == NULL || hp == 0 || mon->maxhp == 0) {
        return 0;
    }

    if (hp > mon->maxhp) {
        return (u16)mon->maxhp;
    }

    return hp;
}

static void OverworldWildSpawns_TryApplySavedBattleHp(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    int battler;
    u16 hp;

    if (bsys == NULL
        || ctx == NULL
        || (sBattleFlags & OW_WILD_BATTLE_FLAG_HP_TRACKING_ACTIVE) == 0
        || (sBattleFlags & OW_WILD_BATTLE_FLAG_HP_APPLIED) != 0
        || ctx->server_seq_no < CONTROLLER_COMMAND_SELECTION_SCREEN_INIT) {
        return;
    }

    hp = OverworldWildSpawns_GetSavedHp(sBattleHpPersonality);
    if (hp == 0) {
        sBattleFlags |= OW_WILD_BATTLE_FLAG_HP_APPLIED;
        return;
    }

    for (battler = BATTLER_ENEMY; battler < CLIENT_MAX; battler += 2) {
        if (battler >= bsys->maxBattlers
            || ctx->battlemon[battler].personal_rnd != sBattleHpPersonality) {
            continue;
        }

        hp = OverworldWildSpawns_ClampBattleHp(&ctx->battlemon[battler], hp);
        if (hp != 0) {
            ctx->battlemon[battler].hp = hp;
            sBattleFlags |= OW_WILD_BATTLE_FLAG_HP_APPLIED;
        }
        return;
    }
}

static void OverworldWildSpawns_TryRecordFledBattleHp(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome)
{
    int battler;

    if (bsys == NULL
        || ctx == NULL
        || (sBattleFlags & OW_WILD_BATTLE_FLAG_HP_TRACKING_ACTIVE) == 0
        || (sBattleFlags & OW_WILD_BATTLE_FLAG_HP_RECORDED) != 0
        || battleOutcome != OW_WILD_BATTLE_OUTCOME_PLAYER_FLED) {
        return;
    }

    for (battler = BATTLER_ENEMY; battler < CLIENT_MAX; battler += 2) {
        u16 hp;

        if (battler >= bsys->maxBattlers
            || ctx->battlemon[battler].personal_rnd != sBattleHpPersonality) {
            continue;
        }

        hp = OverworldWildSpawns_ClampBattleHp(&ctx->battlemon[battler], (u16)ctx->battlemon[battler].hp);
        if (hp != 0) {
            OverworldWildSpawns_SaveHp(sBattleHpPersonality, hp);
            sBattleFlags |= OW_WILD_BATTLE_FLAG_HP_RECORDED;
        }
        return;
    }
}

BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality, BOOL *shiny)
{
    if ((sBattleFlags & OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE) == 0) {
        return FALSE;
    }

    *personality = sBattlePersonalityOverrideValue;
    *shiny = (sBattleFlags & OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE) != 0;
    sBattlePersonalityOverrideValue = 0;
    sBattleFlags &= (u8)~(OW_WILD_BATTLE_FLAG_SHINY_OVERRIDE
        | OW_WILD_BATTLE_FLAG_PERSONALITY_OVERRIDE_ACTIVE);

    return TRUE;
}

void LONG_CALL OverworldWildSpawns_OnBattleContextUpdate(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome)
{
    OverworldWildSpawns_TryApplySavedBattleHp(bsys, ctx);
    OverworldWildSpawns_TryRecordFledBattleHp(bsys, ctx, battleOutcome);
}

void OverworldWildSpawns_CleanupPendingBattle(FieldSystem *fieldSystem, u32 battleResult)
{
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();
    u8 disposition = OW_WILD_BATTLE_DISPOSITION_RETAIN;
    u32 battlePersonality = sBattleHpPersonality;

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
        OverworldWildSpawns_ClearSavedHp(battlePersonality);
    }

    sBattlePersonalityOverrideValue = 0;
    sBattleHpPersonality = 0;
    sBattleFlags = 0;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
