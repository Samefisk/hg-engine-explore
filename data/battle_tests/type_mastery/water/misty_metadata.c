// Test: Type Mastery Water - Misty metadata initializes production enemy mastery
#include "fixture.h"

#ifndef GET_TEST_CASE_ONLY
#include "../../../../include/battle.h"
#include "../../../../include/constants/ability.h"
#include "../../../../include/constants/item.h"
#include "../../../../include/constants/moves.h"
#include "../../../../include/constants/species.h"
#include "../../../../include/test_battle.h"
const struct TestBattleScenario BattleTests[] = {
#endif

    {
        .battleType = BATTLE_TYPE_SINGLE,
        .terrain = TERRAIN_NONE,
        .useProductionTypeMastery = TRUE,
        .enemyTrainerId = 254,
        .playerParty = TM_TARGET_PARTY,
        .enemyParty = TM_WATER_PARTY_FOUR(77, MOVE_WATER_PULSE),
        .playerScript = TM_PLAYER_IDLE_SCRIPT,
        .enemyScript = TM_ENEMY_ATTACK_SCRIPT,
        .expectations = {
            TM_STATE_EXPECTATION(BATTLER_ENEMY_FIRST, 5, 4, 2, 10),
            TM_BONUS_EXPECTATION(BATTLER_ENEMY_FIRST, 10),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
