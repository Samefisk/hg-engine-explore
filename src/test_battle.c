#include "../include/types.h"
#include "../include/debug.h"

#ifdef DEBUG_BATTLE_SCENARIOS

#include "../include/test_battle.h"

u32 gTestBattleState __attribute__((section(".data"))) = 0;
struct TestBattleScenario *gTestBattleScenario
    __attribute__((section(".data"))) = NULL;

#endif // DEBUG_BATTLE_SCENARIOS
