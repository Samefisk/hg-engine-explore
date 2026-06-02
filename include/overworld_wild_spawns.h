#ifndef OVERWORLD_WILD_SPAWNS_H
#define OVERWORLD_WILD_SPAWNS_H

#include "types.h"
#include "pokemon.h"

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem);
BOOL OverworldWildSpawns_PopPendingBattle(u16 *encodedSpecies, u8 *level, BOOL *shiny);
void OverworldWildSpawns_ApplyPendingBattleGender(struct PartyPokemon *mon);
void OverworldWildSpawns_CleanupPendingBattle(u16 battleResult);

#endif // OVERWORLD_WILD_SPAWNS_H
