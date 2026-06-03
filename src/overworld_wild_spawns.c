#include "../include/overworld_wild_spawns_internal.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/species.h"
#include "../include/battle.h"
#include "../include/overlay.h"

#define OW_WILD_BATTLE_OUTCOME_PLAYER_FLED 5
#define OW_WILD_BATTLE_RESULT_PLAYER_FLED 0x5
#define OW_WILD_BATTLE_RESULT_TRY_FLEE 0x80
#define OW_WILD_HP_SLOT_COUNT 10
#define OW_WILD_DISABLE_PLAYER_STEP_HOOK 1

typedef struct OverworldWildSavedHp {
    u32 personality;
    u16 hp;
    u8 active;
} OverworldWildSavedHp;

static OverworldWildSpawnState sOverworldWildSpawnState = {
    .mapId = MAP_NOTHING,
    .pendingSlot = -1,
};

static OverworldWildSavedHp sSavedHp[OW_WILD_HP_SLOT_COUNT];
static u8 sBattlePersonalityOverrideActive;
static u8 sBattleHpTrackingActive;
static u8 sBattleHpApplied;
static u8 sBattleHpRecorded;
static u8 sBattleShinyOverrideValue;
static u32 sBattleHpPersonality;
static u32 sBattlePersonalityOverrideValue;

static const OverworldWildSpawnsOverlayEntry *OverworldWildSpawns_GetOverlayEntry(void)
{
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        && !HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION, 2)) {
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
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();

    if (entry == NULL || entry->onPlayerStep == NULL) {
        return FALSE;
    }

    return entry->onPlayerStep(fieldSystem, &sOverworldWildSpawnState);
#endif
}

BOOL OverworldWildSpawns_PopPendingBattle(u16 *encodedSpecies, u8 *level, BOOL *shiny)
{
    if (sOverworldWildSpawnState.pendingSpecies == SPECIES_NONE
        || sOverworldWildSpawnState.pendingLevel == 0) {
        return FALSE;
    }

    *encodedSpecies = sOverworldWildSpawnState.pendingSpecies;
    *level = sOverworldWildSpawnState.pendingLevel;
    *shiny = sOverworldWildSpawnState.pendingShiny;

    sBattlePersonalityOverrideValue = sOverworldWildSpawnState.pendingPersonality;
    sBattleHpPersonality = sOverworldWildSpawnState.pendingPersonality;
    sBattleShinyOverrideValue = sOverworldWildSpawnState.pendingShiny;
    sBattlePersonalityOverrideActive = TRUE;
    sBattleHpTrackingActive = TRUE;
    sBattleHpApplied = FALSE;
    sBattleHpRecorded = FALSE;

    sOverworldWildSpawnState.pendingPersonality = 0;
    sOverworldWildSpawnState.pendingSpecies = SPECIES_NONE;
    sOverworldWildSpawnState.pendingLevel = 0;
    sOverworldWildSpawnState.pendingShiny = FALSE;

    return TRUE;
}

static BOOL OverworldWildSpawns_BattleResultIsPlayerFlee(u16 battleResult)
{
    return battleResult == OW_WILD_BATTLE_RESULT_PLAYER_FLED
        || (battleResult & OW_WILD_BATTLE_RESULT_TRY_FLEE) != 0;
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
        sSavedHp[slot].personality = 0;
        sSavedHp[slot].hp = 0;
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
        || !sBattleHpTrackingActive
        || sBattleHpApplied
        || ctx->server_seq_no < CONTROLLER_COMMAND_SELECTION_SCREEN_INIT) {
        return;
    }

    hp = OverworldWildSpawns_GetSavedHp(sBattleHpPersonality);
    if (hp == 0) {
        sBattleHpApplied = TRUE;
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
            sBattleHpApplied = TRUE;
        }
        return;
    }
}

static void OverworldWildSpawns_TryRecordFledBattleHp(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome)
{
    int battler;

    if (bsys == NULL
        || ctx == NULL
        || !sBattleHpTrackingActive
        || sBattleHpRecorded
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
            sBattleHpRecorded = TRUE;
        }
        return;
    }
}

BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality, BOOL *shiny)
{
    if (personality == NULL || shiny == NULL || !sBattlePersonalityOverrideActive) {
        return FALSE;
    }

    *personality = sBattlePersonalityOverrideValue;
    *shiny = sBattleShinyOverrideValue;
    sBattleShinyOverrideValue = FALSE;
    sBattlePersonalityOverrideValue = 0;
    sBattlePersonalityOverrideActive = FALSE;

    return TRUE;
}

void LONG_CALL OverworldWildSpawns_OnBattleContextUpdate(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome)
{
    OverworldWildSpawns_TryApplySavedBattleHp(bsys, ctx);
    OverworldWildSpawns_TryRecordFledBattleHp(bsys, ctx, battleOutcome);
}

void OverworldWildSpawns_CleanupPendingBattle(u16 battleResult)
{
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();
    u32 battlePersonality = sBattleHpPersonality;

    if (entry != NULL && entry->cleanupPendingBattle != NULL) {
        entry->cleanupPendingBattle(&sOverworldWildSpawnState, battleResult);
    } else {
        sOverworldWildSpawnState.pendingPersonality = 0;
        sOverworldWildSpawnState.pendingSlot = -1;
    }

    if (!OverworldWildSpawns_BattleResultIsPlayerFlee(battleResult)) {
        OverworldWildSpawns_ClearSavedHp(battlePersonality);
    }

    sBattlePersonalityOverrideValue = 0;
    sBattleShinyOverrideValue = FALSE;
    sBattleHpPersonality = 0;
    sBattlePersonalityOverrideActive = FALSE;
    sBattleHpTrackingActive = FALSE;
    sBattleHpApplied = FALSE;
    sBattleHpRecorded = FALSE;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
