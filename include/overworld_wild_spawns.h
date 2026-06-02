#ifndef OVERWORLD_WILD_SPAWNS_H
#define OVERWORLD_WILD_SPAWNS_H

#include "types.h"
#include "pokemon.h"

#define OVERWORLD_WILD_BATTLE_SHINY_OTID 0

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem);
BOOL OverworldWildSpawns_PopPendingBattle(u16 *encodedSpecies, u8 *level, BOOL *shiny);
BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality, BOOL *shiny);
void OverworldWildSpawns_CleanupPendingBattle(u16 battleResult);

#endif // OVERWORLD_WILD_SPAWNS_H
