#ifndef OVERWORLD_WILD_SPAWNS_H
#define OVERWORLD_WILD_SPAWNS_H

#include "types.h"
#include "pokemon.h"

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem);
BOOL OverworldWildSpawns_ApplyPendingBattleMon(struct PartyPokemon *pokemon, u16 *species, u8 *form);

#endif // OVERWORLD_WILD_SPAWNS_H
