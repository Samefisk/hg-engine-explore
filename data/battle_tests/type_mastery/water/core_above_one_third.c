// Test: Type Mastery Water - core boon stays inactive above one-third HP
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
        .playerTypeMastery = { .enabled = TRUE, .typeLevels = { [TYPE_WATER] = 5 } },
        .playerParty = TM_WATER_PARTY_CORE(52, MOVE_WATER_PULSE),
        .enemyParty = TM_TARGET_PARTY,
        .playerScript = TM_PLAYER_ATTACK_SCRIPT,
        .enemyScript = TM_ENEMY_IDLE_SCRIPT,
        .expectations = {
            TM_STATE_EXPECTATION(BATTLER_PLAYER_FIRST, 5, 2, 1, 5),
            TM_BONUS_EXPECTATION(BATTLER_PLAYER_FIRST, 0),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
