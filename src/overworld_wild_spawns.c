#include "../include/overworld_wild_spawns_internal.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/species.h"
#include "../include/overlay.h"

#define OW_WILD_BATTLE_RESULT_PLAYER_FLED 0x5
#define OW_WILD_BATTLE_RESULT_TRY_FLEE 0x80

static OverworldWildSpawnState sOverworldWildSpawnState = {
    .mapId = MAP_NOTHING,
    .pendingSlot = -1,
};

static u8 sBattlePersonalityOverrideActive;
static u8 sBattleTrackingActive;
static u8 sBattleShinyOverrideValue;
static u16 sBattleHpOverrideValue;
static u32 sBattleTrackedPersonality;
static u32 sBattlePersonalityOverrideValue;
static struct PartyPokemon *sBattleTrackedMon;

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
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();

    if (entry == NULL || entry->onPlayerStep == NULL) {
        return FALSE;
    }

    return entry->onPlayerStep(fieldSystem, &sOverworldWildSpawnState);
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
    sBattleShinyOverrideValue = sOverworldWildSpawnState.pendingShiny;
    sBattleHpOverrideValue = sOverworldWildSpawnState.pendingHp;
    sBattleTrackedPersonality = sOverworldWildSpawnState.pendingPersonality;
    sBattlePersonalityOverrideActive = TRUE;
    sBattleTrackingActive = TRUE;

    sOverworldWildSpawnState.pendingPersonality = 0;
    sOverworldWildSpawnState.pendingHp = 0;
    sOverworldWildSpawnState.pendingSpecies = SPECIES_NONE;
    sOverworldWildSpawnState.pendingLevel = 0;
    sOverworldWildSpawnState.pendingShiny = FALSE;

    return TRUE;
}

static u16 OverworldWildSpawns_ClampHp(struct PartyPokemon *mon, u16 hp)
{
    u16 maxHp;

    if (mon == NULL || hp == 0) {
        return 0;
    }

    maxHp = (u16)GetMonData(mon, MON_DATA_MAXHP, NULL);
    if (maxHp == 0) {
        return 0;
    }

    if (hp > maxHp) {
        return maxHp;
    }

    return hp;
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

void OverworldWildSpawns_ApplyPendingBattleHp(struct PartyPokemon *mon)
{
    u16 hp = OverworldWildSpawns_ClampHp(mon, sBattleHpOverrideValue);

    if (hp != 0) {
        SetMonData(mon, MON_DATA_HP, &hp);
    }
}

void OverworldWildSpawns_RegisterBattleParty(struct Party *party)
{
    int i;

    sBattleTrackedMon = NULL;
    if (party == NULL || !sBattleTrackingActive) {
        return;
    }

    for (i = 0; i < 6; i++) {
        struct PartyPokemon *mon = Party_GetMonByIndex(party, i);
        if (mon != NULL
            && GetMonData(mon, MON_DATA_SPECIES, NULL) != SPECIES_NONE
            && GetMonData(mon, MON_DATA_PERSONALITY, NULL) == sBattleTrackedPersonality) {
            sBattleTrackedMon = mon;
            return;
        }
    }
}

static BOOL OverworldWildSpawns_BattleResultIsPlayerFlee(u16 battleResult)
{
    return battleResult == OW_WILD_BATTLE_RESULT_PLAYER_FLED
        || (battleResult & OW_WILD_BATTLE_RESULT_TRY_FLEE) != 0;
}

static void OverworldWildSpawns_TryStoreFledBattleHp(void)
{
    u16 hp;

    if (sOverworldWildSpawnState.pendingSlot < 0
        || sOverworldWildSpawnState.pendingSlot >= OW_WILD_MAX_SPAWNS
        || sBattleTrackedMon == NULL) {
        return;
    }

    hp = OverworldWildSpawns_ClampHp(sBattleTrackedMon, (u16)GetMonData(sBattleTrackedMon, MON_DATA_HP, NULL));
    if (hp != 0) {
        sOverworldWildSpawnState.spawns[sOverworldWildSpawnState.pendingSlot].currentHp = hp;
    }
}

void OverworldWildSpawns_CleanupPendingBattle(u16 battleResult)
{
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();

    if (OverworldWildSpawns_BattleResultIsPlayerFlee(battleResult)) {
        OverworldWildSpawns_TryStoreFledBattleHp();
    }

    if (entry != NULL && entry->cleanupPendingBattle != NULL) {
        entry->cleanupPendingBattle(&sOverworldWildSpawnState, battleResult);
    } else {
        sOverworldWildSpawnState.pendingPersonality = 0;
        sOverworldWildSpawnState.pendingHp = 0;
        sOverworldWildSpawnState.pendingSlot = -1;
    }

    sBattlePersonalityOverrideValue = 0;
    sBattleShinyOverrideValue = FALSE;
    sBattleHpOverrideValue = 0;
    sBattleTrackedPersonality = 0;
    sBattleTrackedMon = NULL;
    sBattlePersonalityOverrideActive = FALSE;
    sBattleTrackingActive = FALSE;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
