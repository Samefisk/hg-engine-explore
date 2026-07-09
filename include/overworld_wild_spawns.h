#ifndef OVERWORLD_WILD_SPAWNS_H
#define OVERWORLD_WILD_SPAWNS_H

#include "types.h"
#include "pokemon.h"

struct BattleStruct;
struct BattleSystem;

#define OVERWORLD_WILD_BATTLE_SHINY_OTID 0
#define OVERWORLD_WILD_SHINY_BASE_ODDS 8192
#define OVERWORLD_WILD_PENDING_BATTLE_LEVEL_SHIFT 16
#define OVERWORLD_WILD_PENDING_BATTLE_SHINY_SHIFT 24

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem);
void OverworldWildSpawns_OnFieldSystemReady(FieldSystem *fieldSystem);
u32 OverworldWildSpawns_PopPendingBattle(FieldSystem *fieldSystem, LocalMapObject *talkedObject);
BOOL OverworldWildSpawns_ConsumeBattlePersonalityOverride(u32 *personality, BOOL *shiny);
void LONG_CALL OverworldWildSpawns_OnBattleContextUpdate(struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battleOutcome);
void OverworldWildSpawns_CleanupPendingBattle(FieldSystem *fieldSystem, u32 battleResult);
#endif // OVERWORLD_WILD_SPAWNS_H
