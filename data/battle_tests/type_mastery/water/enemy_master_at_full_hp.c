// Test: Type Mastery Water - enemy master receives the same full-HP boon
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
        .enemyTypeMastery = { .enabled = TRUE, .typeLevels = { [TYPE_WATER] = 5 } },
        .playerParty = TM_TARGET_PARTY,
        .enemyParty = TM_WATER_PARTY_MASTER(FULL_HP, MOVE_WATER_PULSE),
        .playerScript = TM_PLAYER_IDLE_SCRIPT,
        .enemyScript = TM_ENEMY_ATTACK_SCRIPT,
        .expectations = {
            TM_STATE_EXPECTATION(BATTLER_ENEMY_FIRST, 5, 6, 3, 15),
            TM_BONUS_EXPECTATION(BATTLER_ENEMY_FIRST, 15),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
