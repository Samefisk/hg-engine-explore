#include "../include/overworld_wild_spawns_internal.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/species.h"
#include "../include/overlay.h"

static OverworldWildSpawnState sOverworldWildSpawnState = {
    .mapId = MAP_NOTHING,
    .pendingGender = POKEMON_GENDER_UNKNOWN,
    .pendingSlot = -1,
};

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

    sOverworldWildSpawnState.pendingSpecies = SPECIES_NONE;
    sOverworldWildSpawnState.pendingLevel = 0;
    sOverworldWildSpawnState.pendingShiny = FALSE;

    return TRUE;
}

void OverworldWildSpawns_ApplyPendingBattleGender(struct PartyPokemon *mon)
{
    u32 gender;

    if (mon == NULL
        || sOverworldWildSpawnState.pendingSlot < 0
        || !sOverworldWildSpawnState.pendingGenderActive) {
        return;
    }

    gender = sOverworldWildSpawnState.pendingGender;
    SetMonData(mon, MON_DATA_GENDER, &gender);

    sOverworldWildSpawnState.pendingGender = POKEMON_GENDER_UNKNOWN;
    sOverworldWildSpawnState.pendingGenderActive = FALSE;
}

void OverworldWildSpawns_CleanupPendingBattle(u16 battleResult)
{
    const OverworldWildSpawnsOverlayEntry *entry = OverworldWildSpawns_GetOverlayEntry();

    if (entry != NULL && entry->cleanupPendingBattle != NULL) {
        entry->cleanupPendingBattle(&sOverworldWildSpawnState, battleResult);
    } else {
        sOverworldWildSpawnState.pendingGender = POKEMON_GENDER_UNKNOWN;
        sOverworldWildSpawnState.pendingGenderActive = FALSE;
        sOverworldWildSpawnState.pendingSlot = -1;
    }
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
