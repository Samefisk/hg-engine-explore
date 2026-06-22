#ifndef OVERWORLD_WILD_SPAWNS_H
#define OVERWORLD_WILD_SPAWNS_H

#include "types.h"
#include "pokemon.h"

struct BattleStruct;
struct BattleSystem;

#define OVERWORLD_WILD_BATTLE_SHINY_OTID 0
#define OVERWORLD_WILD_SHINY_BASE_ODDS 8192

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem);
void OverworldWildSpawns_OnFieldSystemReady(FieldSystem *fieldSystem);
BOOL OverworldWildSpawns_PopPendingBattle(u16 *encodedSpecies, u8 *level, BOOL *shiny);
BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality, BOOL *shiny);
void LONG_CALL OverworldWildSpawns_OnBattleContextUpdate(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome);
void OverworldWildSpawns_CleanupPendingBattle(FieldSystem *fieldSystem, u16 battleResult);
void OverworldWildSpawns_MankeyTreeTopDrawWrapper(LocalMapObject *mapObject);
extern u8 gOverworldWildSoundTesterActive;
extern u8 gOverworldWildVisualTesterActive;

#endif // OVERWORLD_WILD_SPAWNS_H
