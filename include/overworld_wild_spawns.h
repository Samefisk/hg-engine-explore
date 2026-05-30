#ifndef OVERWORLD_WILD_SPAWNS_H
#define OVERWORLD_WILD_SPAWNS_H

#include "types.h"
#include "pokemon.h"

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem);
void OverworldWildSpawns_OnFieldSystemTick(FieldSystem *fieldSystem);
void OverworldWildSpawns_OnMapObjectManTick(void *mapObjectMan);
BOOL OverworldWildSpawns_PopPendingBattle(u16 *encodedSpecies, u8 *level);
void OverworldWildSpawns_CleanupPendingBattle(void);

#endif // OVERWORLD_WILD_SPAWNS_H
