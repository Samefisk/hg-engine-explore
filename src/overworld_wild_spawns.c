#include "../include/overworld_wild_spawns_internal.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/species.h"
#include "../include/overlay.h"

static OverworldWildSpawnState sOverworldWildSpawnState = {
    .mapId = MAP_NOTHING,
    .pendingSlot = -1,
};

static u8 sBattlePersonalityOverrideActive;
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
    sBattlePersonalityOverrideActive = TRUE;

    sOverworldWildSpawnState.pendingPersonality = 0;
    sOverworldWildSpawnState.pendingSpecies = SPECIES_NONE;
    sOverworldWildSpawnState.pendingLevel = 0;
    sOverworldWildSpawnState.pendingShiny = FALSE;

    return TRUE;
}

BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality)
{
    if (personality == NULL || !sBattlePersonalityOverrideActive) {
        return FALSE;
    }

    *personality = sBattlePersonalityOverrideValue;
    sBattlePersonalityOverrideValue = 0;
    sBattlePersonalityOverrideActive = FALSE;

    return TRUE;
}

void OverworldWildSpawns_CleanupPendingBattle(u16 battleResult)
{
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();

    if (entry != NULL && entry->cleanupPendingBattle != NULL) {
        entry->cleanupPendingBattle(&sOverworldWildSpawnState, battleResult);
    } else {
        sOverworldWildSpawnState.pendingPersonality = 0;
        sOverworldWildSpawnState.pendingSlot = -1;
    }

    sBattlePersonalityOverrideValue = 0;
    sBattlePersonalityOverrideActive = FALSE;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
